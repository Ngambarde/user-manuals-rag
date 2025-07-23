import pytest
import time
from fastapi.testclient import TestClient
from unittest.mock import MagicMock


class TestHealthEndpoint:
    """Test cases for the health endpoint"""

    def test_health_check_success(self, test_client: TestClient):
        """Test successful health check response"""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "status" in data
        assert data["status"] == "healthy"
        assert "components" in data
        assert "timestamp" in data

        # Verify components structure
        components = data["components"]
        assert "vector_store" in components
        assert "embeddings" in components
        assert "llm" in components

        # Verify vector store info
        vector_store = components["vector_store"]
        assert vector_store["status"] == "healthy"
        assert "vector_count" in vector_store

    def test_health_check_response_time(self, test_client: TestClient):
        """Test that health check responds quickly"""
        start_time = time.time()
        response = test_client.get("/health")
        end_time = time.time()

        assert response.status_code == 200
        assert (end_time - start_time) < 1.0  # Should respond within 1 second

    def test_health_check_with_rag_system_failure(
        self, mock_rag_system: MagicMock, test_client: TestClient
    ):
        """Test health check when RAG system health check fails"""
        # Configure mock to raise an exception
        mock_rag_system.health_check.side_effect = Exception("Health check failed")

        response = test_client.get("/health")

        assert response.status_code == 200  # Health endpoint should still return 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data
        assert "Health check failed" in data["error"]


@pytest.mark.parametrize("endpoint", ["/health"])
def test_health_endpoint_methods(test_client: TestClient, endpoint: str):
    """Test that health endpoint only accepts GET method"""
    # Test that GET works
    response = test_client.get(endpoint)
    assert response.status_code == 200

    # Test that POST is not allowed
    response = test_client.post(endpoint)
    assert response.status_code == 405  # Method Not Allowed

    # Test that PUT is not allowed
    response = test_client.put(endpoint)
    assert response.status_code == 405

    # Test that DELETE is not allowed
    response = test_client.delete(endpoint)
    assert response.status_code == 405
