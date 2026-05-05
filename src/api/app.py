"""
EcoTrace Flask REST API.

Exposes EcoScore data from inference pipeline for dashboard and external integrations.
Reads data from results/scores.json and data/suppliers/suppliers_sample.csv.
"""

import logging
import json
import csv
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from flask import Flask, jsonify, request, g
from flask_cors import CORS


logger = logging.getLogger(__name__)


class DataManager:
    """Manages data loading from results/scores.json and supplier metadata."""

    def __init__(self, scores_file: str = "results/scores.json", suppliers_file: str = "data/suppliers/suppliers_sample.csv"):
        """
        Initialize DataManager.

        Args:
            scores_file: Path to inference results JSON
            suppliers_file: Path to suppliers CSV metadata
        """
        self.scores_file = Path(scores_file)
        self.suppliers_file = Path(suppliers_file)
        self._scores_cache = None
        self._suppliers_cache = None
        self._load_timestamp = None

    def load_scores(self, force_reload: bool = False) -> Dict:
        """
        Load EcoScores from results/scores.json.

        Args:
            force_reload: Force reload even if cached

        Returns:
            Dictionary mapping supplier_id -> scores
        """
        if self._scores_cache is not None and not force_reload:
            return self._scores_cache

        if not self.scores_file.exists():
            logger.warning(f"Scores file not found: {self.scores_file}")
            return {}

        try:
            with open(self.scores_file, 'r') as f:
                self._scores_cache = json.load(f)
            self._load_timestamp = datetime.utcnow().isoformat()
            logger.info(f"Loaded {len(self._scores_cache)} supplier scores")
            return self._scores_cache
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing scores JSON: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error loading scores: {e}")
            return {}

    def load_suppliers(self, force_reload: bool = False) -> Dict:
        """
        Load supplier metadata from CSV.

        Args:
            force_reload: Force reload even if cached

        Returns:
            Dictionary mapping supplier_id -> metadata
        """
        if self._suppliers_cache is not None and not force_reload:
            return self._suppliers_cache

        if not self.suppliers_file.exists():
            logger.warning(f"Suppliers file not found: {self.suppliers_file}")
            return {}

        try:
            self._suppliers_cache = {}
            with open(self.suppliers_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    supplier_id = row['supplier_id']
                    self._suppliers_cache[supplier_id] = {
                        'supplier_id': supplier_id,
                        'name': row['name'],
                        'country': row['country'],
                        'latitude': float(row['latitude']),
                        'longitude': float(row['longitude']),
                        'category': row['category']
                    }
            logger.info(f"Loaded {len(self._suppliers_cache)} supplier metadata")
            return self._suppliers_cache
        except Exception as e:
            logger.error(f"Error loading suppliers: {e}")
            return {}

    def get_supplier_full(self, supplier_id: str) -> Optional[Dict]:
        """
        Get complete supplier data (metadata + scores).

        Args:
            supplier_id: Supplier identifier

        Returns:
            Combined supplier dictionary or None if not found
        """
        suppliers = self.load_suppliers()
        scores = self.load_scores()

        if supplier_id not in suppliers or supplier_id not in scores:
            return None

        supplier = suppliers[supplier_id].copy()
        supplier.update(scores[supplier_id])
        supplier['eo_date'] = self._load_timestamp or scores[supplier_id].get('updated', '')
        supplier['satellite'] = 'Sentinel-2 L2A'
        supplier['confidence'] = 0.91  # Default confidence from README

        return supplier

    def get_all_suppliers(self) -> List[Dict]:
        """Get all suppliers with scores."""
        suppliers = self.load_suppliers()
        scores = self.load_scores()

        all_suppliers = []
        for supplier_id, metadata in suppliers.items():
            if supplier_id in scores:
                supplier = metadata.copy()
                supplier.update(scores[supplier_id])
                all_suppliers.append(supplier)

        return all_suppliers

    def filter_suppliers(
        self,
        suppliers: List[Dict],
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict], int]:
        """
        Filter and paginate suppliers.

        Args:
            suppliers: List of supplier dictionaries
            status: Filter by status (COMPLIANT, REVIEW, CRITICAL)
            limit: Results per page
            offset: Pagination offset

        Returns:
            Tuple of (filtered_suppliers, total_count)
        """
        # Filter by status
        if status:
            suppliers = [s for s in suppliers if s.get('status') == status]

        total = len(suppliers)

        # Paginate
        suppliers = suppliers[offset:offset + limit]

        return suppliers, total

    def generate_alerts(self) -> List[Dict]:
        """
        Generate alerts from low-scoring suppliers.

        Returns:
            List of alert dictionaries
        """
        suppliers = self.get_all_suppliers()
        alerts = []
        alert_id_counter = 1

        for supplier in suppliers:
            ecoscore = supplier.get('ecoscore', 50)
            status = supplier.get('status', 'UNKNOWN')

            if status == 'CRITICAL':
                if supplier.get('deforestation_risk', 0) > 30:
                    alerts.append({
                        'alert_id': f'ALT{alert_id_counter:03d}',
                        'supplier_id': supplier['supplier_id'],
                        'supplier_name': supplier['name'],
                        'severity': 'CRITICAL',
                        'title': 'Critical deforestation risk detected',
                        'message': f"Deforestation risk score: {supplier.get('deforestation_risk', 0)}/100",
                        'created': datetime.utcnow().isoformat(),
                        'resolved': False
                    })
                    alert_id_counter += 1

                if supplier.get('water_stress', 0) > 30:
                    alerts.append({
                        'alert_id': f'ALT{alert_id_counter:03d}',
                        'supplier_id': supplier['supplier_id'],
                        'supplier_name': supplier['name'],
                        'severity': 'CRITICAL',
                        'title': 'Critical water stress detected',
                        'message': f"Water stress score: {supplier.get('water_stress', 0)}/100",
                        'created': datetime.utcnow().isoformat(),
                        'resolved': False
                    })
                    alert_id_counter += 1

            elif status == 'REVIEW':
                alerts.append({
                    'alert_id': f'ALT{alert_id_counter:03d}',
                    'supplier_id': supplier['supplier_id'],
                    'supplier_name': supplier['name'],
                    'severity': 'WARNING',
                    'title': 'Review required',
                    'message': f"EcoScore {ecoscore}/100 - Environmental risks require review",
                    'created': datetime.utcnow().isoformat(),
                    'resolved': False
                })
                alert_id_counter += 1

        return alerts

    def get_csrd_export(self) -> Dict:
        """
        Generate CSRD-compliant export.

        Returns:
            CSRD-formatted export dictionary
        """
        suppliers = self.get_all_suppliers()

        # Compute summary statistics
        compliant = sum(1 for s in suppliers if s.get('status') == 'COMPLIANT')
        review = sum(1 for s in suppliers if s.get('status') == 'REVIEW')
        critical = sum(1 for s in suppliers if s.get('status') == 'CRITICAL')

        csrd_suppliers = []
        for supplier in suppliers:
            csrd_suppliers.append({
                'supplier_id': supplier['supplier_id'],
                'name': supplier['name'],
                'location': {
                    'country': supplier['country'],
                    'latitude': supplier['latitude'],
                    'longitude': supplier['longitude']
                },
                'environmental_risks': {
                    'deforestation_risk': supplier.get('deforestation_risk', 0),
                    'water_stress': supplier.get('water_stress', 0),
                    'pollution': supplier.get('pollution_proxy', 0)
                },
                'ecoscore': supplier.get('ecoscore', 0),
                'compliance_status': supplier.get('status', 'UNKNOWN'),
                'evidence': 'Satellite monitoring Jan 2019 - Dec 2024'
            })

        return {
            'export_format': 'CSRD-E2/E3/E4',
            'export_date': datetime.utcnow().isoformat(),
            'suppliers': csrd_suppliers,
            'summary': {
                'total_suppliers': len(suppliers),
                'compliant': compliant,
                'review_required': review,
                'critical_risk': critical
            }
        }


def create_app(config_name: str = "development") -> Flask:
    """
    Application factory.

    Args:
        config_name: Configuration environment (development, production)

    Returns:
        Configured Flask app
    """
    app = Flask(__name__)
    CORS(app)

    # Load config
    if config_name == "production":
        app.config['DEBUG'] = False
    else:
        app.config['DEBUG'] = True

    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['JSON_SORT_KEYS'] = False

    # Initialize data manager
    data_manager = DataManager()

    @app.before_request
    def load_data():
        """Load data into request context."""
        g.data_manager = data_manager

    # Register blueprints with data manager
    from .routes.scores import create_scores_bp
    from .routes.alerts import create_alerts_bp
    from .routes.export import create_export_bp

    app.register_blueprint(create_scores_bp(data_manager))
    app.register_blueprint(create_alerts_bp(data_manager))
    app.register_blueprint(create_export_bp(data_manager))

    # Health check
    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint with data status."""
        scores = data_manager.load_scores()
        suppliers = data_manager.load_suppliers()
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'data_status': {
                'scores_loaded': len(scores) > 0,
                'suppliers_loaded': len(suppliers) > 0,
                'total_suppliers': len(suppliers),
                'scores_available': len(scores)
            }
        }), 200

    # Root endpoint
    @app.route('/', methods=['GET'])
    def root():
        """API root with version and capabilities."""
        return jsonify({
            'name': 'EcoTrace API',
            'version': '1.0.0',
            'description': 'AI-powered sustainability traceability for fashion supply chains',
            'endpoints': {
                'suppliers': '/api/v1/suppliers',
                'supplier_detail': '/api/v1/suppliers/{id}',
                'supplier_score': '/api/v1/suppliers/{id}/score',
                'alerts': '/api/v1/alerts',
                'export_csrd': '/api/v1/export/csrd',
                'qr_page': '/api/v1/qr/{id}'
            }
        }), 200

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return jsonify({'error': 'Resource not found', 'status': 404}), 404

    @app.errorhandler(500)
    def server_error(error):
        """Handle 500 errors."""
        logger.error(f"Server error: {error}")
        return jsonify({'error': 'Internal server error', 'status': 500}), 500

    return app


if __name__ == "__main__":
    app = create_app("development")
    app.run(host="0.0.0.0", port=5000, debug=True)
