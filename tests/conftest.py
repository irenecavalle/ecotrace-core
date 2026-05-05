"""
Pytest configuration and shared fixtures.

Provides common fixtures for testing across the project.
"""

import pytest
import numpy as np
import torch
from pathlib import Path


@pytest.fixture
def sample_sentinel2_patch():
    """Sample Sentinel-2 bi-temporal patch for testing."""
    return np.random.rand(64, 64, 12).astype(np.float32)


@pytest.fixture
def sample_indices():
    """Sample spectral indices (8 × 64 × 64)."""
    return np.random.rand(8, 64, 64).astype(np.float32)


@pytest.fixture
def sample_water_features():
    """Sample water stress feature vector (96,)."""
    return np.random.rand(96).astype(np.float32)


@pytest.fixture
def sample_suppliers_df():
    """Sample suppliers dataframe for testing."""
    import pandas as pd
    return pd.DataFrame({
        "supplier_id": ["SUP001", "SUP002"],
        "name": ["Supplier A", "Supplier B"],
        "latitude": [31.418, 32.061],
        "longitude": [73.079, 118.796],
        "country": ["PK", "CN"]
    })


@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary directory for test outputs."""
    return str(tmp_path)
