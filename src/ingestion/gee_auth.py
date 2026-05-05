"""
Google Earth Engine authentication and initialization.

Handles service account authentication and GEE initialization.
"""

import os
import json
import logging
import ee


logger = logging.getLogger(__name__)


def authenticate() -> None:
    """
    Authenticate with Google Earth Engine using service account key.

    Reads GEE_KEY_FILE environment variable and authenticates.
    Raises:
        FileNotFoundError: If key file not found
        Exception: If authentication fails
    """
    key_file = os.getenv('GEE_KEY_FILE')
    if not key_file:
        raise ValueError("GEE_KEY_FILE environment variable not set")

    if not os.path.exists(key_file):
        raise FileNotFoundError(f"GEE key file not found: {key_file}")

    try:
        credentials = ee.ServiceAccountCredentials(
            email=None,
            key_data=json.load(open(key_file))
        )
        ee.Initialize(credentials)
        logger.info(f"GEE authentication successful with service account from {key_file}")
    except Exception as e:
        logger.error(f"GEE authentication failed: {e}")
        raise


def initialize() -> None:
    """Initialize Google Earth Engine if not already authenticated."""
    try:
        ee.Initialize()
        logger.info("GEE initialized successfully")
    except Exception as e:
        logger.debug(f"GEE not pre-authenticated, attempting service account auth: {e}")
        authenticate()


def test_connection() -> bool:
    """Test GEE connection by retrieving a simple image."""
    try:
        test_image = ee.Image('COPERNICUS/S2/20170102T101031_20170102T101026_T32UQD')
        _ = test_image.getInfo()
        logger.info("GEE connection test successful")
        return True
    except Exception as e:
        logger.error(f"GEE connection test failed: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    authenticate()
    initialize()
    if test_connection():
        logger.info("GEE authentication successful")
    else:
        logger.error("GEE authentication failed")
