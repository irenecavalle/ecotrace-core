"""
Tests for Flask API endpoints.

Tests all REST API routes and response formats.
"""

import pytest
import json


@pytest.fixture
def client():
    """Flask test client."""
    from src.api.app import create_app
    app = create_app("testing")
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Tests for health check."""

    def test_health_check(self, client):
        """Test /health endpoint."""
        # TODO: GET /health, verify 200 status and healthy response
        pass

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        # TODO: GET /, verify API info in response
        pass


class TestSupplierEndpoints:
    """Tests for supplier endpoints."""

    def test_list_suppliers(self, client):
        """Test GET /api/v1/suppliers."""
        # TODO: Get supplier list, verify structure and mock data
        pass

    def test_get_supplier(self, client):
        """Test GET /api/v1/suppliers/<id>."""
        # TODO: Get single supplier, verify full details returned
        pass

    def test_get_supplier_score(self, client):
        """Test GET /api/v1/suppliers/<id>/score."""
        # TODO: Get supplier score, verify ecoscore and sub-scores
        pass

    def test_create_supplier(self, client):
        """Test POST /api/v1/suppliers."""
        # TODO: Create new supplier with POST, verify 201 response
        pass


class TestAlertEndpoints:
    """Tests for alert endpoints."""

    def test_get_alerts(self, client):
        """Test GET /api/v1/alerts."""
        # TODO: Get alerts list, verify alert structure
        pass


class TestExportEndpoints:
    """Tests for export endpoints."""

    def test_export_csrd(self, client):
        """Test GET /api/v1/export/csrd."""
        # TODO: Get CSRD export, verify format compliance
        pass

    def test_qr_page(self, client):
        """Test GET /api/v1/qr/<id>."""
        # TODO: Get QR landing page, verify consumer-safe data only
        pass
