"""
Compute water stress features from satellite NDVI/NDWI indices.

Reads raw monthly satellite indices and computes:
- Annual aggregates (mean NDVI, mean NDWI)
- NDVI trend slope (deforestation signal)
- NDWI anomaly (water stress indicator)
- Peak stress month
"""

import csv
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def read_raw_indices(csv_path: str) -> pd.DataFrame:
    """
    Read raw satellite indices from CSV.

    Args:
        csv_path: Path to raw_indices.csv

    Returns:
        DataFrame with columns: zone, year, month, mean_ndvi, mean_ndwi
    """
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} records from {csv_path}")
    return df


def compute_annual_means(df: pd.DataFrame, zone: str) -> Tuple[float, float]:
    """
    Compute annual mean NDVI and NDWI for a zone.

    Args:
        df: DataFrame with all data
        zone: Zone name

    Returns:
        Tuple of (mean_ndvi, mean_ndwi)
    """
    zone_data = df[df['zone'] == zone]
    mean_ndvi = zone_data['mean_ndvi'].mean()
    mean_ndwi = zone_data['mean_ndwi'].mean()
    return mean_ndvi, mean_ndwi


def compute_ndvi_trend(df: pd.DataFrame, zone: str) -> float:
    """
    Compute NDVI trend slope across months using polynomial fit.

    Negative slope indicates vegetation loss (deforestation signal).

    Args:
        df: DataFrame with all data
        zone: Zone name

    Returns:
        Slope of NDVI trend (per month)
    """
    zone_data = df[df['zone'] == zone].sort_values('month')

    if len(zone_data) < 2:
        return 0.0

    months = zone_data['month'].values.astype(float)
    ndvi_values = zone_data['mean_ndvi'].values

    # Fit polynomial (degree 1 = linear)
    coeffs = np.polyfit(months, ndvi_values, 1)
    slope = coeffs[0]  # Linear coefficient is the slope

    return float(slope)


def compute_ndwi_anomaly(df: pd.DataFrame, zone: str) -> Dict[int, float]:
    """
    Compute NDWI anomaly for each month (std deviations below zone mean).

    Higher values indicate more water stress.

    Args:
        df: DataFrame with all data
        zone: Zone name

    Returns:
        Dict mapping month to anomaly value
    """
    zone_data = df[df['zone'] == zone]

    mean_ndwi = zone_data['mean_ndwi'].mean()
    std_ndwi = zone_data['mean_ndwi'].std()

    if std_ndwi == 0:
        return {month: 0.0 for month in zone_data['month'].values}

    anomalies = {}
    for _, row in zone_data.iterrows():
        month = int(row['month'])
        ndwi_value = row['mean_ndwi']
        # Anomaly = how many std devs below the mean (negative = below mean)
        # We invert so positive = more stress
        anomaly = (mean_ndwi - ndwi_value) / std_ndwi
        anomalies[month] = float(anomaly)

    return anomalies


def find_peak_stress_month(df: pd.DataFrame, zone: str) -> Tuple[int, float]:
    """
    Find month with lowest NDWI (peak water stress).

    Args:
        df: DataFrame with all data
        zone: Zone name

    Returns:
        Tuple of (month, min_ndwi)
    """
    zone_data = df[df['zone'] == zone]

    if zone_data.empty:
        return None, None

    min_idx = zone_data['mean_ndwi'].idxmin()
    month = int(zone_data.loc[min_idx, 'month'])
    min_ndwi = zone_data.loc[min_idx, 'mean_ndwi']

    return month, float(min_ndwi)


def process_zones(df: pd.DataFrame) -> List[Dict]:
    """
    Process all zones and compute features.

    Args:
        df: DataFrame with raw indices

    Returns:
        List of feature dictionaries
    """
    results = []
    zones = df['zone'].unique()

    for zone in zones:
        logger.info(f"Processing {zone}...")

        # Annual aggregates
        mean_ndvi, mean_ndwi = compute_annual_means(df, zone)

        # NDVI trend
        ndvi_slope = compute_ndvi_trend(df, zone)

        # NDWI anomalies
        anomalies = compute_ndwi_anomaly(df, zone)
        mean_anomaly = np.mean(list(anomalies.values())) if anomalies else 0.0

        # Peak stress
        stress_month, stress_ndwi = find_peak_stress_month(df, zone)

        results.append({
            'zone': zone,
            'annual_mean_ndvi': round(mean_ndvi, 6),
            'annual_mean_ndwi': round(mean_ndwi, 6),
            'ndvi_trend_slope': round(ndvi_slope, 6),
            'mean_ndwi_anomaly': round(mean_anomaly, 6),
            'peak_stress_month': stress_month,
            'peak_stress_ndwi': round(stress_ndwi, 6)
        })

    return results


def save_features(results: List[Dict], output_path: str) -> None:
    """
    Save computed features to CSV.

    Args:
        results: List of feature dictionaries
        output_path: Path to output CSV
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        fieldnames = [
            'zone',
            'annual_mean_ndvi',
            'annual_mean_ndwi',
            'ndvi_trend_slope',
            'mean_ndwi_anomaly',
            'peak_stress_month',
            'peak_stress_ndwi'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"Features saved to {output_path}")


def print_summary(results: List[Dict]) -> None:
    """
    Print summary table of results.

    Args:
        results: List of feature dictionaries
    """
    print("\n" + "="*100)
    print("WATER STRESS FEATURES SUMMARY")
    print("="*100)
    print(f"{'Zone':<15} {'Mean NDVI':<12} {'Mean NDWI':<12} {'NDVI Trend':<12} {'NDWI Anomaly':<15} {'Peak Stress':<12}")
    print("-"*100)

    for result in results:
        zone = result['zone']
        ndvi = result['annual_mean_ndvi']
        ndwi = result['annual_mean_ndwi']
        trend = result['ndvi_trend_slope']
        anomaly = result['mean_ndwi_anomaly']
        month = result['peak_stress_month']

        trend_indicator = "[LOSS]" if trend < 0 else "[GAIN]"
        if anomaly > 0.5:
            stress_indicator = "[STRESS]"
        elif anomaly > 0:
            stress_indicator = "[ALERT]"
        else:
            stress_indicator = "[NORMAL]"

        print(f"{zone:<15} {ndvi:<12.4f} {ndwi:<12.4f} {trend:.6f} {anomaly:<15.4f} M{month} {stress_indicator} {trend_indicator}")

    print("="*100 + "\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Compute water stress features from satellite indices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
USAGE:
  python -m src.preprocessing.compute_indices
  python -m src.preprocessing.compute_indices --input data/processed/raw_indices.csv --output data/processed/features_water_stress.csv

OUTPUT:
  File: data/processed/features_water_stress.csv
  Columns:
    - annual_mean_ndvi: Mean vegetation index
    - annual_mean_ndwi: Mean water index
    - ndvi_trend_slope: Vegetation loss rate (negative = loss)
    - mean_ndwi_anomaly: Average water stress (std devs below mean)
    - peak_stress_month: Month with lowest water availability
    - peak_stress_ndwi: NDWI value in peak stress month
        """
    )
    parser.add_argument(
        "--input",
        default="data/processed/raw_indices.csv",
        help="Input CSV with raw indices (default: data/processed/raw_indices.csv)"
    )
    parser.add_argument(
        "--output",
        default="data/processed/features_water_stress.csv",
        help="Output CSV with features (default: data/processed/features_water_stress.csv)"
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(message)s')

    print("\n" + "="*100)
    print("WATER STRESS FEATURE COMPUTATION")
    print("="*100 + "\n")

    try:
        # Read raw indices
        df = read_raw_indices(args.input)

        # Process zones
        print(f"[*] Computing features for {df['zone'].nunique()} zones...\n")
        results = process_zones(df)

        # Save features
        save_features(results, args.output)

        # Print summary
        print_summary(results)

        print(f"[SUCCESS] Done! Features saved to {args.output}")
        return 0

    except Exception as e:
        logger.error(f"[!] Error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
