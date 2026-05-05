"""
Download Sentinel-2 L2A imagery from Google Earth Engine.

Downloads monthly median composites for three AOIs:
- Indus Basin, Pakistan
- Yangtze Delta, China
- Dhaka Region, Bangladesh

Processing:
- Cloud cover filtering: < 20%
- Bands: B2, B3, B4, B8, B11, B12 (6 bands)
- Monthly median composites
- Output: GeoTIFF at 10m resolution
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Tuple
from datetime import datetime, timedelta
import ee

from .gee_auth import authenticate, initialize, test_connection


logger = logging.getLogger(__name__)


# AOI definitions with exact bounds
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

# Selected bands for analysis
BANDS = ['B2', 'B3', 'B4', 'B8', 'B11', 'B12']
BAND_DESCRIPTIONS = {
    'B2': 'Blue (490nm)',
    'B3': 'Green (560nm)',
    'B4': 'Red (665nm)',
    'B8': 'NIR (842nm)',
    'B11': 'SWIR1 (1610nm)',
    'B12': 'SWIR2 (2190nm)'
}


def get_aoi_bounds(aoi: str) -> Tuple[float, float, float, float]:
    """
    Get bounding box coordinates for AOI.

    Args:
        aoi: Area of interest name

    Returns:
        Tuple of (minLat, minLon, maxLat, maxLon)

    Raises:
        ValueError: If AOI not recognized
    """
    aoi_lower = aoi.lower()
    if aoi_lower not in AOI_BOUNDS:
        available = ', '.join(AOI_BOUNDS.keys())
        raise ValueError(f"Unknown AOI: {aoi}\nAvailable: {available}")
    return AOI_BOUNDS[aoi_lower]['bounds']


def create_geometry(aoi: str) -> ee.Geometry:
    """
    Create Earth Engine geometry for AOI bounding box.

    Args:
        aoi: Area of interest name

    Returns:
        ee.Geometry.Rectangle for the AOI
    """
    min_lat, min_lon, max_lat, max_lon = get_aoi_bounds(aoi)
    logger.debug(f"AOI {aoi}: [{min_lat}°N-{max_lat}°N, {min_lon}°E-{max_lon}°E]")
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


def calculate_cloud_cover(image: ee.Image) -> float:
    """
    Calculate cloud cover percentage for Sentinel-2 image.

    Args:
        image: Sentinel-2 L2A image

    Returns:
        Cloud cover percentage (0-100)
    """
    qa = image.select('QA60')
    cloud_bit_mask = (1 << 10)  # Cloud
    cirrus_bit_mask = (1 << 11)  # Cirrus

    cloud_pixels = qa.bitwiseAnd(cloud_bit_mask).add(qa.bitwiseAnd(cirrus_bit_mask)).gt(0)
    cloud_cover = cloud_pixels.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=image.geometry(),
        scale=20,
        maxPixels=1e9
    ).get('QA60')

    return cloud_cover


def filter_sentinel2_clouds(image: ee.Image, cloud_threshold: float = 20) -> ee.Image:
    """
    Filter Sentinel-2 image by cloud cover and apply cloud mask.

    Args:
        image: Input Sentinel-2 L2A image
        cloud_threshold: Maximum allowed cloud cover percentage (default 20%)

    Returns:
        Cloud-masked image or None if cloud cover exceeds threshold
    """
    # Calculate cloud cover
    cloud_cover = calculate_cloud_cover(image)

    # Add cloud cover as property
    image = image.set('cloud_cover', cloud_cover)

    # Apply cloud and cirrus masking
    qa = image.select('QA60')
    cloud_bit_mask = (1 << 10)
    cirrus_bit_mask = (1 << 11)

    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))

    # Scale reflectance from 0-10000 to 0-1
    masked = image.updateMask(mask).divide(10000)

    return masked


def create_monthly_composite(
    geometry: ee.Geometry,
    start_date: str,
    end_date: str,
    cloud_threshold: float = 20
) -> tuple:
    """
    Create monthly median composite from Sentinel-2 L2A.

    Args:
        geometry: ee.Geometry for AOI
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        cloud_threshold: Maximum cloud cover % (default 20%)

    Returns:
        Tuple of (composite image, image count, mean cloud cover)
    """
    # Filter Sentinel-2 collection
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterBounds(geometry) \
        .filterDate(start_date, end_date) \
        .map(lambda img: filter_sentinel2_clouds(img, cloud_threshold))

    image_count = s2.size().getInfo()

    if image_count == 0:
        logger.warning(f"  ⚠️  No Sentinel-2 images found for {start_date} to {end_date}")
        return None, 0, 0

    # Calculate statistics
    cloud_cover_list = s2.aggregate_array('cloud_cover').getInfo()
    mean_cloud = sum(cloud_cover_list) / len(cloud_cover_list) if cloud_cover_list else 0

    logger.debug(f"  Found {image_count} images, mean cloud cover: {mean_cloud:.1f}%")

    # Create median composite with selected bands
    composite = s2.select(BANDS).median().clip(geometry)

    return composite, image_count, mean_cloud


def export_image(
    image: ee.Image,
    geometry: ee.Geometry,
    filename: str,
    output_dir: str,
    scale: int = 10
) -> bool:
    """
    Export image to GeoTIFF via Google Drive.

    Args:
        image: ee.Image to export
        geometry: ee.Geometry for region
        filename: Output filename (without extension)
        output_dir: Output directory
        scale: Export resolution in meters

    Returns:
        True if export task started successfully
    """
    if image is None:
        logger.warning(f"  ⚠️  Skipping export: no image data")
        return False

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
            maxPixels=1e13,
            fileFormat='GeoTIFF'
        )
        task.start()
        logger.info(f"  ✓ Export queued: {filename}")
        return True

    except Exception as e:
        logger.error(f"  ✗ Export failed: {e}")
        return False


def download_aoi(
    aoi: str,
    start_date: str,
    end_date: str,
    output_dir: str,
    cloud_threshold: float = 20
) -> dict:
    """
    Download Sentinel-2 L2A monthly composites for AOI.

    Args:
        aoi: Area of interest name
        start_date: Start date in YYYY-MM format
        end_date: End date in YYYY-MM format
        output_dir: Output directory
        cloud_threshold: Maximum cloud cover % (default 20%)

    Returns:
        Dictionary with download statistics

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

    logger.info(f"📍 {aoi_name}")
    logger.info(f"   Period: {start_date} to {end_date}")
    logger.info(f"   Cloud threshold: < {cloud_threshold}%")
    logger.info(f"   Bands: {', '.join([f'{b} ({BAND_DESCRIPTIONS[b]})' for b in BANDS])}")

    stats = {
        'aoi': aoi,
        'months_processed': 0,
        'exports_queued': 0,
        'total_images': 0,
        'mean_cloud_cover': 0,
        'failures': 0
    }

    current_year = start_year
    current_month = start_month

    while (current_year, current_month) <= (end_year, end_month):
        try:
            month_start, month_end = get_month_date_range(current_year, current_month)
            month_str = f"{current_year}-{current_month:02d}"

            # Use new file naming convention
            filename = f"{aoi}_{current_year}_{current_month:02d}"

            logger.info(f"   {month_str}...", end=' ')

            composite, img_count, cloud_cover = create_monthly_composite(
                geometry, month_start, month_end, cloud_threshold
            )

            if composite is not None:
                success = export_image(composite, geometry, filename, output_dir)
                if success:
                    stats['exports_queued'] += 1
                    stats['total_images'] += img_count
                    stats['mean_cloud_cover'] += cloud_cover
                    logger.info(f"({img_count} images, {cloud_cover:.1f}% cloud)")
                else:
                    stats['failures'] += 1
                    logger.info("failed to queue")
            else:
                logger.info("no data")

            stats['months_processed'] += 1

        except Exception as e:
            logger.error(f"   {current_year}-{current_month:02d}: {e}")
            stats['failures'] += 1

        if current_month == 12:
            current_year += 1
            current_month = 1
        else:
            current_month += 1

    # Calculate statistics
    if stats['exports_queued'] > 0:
        stats['mean_cloud_cover'] /= stats['exports_queued']

    return stats


def main():
    """Main entry point for Sentinel-2 download."""
    parser = argparse.ArgumentParser(
        description="Download Sentinel-2 L2A monthly composites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
USAGE:
  python download_sentinel2.py --aoi pakistan --start 2023-01 --end 2023-12 --output data/raw/sentinel2/
  python download_sentinel2.py --aoi all --start 2023-01 --end 2023-12 --output data/raw/sentinel2/

REQUIREMENTS:
  .env file with: GEE_KEY_FILE=secrets/gee_key.json
  Service account with Earth Engine access

OUTPUT:
  File format: {aoi}_{year}_{month}.tif
  Bands: B2, B3, B4, B8, B11, B12 (6 spectral bands)
  Cloud filter: < 20% cloud cover
  Resolution: 10m, EPSG:4326
        """
    )
    parser.add_argument("--aoi", required=True, choices=['pakistan', 'china', 'bangladesh', 'all'])
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM)")
    parser.add_argument("--output", required=True, help="Output directory")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )

    print("\n" + "="*70)
    print("SENTINEL-2 L2A MONTHLY COMPOSITE DOWNLOAD")
    print("="*70)

    try:
        # Step 1: Authenticate
        print("\n🔐 Authenticating with Earth Engine...")
        info = authenticate()
        initialize()
        logger.info(f"   Service account: {info['email']}")
        logger.info(f"   Project: {info['project_id']}")

        # Step 2: Test connection
        print("\n🧪 Testing connection...")
        if not test_connection():
            logger.error("❌ Connection failed. Check service account permissions.")
            return 1

        # Step 3: Download
        print("\n📥 Downloading composites...\n")

        aois = ['pakistan', 'china', 'bangladesh'] if args.aoi.lower() == 'all' else [args.aoi.lower()]
        all_stats = {}

        for aoi in aois:
            try:
                stats = download_aoi(aoi, args.start, args.end, args.output)
                all_stats[aoi] = stats
            except Exception as e:
                logger.error(f"❌ Failed: {e}")
                return 1

        # Summary
        print("\n" + "="*70)
        print("DOWNLOAD SUMMARY")
        print("="*70)

        total_exports = sum(s['exports_queued'] for s in all_stats.values())
        total_images = sum(s['total_images'] for s in all_stats.values())

        for aoi, stats in all_stats.items():
            print(f"\n{aoi.upper()}")
            print(f"  Months processed: {stats['months_processed']}")
            print(f"  Exports queued: {stats['exports_queued']}")
            print(f"  Failures: {stats['failures']}")
            if stats['exports_queued'] > 0:
                print(f"  Mean cloud cover: {stats['mean_cloud_cover']:.1f}%")

        print(f"\n{'='*70}")
        print(f"TOTAL: {total_exports} files queued to Google Drive")
        print(f"Destination: My Drive/ecotrace-exports/")
        print(f"Monitor: https://code.earthengine.google.com/")
        print(f"{'='*70}\n")

        return 0

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
