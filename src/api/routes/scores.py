"""
Supplier score endpoints.

GET /api/v1/suppliers - List all suppliers
GET /api/v1/suppliers/<id> - Get supplier details
GET /api/v1/suppliers/<id>/score - Get supplier EcoScore
POST /api/v1/suppliers - Add new supplier
"""

from flask import Blueprint, jsonify, request
from datetime import datetime


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
        List of suppliers with scores
    """
    # TODO: Query database, return supplier list with scores
    return jsonify({
        "data": [
            {
                "supplier_id": "SUP001",
                "name": "Mehran Textile Mills",
                "country": "PK",
                "ecoscore": 28,
                "status": "CRITICAL",
                "updated": "2025-05-01"
            },
            {
                "supplier_id": "SUP002",
                "name": "Yangtze Fiber Co.",
                "country": "CN",
                "ecoscore": 65,
                "status": "REVIEW",
                "updated": "2025-05-01"
            }
        ],
        "total": 2,
        "limit": 50,
        "offset": 0
    }), 200


@scores_bp.route('/suppliers/<supplier_id>', methods=['GET'])
def get_supplier(supplier_id):
    """
    Get supplier full details.

    Returns:
        Supplier profile with all metadata
    """
    # TODO: Query database for supplier details
    return jsonify({
        "supplier_id": supplier_id,
        "name": "Mehran Textile Mills",
        "country": "PK",
        "latitude": 31.418,
        "longitude": 73.079,
        "category": "Cotton weaving",
        "ecoscore": 28,
        "sub_scores": {
            "deforestation_risk": 22,
            "water_stress": 31,
            "pollution_proxy": 35
        },
        "status": "CRITICAL",
        "confidence": 0.91,
        "eo_date": "2025-05-01",
        "satellite": "Sentinel-2 L2A"
    }), 200


@scores_bp.route('/suppliers/<supplier_id>/score', methods=['GET'])
def get_supplier_score(supplier_id):
    """
    Get supplier EcoScore only.

    Returns:
        Minimal score response
    """
    # TODO: Query score from database
    return jsonify({
        "supplier_id": supplier_id,
        "ecoscore": 28,
        "sub_scores": {
            "deforestation_risk": 22,
            "water_stress": 31,
            "pollution_proxy": 35
        },
        "status": "CRITICAL",
        "confidence": 0.91,
        "updated": "2025-05-01"
    }), 200


@scores_bp.route('/suppliers', methods=['POST'])
def create_supplier():
    """
    Add new supplier.

    Request body:
    {
        "name": "Supplier name",
        "country": "Country code",
        "latitude": 0.0,
        "longitude": 0.0,
        "category": "Industry category"
    }

    Returns:
        Created supplier with ID
    """
    # TODO: Validate input, create supplier in database, trigger scoring
    data = request.get_json()
    return jsonify({
        "supplier_id": "SUP_NEW",
        "name": data.get("name"),
        "country": data.get("country"),
        "created": datetime.utcnow().isoformat()
    }), 201
