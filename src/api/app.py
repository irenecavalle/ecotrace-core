"""
EcoTrace Flask REST API.

Exposes EcoScore data for dashboard consumption and external integrations.
"""

import logging
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime
import os


logger = logging.getLogger(__name__)


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

    # Register blueprints
    from .routes.scores import scores_bp
    from .routes.alerts import alerts_bp
    from .routes.export import export_bp

    app.register_blueprint(scores_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(export_bp)

    # Health check
    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat()
        }), 200

    # Root endpoint
    @app.route('/', methods=['GET'])
    def root():
        """API root."""
        return jsonify({
            "name": "EcoTrace API",
            "version": "1.0.0",
            "description": "AI-powered sustainability traceability for fashion supply chains"
        }), 200

    return app


if __name__ == "__main__":
    app = create_app("development")
    app.run(host="0.0.0.0", port=5000, debug=True)
