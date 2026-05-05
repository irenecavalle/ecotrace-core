"""
Download Sentinel-2 L2A imagery from Google Earth Engine.

Retrieves monthly composite Sentinel-2 data for specified AOIs and date ranges.
Applies cloud masking and exports to local storage.
"""

import argparse
import logging
import os
from pathlib import Path
from typing import Dict, Tuple
from datetime import datetime, timedelta
import ee

from .gee_auth import authenticate, initialize, test_connection


logger = logging.getLogger(__name__)


AOI_BOUNDS = {
    'pakistan': {
        'name': 'Indus Basin, Pakistan',
        'bounds': (25.0, 66.5, 34.5, 74.5),  # (minLat, minLon, maxLat, maxLon)
    },
    'china': {
        'name': 'Yangtze Delta, China',
        'bounds': (29.0, 118.0, 32.0, 122.0),
    },
    'bangladesh': {
        'name': 'Dhaka Region, Bangladesh',
        'bounds': (23.0, 89.5, 24.5, 91.5),
    }
}


def get_aoi_bounds(aoi: str) -> Tuple[float, float, float, float]:
    """
    Get bounding box coordinates for AOI.

    Args:
        aoi: Area of interest name (pakistan, china, bangladesh)

    Returns:
        Tuple of (minLat, minLon, maxLat, maxLon)

    Raises:
        ValueError: If AOI not recognized
    """
    aoi_lower = aoi.lower()
    if aoi_lower not in AOI_BOUNDS:
        raise ValueError(f"Unknown AOI: {aoi}. Available: {list(AOI_BOUNDS.keys())}")
    return AOI_BOUNDS[aoi_lower]['bounds']


def create_geometry(aoi: str) -> ee.Geometry:
    """
    Create Earth Engine geometry for AOI.

    Args:
        aoi: Area of interest name

    Returns:
        ee.Geometry.Rectangle for the AOI
    """
    min_lat, min_lon, max_lat, max_lon = get_aoi_bounds(aoi)
    return ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])


def get_month_date_range(year: int, month: int) -> Tuple[str, str]:
    """
    Get start and end dates for a given month.

    Args:
        year: Year
        month: Month (1-12)

    Returns:
        Tuple of (start_date, end_date) in YYYY-MM-DD format
    """
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(days=1)
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')


def filter_sentinel2_cloud(image: ee.Image) -> ee.Image:
    """
    Apply cloud mask to Sentinel-2 image using QA60 band.

    Args:
        image: Input Sentinel-2 L2A image

    Returns:
        Masked image
    """
    qa = image.select('QA60')
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000).select('B.*').copyProperties(image, ['system:time_start'])


def create_monthly_composite(
    geometry: ee.Geometry,
    start_date: str,
    end_date: str
) -> ee.Image:
    """
    Create monthly median composite from Sentinel-2 L2A.

    Args:
        geometry: ee.Geometry for AOI
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Monthly median composite image
    """
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterBounds(geometry) \
        .filterDate(start_date, end_date) \
        .map(filter_sentinel2_cloud)

    if s2.size().getInfo() == 0:
        logger.warning(f"No Sentinel-2 images found for {start_date} to {end_date}")
        return None

    composite = s2.median().select(['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B11', 'B12'])
    return composite.clip(geometry)


def export_image(
    image: ee.Image,
    geometry: ee.Geometry,
    filename: str,
    output_dir: str,
    scale: int = 10
) -> None:
    """
    Export image to GeoTIFF file.

    Args:
        image: ee.Image to export
        geometry: ee.Geometry for region
        filename: Output filename (without extension)
        output_dir: Output directory
        scale: Export resolution in meters
    """
    if image is None:
        logger.warning(f"Skipping export of {filename}: image is None")
        return

    output_path = Path(output_dir) / f"{filename}.tif"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        task = ee.batch.Export.image.toDrive(
            image=image,
            description=filename,
            folder='ecotrace-exports',
            fileNamePrefix=filename,
            region=geometry,
            scale=scale,
            crs='EPSG:4326',
            maxPixels=1e13
        )
        task.start()
        logger.info(f"Started export task: {filename}")
        logger.info(f"Track progress at: https://code.earthengine.google.com/")

        while task.active():
            import time
            time.sleep(5)

        if task.status()['state'] == 'COMPLETED':
            logger.info(f"Export completed: {filename}")
        else:
            logger.error(f"Export failed: {filename}")
            logger.error(f"Error: {task.status()}")

    except Exception as e:
        logger.error(f"Export error for {filename}: {e}")


def download_aoi(
    aoi: str,
    start_date: str,
    end_date: str,
    output_dir: str
) -> None:
    """
    Download Sentinel-2 L2A imagery for a specific AOI.

    Creates monthly median composites for all months between start_date and end_date.

    Args:
        aoi: Area of interest name (pakistan, china, bangladesh)
        start_date: Start date in YYYY-MM format
        end_date: End date in YYYY-MM format
        output_dir: Output directory for downloaded data

    Raises:
        ValueError: If date format invalid
    """
    try:
        start_year, start_month = map(int, start_date.split('-'))
        end_year, end_month = map(int, end_date.split('-'))
    except ValueError:
        raise ValueError("Dates must be in YYYY-MM format")

    geometry = create_geometry(aoi)
    aoi_name = AOI_BOUNDS[aoi.lower()]['name']
    logger.info(f"Downloading Sentinel-2 L2A for {aoi_name}")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Output directory: {output_dir}")

    month_count = 0
    current_year = start_year
    current_month = start_month

    while (current_year, current_month) <= (end_year, end_month):
        try:
            month_start, month_end = get_month_date_range(current_year, current_month)
            filename = f"S2L2A_{aoi.lower()}_{current_year}{current_month:02d}"

            logger.info(f"Processing {month_start} to {month_end}...")
            composite = create_monthly_composite(geometry, month_start, month_end)

            if composite is not None:
                export_image(composite, geometry, filename, output_dir)
                month_count += 1

        except Exception as e:
            logger.error(f"Error processing {current_year}-{current_month:02d}: {e}")

        if current_month == 12:
            current_year += 1
            current_month = 1
        else:
            current_month += 1

    logger.info(f"Completed download for {aoi}: {month_count} monthly composites")


def main():
    """Main entry point for Sentinel-2 download."""
    parser = argparse.ArgumentParser(description="Download Sentinel-2 L2A imagery from Google Earth Engine")
    parser.add_argument("--aoi", required=True, help="Area of interest (pakistan|china|bangladesh|all)")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM)")
    parser.add_argument("--output", required=True, help="Output directory")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        logger.info("Authenticating with Google Earth Engine...")
        authenticate()
        initialize()

        if not test_connection():
            logger.error("Failed to connect to Google Earth Engine")
            return

        aois = ['pakistan', 'china', 'bangladesh'] if args.aoi.lower() == 'all' else [args.aoi.lower()]

        for aoi in aois:
            try:
                download_aoi(aoi, args.start, args.end, args.output)
            except Exception as e:
                logger.error(f"Failed to download {aoi}: {e}")

        logger.info("Download complete!")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
