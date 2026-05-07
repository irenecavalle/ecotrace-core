"""
EcoTrace API Entry Point - Root Level

This file serves as the main entry point for deployment platforms
that expect app.py in the project root (Railway, Heroku, etc.).

It imports the Flask application from src/api/app.py and configures it
to listen on the PORT environment variable.
"""

import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Flask app from src.api
from src.api.app import app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
