"""
Cloud masking for Sentinel-2 L2A imagery.

Uses the Scene Classification Layer (SCL) band to identify and mask clouds,
cloud shadows, and high aerosol pixels. Discards scenes with >50% cloud coverage.
"""

import logging
import numpy as np
import rasterio
from rasterio.mask import mask as rio_mask
from pathlib import Path
from typing import Tuple, Optional
import json


logger = logging.getLogger(__name__)


class CloudMasker:
    """Apply cloud masking to Sentinel-2 L2A products using SCL band."""

    # SCL class definitions (from Sentinel-2 documentation)
    SCL_CLASSES = {
        0: "nodata",
        1: "saturated_defective",
        2: "dark_features",
        3: "cloud_shadow",
        4: "vegetation",
        5: "non_vegetated",
        6: "water",
        7: "unclassified",
        8: "cloud_medium",
        9: "cloud_high",
        10: "thin_cirrus",
        11: "snow_ice"
    }

    # Pixels to mask: clouds, shadows, high aerosol, snow/ice
    CLOUD_CLASSES = {0, 1, 3, 8, 9, 10, 11}

    def __init__(self, cloud_threshold: float = 0.5):
        """
        Initialize CloudMasker.

        Args:
            cloud_threshold: Maximum allowed cloud percentage (0-1). Default 0.5 (50%)
        """
        if not 0 <= cloud_threshold <= 1:
            raise ValueError("cloud_threshold must be between 0 and 1")
        self.cloud_threshold = cloud_threshold
        logger.info(f"CloudMasker initialized with threshold: {cloud_threshold*100:.1f}%")

    def calculate_cloud_coverage(self, scl_data: np.ndarray) -> float:
        """
        Calculate cloud coverage percentage from SCL band.

        Args:
            scl_data: SCL band array (2D)

        Returns:
            Cloud coverage as fraction (0-1)
        """
        total_pixels = scl_data.size
        if total_pixels == 0:
            return 0.0

        cloud_pixels = np.sum(np.isin(scl_data, list(self.CLOUD_CLASSES)))
        coverage = cloud_pixels / total_pixels
        return coverage

    def mask_image(self, scl_path: str, data_path: str, output_path: str) -> bool:
        """
        Apply cloud mask to image using SCL band.

        Reads SCL band, calculates cloud coverage, and if acceptable (<threshold),
        masks clouds/shadows/aerosol in data bands and saves output.

        Args:
            scl_path: Path to Scene Classification Layer raster (band 11 from S2 L2A)
            data_path: Path to image data to mask (typically reflectance bands)
            output_path: Path to write masked output GeoTIFF

        Returns:
            True if masking successful and cloud coverage acceptable,
            False if cloud coverage exceeds threshold

        Raises:
            FileNotFoundError: If input files not found
            rasterio.RasterioIOError: If files cannot be opened
        """
        try:
            # Read SCL band
            with rasterio.open(scl_path) as scl_src:
                scl_data = scl_src.read(1).astype(np.uint8)
                scl_profile = scl_src.profile

            # Calculate cloud coverage
            cloud_coverage = self.calculate_cloud_coverage(scl_data)
            logger.info(f"Cloud coverage: {cloud_coverage*100:.1f}%")

            # Check threshold
            if cloud_coverage > self.cloud_threshold:
                logger.warning(
                    f"Scene rejected: {cloud_coverage*100:.1f}% cloud coverage "
                    f"exceeds threshold of {self.cloud_threshold*100:.1f}%"
                )
                return False

            # Create mask: valid pixels (not in cloud classes)
            valid_mask = ~np.isin(scl_data, list(self.CLOUD_CLASSES))

            # Read data file
            with rasterio.open(data_path) as data_src:
                bands = data_src.read()
                profile = data_src.profile

            # Apply mask to all bands (set masked pixels to 0)
            masked_bands = bands.copy()
            for i in range(masked_bands.shape[0]):
                masked_bands[i, ~valid_mask] = 0

            # Update profile for output
            profile.update(
                dtype=rasterio.uint16,
                compress='lzw',
                nodata=0
            )

            # Write masked output
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(output_path, 'w', **profile) as dst:
                dst.write(masked_bands)

            logger.info(f"Masked image saved: {output_path}")
            return True

        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            raise
        except Exception as e:
            logger.error(f"Error masking image: {e}")
            raise

    def batch_mask_directory(
        self,
        input_dir: str,
        output_dir: str,
        scl_suffix: str = "_SCL.tif",
        data_suffix: str = ".tif"
    ) -> dict:
        """
        Apply cloud masking to all image pairs in directory.

        Expects pairs of files: scene_SCL.tif and scene.tif

        Args:
            input_dir: Input directory containing raw Sentinel-2 files
            output_dir: Output directory for masked images
            scl_suffix: Suffix for SCL band files
            data_suffix: Suffix for data files

        Returns:
            Dict with processing statistics
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        stats = {
            'total': 0,
            'accepted': 0,
            'rejected': 0,
            'errors': 0,
            'rejected_files': []
        }

        # Find all SCL files
        scl_files = sorted(input_path.glob(f"*{scl_suffix}"))
        logger.info(f"Found {len(scl_files)} SCL files in {input_dir}")

        for scl_file in scl_files:
            stats['total'] += 1
            base_name = scl_file.name.replace(scl_suffix, '')
            data_file = input_path / f"{base_name}{data_suffix}"

            if not data_file.exists():
                logger.warning(f"Data file not found for {scl_file.name}")
                stats['errors'] += 1
                continue

            output_file = output_path / f"{base_name}_masked.tif"

            try:
                success = self.mask_image(str(scl_file), str(data_file), str(output_file))
                if success:
                    stats['accepted'] += 1
                else:
                    stats['rejected'] += 1
                    stats['rejected_files'].append(base_name)
            except Exception as e:
                logger.error(f"Error processing {base_name}: {e}")
                stats['errors'] += 1

        logger.info(
            f"Batch processing complete: {stats['accepted']} accepted, "
            f"{stats['rejected']} rejected, {stats['errors']} errors"
        )
        return stats


def process_directory(input_dir: str, output_dir: str, threshold: float = 0.5) -> dict:
    """
    Apply cloud masking to all images in directory.

    Args:
        input_dir: Input directory containing raw Sentinel-2 data
        output_dir: Output directory for masked images
        threshold: Cloud coverage threshold (0-1)

    Returns:
        Processing statistics dictionary
    """
    masker = CloudMasker(cloud_threshold=threshold)
    return masker.batch_mask_directory(input_dir, output_dir)


def main():
    """Command-line entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Apply cloud masking to Sentinel-2 L2A data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cloud_mask.py --input data/raw/sentinel2 --output data/processed/masked --threshold 0.5
  python cloud_mask.py --input /path/to/s2/scenes --output /path/to/masked --threshold 0.3
        """
    )
    parser.add_argument("--input", required=True, help="Input directory with S2 L2A files")
    parser.add_argument("--output", required=True, help="Output directory for masked images")
    parser.add_argument("--threshold", type=float, default=0.5, help="Cloud threshold (0-1, default 0.5)")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info(f"Starting cloud masking: {args.input} -> {args.output}")
    logger.info(f"Cloud coverage threshold: {args.threshold*100:.1f}%")

    stats = process_directory(args.input, args.output, args.threshold)
    print(f"\n{'='*60}")
    print(f"Cloud Masking Summary")
    print(f"{'='*60}")
    print(f"Total processed:  {stats['total']}")
    print(f"Accepted:         {stats['accepted']}")
    print(f"Rejected (cloud): {stats['rejected']}")
    print(f"Errors:           {stats['errors']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
