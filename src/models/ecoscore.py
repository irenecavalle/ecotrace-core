"""
EcoScore model: Sustainability ratings based on satellite indices.

Computes environmental scores combining:
- Deforestation risk (NDVI trend)
- Water stress (NDWI availability)
- Pollution proxy (vegetation/water degradation)

Score: 0-100 (100 = most sustainable)
Status: COMPLIANT (>=70), REVIEW (40-69), CRITICAL (<40)
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class EcoScorer:
    """Compute environmental sustainability scores from satellite data."""

    def __init__(self):
        """Initialize scorer."""
        self.zone_scores = {}
        self.min_max_values = {}

    def read_features(self, csv_path: str) -> pd.DataFrame:
        """
        Read water stress features from CSV.

        Args:
            csv_path: Path to features_water_stress.csv

        Returns:
            DataFrame with feature columns
        """
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded features for {len(df)} zones from {csv_path}")
        return df

    def normalize_feature(
        self,
        value: float,
        min_val: float,
        max_val: float
    ) -> float:
        """
        Normalize feature to 0-100 scale.

        Args:
            value: Feature value
            min_val: Minimum expected value
            max_val: Maximum expected value

        Returns:
            Normalized value 0-100 (clipped)
        """
        if max_val == min_val:
            return 50.0

        normalized = ((value - min_val) / (max_val - min_val)) * 100
        return float(np.clip(normalized, 0, 100))

    def compute_deforestation_risk(self, row: Dict) -> Tuple[float, float]:
        """
        Compute deforestation risk (0-100, higher = worse).

        Based on NDVI trend slope and absolute NDVI values.
        Negative trend = vegetation loss = high risk.

        Args:
            row: Feature row with ndvi_trend_slope and annual_mean_ndvi

        Returns:
            Tuple of (normalized_risk_value 0-100, raw_risk_metric)
        """
        trend_slope = row['ndvi_trend_slope']
        mean_ndvi = row['annual_mean_ndvi']

        # NDVI trend: -0.1 to +0.1 is reasonable range
        # Normalize trend to 0-100 where negative = high risk
        # Invert so negative trends = high values (100 = loss, 0 = gain)
        trend_risk = self.normalize_feature(
            -trend_slope,  # Invert: negative slope becomes positive risk
            -0.15,  # Min trend (strong growth)
            0.15    # Max trend (strong loss)
        )

        # NDVI vegetation risk: low NDVI = degraded
        # Use 0-0.8 as typical range (lower = more risk)
        vegetation_risk = self.normalize_feature(
            0.8 - mean_ndvi,  # Invert: low NDVI = high risk
            0,
            0.8
        )

        # Combine: weight trend more heavily (60%) than absolute NDVI (40%)
        deforestation_risk = (trend_risk * 0.6) + (vegetation_risk * 0.4)

        return float(np.clip(deforestation_risk, 0, 100)), trend_slope

    def compute_water_stress(self, row: Dict) -> Tuple[float, float]:
        """
        Compute water stress risk (0-100, higher = worse).

        Based on NDWI values and anomalies.
        Low NDWI = water stress.

        Args:
            row: Feature row with annual_mean_ndwi and mean_ndwi_anomaly

        Returns:
            Tuple of (normalized_stress_value 0-100, raw_stress_metric)
        """
        mean_ndwi = row['annual_mean_ndwi']
        anomaly = row['mean_ndwi_anomaly']

        # NDWI water availability: -1 to 1 typical range
        # Lower NDWI = more water stress
        ndwi_stress = self.normalize_feature(
            0.5 - mean_ndwi,  # Invert: low NDWI = high stress
            -0.5,
            0.5
        )

        # Anomaly stress: positive anomaly = below normal = stress
        anomaly_stress = self.normalize_feature(
            max(anomaly, 0),  # Only count negative anomalies (stress)
            0,
            1.0
        )

        # Combine: NDWI more important (70%) than anomaly (30%)
        water_stress = (ndwi_stress * 0.7) + (anomaly_stress * 0.3)

        return float(np.clip(water_stress, 0, 100)), mean_ndwi

    def compute_pollution_proxy(self, row: Dict) -> Tuple[float, float]:
        """
        Compute pollution proxy risk (0-100, higher = worse).

        Derived from combination of low vegetation and water stress.
        Indicates overall environmental degradation.

        Args:
            row: Feature row with vegetation and water metrics

        Returns:
            Tuple of (normalized_pollution_value 0-100, raw_proxy_metric)
        """
        mean_ndvi = row['annual_mean_ndvi']
        mean_ndwi = row['annual_mean_ndwi']
        peak_stress_ndwi = row['peak_stress_ndwi']

        # Low vegetation index = degradation signal
        vegetation_degradation = self.normalize_feature(
            0.5 - mean_ndvi,
            -0.5,
            0.5
        )

        # Water quality proxy: very low NDWI in peak stress = concern
        water_quality = self.normalize_feature(
            0.2 - peak_stress_ndwi,
            -0.2,
            0.2
        )

        # Combine: equal weight
        pollution_proxy = (vegetation_degradation * 0.5) + (water_quality * 0.5)

        return float(np.clip(pollution_proxy, 0, 100)), (mean_ndvi + mean_ndwi) / 2

    def compute_ecoscore(
        self,
        deforestation_risk: float,
        water_stress: float,
        pollution_proxy: float
    ) -> float:
        """
        Compute EcoScore (0-100).

        EcoScore = 100 - (0.40 × deforestation + 0.35 × water_stress + 0.25 × pollution)

        Args:
            deforestation_risk: Risk value 0-100
            water_stress: Risk value 0-100
            pollution_proxy: Risk value 0-100

        Returns:
            EcoScore 0-100 (higher = better)
        """
        risk_score = (
            (0.40 * deforestation_risk) +
            (0.35 * water_stress) +
            (0.25 * pollution_proxy)
        )
        ecoscore = 100 - risk_score
        return float(np.clip(ecoscore, 0, 100))

    def get_status(self, ecoscore: float) -> str:
        """
        Get compliance status based on EcoScore.

        Args:
            ecoscore: Score 0-100

        Returns:
            Status: COMPLIANT, REVIEW, or CRITICAL
        """
        if ecoscore >= 70:
            return "COMPLIANT"
        elif ecoscore >= 40:
            return "REVIEW"
        else:
            return "CRITICAL"

    def process_zones(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """
        Compute EcoScores for all zones.

        Args:
            df: DataFrame with features

        Returns:
            Dict mapping zone name to score details
        """
        scores = {}

        for _, row in df.iterrows():
            zone = row['zone']

            # Compute risk components
            deforestation, deforest_raw = self.compute_deforestation_risk(row)
            water_stress, water_raw = self.compute_water_stress(row)
            pollution, pollution_raw = self.compute_pollution_proxy(row)

            # Compute overall score
            ecoscore = self.compute_ecoscore(deforestation, water_stress, pollution)
            status = self.get_status(ecoscore)

            scores[zone] = {
                'zone': zone,
                'ecoscore': round(ecoscore, 2),
                'status': status,
                'deforestation_risk': round(deforestation, 2),
                'water_stress': round(water_stress, 2),
                'pollution_proxy': round(pollution, 2),
                'ndvi': round(row['annual_mean_ndvi'], 4),
                'ndwi': round(row['annual_mean_ndwi'], 4),
                'ndvi_trend': round(row['ndvi_trend_slope'], 6)
            }

        self.zone_scores = scores
        return scores

    def generate_suppliers(self, zone_scores: Dict) -> List[Dict]:
        """
        Generate supplier list with 25 monitored and 15 marketplace suppliers.

        Uses zone scores as base values with realistic variations.

        Args:
            zone_scores: Dict of zone scores

        Returns:
            List of supplier records
        """
        suppliers = []

        # Define supplier names and their associated zones
        monitored_suppliers = [
            ('Indus Delta Textiles', 'pakistan'),
            ('Sindh Agricultural Co.', 'pakistan'),
            ('Punjab Cotton Mills', 'pakistan'),
            ('Karachi Export Group', 'pakistan'),
            ('Pakistan Fabrics Ltd', 'pakistan'),
            ('Yangtze River Mills', 'china'),
            ('Zhejiang Textile Co.', 'china'),
            ('Jiangsu Green Fabrics', 'china'),
            ('Shanghai Processing', 'china'),
            ('Wuhan Dye Works', 'china'),
            ('Dhaka Garment Hub', 'bangladesh'),
            ('Bangladesh Cotton Ind.', 'bangladesh'),
            ('Chittagong Export Mills', 'bangladesh'),
            ('Rajshahi Fabrics', 'bangladesh'),
            ('Narayanganj Spinners', 'bangladesh'),
            ('Delta Farming Pakistan', 'pakistan'),
            ('Ganges Agricultural', 'bangladesh'),
            ('Yangtze Valley Farms', 'china'),
            ('Pakistan Rice Mills', 'pakistan'),
            ('Bangladesh Sugar Corp', 'bangladesh'),
            ('Central China Grain', 'china'),
            ('Indus Fisheries Co.', 'pakistan'),
            ('Ganges Fisheries Ltd', 'bangladesh'),
            ('Yangtze Aquaculture', 'china'),
            ('Pakistan Leather Works', 'pakistan'),
        ]

        marketplace_suppliers = [
            ('Eco Traders Asia', 'bangladesh'),
            ('Green Supply Net', 'pakistan'),
            ('Sustainable Import Co.', 'china'),
            ('Fair Trade Group', 'bangladesh'),
            ('EcoLogistics Ltd', 'pakistan'),
            ('Clean Sourcing Hub', 'china'),
            ('Responsible Retailers', 'bangladesh'),
            ('Ethical Trading Co.', 'pakistan'),
            ('Green Products LLC', 'china'),
            ('Sustainability Partners', 'bangladesh'),
            ('Organic Sourcing', 'pakistan'),
            ('Carbon Neutral Trade', 'china'),
            ('Water Efficient Farms', 'bangladesh'),
            ('Zero Waste Producers', 'pakistan'),
            ('Climate Smart Supply', 'china'),
        ]

        # Generate monitored suppliers
        np.random.seed(42)  # Reproducible
        for i, (name, zone) in enumerate(monitored_suppliers):
            base_score = zone_scores[zone]['ecoscore']
            # Add variation (-10 to +5 points) - monitored are typically lower
            variation = np.random.uniform(-10, 5)
            ecoscore = float(np.clip(base_score + variation, 0, 100))

            suppliers.append({
                'id': f'MON-{i+1:03d}',
                'name': name,
                'zone': zone,
                'type': 'monitored',
                'ecoscore': round(ecoscore, 2),
                'status': self.get_status(ecoscore),
                'audit_frequency': 'quarterly' if ecoscore < 60 else 'annual'
            })

        # Generate marketplace suppliers
        for i, (name, zone) in enumerate(marketplace_suppliers):
            base_score = zone_scores[zone]['ecoscore']
            # Add variation (-5 to +10 points) - marketplace typically higher
            variation = np.random.uniform(-5, 10)
            ecoscore = float(np.clip(base_score + variation, 0, 100))

            suppliers.append({
                'id': f'MKT-{i+1:03d}',
                'name': name,
                'zone': zone,
                'type': 'marketplace',
                'ecoscore': round(ecoscore, 2),
                'status': self.get_status(ecoscore),
                'audit_frequency': 'biennial' if ecoscore > 70 else 'annual'
            })

        return suppliers

    def save_results(self, suppliers: List[Dict], output_path: str) -> None:
        """
        Save results to JSON file.

        Args:
            suppliers: List of supplier records
            output_path: Path to output JSON
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        results = {
            'metadata': {
                'version': '1.0',
                'description': 'EcoScore sustainability assessments for suppliers',
                'total_suppliers': len(suppliers),
                'monitored_count': sum(1 for s in suppliers if s['type'] == 'monitored'),
                'marketplace_count': sum(1 for s in suppliers if s['type'] == 'marketplace'),
                'zones': list(self.zone_scores.keys())
            },
            'zone_scores': self.zone_scores,
            'suppliers': suppliers
        }

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"Results saved to {output_path}")

    def print_summary(self) -> None:
        """Print EcoScore summary table."""
        print("\n" + "="*100)
        print("ECOSCORE ASSESSMENT RESULTS")
        print("="*100)
        print(f"{'Zone':<15} {'EcoScore':<12} {'Status':<12} {'Deforest':<12} {'Water Stress':<14} {'Pollution':<12}")
        print("-"*100)

        for zone, details in self.zone_scores.items():
            print(
                f"{zone:<15} {details['ecoscore']:<12.2f} {details['status']:<12} "
                f"{details['deforestation_risk']:<12.2f} {details['water_stress']:<14.2f} "
                f"{details['pollution_proxy']:<12.2f}"
            )

        print("="*100 + "\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Compute EcoScore sustainability ratings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
USAGE:
  python -m src.models.ecoscore
  python -m src.models.ecoscore --input data/processed/features_water_stress.csv --output results/scores.json

OUTPUT:
  File: results/scores.json
  Contains:
    - Zone-level EcoScores
    - 25 monitored suppliers
    - 15 marketplace suppliers
    - Risk component breakdown

SCORING:
  EcoScore = 100 - (0.40 × deforestation + 0.35 × water_stress + 0.25 × pollution)

  Status:
    - COMPLIANT (>= 70): Passes all requirements
    - REVIEW (40-69): Needs improvement
    - CRITICAL (< 40): Immediate intervention needed
        """
    )
    parser.add_argument(
        "--input",
        default="data/processed/features_water_stress.csv",
        help="Input features CSV"
    )
    parser.add_argument(
        "--output",
        default="results/scores.json",
        help="Output results JSON"
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(message)s')

    print("\n" + "="*100)
    print("ECOSCORE MODEL")
    print("="*100 + "\n")

    try:
        scorer = EcoScorer()

        # Step 1: Read features
        print("[*] Loading features...")
        df = scorer.read_features(args.input)

        # Step 2: Compute zone scores
        print("[*] Computing EcoScores...\n")
        zone_scores = scorer.process_zones(df)

        # Step 3: Generate suppliers
        print("[*] Generating supplier list...")
        suppliers = scorer.generate_suppliers(zone_scores)
        print(f"   Created {len(suppliers)} suppliers")
        print(f"   - {sum(1 for s in suppliers if s['type'] == 'monitored')} monitored")
        print(f"   - {sum(1 for s in suppliers if s['type'] == 'marketplace')} marketplace\n")

        # Step 4: Save results
        print(f"[*] Saving results...")
        scorer.save_results(suppliers, args.output)

        # Step 5: Print summary
        scorer.print_summary()

        print(f"[SUCCESS] Results saved to {args.output}\n")

        return 0

    except Exception as e:
        logger.error(f"[!] Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
