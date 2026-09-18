"""Exact serialization and failure guarantees across buffered payload boundaries."""

import numpy as np
import pytest

from justpfm import justpfm


@pytest.mark.parametrize("shape", [(5, 7), (5, 7, 1), (5, 7, 3)])
@pytest.mark.parametrize("endian", ["<", ">"])
@pytest.mark.parametrize(
    "layout", ["c", "fortran", "rows", "columns", "strided", "broadcast"]
)
@pytest.mark.parametrize("budget", [16, 200])
def test_bulk_write_preserves_exact_bits(
    tmp_path, monkeypatch, shape, endian, layout, budget
):
    """Preserve NaN payloads, signed zero, endian and row order even at block edges."""
    bits = (
        np.resize(
            np.array(
                [
                    0,
                    0x80000000,
                    0x7FC00001,
                    0x7F800001,
                    0x7F800000,
                    0xFF800000,
                    0x3F800000,
                ],
                dtype=endian + "u4",
            ),
            np.prod(shape),
        )
        .astype(endian + "u4")
        .reshape(shape)
    )
    data = bits.view(endian + "f4")
    if layout == "fortran":
        data = np.asfortranarray(data)
    elif layout == "rows":
        data = data[::-1]
    elif layout == "columns":
        data = data[:, ::-1]
    elif layout == "strided":
        backing = np.empty((shape[0], shape[1] * 2) + shape[2:], dtype=data.dtype)
        backing[:, ::2] = data
        data = backing[:, ::2]
    elif layout == "broadcast":
        data = np.broadcast_to(data[:1], shape)
    data.flags.writeable = False
    before = data.tobytes()
    monkeypatch.setattr(justpfm, "_WRITE_BUFFER_BYTES", budget)
    path = tmp_path / "image.pfm"
    justpfm.write_pfm(path, data, scale=0.5)
    magic = b"PF" if shape[-1] == 3 and len(shape) == 3 else b"Pf"
    signed_scale = b"-0.5" if endian == "<" else b"0.5"
    expected = magic + b"\n7 5\n" + signed_scale + b"\n" + data[::-1].tobytes()
    assert path.read_bytes() == expected
    assert data.tobytes() == before


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("failure", ["allocate", "second_block"])
def test_buffer_failure_preserves_destination(tmp_path, monkeypatch, existing, failure):
    """Allocation or a later block failure cannot publish a partial destination."""
    data = np.arange(60, dtype=np.float32).reshape(5, 4, 3)
    path = tmp_path / "image.pfm"
    if existing:
        path.write_bytes(b"original")
    monkeypatch.setattr(justpfm, "_WRITE_BUFFER_BYTES", 48)
    real_copyto = np.copyto
    copies = []

    def fail_allocate(*args, **kwargs):
        raise MemoryError("injected allocation failure")

    def fail_second_copy(destination, source):
        copies.append(source.shape)
        if len(copies) == 2:
            raise OSError("injected block failure")
        real_copyto(destination, source)

    if failure == "allocate":
        monkeypatch.setattr(np, "empty", fail_allocate)
        error = MemoryError
    else:
        monkeypatch.setattr(np, "copyto", fail_second_copy)
        error = OSError
    with pytest.raises(error, match="injected"):
        justpfm.write_pfm(path, data)
    if existing:
        assert path.read_bytes() == b"original"
        assert list(tmp_path.iterdir()) == [path]
    else:
        assert not path.exists()
        assert list(tmp_path.iterdir()) == []
