"""
EcoScore Sustainability API

Complete Flask API for supplier sustainability monitoring and reporting.
Provides real-time access to satellite-derived EcoScores and environmental metrics.
Loads data from results/scores.json on startup.
"""

import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any

from flask import Flask, jsonify, request
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Global data storage
SCORES_DATA = {}
SUPPLIERS_MAP = {}
ZONES_MAP = {}

# Load data on app startup (before any requests)
def _load_on_startup():
    """Load scores data when app starts."""
    global SCORES_DATA, SUPPLIERS_MAP, ZONES_MAP
    try:
        scores_path = os.path.join(os.path.dirname(__file__), '../../results/scores.json')
        scores_path = os.path.abspath(scores_path)

        print(f"\n[*] Loading scores from: {scores_path}")

        if not os.path.exists(scores_path):
            print(f"[ERROR] File not found: {scores_path}")
            return False

        with open(scores_path, 'r') as f:
            SCORES_DATA = json.load(f)

        SUPPLIERS_MAP = {s['id']: s for s in SCORES_DATA.get('suppliers', [])}
        ZONES_MAP = SCORES_DATA.get('zone_scores', {})

        print(f"[OK] Loaded {len(SUPPLIERS_MAP)} suppliers")
        print(f"[OK] Loaded {len(ZONES_MAP)} zones\n")

        logger.info(f"Loaded {len(SUPPLIERS_MAP)} suppliers from {scores_path}")
        logger.info(f"Loaded {len(ZONES_MAP)} zones")

        return True
    except Exception as e:
        logger.error(f"Failed to load scores data: {e}")
        print(f"[ERROR] Failed to load scores data: {e}")
        return False

# Load data immediately
_load_on_startup()


def load_scores_data():
    """Load scores.json on application startup."""
    global SCORES_DATA, SUPPLIERS_MAP, ZONES_MAP

    try:
        # Use absolute path relative to project root
        scores_path = os.path.join(os.path.dirname(__file__), '../../results/scores.json')
        scores_path = os.path.abspath(scores_path)

        print(f"\n[*] Loading scores from: {scores_path}")

        if not os.path.exists(scores_path):
            print(f"[ERROR] File not found: {scores_path}")
            print(f"[DEBUG] Current __file__: {__file__}")
            print(f"[DEBUG] Directory exists: {os.path.exists(os.path.dirname(scores_path))}")
            return False

        with open(scores_path, 'r') as f:
            SCORES_DATA = json.load(f)

        SUPPLIERS_MAP = {s['id']: s for s in SCORES_DATA.get('suppliers', [])}
        ZONES_MAP = SCORES_DATA.get('zone_scores', {})

        print(f"[OK] Loaded {len(SUPPLIERS_MAP)} suppliers")
        print(f"[OK] Loaded {len(ZONES_MAP)} zones")

        logger.info(f"Loaded {len(SUPPLIERS_MAP)} suppliers from {scores_path}")
        logger.info(f"Loaded {len(ZONES_MAP)} zones")

        return True
    except Exception as e:
        logger.error(f"Failed to load scores data: {e}")
        print(f"[ERROR] Failed to load scores data: {e}")
        return False


@app.before_request
def before_request():
    """Add request metadata."""
    request.start_time = datetime.utcnow()


@app.after_request
def after_request(response):
    """Add response headers."""
    response.headers['Content-Type'] = 'application/json'
    response.headers['API-Version'] = '1.0'
    return response


# ============================================================================
# Health & Metadata Endpoints
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'EcoScore API',
        'version': '1.0',
        'timestamp': datetime.utcnow().isoformat(),
        'suppliers_loaded': len(SUPPLIERS_MAP),
        'zones_loaded': len(ZONES_MAP)
    }), 200


@app.route('/api/v1/metadata', methods=['GET'])
def metadata():
    """Get API metadata and available resources."""
    return jsonify({
        'api': 'EcoScore Sustainability API',
        'version': '1.0',
        'description': 'Real-time supplier sustainability monitoring based on Sentinel-2 satellite data',
        'data_source': 'Sentinel-2 L2A with NDVI/NDWI indices',
        'update_frequency': 'Monthly',
        'zones': list(ZONES_MAP.keys()),
        'total_suppliers': len(SUPPLIERS_MAP),
        'monitored_suppliers': len([s for s in SUPPLIERS_MAP.values() if s['type'] == 'monitored']),
        'marketplace_suppliers': len([s for s in SUPPLIERS_MAP.values() if s['type'] == 'marketplace']),
        'endpoints': {
            'suppliers': '/api/v1/suppliers',
            'supplier_detail': '/api/v1/suppliers/<id>',
            'supplier_score': '/api/v1/suppliers/<id>/score',
            'marketplace': '/api/v1/marketplace',
            'alerts': '/api/v1/alerts',
            'export_csrd': '/api/v1/export/csrd'
        }
    }), 200


# ============================================================================
# Monitored Suppliers Endpoints
# ============================================================================

@app.route('/api/v1/suppliers', methods=['GET'])
def get_suppliers():
    """Get all monitored suppliers."""
    try:
        monitored = [s for s in SUPPLIERS_MAP.values() if s['type'] == 'monitored']

        return jsonify({
            'count': len(monitored),
            'suppliers': monitored,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Error retrieving suppliers: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/suppliers/<supplier_id>', methods=['GET'])
def get_supplier(supplier_id):
    """Get single supplier full detail by ID."""
    try:
        supplier = SUPPLIERS_MAP.get(supplier_id)

        if not supplier:
            return jsonify({
                'error': f'Supplier {supplier_id} not found',
                'available_ids': list(SUPPLIERS_MAP.keys())[:10]
            }), 404

        zone_data = ZONES_MAP.get(supplier['zone'], {})

        return jsonify({
            'supplier': supplier,
            'zone': {
                'name': supplier['zone'],
                'ecoscore': zone_data.get('ecoscore'),
                'status': zone_data.get('status'),
                'ndvi': zone_data.get('ndvi'),
                'ndwi': zone_data.get('ndwi')
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Error retrieving supplier {supplier_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/suppliers/<supplier_id>/score', methods=['GET'])
def get_supplier_score(supplier_id):
    """Get supplier EcoScore and risk components."""
    try:
        supplier = SUPPLIERS_MAP.get(supplier_id)

        if not supplier:
            return jsonify({'error': f'Supplier {supplier_id} not found'}), 404

        zone_data = ZONES_MAP.get(supplier['zone'], {})

        return jsonify({
            'supplier_id': supplier_id,
            'name': supplier['name'],
            'ecoscore': supplier.get('ecoscore'),
            'status': supplier.get('status'),
            'deforestation_risk': zone_data.get('deforestation_risk'),
            'water_stress': zone_data.get('water_stress'),
            'pollution_proxy': zone_data.get('pollution_proxy'),
            'confidence': 0.85,
            'eo_date': '2024-05-06',
            'ndvi_trend': zone_data.get('ndvi_trend'),
            'audit_frequency': supplier.get('audit_frequency'),
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Error retrieving score for {supplier_id}: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Marketplace Suppliers Endpoints
# ============================================================================

@app.route('/api/v1/marketplace', methods=['GET'])
def get_marketplace():
    """Get marketplace suppliers with optional filtering."""
    try:
        marketplace = [s for s in SUPPLIERS_MAP.values() if s['type'] == 'marketplace']

        min_score = request.args.get('min_score', type=float)
        zone = request.args.get('zone', type=str)

        if min_score is not None:
            marketplace = [s for s in marketplace if s.get('ecoscore', 0) >= min_score]

        if zone:
            marketplace = [s for s in marketplace if s.get('zone') == zone.lower()]

        return jsonify({
            'count': len(marketplace),
            'filters': {
                'min_score': min_score,
                'zone': zone
            },
            'suppliers': marketplace,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Error retrieving marketplace suppliers: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Alerts & Monitoring Endpoints
# ============================================================================

@app.route('/api/v1/alerts', methods=['GET'])
def get_alerts():
    """Get all critical status suppliers as alerts."""
    try:
        critical_suppliers = [s for s in SUPPLIERS_MAP.values() if s.get('status') == 'CRITICAL']

        alerts = []
        for supplier in critical_suppliers:
            zone_data = ZONES_MAP.get(supplier['zone'], {})

            deforest_risk = zone_data.get('deforestation_risk', 0)
            water_stress = zone_data.get('water_stress', 0)
            pollution = zone_data.get('pollution_proxy', 0)

            risks = {
                'deforestation': deforest_risk,
                'water_stress': water_stress,
                'pollution': pollution
            }

            alert_type = max(risks, key=risks.get)
            alert_descriptions = {
                'deforestation': f'Vegetation loss detected (trend: {zone_data.get("ndvi_trend", 0):.4f})',
                'water_stress': f'Critical water stress: NDWI = {zone_data.get("ndwi", 0):.4f}',
                'pollution': f'Environmental degradation detected in {supplier["zone"]} region'
            }

            alerts.append({
                'supplier_id': supplier['id'],
                'name': supplier['name'],
                'zone': supplier['zone'],
                'alert_type': alert_type,
                'description': alert_descriptions.get(alert_type, 'Sustainability alert'),
                'severity': 'CRITICAL',
                'ecoscore': supplier.get('ecoscore'),
                'risk_level': risks[alert_type],
                'recommended_action': 'Immediate audit required',
                'date': datetime.utcnow().isoformat()
            })

        return jsonify({
            'count': len(alerts),
            'alerts': alerts,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Error retrieving alerts: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Export & Compliance Endpoints
# ============================================================================

@app.route('/api/v1/export/csrd', methods=['GET'])
def export_csrd():
    """Export all monitored suppliers in ESRS E2/E3/E4 format."""
    try:
        monitored = [s for s in SUPPLIERS_MAP.values() if s['type'] == 'monitored']

        suppliers_by_zone = {}
        for supplier in monitored:
            zone = supplier['zone']
            if zone not in suppliers_by_zone:
                suppliers_by_zone[zone] = []
            suppliers_by_zone[zone].append(supplier)

        esrs_data = {
            'metadata': {
                'report_date': datetime.utcnow().isoformat(),
                'reporting_standard': 'ESRS E2/E3/E4',
                'data_source': 'Sentinel-2 Satellite Data',
                'scope': 'Monitored suppliers across 3 zones',
                'total_suppliers': len(monitored)
            },
            'esrs_e2_pollution': {
                'title': 'Pollution Disclosure',
                'kpis': [
                    {
                        'name': 'Average Pollution Proxy Score',
                        'value': sum(
                            ZONES_MAP[z].get('pollution_proxy', 0)
                            for z in suppliers_by_zone.keys()
                        ) / len(suppliers_by_zone) if suppliers_by_zone else 0,
                        'scale': '0-100 (lower is better)',
                        'description': 'Environmental degradation indicator from satellite data'
                    }
                ],
                'suppliers': {zone: len(sups) for zone, sups in suppliers_by_zone.items()}
            },
            'esrs_e3_water': {
                'title': 'Water & Marine Resources Disclosure',
                'kpis': [
                    {
                        'name': 'Average Water Stress Index',
                        'value': sum(
                            ZONES_MAP[z].get('water_stress', 0)
                            for z in suppliers_by_zone.keys()
                        ) / len(suppliers_by_zone) if suppliers_by_zone else 0,
                        'scale': '0-100 (lower is better)',
                        'description': 'NDWI-based water availability assessment'
                    }
                ],
                'critical_suppliers': len([s for s in monitored if s.get('status') == 'CRITICAL'])
            },
            'esrs_e4_biodiversity': {
                'title': 'Biodiversity & Ecosystems Disclosure',
                'kpis': [
                    {
                        'name': 'Average Vegetation Index (NDVI)',
                        'value': sum(
                            ZONES_MAP[z].get('ndvi', 0)
                            for z in suppliers_by_zone.keys()
                        ) / len(suppliers_by_zone) if suppliers_by_zone else 0,
                        'scale': '-1 to 1 (higher indicates healthier vegetation)',
                        'description': 'Normalized Difference Vegetation Index'
                    },
                    {
                        'name': 'Deforestation Risk',
                        'value': sum(
                            ZONES_MAP[z].get('deforestation_risk', 0)
                            for z in suppliers_by_zone.keys()
                        ) / len(suppliers_by_zone) if suppliers_by_zone else 0,
                        'scale': '0-100 (lower is better)',
                        'description': 'Vegetation loss trend analysis'
                    }
                ],
                'suppliers_by_status': {
                    'compliant': len([s for s in monitored if s.get('status') == 'COMPLIANT']),
                    'review': len([s for s in monitored if s.get('status') == 'REVIEW']),
                    'critical': len([s for s in monitored if s.get('status') == 'CRITICAL'])
                }
            },
            'detailed_supplier_data': [
                {
                    'supplier_id': s['id'],
                    'name': s['name'],
                    'zone': s['zone'],
                    'ecoscore': s.get('ecoscore'),
                    'status': s.get('status'),
                    'audit_frequency': s.get('audit_frequency'),
                    'zone_metrics': {
                        'ndvi': ZONES_MAP[s['zone']].get('ndvi'),
                        'ndwi': ZONES_MAP[s['zone']].get('ndwi'),
                        'deforestation_risk': ZONES_MAP[s['zone']].get('deforestation_risk'),
                        'water_stress': ZONES_MAP[s['zone']].get('water_stress'),
                        'pollution_proxy': ZONES_MAP[s['zone']].get('pollution_proxy')
                    }
                }
                for s in monitored
            ]
        }

        return jsonify(esrs_data), 200
    except Exception as e:
        logger.error(f"Error exporting CSRD data: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'error': 'Endpoint not found',
        'message': 'Check /api/v1/metadata for available endpoints'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# Application Entry Point
# ============================================================================

def main():
    """Initialize and run the Flask application."""
    print("\n" + "="*80)
    print("EcoScore Sustainability API")
    print("="*80 + "\n")

    if not load_scores_data():
        print("[ERROR] Failed to load scores data. Exiting.")
        return 1

    print(f"[OK] Loaded {len(SUPPLIERS_MAP)} suppliers")
    print(f"[OK] Loaded {len(ZONES_MAP)} zones")
    print("\n[INFO] Starting Flask server...")
    print("[INFO] API Documentation: http://localhost:5000/api/v1/metadata")
    print("[INFO] Health Check: http://localhost:5000/health")
    print("\n" + "="*80 + "\n")

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False
    )


if __name__ == '__main__':
    exit(main())
