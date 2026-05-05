"""
Alert endpoints.

GET /api/v1/alerts - Get active risk alerts from supplier scores
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import logging


logger = logging.getLogger(__name__)


def create_alerts_bp(data_manager):
    """
    Factory function to create alerts blueprint with data manager.

    Args:
        data_manager: DataManager instance

    Returns:
        Configured Blueprint
    """
    alerts_bp = Blueprint('alerts', __name__, url_prefix='/api/v1')

    @alerts_bp.route('/alerts', methods=['GET'])
    def get_alerts():
        """
        Get active risk alerts.

        Generates alerts from suppliers with low EcoScores.

        Query parameters:
        - severity: Filter by severity (CRITICAL, WARNING, INFO)
        - limit: Max results (default 20)

        Returns:
            List of alerts sorted by severity
        """
        severity = request.args.get('severity', default=None, type=str)
        limit = request.args.get('limit', default=20, type=int)

        # Generate alerts from suppliers
        all_alerts = data_manager.generate_alerts()

        # Filter by severity
        if severity:
            all_alerts = [a for a in all_alerts if a['severity'] == severity]

        # Limit results
        alerts = all_alerts[:limit]

        # Compute statistics
        critical_count = sum(1 for a in all_alerts if a['severity'] == 'CRITICAL')
        warning_count = sum(1 for a in all_alerts if a['severity'] == 'WARNING')

        return jsonify({
            'data': alerts,
            'statistics': {
                'total': len(all_alerts),
                'active_count': len(all_alerts),
                'critical_count': critical_count,
                'warning_count': warning_count
            },
            'pagination': {
                'limit': limit,
                'returned': len(alerts),
                'has_more': len(alerts) < len(all_alerts)
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    return alerts_bp
