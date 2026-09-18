"""Public write guarantees when saving or replacing images."""

import os
from pathlib import Path
from stat import S_IMODE

import numpy as np
import pytest

from justpfm import justpfm


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("failure", ["write", "close", "replace"])
def test_failed_save_preserves_destination(tmp_path, monkeypatch, existing, failure):
    """Failures leave the original bytes intact and no temporary files behind."""
    destination = tmp_path / "image.pfm"
    original = b"existing image bytes"
    if existing:
        destination.write_bytes(original)
        original_mode = S_IMODE(destination.stat().st_mode)
    data = np.arange(6, dtype=np.float32).reshape(2, 3)

    def fail_replace(*_args):
        raise OSError("injected replace failure")

    def fail_payload(file, _data):
        """Simulate a partial pixel write followed by disk failure."""
        file.write(b"partial pixels")
        raise OSError("injected write failure")

    real_temporary = justpfm.NamedTemporaryFile

    class FailingClose:
        """Raise at context exit after the underlying file is closed."""

        def __init__(self, **kwargs):
            self.temporary = real_temporary(**kwargs)
            self.name = self.temporary.name

        def __enter__(self):
            return self.temporary.__enter__()

        def __exit__(self, *args):
            self.temporary.__exit__(*args)
            raise OSError("injected close failure")

    if failure == "write":
        monkeypatch.setattr(justpfm, "_write_pfm_payload", fail_payload)
    elif failure == "close":
        monkeypatch.setattr(justpfm, "NamedTemporaryFile", FailingClose)
    else:
        monkeypatch.setattr(justpfm, "replace", fail_replace)

    with pytest.raises(OSError, match="injected " + failure + " failure"):
        justpfm.write_pfm(destination, data)

    if existing:
        assert destination.read_bytes() == original
        assert S_IMODE(destination.stat().st_mode) == original_mode
        assert list(tmp_path.iterdir()) == [destination]
    else:
        assert not destination.exists()
        assert list(tmp_path.iterdir()) == []


def test_destination_changes_only_after_close(tmp_path, monkeypatch):
    """The original stays visible until a complete, closed sibling is ready."""
    destination = tmp_path / "image.pfm"
    original = b"old image"
    destination.write_bytes(original)
    data = np.arange(18, dtype=np.float32).reshape(2, 3, 3)
    real_replace = justpfm.replace
    real_temporary = justpfm.NamedTemporaryFile
    temporary_files = []

    def track_temporary(**kwargs):
        temporary = real_temporary(**kwargs)
        temporary_files.append(temporary)
        return temporary

    def checked_replace(source, target):
        assert destination.read_bytes() == original
        assert Path(source).parent == destination.parent
        assert temporary_files[0].closed
        np.testing.assert_array_equal(justpfm.read_pfm(source), data)
        real_replace(source, target)

    monkeypatch.setattr(justpfm, "NamedTemporaryFile", track_temporary)
    monkeypatch.setattr(justpfm, "replace", checked_replace)
    justpfm.write_pfm(str(destination), data)
    np.testing.assert_array_equal(justpfm.read_pfm(destination), data)
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions and symlinks")
def test_private_permissions_and_symlink_policy(tmp_path):
    """Saving replaces symlinks and preserves existing regular file permissions."""
    target = tmp_path / "target.pfm"
    target.write_bytes(b"untouched target")
    destination = tmp_path / "image.pfm"
    destination.symlink_to(target)
    data = np.arange(6, dtype=np.float32).reshape(2, 3)
    justpfm.write_pfm(destination, data)
    assert not destination.is_symlink()
    assert target.read_bytes() == b"untouched target"
    assert S_IMODE(destination.stat().st_mode) == 0o600
    destination.chmod(0o644)
    justpfm.write_pfm(destination, data)
    assert S_IMODE(destination.stat().st_mode) == 0o644
    np.testing.assert_array_equal(justpfm.read_pfm(destination)[..., 0], data)
    assert set(tmp_path.iterdir()) == {destination, target}


def test_temporary_creation_failure_preserves_destination(tmp_path, monkeypatch):
    """Failure before opening a temporary file never touches the destination."""
    destination = tmp_path / "image.pfm"
    destination.write_bytes(b"old image")

    def fail_open(**_kwargs):
        raise OSError("cannot create temporary file")

    monkeypatch.setattr(justpfm, "NamedTemporaryFile", fail_open)
    with pytest.raises(OSError, match="cannot create temporary file"):
        justpfm.write_pfm(destination, np.ones((2, 3), dtype=np.float32))
    assert destination.read_bytes() == b"old image"
    assert list(tmp_path.iterdir()) == [destination]


def test_read_only_replacement_failure_cleans_temporary(tmp_path, monkeypatch):
    """Emulate Windows rejecting read-only files during both replace and unlink."""
    destination = tmp_path / "image.pfm"
    destination.write_bytes(b"original image")
    destination.chmod(0o400)
    original_mode = S_IMODE(destination.stat().st_mode)
    real_unlink = Path.unlink
    failure = PermissionError("destination is read-only")
    removed = []

    def fail_replace(source, target):
        assert S_IMODE(Path(source).stat().st_mode) == original_mode
        assert target == destination
        raise failure

    def windows_unlink(path, *args, **kwargs):
        if not path.stat().st_mode & 0o200:
            raise PermissionError("cannot unlink a read-only temporary")
        removed.append(path)
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(justpfm, "replace", fail_replace)
    monkeypatch.setattr(Path, "unlink", windows_unlink)
    try:
        with pytest.raises(PermissionError) as raised:
            justpfm.write_pfm(destination, np.ones((2, 3), dtype=np.float32))
        assert raised.value is failure
        assert len(removed) == 1
        assert removed[0].parent == tmp_path
        assert destination.read_bytes() == b"original image"
        assert S_IMODE(destination.stat().st_mode) == original_mode
        assert list(tmp_path.iterdir()) == [destination]
    finally:
        destination.chmod(0o600)


def test_permissions_are_copied_after_close(tmp_path, monkeypatch):
    """Only complete closed files receive the original file's permission bits."""
    destination = tmp_path / "image.pfm"
    destination.write_bytes(b"original image")
    real_chmod = justpfm.chmod
    real_temporary = justpfm.NamedTemporaryFile
    temporary_files = []

    def track_temporary(**kwargs):
        temporary = real_temporary(**kwargs)
        temporary_files.append(temporary)
        return temporary

    def checked_chmod(path, mode):
        assert temporary_files[0].closed
        return real_chmod(path, mode)

    monkeypatch.setattr(justpfm, "NamedTemporaryFile", track_temporary)
    monkeypatch.setattr(justpfm, "chmod", checked_chmod)
    justpfm.write_pfm(destination, np.ones((2, 3), dtype=np.float32))
