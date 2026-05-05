"""
Supplier score endpoints.

GET /api/v1/suppliers - List all suppliers with scores
GET /api/v1/suppliers/<id> - Get supplier full details and scores
GET /api/v1/suppliers/<id>/score - Get supplier EcoScore only
POST /api/v1/suppliers - Add new supplier (not yet implemented)
"""

from flask import Blueprint, jsonify, request, g
from datetime import datetime
import logging


logger = logging.getLogger(__name__)


def create_scores_bp(data_manager):
    """
    Factory function to create scores blueprint with data manager.

    Args:
        data_manager: DataManager instance

    Returns:
        Configured Blueprint
    """
    scores_bp = Blueprint('scores', __name__, url_prefix='/api/v1')

    @scores_bp.route('/suppliers', methods=['GET'])
    def list_suppliers():
        """
        List all suppliers with current EcoScore.

        Query parameters:
        - limit: Max results (default 50)
        - offset: Pagination offset (default 0)
        - status: Filter by status (COMPLIANT, REVIEW, CRITICAL)

        Returns:
            List of suppliers with scores and pagination info
        """
        limit = request.args.get('limit', default=50, type=int)
        offset = request.args.get('offset', default=0, type=int)
        status = request.args.get('status', default=None, type=str)

        # Validate pagination
        limit = min(limit, 100)  # Max 100 per page
        offset = max(offset, 0)

        # Get all suppliers
        all_suppliers = data_manager.get_all_suppliers()

        # Filter and paginate
        filtered_suppliers, total = data_manager.filter_suppliers(
            all_suppliers,
            status=status,
            limit=limit,
            offset=offset
        )

        # Format response
        return jsonify({
            'data': filtered_suppliers,
            'pagination': {
                'total': total,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + limit) < total
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    @scores_bp.route('/suppliers/<supplier_id>', methods=['GET'])
    def get_supplier(supplier_id):
        """
        Get supplier full details including metadata and scores.

        Args:
            supplier_id: Supplier identifier (e.g., SUP001)

        Returns:
            Complete supplier information with all scores and metadata
        """
        supplier = data_manager.get_supplier_full(supplier_id)

        if not supplier:
            return jsonify({
                'error': f'Supplier {supplier_id} not found',
                'status': 404
            }), 404

        # Format sub_scores from individual components
        supplier['sub_scores'] = {
            'deforestation_risk': supplier.get('deforestation_risk', 0),
            'water_stress': supplier.get('water_stress', 0),
            'pollution_proxy': supplier.get('pollution_proxy', 0)
        }

        return jsonify(supplier), 200

    @scores_bp.route('/suppliers/<supplier_id>/score', methods=['GET'])
    def get_supplier_score(supplier_id):
        """
        Get supplier EcoScore only (minimal response).

        Args:
            supplier_id: Supplier identifier

        Returns:
            Supplier ID, EcoScore, sub-scores, and status
        """
        supplier = data_manager.get_supplier_full(supplier_id)

        if not supplier:
            return jsonify({
                'error': f'Supplier {supplier_id} not found',
                'status': 404
            }), 404

        return jsonify({
            'supplier_id': supplier['supplier_id'],
            'ecoscore': supplier.get('ecoscore', 0),
            'sub_scores': {
                'deforestation_risk': supplier.get('deforestation_risk', 0),
                'water_stress': supplier.get('water_stress', 0),
                'pollution_proxy': supplier.get('pollution_proxy', 0)
            },
            'status': supplier.get('status', 'UNKNOWN'),
            'confidence': supplier.get('confidence', 0.91),
            'updated': supplier.get('updated', '')
        }), 200

    @scores_bp.route('/suppliers', methods=['POST'])
    def create_supplier():
        """
        Add new supplier (placeholder - actual implementation requires inference pipeline).

        Request body should contain:
        {
            "name": "Supplier name",
            "country": "Country code",
            "latitude": 0.0,
            "longitude": 0.0,
            "category": "Industry category"
        }

        Returns:
            Created supplier with temporary ID (501 Not Implemented)
        """
        return jsonify({
            'error': 'Feature not yet implemented',
            'message': 'New suppliers require running the inference pipeline',
            'status': 501
        }), 501

    return scores_bp
