import pytest
from fastapi.testclient import TestClient
from typing import Dict, Any
from unittest.mock import MagicMock


class TestSystemInfo:
    """Test cases for the system info endpoint"""

    def test_system_info_success(self, test_client: TestClient):
        """Test successful system info response"""
        response = test_client.get("/system-info")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "config" in data
        assert "vector_store_info" in data

        # Verify config structure
        config = data["config"]
        assert "project_id" in config
        assert "model_name" in config
        assert "max_retrieval_docs" in config

        # Verify vector store info
        vector_store_info = data["vector_store_info"]
        assert "vector_count" in vector_store_info
        assert "dimension" in vector_store_info

        # Verify data types
        assert isinstance(config["project_id"], str)
        assert isinstance(config["model_name"], str)
        assert isinstance(config["max_retrieval_docs"], int)
        assert isinstance(vector_store_info["vector_count"], int)
        assert isinstance(vector_store_info["dimension"], int)

    def test_system_info_with_rag_system_error(
        self, mock_rag_system: MagicMock, test_client: TestClient
    ):
        """Test system info when RAG system raises an error"""
        # Configure mock to raise an exception
        mock_rag_system.get_system_info.side_effect = Exception("System info failed")

        response = test_client.get("/system-info")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to retrieve system information" in data["detail"]


@pytest.mark.parametrize("endpoint", ["/system-info"])
def test_system_info_endpoint_methods(test_client: TestClient, endpoint: str):
    """Test that system info endpoint only accepts GET method"""
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


class TestIntegration:
    """Integration tests for full request flows"""

    @pytest.mark.integration
    def test_full_request_flow(
        self, test_client: TestClient, test_config: Dict[str, Any]
    ):
        """Test complete request flow from health check to query to system info"""

        # Step 1: Health check
        health_response = test_client.get("/health")
        assert health_response.status_code == 200
        health_data = health_response.json()
        assert health_data["status"] == "healthy"

        # Step 2: Query
        query_data = {"text": "What is the equipment setup process?"}
        query_response = test_client.post("/query", json=query_data)
        assert query_response.status_code == 200
        query_data = query_response.json()
        assert "answer" in query_data
        assert "source_documents" in query_data

        # Step 3: System info
        system_response = test_client.get("/system-info")
        assert system_response.status_code == 200
        system_data = system_response.json()
        assert "config" in system_data
        assert "vector_store_info" in system_data

        # Verify consistency across responses
        # Health check should show healthy status
        assert health_data["status"] == "healthy"

        # Query should have valid response
        assert len(query_data["answer"]) > 0
        assert len(query_data["source_documents"]) > 0

        # System info should have valid configuration
        assert system_data["config"]["project_id"] == "test-project"

    @pytest.mark.integration
    def test_error_propagation(
        self, mock_rag_system: MagicMock, test_client: TestClient
    ):
        """Test that errors properly propagate through the system"""
        from src.rag_handler import RAGError

        # Configure mock to fail on query but work on other endpoints
        mock_rag_system.get_rag_response.side_effect = RAGError(
            "Query processing failed"
        )

        # Health check should still work
        health_response = test_client.get("/health")
        assert health_response.status_code == 200

        # Query should fail with proper error
        query_response = test_client.post("/query", json={"text": "test"})
        assert query_response.status_code == 400
        query_data = query_response.json()
        assert "Query processing failed" in query_data["detail"]

        # System info should still work
        system_response = test_client.get("/system-info")
        assert system_response.status_code == 200

    @pytest.mark.integration
    def test_concurrent_requests(self, test_client: TestClient):
        """Test handling of concurrent requests"""
        import threading

        results = []
        errors = []

        def make_request():
            try:
                response = test_client.get("/health")
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))

        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all requests succeeded
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5
        assert all(status == 200 for status in results)
