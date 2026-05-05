"""
Compute spectral indices from Sentinel-2 composite data.

Calculates NDVI, NDWI, NDBI, and Red-Edge Chlorophyll Index (RE-ChlI)
for downstream analysis.
"""

import logging
from pathlib import Path
import numpy as np
import rasterio
from typing import Tuple


logger = logging.getLogger(__name__)


class SpectralIndexComputer:
    """Compute spectral indices from multispectral imagery."""

    # Sentinel-2 band names and indices
    BANDS = {
        "B2": 1,    # Blue (490nm)
        "B3": 2,    # Green (560nm)
        "B4": 3,    # Red (665nm)
        "B5": 4,    # RE1 (705nm)
        "B6": 5,    # RE2 (740nm)
        "B7": 6,    # RE3 (783nm)
        "B8": 7,    # NIR (842nm)
        "B8A": 8,   # RE4 (865nm)
        "B11": 9,   # SWIR1 (1610nm)
        "B12": 10   # SWIR2 (2190nm)
    }

    def __init__(self):
        """Initialize index computer."""
        # TODO: Initialize band mappings
        pass

    def compute_ndvi(self, nir: np.ndarray, red: np.ndarray) -> np.ndarray:
        """
        Compute Normalized Difference Vegetation Index.

        NDVI = (NIR - Red) / (NIR + Red)
        """
        # TODO: Implement NDVI calculation with safe division
        pass

    def compute_ndwi(self, nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
        """
        Compute Normalized Difference Water Index.

        NDWI = (NIR - SWIR) / (NIR + SWIR)
        """
        # TODO: Implement NDWI calculation
        pass

    def compute_ndbi(self, swir: np.ndarray, nir: np.ndarray) -> np.ndarray:
        """
        Compute Normalized Difference Built-up Index.

        NDBI = (SWIR - NIR) / (SWIR + NIR)
        """
        # TODO: Implement NDBI calculation
        pass

    def compute_re_chli(
        self,
        re3: np.ndarray,
        re1: np.ndarray,
        red: np.ndarray
    ) -> np.ndarray:
        """
        Compute Red-Edge Chlorophyll Index.

        RE-ChlI = (RE3 / RE1) - 1
        Used for chlorophyll estimation and water pollution proxy.
        """
        # TODO: Implement RE-ChlI calculation
        pass

    def process_composite(self, input_path: str, output_dir: str) -> None:
        """
        Compute all indices for a monthly composite.

        Args:
            input_path: Path to composite GeoTIFF
            output_dir: Directory to write index outputs
        """
        # TODO: Read composite, compute indices, save outputs
        pass


def main():
    """Command-line entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Compute spectral indices from composites")
    parser.add_argument("--input", required=True, help="Input directory")
    parser.add_argument("--output", required=True, help="Output directory")

    args = parser.parse_args()

    # TODO: Iterate through input directory and process composites
    pass


if __name__ == "__main__":
    main()
