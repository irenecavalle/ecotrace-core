"""
Download Sentinel-2 L2A imagery and compute NDVI/NDWI indices.

Computes monthly NDVI and NDWI values for three AOIs:
- Indus Basin, Pakistan
- Yangtze Delta, China
- Dhaka Region, Bangladesh

Processing:
- Cloud cover filtering: < 20%
- NDVI = (B8 - B4) / (B8 + B4)
- NDWI = (B8 - B11) / (B8 + B11)
- Monthly median composites
- Output: CSV file with mean indices
"""

import argparse
import logging
import os
import sys
import csv
from pathlib import Path
from typing import Tuple
from datetime import datetime, timedelta
import ee
from dotenv import load_dotenv

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

# Index calculations
INDEX_FORMULAS = {
    'ndvi': {'name': 'Normalized Difference Vegetation Index', 'formula': '(B8 - B4) / (B8 + B4)'},
    'ndwi': {'name': 'Normalized Difference Water Index', 'formula': '(B8 - B11) / (B8 + B11)'}
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


def filter_sentinel2_clouds(image: ee.Image, cloud_threshold: float = 20) -> ee.Image:
    """
    Filter Sentinel-2 image by cloud cover using CLOUDY_PIXEL_PERCENTAGE.

    Args:
        image: Input Sentinel-2 L2A image
        cloud_threshold: Maximum allowed cloud cover percentage (default 20%)

    Returns:
        Masked image with cloud_cover property
    """
    # Get cloud cover percentage from metadata
    cloud_cover = ee.Number(image.get('CLOUDY_PIXEL_PERCENTAGE'))

    # Create mask: 1 where cloud cover is below threshold, 0 otherwise
    cloud_mask = cloud_cover.lt(cloud_threshold)

    # Add cloud cover as property
    image = image.set('cloud_cover', cloud_cover)
    image = image.set('passes_filter', cloud_mask)

    # Scale reflectance from 0-10000 to 0-1
    masked = image.divide(10000)

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
        Tuple of (composite image, filtered_image_count)
    """
    # Filter Sentinel-2 collection
    s2_raw = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterBounds(geometry) \
        .filterDate(start_date, end_date) \
        .filterMetadata('CLOUDY_PIXEL_PERCENTAGE', 'less_than', cloud_threshold)

    image_count = s2_raw.size().getInfo()

    if image_count == 0:
        logger.warning(f"  [!] No Sentinel-2 images found for {start_date} to {end_date}")
        return None, 0

    # Create median composite with selected bands, scaled to 0-1
    composite = s2_raw.select(BANDS).map(lambda img: img.divide(10000)).median().clip(geometry)

    return composite, image_count


def compute_indices(
    image: ee.Image,
    geometry: ee.Geometry,
    aoi: str,
    year: int,
    month: int
) -> dict:
    """
    Compute NDVI and NDWI indices using reduceRegion with timeout handling.

    Args:
        image: ee.Image composite
        geometry: ee.Geometry for region
        aoi: Area of interest name
        year: Year
        month: Month

    Returns:
        Dict with zone, year, month, mean_ndvi, mean_ndwi
    """
    if image is None:
        return None

    try:
        # Calculate NDVI: (NIR - Red) / (NIR + Red)
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('ndvi')

        # Calculate NDWI: (NIR - SWIR1) / (NIR + SWIR1)
        ndwi = image.normalizedDifference(['B8', 'B11']).rename('ndwi')

        # Combine indices
        indices = image.addBands(ndvi).addBands(ndwi).select(['ndvi', 'ndwi'])

        # Compute mean values at 100m scale to reduce computation
        # This significantly reduces the number of pixels to process
        stats = indices.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=100,  # Use 100m instead of 10m for faster computation
            maxPixels=1e8,
            bestEffort=True  # Allow approximate results if exact computation times out
        ).getInfo()

        mean_ndvi = round(float(stats.get('ndvi', None)), 6) if stats.get('ndvi') is not None else None
        mean_ndwi = round(float(stats.get('ndwi', None)), 6) if stats.get('ndwi') is not None else None

        return {
            'zone': aoi,
            'year': year,
            'month': month,
            'mean_ndvi': mean_ndvi,
            'mean_ndwi': mean_ndwi
        }

    except Exception as e:
        logger.error(f"  [ERR] Index computation failed: {e}")
        return None


def download_aoi(
    aoi: str,
    start_date: str,
    end_date: str,
    cloud_threshold: float = 20
) -> tuple:
    """
    Compute NDVI/NDWI indices for Sentinel-2 L2A monthly composites.

    Args:
        aoi: Area of interest name
        start_date: Start date in YYYY-MM format
        end_date: End date in YYYY-MM format
        cloud_threshold: Maximum cloud cover % (default 20%)

    Returns:
        Tuple of (list of result dicts, statistics dict)

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

    logger.info(f"[AOI] {aoi_name}")
    logger.info(f"   Period: {start_date} to {end_date}")
    logger.info(f"   Cloud threshold: < {cloud_threshold}%")
    logger.info(f"   Indices: NDVI (vegetation), NDWI (water)")

    results = []
    stats = {
        'aoi': aoi,
        'months_processed': 0,
        'computed': 0,
        'failures': 0,
    }

    current_year = start_year
    current_month = start_month

    while (current_year, current_month) <= (end_year, end_month):
        try:
            month_start, month_end = get_month_date_range(current_year, current_month)
            month_str = f"{current_year}-{current_month:02d}"

            sys.stdout.write(f"   {month_str}... ")
            sys.stdout.flush()

            composite, img_count = create_monthly_composite(
                geometry, month_start, month_end, cloud_threshold
            )

            if composite is not None:
                result = compute_indices(composite, geometry, aoi, current_year, current_month)
                if result:
                    results.append(result)
                    stats['computed'] += 1
                    ndvi_str = f"{result['mean_ndvi']:.4f}" if result['mean_ndvi'] else "N/A"
                    ndwi_str = f"{result['mean_ndwi']:.4f}" if result['mean_ndwi'] else "N/A"
                    print(f"NDVI={ndvi_str}, NDWI={ndwi_str} ({img_count} images)")
                else:
                    stats['failures'] += 1
                    print("FAILED")
            else:
                print("no data found")

            stats['months_processed'] += 1

        except Exception as e:
            logger.error(f"   {current_year}-{current_month:02d}: {e}")
            stats['failures'] += 1

        if current_month == 12:
            current_year += 1
            current_month = 1
        else:
            current_month += 1

    return results, stats


def write_results_csv(results: list, output_path: str) -> None:
    """
    Write computed indices to CSV file.

    Args:
        results: List of result dicts with zone, year, month, mean_ndvi, mean_ndwi
        output_path: Path to output CSV file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['zone', 'year', 'month', 'mean_ndvi', 'mean_ndwi'])
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    logger.info(f"Results saved to: {output_path}")


def main():
    """Main entry point for Sentinel-2 index computation."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Compute NDVI and NDWI indices from Sentinel-2 L2A data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
USAGE:
  python download_sentinel2.py --aoi pakistan --start 2023-01 --end 2023-12
  python download_sentinel2.py --aoi all --start 2023-01 --end 2023-12

REQUIREMENTS:
  .env file with: GEE_KEY_FILE=secrets/gee_key.json
  Service account with Earth Engine access

OUTPUT:
  File: data/processed/raw_indices.csv
  Columns: zone, year, month, mean_ndvi, mean_ndwi
  Cloud filter: < 20% cloud cover
        """
    )
    parser.add_argument("--aoi", required=True, choices=['pakistan', 'china', 'bangladesh', 'all'])
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM)")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )

    print("\n" + "="*70)
    print("SENTINEL-2 NDVI/NDWI INDEX COMPUTATION")
    print("="*70)

    try:
        # Step 1: Authenticate
        print("\n[*] Authenticating with Earth Engine...")
        info = authenticate()
        initialize()
        logger.info(f"   Service account: {info['email']}")
        logger.info(f"   Project: {info['project_id']}")

        # Step 2: Test connection
        print("\n[*] Testing connection...")
        if not test_connection():
            logger.error("[!] Connection failed. Check service account permissions.")
            return 1

        # Step 3: Compute indices
        print(f"\n[*] Computing indices\n")

        aois = ['pakistan', 'china', 'bangladesh'] if args.aoi.lower() == 'all' else [args.aoi.lower()]
        all_results = []
        all_stats = {}

        for aoi in aois:
            try:
                results, stats = download_aoi(aoi, args.start, args.end)
                all_results.extend(results)
                all_stats[aoi] = stats
            except Exception as e:
                logger.error(f"[!] Failed: {e}")
                return 1

        # Write results to CSV
        csv_path = 'data/processed/raw_indices.csv'
        write_results_csv(all_results, csv_path)

        # Summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)

        total_computed = sum(s['computed'] for s in all_stats.values())
        total_processed = sum(s['months_processed'] for s in all_stats.values())

        for aoi, stats in all_stats.items():
            print(f"\n{aoi.upper()}")
            print(f"  Months processed: {stats['months_processed']}")
            print(f"  Indices computed: {stats['computed']}")
            print(f"  Failures: {stats['failures']}")

        print(f"\n{'='*70}")
        print(f"TOTAL PROCESSED: {total_processed} months")
        print(f"TOTAL COMPUTED: {total_computed} records")
        print(f"OUTPUT: {csv_path}")
        print(f"{'='*70}\n")

        return 0

    except Exception as e:
        logger.error(f"[!] Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
