"""
Create monthly median composites from cloud-masked Sentinel-2 images.

Generates monthly composites by calculating median values across all
cloud-masked images within each month. Handles different sensors and
data types automatically.
"""

import logging
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
from collections import defaultdict


logger = logging.getLogger(__name__)


class CompositeGenerator:
    """Generate monthly median composite images from time series data."""

    def __init__(self, output_resolution: int = 10, compression: str = 'lzw'):
        """
        Initialize CompositeGenerator.

        Args:
            output_resolution: Output raster resolution in meters
            compression: Rasterio compression method (lzw, deflate, etc.)
        """
        self.output_resolution = output_resolution
        self.compression = compression
        logger.info(f"CompositeGenerator initialized: {output_resolution}m resolution")

    def get_date_from_filename(self, filename: str) -> Tuple[int, int]:
        """
        Extract year and month from filename.

        Expects format: ...YYYYMM... or ...YYYY-MM-DD...

        Args:
            filename: Input filename

        Returns:
            Tuple of (year, month)

        Raises:
            ValueError: If date cannot be extracted
        """
        # Try format: YYYYMM (compact)
        for part in filename.split('_'):
            if len(part) == 6 and part.isdigit():
                try:
                    year, month = int(part[:4]), int(part[4:6])
                    if 1 <= month <= 12:
                        return year, month
                except ValueError:
                    continue

        # Try format: YYYY-MM-DD
        for part in filename.split('_'):
            if len(part) == 10 and part[4] == '-' and part[7] == '-':
                try:
                    dt = datetime.strptime(part, '%Y-%m-%d')
                    return dt.year, dt.month
                except ValueError:
                    continue

        raise ValueError(f"Could not extract date from filename: {filename}")

    def load_and_align_image(self, path: str, reference_crs=None, reference_res=None):
        """
        Load image and optionally align to reference CRS and resolution.

        Args:
            path: Path to image file
            reference_crs: Optional reference CRS for warping
            reference_res: Optional reference resolution for warping

        Returns:
            Tuple of (data, profile)
        """
        with rasterio.open(path) as src:
            data = src.read()
            profile = src.profile

            # Warp to reference CRS if provided
            if reference_crs and src.crs != reference_crs:
                with WarpedVRT(src, crs=reference_crs) as vrt:
                    data = vrt.read()
                    profile = vrt.profile

        return data, profile

    def compute_median_composite(
        self,
        image_arrays: List[np.ndarray],
        ignore_zero: bool = True
    ) -> np.ndarray:
        """
        Compute median across image arrays.

        Args:
            image_arrays: List of image arrays to composite
            ignore_zero: If True, treat 0 values as masked (no data)

        Returns:
            Median composite array with same shape as input images
        """
        if not image_arrays:
            raise ValueError("No images provided for composite")

        # Stack arrays: shape becomes (n_images, bands, height, width)
        stacked = np.stack(image_arrays, axis=0)
        logger.debug(f"Stacked shape: {stacked.shape}")

        if ignore_zero:
            # Mask zero values (nodata)
            masked_array = np.ma.masked_equal(stacked, 0)
            composite = np.ma.median(masked_array, axis=0).filled(0)
        else:
            composite = np.median(stacked, axis=0)

        return composite.astype(image_arrays[0].dtype)

    def create_monthly_composite(
        self,
        image_paths: List[str],
        output_path: str,
        month: str = None,
        method: str = "median"
    ) -> bool:
        """
        Create monthly composite from list of images.

        Args:
            image_paths: List of input image paths for the month
            output_path: Path to write composite output
            month: Month identifier (YYYY-MM) for logging
            method: Compositing method (median, mean)

        Returns:
            True if composite created successfully

        Raises:
            ValueError: If image_paths is empty or method invalid
        """
        if not image_paths:
            logger.warning(f"No images for month {month}")
            return False

        if method not in ['median', 'mean']:
            raise ValueError(f"Invalid method: {method}. Use 'median' or 'mean'")

        try:
            logger.info(f"Creating {method} composite from {len(image_paths)} images for {month}")

            # Load all images
            image_arrays = []
            reference_profile = None

            for i, path in enumerate(image_paths):
                try:
                    data, profile = self.load_and_align_image(path)
                    image_arrays.append(data)

                    if reference_profile is None:
                        reference_profile = profile
                    logger.debug(f"  Loaded {i+1}/{len(image_paths)}: {Path(path).name} - shape {data.shape}")

                except Exception as e:
                    logger.warning(f"  Failed to load {path}: {e}")
                    continue

            if not image_arrays:
                logger.warning(f"No valid images loaded for month {month}")
                return False

            # Compute composite
            if method == 'median':
                composite = self.compute_median_composite(image_arrays, ignore_zero=True)
            else:  # mean
                stacked = np.stack(image_arrays, axis=0)
                masked = np.ma.masked_equal(stacked, 0)
                composite = np.ma.mean(masked, axis=0).filled(0).astype(image_arrays[0].dtype)

            # Update profile for output
            output_profile = reference_profile.copy()
            output_profile.update(
                dtype=composite.dtype,
                compress=self.compression,
                nodata=0
            )

            # Write output
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(output_path, 'w', **output_profile) as dst:
                dst.write(composite)

            logger.info(f"Composite saved: {output_path} - shape {composite.shape}")
            return True

        except Exception as e:
            logger.error(f"Error creating composite for {month}: {e}")
            return False

    def composite_from_directory(
        self,
        input_dir: str,
        output_dir: str,
        method: str = "median",
        pattern: str = "*.tif"
    ) -> Dict:
        """
        Create monthly composites from all images in directory.

        Groups images by month and generates median/mean composites.

        Args:
            input_dir: Input directory with cloud-masked images
            output_dir: Output directory for composites
            method: Compositing method (median, mean)
            pattern: File pattern to match (default *.tif)

        Returns:
            Dict with compositing statistics
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Find all matching files
        files = sorted(input_path.glob(pattern))
        logger.info(f"Found {len(files)} files matching pattern '{pattern}'")

        # Group by month
        monthly_files = defaultdict(list)
        failed_dates = []

        for file_path in files:
            try:
                year, month = self.get_date_from_filename(file_path.name)
                monthly_files[(year, month)].append(str(file_path))
            except ValueError as e:
                logger.debug(f"Could not extract date from {file_path.name}: {e}")
                failed_dates.append(file_path.name)

        logger.info(f"Grouped into {len(monthly_files)} months")
        if failed_dates:
            logger.warning(f"Could not parse dates for {len(failed_dates)} files")

        # Create composites for each month
        stats = {
            'total_months': len(monthly_files),
            'successful': 0,
            'failed': 0,
            'composites': []
        }

        for (year, month), paths in sorted(monthly_files.items()):
            month_str = f"{year}-{month:02d}"
            output_file = output_path / f"composite_{year}{month:02d}.tif"

            success = self.create_monthly_composite(
                paths,
                str(output_file),
                month=month_str,
                method=method
            )

            if success:
                stats['successful'] += 1
                stats['composites'].append({
                    'month': month_str,
                    'output': str(output_file),
                    'n_images': len(paths)
                })
            else:
                stats['failed'] += 1

        logger.info(
            f"Compositing complete: {stats['successful']} successful, {stats['failed']} failed"
        )
        return stats


def get_images_for_month(directory: str, year: int, month: int) -> List[str]:
    """
    Retrieve all images for a specific month.

    Args:
        directory: Directory to search
        year: Year
        month: Month (1-12)

    Returns:
        List of matching file paths
    """
    path = Path(directory)
    month_str = f"{year}{month:02d}"

    # Look for files with YYYYMM pattern
    files = []
    for file in path.glob("*.tif"):
        if month_str in file.name:
            files.append(str(file))

    return sorted(files)


def main():
    """Command-line entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Create monthly composites from cloud-masked Sentinel-2 images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python monthly_composite.py --input data/processed/masked --output data/processed/composites --method median
  python monthly_composite.py --input /path/to/masked --output /path/to/composites --method mean
        """
    )
    parser.add_argument("--input", required=True, help="Input directory with cloud-masked images")
    parser.add_argument("--output", required=True, help="Output directory for monthly composites")
    parser.add_argument("--method", default="median", choices=['median', 'mean'],
                       help="Compositing method (default median)")
    parser.add_argument("--pattern", default="*.tif", help="File pattern to match (default *.tif)")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info(f"Starting monthly composite generation")
    logger.info(f"Input: {args.input}")
    logger.info(f"Output: {args.output}")
    logger.info(f"Method: {args.method}")

    generator = CompositeGenerator()
    stats = generator.composite_from_directory(
        args.input,
        args.output,
        method=args.method,
        pattern=args.pattern
    )

    print(f"\n{'='*60}")
    print(f"Monthly Composite Summary")
    print(f"{'='*60}")
    print(f"Total months:    {stats['total_months']}")
    print(f"Successful:      {stats['successful']}")
    print(f"Failed:          {stats['failed']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
