"""
Generate PDF Evidence Packs for supplier sustainability assessments.

Creates 3-page PDFs with:
- Cover: Supplier details and EcoScore
- Risk Breakdown: Deforestation, water stress, pollution
- Methodology: Satellite data, formula, CSRD compliance info
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white, red, orange, green
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image,
    Table, TableStyle, KeepTogether
)
from reportlab.pdfgen import canvas
from reportlab.lib import colors

logger = logging.getLogger(__name__)


class EvidencePackGenerator:
    """Generate PDF Evidence Packs for suppliers."""

    def __init__(self, scores_path: str = "results/scores.json"):
        """Initialize generator with supplier data."""
        self.scores_path = Path(scores_path)
        self.suppliers = {}
        self.zones = {}
        self.load_data()

    def load_data(self) -> None:
        """Load supplier and zone data from JSON."""
        try:
            with open(self.scores_path, 'r') as f:
                data = json.load(f)

            self.suppliers = {s['id']: s for s in data.get('suppliers', [])}
            self.zones = data.get('zone_scores', {})

            logger.info(f"Loaded {len(self.suppliers)} suppliers")
            logger.info(f"Loaded {len(self.zones)} zones")
        except Exception as e:
            logger.error(f"Failed to load scores data: {e}")
            raise

    def get_hex_color_for_score(self, score: float) -> str:
        """Get hex color for EcoScore."""
        if score >= 70:
            return "#2ECC71"  # Green
        elif score >= 40:
            return "#F39C12"  # Amber/Orange
        else:
            return "#E74C3C"  # Red

    def get_risk_explanation(self, risk_type: str, value: float) -> str:
        """Get one-line explanation for risk value."""
        if risk_type == "deforestation":
            if value < 30:
                return "Vegetation cover stable and healthy."
            elif value < 60:
                return "Moderate vegetation loss detected; monitoring recommended."
            else:
                return "Significant vegetation loss; immediate intervention needed."

        elif risk_type == "water":
            if value < 30:
                return "Water availability adequate; stress indicators low."
            elif value < 60:
                return "Moderate water stress; seasonal variation observed."
            else:
                return "Critical water scarcity; supply chain risk identified."

        elif risk_type == "pollution":
            if value < 30:
                return "Environmental quality indicators good."
            elif value < 60:
                return "Environmental degradation signals moderate; remediation advised."
            else:
                return "Severe environmental degradation; urgent action required."

        return "See detailed metrics for analysis."

    def _create_risk_section(self, title: str, value: float, risk_type: str, styles) -> List:
        """Create a single risk section with score bar and explanation."""
        elements = []

        title_style = ParagraphStyle(
            'RiskTitle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=black,
            fontName='Helvetica-Bold',
            spaceAfter=6
        )
        elements.append(Paragraph(f"{title}: {value:.1f}/100", title_style))

        # Progress bar using text-based visual
        bar_filled = int(value / 10)
        bar_empty = 10 - bar_filled
        color_hex = self.get_hex_color_for_score(100 - value)

        bar_text = (
            f"<font color='{color_hex}'>{'█' * bar_filled}</font>"
            f"<font color='#e0e0e0'>{'░' * bar_empty}</font>"
        )
        bar_style = ParagraphStyle(
            'Bar',
            parent=styles['Normal'],
            fontSize=14,
            spaceAfter=8,
            leading=14
        )
        elements.append(Paragraph(bar_text, bar_style))

        # Explanation
        explanation = self.get_risk_explanation(risk_type, value)
        explanation_style = ParagraphStyle(
            'Explanation',
            parent=styles['Normal'],
            fontSize=10,
            textColor=HexColor("#666666"),
            spaceAfter=12,
            leading=14
        )
        elements.append(Paragraph(explanation, explanation_style))

        return elements

    def _build_cover_story(self, supplier: Dict, zone_data: Dict, styles) -> List:
        """Build Page 1 cover story elements."""
        story = []

        story.append(Spacer(1, 0.5*inch))

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=HexColor("#1a1a1a"),
            spaceAfter=30,
            alignment=1
        )
        story.append(Paragraph("EcoTrace Evidence Pack", title_style))

        story.append(Spacer(1, 0.3*inch))

        name_style = ParagraphStyle(
            'SupplierName',
            parent=styles['Heading2'],
            fontSize=28,
            textColor=black,
            spaceAfter=12,
            alignment=1,
            fontName='Helvetica-Bold'
        )
        story.append(Paragraph(supplier['name'], name_style))

        meta_style = ParagraphStyle(
            'Meta',
            parent=styles['Normal'],
            fontSize=12,
            textColor=HexColor("#666666"),
            spaceAfter=30,
            alignment=1
        )
        story.append(Paragraph(
            f"{supplier['zone'].upper()} · {supplier['type'].upper()}",
            meta_style
        ))

        story.append(Spacer(1, 0.4*inch))

        ecoscore = supplier.get('ecoscore', 0)
        color_hex = self.get_hex_color_for_score(ecoscore)

        score_style = ParagraphStyle(
            'Score',
            parent=styles['Heading1'],
            fontSize=72,
            textColor=HexColor(color_hex),
            alignment=1,
            fontName='Helvetica-Bold'
        )
        story.append(Paragraph(f"{ecoscore:.1f}", score_style))

        status_style = ParagraphStyle(
            'Status',
            parent=styles['Normal'],
            fontSize=16,
            textColor=HexColor(color_hex),
            alignment=1,
            spaceAfter=40
        )
        story.append(Paragraph(supplier['status'], status_style))

        story.append(Spacer(1, 0.6*inch))

        date_style = ParagraphStyle(
            'Date',
            parent=styles['Normal'],
            fontSize=11,
            textColor=HexColor("#999999"),
            alignment=1
        )
        story.append(Paragraph("Date Generated: Q1 2024", date_style))

        story.append(Spacer(1, 0.8*inch))

        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=10,
            textColor=HexColor("#cccccc"),
            alignment=1
        )
        story.append(Paragraph(
            "Powered by Sentinel-2 · ESA Copernicus",
            footer_style
        ))

        return story

    def _build_risk_story(self, supplier: Dict, zone_data: Dict, styles) -> List:
        """Build Page 2 risk breakdown story elements."""
        story = []

        title_style = ParagraphStyle(
            'PageTitle',
            parent=styles['Heading2'],
            fontSize=18,
            textColor=black,
            spaceAfter=24,
            fontName='Helvetica-Bold'
        )
        story.append(Paragraph("Risk Assessment Breakdown", title_style))

        deforestation = zone_data.get('deforestation_risk', 0)
        water_stress = zone_data.get('water_stress', 0)
        pollution = zone_data.get('pollution_proxy', 0)

        story.extend(self._create_risk_section(
            "Deforestation Risk",
            deforestation,
            "deforestation",
            styles
        ))

        story.append(Spacer(1, 0.3*inch))

        story.extend(self._create_risk_section(
            "Water Stress",
            water_stress,
            "water",
            styles
        ))

        story.append(Spacer(1, 0.3*inch))

        story.extend(self._create_risk_section(
            "Environmental Pollution Proxy",
            pollution,
            "pollution",
            styles
        ))

        return story

    def _build_methodology_story(self, supplier: Dict, styles) -> List:
        """Build Page 3 methodology story elements."""
        story = []

        title_style = ParagraphStyle(
            'PageTitle',
            parent=styles['Heading2'],
            fontSize=18,
            textColor=black,
            spaceAfter=20,
            fontName='Helvetica-Bold'
        )
        story.append(Paragraph("Methodology &amp; Data Source", title_style))

        section_style = ParagraphStyle(
            'SectionHead',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=black,
            spaceAfter=8,
            fontName='Helvetica-Bold'
        )

        content_style = ParagraphStyle(
            'Content',
            parent=styles['Normal'],
            fontSize=10,
            textColor=HexColor("#333333"),
            spaceAfter=12,
            leading=14
        )

        story.append(Paragraph("Satellite Data", section_style))
        story.append(Paragraph(
            "Sentinel-2 L2A multispectral imagery, Q1 2024. "
            "Data processed at 100m resolution with NDVI (Normalized Difference Vegetation Index) "
            "and NDWI (Normalized Difference Water Index) computations.",
            content_style
        ))

        story.append(Spacer(1, 0.15*inch))

        story.append(Paragraph("Scoring Formula", section_style))
        formula_style = ParagraphStyle(
            'Formula',
            parent=styles['Normal'],
            fontSize=10,
            textColor=HexColor("#1a1a1a"),
            spaceAfter=12,
            leading=16,
            fontName='Courier'
        )
        story.append(Paragraph(
            "EcoScore = 100 - (0.40 × Deforestation + 0.35 × Water Stress + 0.25 × Pollution)",
            formula_style
        ))

        story.append(Spacer(1, 0.15*inch))

        story.append(Paragraph("Compliance Status", section_style))
        story.append(Paragraph(
            "<b>COMPLIANT</b> (≥70): Meets sustainability requirements<br/>"
            "<b>REVIEW</b> (40–69): Improvement recommended<br/>"
            "<b>CRITICAL</b> (&lt;40): Immediate intervention required",
            content_style
        ))

        story.append(Spacer(1, 0.2*inch))

        story.append(Paragraph("Disclaimer", section_style))
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=HexColor("#666666"),
            spaceAfter=12,
            leading=12
        )
        story.append(Paragraph(
            "This assessment covers environmental dimensions only. "
            "Does not cover labour practices, governance, or financial sustainability. "
            "For CSRD reporting, align with ESRS E2 (Pollution), E3 (Water &amp; Marine Resources), "
            "and E4 (Biodiversity &amp; Ecosystems).",
            disclaimer_style
        ))

        return story

    def generate_pdf(self, supplier_id: str, output_path: Path) -> bool:
        """
        Generate 3-page PDF for a single supplier.

        Args:
            supplier_id: Supplier ID (e.g., 'MON-001')
            output_path: Path to save PDF

        Returns:
            True if successful, False otherwise
        """
        try:
            supplier = self.suppliers.get(supplier_id)
            if not supplier:
                logger.error(f"Supplier {supplier_id} not found")
                return False

            zone_data = self.zones.get(supplier['zone'], {})

            output_path.parent.mkdir(parents=True, exist_ok=True)

            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=letter,
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=0.75*inch,
                bottomMargin=0.75*inch,
                title=f"EcoTrace Evidence Pack - {supplier['name']}"
            )

            styles = getSampleStyleSheet()
            story = []

            # Page 1: Cover
            cover_story = self._build_cover_story(supplier, zone_data, styles)
            story.extend(cover_story)
            story.append(PageBreak())

            # Page 2: Risk Breakdown
            risk_story = self._build_risk_story(supplier, zone_data, styles)
            story.extend(risk_story)
            story.append(PageBreak())

            # Page 3: Methodology
            method_story = self._build_methodology_story(supplier, styles)
            story.extend(method_story)

            doc.build(story)
            logger.info(f"Generated PDF for {supplier_id}: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to generate PDF for {supplier_id}: {e}")
            return False

    def generate_all_monitored(self) -> Dict[str, bool]:
        """
        Generate PDFs for all 25 monitored suppliers.

        Returns:
            Dict mapping supplier_id to success status
        """
        results = {}
        output_dir = Path("results/evidence_packs")
        output_dir.mkdir(parents=True, exist_ok=True)

        monitored = [s for s in self.suppliers.values() if s['type'] == 'monitored']
        logger.info(f"Generating PDFs for {len(monitored)} monitored suppliers...")

        for supplier in monitored:
            supplier_id = supplier['id']
            output_path = output_dir / f"{supplier_id}.pdf"
            success = self.generate_pdf(supplier_id, output_path)
            results[supplier_id] = success

        return results


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate PDF Evidence Packs for suppliers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
USAGE:
  python -m src.inference.evidence_pack
  python -m src.inference.evidence_pack --input results/scores.json --output results/evidence_packs

OUTPUT:
  Files: results/evidence_packs/{supplier_id}.pdf
  One 3-page PDF per monitored supplier (25 total)

PAGES:
  1. Cover: EcoScore, supplier name, status
  2. Risk Breakdown: Deforestation, water stress, pollution
  3. Methodology: Sentinel-2 data, formula, CSRD alignment
        """
    )
    parser.add_argument(
        "--input",
        default="results/scores.json",
        help="Input scores JSON"
    )
    parser.add_argument(
        "--output",
        default="results/evidence_packs",
        help="Output directory for PDFs"
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(message)s')

    print("\n" + "="*80)
    print("PDF EVIDENCE PACK GENERATOR")
    print("="*80 + "\n")

    try:
        generator = EvidencePackGenerator(args.input)

        print(f"[*] Generating Evidence Packs...")
        results = generator.generate_all_monitored()

        successful = sum(1 for v in results.values() if v)
        failed = sum(1 for v in results.values() if not v)

        print(f"\n[SUCCESS] Generated {successful} PDFs")
        if failed > 0:
            print(f"[WARNING] Failed to generate {failed} PDFs")

        output_dir = Path(args.output)
        pdf_files = list(output_dir.glob("*.pdf"))
        print(f"\n[OK] {len(pdf_files)} PDF files in {output_dir}")
        for pdf_file in sorted(pdf_files)[:5]:
            size_kb = pdf_file.stat().st_size / 1024
            print(f"     - {pdf_file.name} ({size_kb:.1f} KB)")
        if len(pdf_files) > 5:
            print(f"     ... and {len(pdf_files) - 5} more")

        print("\n" + "="*80 + "\n")

        return 0 if successful == len(results) else 1

    except Exception as e:
        logger.error(f"[!] Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
