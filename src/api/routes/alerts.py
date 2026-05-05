"""
Alert endpoints.

GET /api/v1/alerts - Get active risk alerts
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta


alerts_bp = Blueprint('alerts', __name__, url_prefix='/api/v1')


@alerts_bp.route('/alerts', methods=['GET'])
def get_alerts():
    """
    Get active risk alerts.

    Query parameters:
    - severity: Filter by severity (CRITICAL, WARNING, INFO)
    - limit: Max results (default 20)

    Returns:
        List of recent alerts
    """
    # TODO: Query database for recent alerts
    return jsonify({
        "data": [
            {
                "alert_id": "ALT001",
                "supplier_id": "SUP001",
                "supplier_name": "Mehran Textile Mills",
                "severity": "CRITICAL",
                "title": "Critical water stress detected",
                "message": "NDWI index shows severe water stress in last 3 months",
                "created": (datetime.utcnow() - timedelta(days=2)).isoformat(),
                "resolved": False
            },
            {
                "alert_id": "ALT002",
                "supplier_id": "SUP002",
                "supplier_name": "Yangtze Fiber Co.",
                "severity": "WARNING",
                "title": "Increased deforestation risk",
                "message": "Recent satellite data shows potential vegetation loss near supplier",
                "created": (datetime.utcnow() - timedelta(days=1)).isoformat(),
                "resolved": False
            }
        ],
        "total": 2,
        "active_count": 2,
        "critical_count": 1
    }), 200
