"""Common objects used in unit tests"""

import numpy as np
import pytest


@pytest.fixture
def get_ones_matrix_1_channel() -> np.ndarray:
    """Return a matrix with shape (w, h, 1)"""
    return np.ones((5, 5, 1), dtype="float32")


@pytest.fixture
def get_ones_matrix_3_channel() -> np.ndarray:
    """Return a matrix with shape (w, h, 3)"""
    return np.ones((5, 5, 3), dtype="float32")


@pytest.fixture
def get_ones_matrix_2_channel() -> np.ndarray:
    """Return a matrix with shape (w, h, 2)"""
    return np.ones((5, 5, 2), dtype="float32")


@pytest.fixture
def get_ones_matrix() -> np.ndarray:
    """Return a matrix with shape (w, h)"""
    return np.ones((5, 5), dtype="float32")
