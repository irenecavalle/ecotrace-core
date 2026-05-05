"""
Download Sentinel-1 GRD imagery from Google Earth Engine.

Retrieves Sentinel-1 Ground Range Detected data for cloud-gap filling
and water extent mapping.
"""

import argparse
import logging
from typing import Tuple
import ee


logger = logging.getLogger(__name__)


def download_sentinel1(
    aoi: str,
    start_date: str,
    end_date: str,
    output_dir: str
) -> None:
    """
    Download Sentinel-1 GRD imagery for a specific AOI.

    Args:
        aoi: Area of interest name
        start_date: Start date in YYYY-MM format
        end_date: End date in YYYY-MM format
        output_dir: Output directory for downloaded data
    """
    # TODO: Implement Sentinel-1 GRD download from GEE
    pass


def filter_sentinel1(
    geometry: ee.Geometry,
    start_date: str,
    end_date: str
) -> ee.ImageCollection:
    """Filter Sentinel-1 collection for specified geometry and date range."""
    # TODO: Apply filters for VV/VH polarization, ascending/descending
    pass


def main():
    """Main entry point for Sentinel-1 download."""
    parser = argparse.ArgumentParser(description="Download Sentinel-1 GRD imagery")
    parser.add_argument("--aoi", required=True, help="Area of interest")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM)")
    parser.add_argument("--output", required=True, help="Output directory")

    args = parser.parse_args()

    # TODO: Parse arguments and call download_sentinel1
    pass


if __name__ == "__main__":
    main()
