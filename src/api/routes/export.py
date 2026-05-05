"""
Export endpoints.

GET /api/v1/export/csrd - CSRD E2/E3/E4 formatted export
GET /api/v1/qr/<id> - Public QR code landing page (consumer-facing)
"""

from flask import Blueprint, jsonify
from datetime import datetime
import logging


logger = logging.getLogger(__name__)


def create_export_bp(data_manager):
    """
    Factory function to create export blueprint with data manager.

    Args:
        data_manager: DataManager instance

    Returns:
        Configured Blueprint
    """
    export_bp = Blueprint('export', __name__, url_prefix='/api/v1')

    @export_bp.route('/export/csrd', methods=['GET'])
    def export_csrd():
        """
        Export supplier data in CSRD E2/E3/E4 compliance format.

        Returns:
            CSRD-compliant JSON export with all supplier environmental data
        """
        csrd_data = data_manager.get_csrd_export()
        return jsonify(csrd_data), 200

    @export_bp.route('/qr/<supplier_id>', methods=['GET'])
    def get_qr_page(supplier_id):
        """
        Public QR code landing page (consumer-facing, no sensitive data).

        Args:
            supplier_id: Supplier identifier

        Returns:
            Public supplier information suitable for QR code scanning
        """
        supplier = data_manager.get_supplier_full(supplier_id)

        if not supplier:
            return jsonify({
                'error': f'Supplier {supplier_id} not found',
                'status': 404
            }), 404

        # Map status to emoji description for consumer visibility
        status_emoji = {
            'COMPLIANT': '✅ COMPLIANT',
            'REVIEW': '⚠️ REVIEW REQUIRED',
            'CRITICAL': '🔴 CRITICAL RISK'
        }

        status = supplier.get('status', 'UNKNOWN')
        emoji_status = status_emoji.get(status, f'ℹ️ {status}')

        # Consumer-friendly message
        if status == 'COMPLIANT':
            message = 'This supplier meets environmental compliance standards based on satellite monitoring.'
        elif status == 'REVIEW':
            message = 'This supplier has environmental factors that require attention and review.'
        elif status == 'CRITICAL':
            message = 'This supplier has significant environmental risks that require immediate action.'
        else:
            message = 'Environmental assessment data is available for this supplier.'

        return jsonify({
            'supplier_id': supplier['supplier_id'],
            'supplier_name': supplier['name'],
            'country': supplier['country'],
            'ecoscore': supplier.get('ecoscore', 0),
            'status': emoji_status,
            'message': message,
            'environmental_indicators': {
                'deforestation_risk': supplier.get('deforestation_risk', 0),
                'water_stress': supplier.get('water_stress', 0),
                'pollution_risk': supplier.get('pollution_proxy', 0)
            },
            'website_url': f'https://app.ecotrace.earth/suppliers/{supplier_id}',
            'disclaimer': 'Scores are based on independent satellite monitoring (Sentinel-2 L2A) from January 2019 to December 2024. They are not based on supplier self-reporting and represent environmental indicators detected at supplier locations.',
            'more_info': 'Visit app.ecotrace.earth for detailed analysis and full methodology documentation.'
        }), 200

    return export_bp
