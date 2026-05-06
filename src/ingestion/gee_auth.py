"""
Google Earth Engine authentication and initialization.

Handles service account authentication using credentials from .env file.
Service account key must be at secrets/gee_key.json
"""

import os
import json
import logging
from pathlib import Path
import ee


logger = logging.getLogger(__name__)


def load_env():
    """Load environment variables from .env file if present."""
    env_file = Path('.env')
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            logger.debug("Loaded .env file")
        except ImportError:
            # dotenv not available, parse manually
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
            logger.debug("Loaded .env file (manual parsing)")


def authenticate() -> dict:
    """
    Authenticate with Google Earth Engine using service account key.

    Reads GEE_KEY_FILE environment variable and authenticates.
    Typically: secrets/gee_key.json

    Returns:
        Dictionary with service account info (email, project_id)

    Raises:
        FileNotFoundError: If key file not found
        ValueError: If GEE_KEY_FILE not set
        Exception: If authentication fails
    """
    # Load environment variables
    load_env()

    key_file = os.getenv('GEE_KEY_FILE')
    if not key_file:
        raise ValueError(
            "GEE_KEY_FILE environment variable not set. "
            "Set it in .env file or export it: export GEE_KEY_FILE=secrets/gee_key.json"
        )

    # Resolve path (relative or absolute)
    key_path = Path(key_file)
    if not key_path.is_absolute():
        key_path = Path.cwd() / key_path

    key_path = key_path.expanduser()  # Support ~ expansion

    if not key_path.exists():
        raise FileNotFoundError(
            f"GEE key file not found: {key_file}\n"
            f"Resolved to: {key_path}\n"
            f"Current directory: {Path.cwd()}"
        )

    try:
        with open(key_path) as f:
            key_json = f.read()
            key_data = json.loads(key_json)

        service_account_email = key_data.get('client_email')
        project_id = key_data.get('project_id')

        logger.info(f"[AUTH] Authenticating with service account...")
        logger.info(f"   Email: {service_account_email}")
        logger.info(f"   Project: {project_id}")

        credentials = ee.ServiceAccountCredentials(
            email=service_account_email,
            key_data=key_json
        )
        ee.Initialize(credentials)

        logger.info(f"[OK] Earth Engine authentication successful")

        return {
            'email': service_account_email,
            'project_id': project_id
        }

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in key file {key_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"GEE authentication failed: {e}")
        raise


def initialize() -> None:
    """Initialize Earth Engine connection."""
    try:
        # Test if already initialized by accessing a dataset
        collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').first()
        if collection is not None:
            logger.debug("Earth Engine already initialized")
            return
    except Exception:
        pass

    # Authenticate if not initialized
    authenticate()


def test_connection() -> bool:
    """
    Test Earth Engine connection with real Sentinel-2 data.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        logger.info("[TEST] Testing Earth Engine connection...")

        # Test with Sentinel-2 collection
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterDate('2023-01-01', '2023-01-31') \
            .limit(1)

        count = s2.size().getInfo()
        logger.info(f"[OK] Connection successful (found {count} S2 images for Jan 2023)")
        return True

    except Exception as e:
        logger.error(f"[ERR] Connection test failed: {e}")
        return False


def get_service_account_info() -> dict:
    """Get service account information from credentials."""
    load_env()
    key_file = os.getenv('GEE_KEY_FILE')

    if not key_file:
        return {}

    try:
        key_path = Path(key_file)
        if not key_path.is_absolute():
            key_path = Path.cwd() / key_path

        with open(key_path.expanduser()) as f:
            key_data = json.load(f)

        return {
            'email': key_data.get('client_email'),
            'project_id': key_data.get('project_id')
        }
    except Exception:
        return {}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    logger.info("="*70)
    logger.info("Earth Engine Authentication Test")
    logger.info("="*70)

    try:
        info = authenticate()
        logger.info("\nService Account Info:")
        logger.info(f"  Email: {info['email']}")
        logger.info(f"  Project: {info['project_id']}")

        if test_connection():
            logger.info("\n[OK] All systems operational!")
        else:
            logger.error("\n[ERR] Connection test failed")

    except Exception as e:
        logger.error(f"\n[ERR] Authentication failed: {e}")
        exit(1)
