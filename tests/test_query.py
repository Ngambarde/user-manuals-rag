import pytest
import time
from fastapi.testclient import TestClient
from typing import Dict, Any
from unittest.mock import MagicMock


class TestQueryEndpoint:
    """Test cases for the query endpoint"""

    def test_query_success(self, test_client: TestClient, test_config: Dict[str, Any]):
        """Test successful query response"""
        query_data = {"text": "What is the equipment setup process?"}
        response = test_client.post("/query", json=query_data)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "answer" in data
        assert "source_documents" in data
        assert "stats" in data

        # Verify answer content
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

        # Verify source documents
        assert isinstance(data["source_documents"], list)
        assert len(data["source_documents"]) > 0

        # Verify stats structure
        stats = data["stats"]
        assert "query" in stats
        assert "processing_time" in stats
        assert "documents_retrieved" in stats
        assert "success" in stats
        assert stats["success"] is True

    @pytest.mark.parametrize(
        "query_text,expected_status,expected_detail",
        [
            ("", 422, "String should have at least 1 character"),  # Pydantic validation
            (
                "   ",
                400,
                "Query text cannot be empty or whitespace only",
            ),  # Custom validation
            ("valid query", 200, None),
            ("a" * 1000, 200, None),  # Long query
            ("Special chars: !@#$%^&*()", 200, None),  # Special characters
            ("Unicode: 中文 Español Français", 200, None),  # Unicode
        ],
    )
    def test_query_validation(
        self,
        test_client: TestClient,
        query_text: str,
        expected_status: int,
        expected_detail: str,
    ):
        """Test query validation with various inputs"""
        query_data = {"text": query_text}
        response = test_client.post("/query", json=query_data)

        assert response.status_code == expected_status

        if expected_status == 200:
            data = response.json()
            assert "answer" in data
            assert "source_documents" in data
        else:
            data = response.json()
            if expected_detail:
                assert expected_detail in str(data)

    def test_query_missing_text_field(self, test_client: TestClient):
        """Test query with missing text field"""
        response = test_client.post("/query", json={})
        assert response.status_code == 422  # Validation error

    def test_query_invalid_json(self, test_client: TestClient):
        """Test query with invalid JSON"""
        response = test_client.post(
            "/query", data="invalid json", headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_query_with_rag_system_error(
        self, mock_rag_system: MagicMock, test_client: TestClient
    ):
        """Test query when RAG system raises an error"""
        from src.rag_handler import RAGError

        # Configure mock to raise RAGError
        mock_rag_system.get_rag_response.side_effect = RAGError("RAG processing failed")

        query_data = {"text": "test query"}
        response = test_client.post("/query", json=query_data)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "RAG processing failed" in data["detail"]

    def test_query_with_unexpected_error(
        self, mock_rag_system: MagicMock, test_client: TestClient
    ):
        """Test query when RAG system raises unexpected error"""
        # Configure mock to raise unexpected error
        mock_rag_system.get_rag_response.side_effect = Exception("Unexpected error")

        query_data = {"text": "test query"}
        response = test_client.post("/query", json=query_data)

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Internal server error" in data["detail"]


@pytest.mark.parametrize("endpoint", ["/query"])
def test_query_endpoint_methods(test_client: TestClient, endpoint: str):
    """Test that query endpoint only accepts POST method"""
    # Test that POST works
    response = test_client.post(endpoint, json={"text": "test"})
    assert response.status_code == 200

    # Test that GET is not allowed
    response = test_client.get(endpoint)
    assert response.status_code == 405  # Method Not Allowed

    # Test that PUT is not allowed
    response = test_client.put(endpoint, json={"text": "test"})
    assert response.status_code == 405

    # Test that DELETE is not allowed
    response = test_client.delete(endpoint)
    assert response.status_code == 405


class TestQueryPerformance:
    """Performance tests for query endpoint"""

    @pytest.mark.slow
    def test_multiple_queries(self, test_client: TestClient):
        """Test multiple queries in sequence"""
        queries = [
            "What is the equipment setup process?",
            "How do I troubleshoot the system?",
            "What are the safety procedures?",
            "How do I maintain the equipment?",
            "What are the technical specifications?",
        ]

        start_time = time.time()
        responses = []

        for query in queries:
            response = test_client.post("/query", json={"text": query})
            assert response.status_code == 200
            responses.append(response.json())

        end_time = time.time()
        total_time = end_time - start_time

        # Verify all responses are valid
        for response in responses:
            assert "answer" in response
            assert "source_documents" in response

        # Performance assertion (should complete within reasonable time)
        assert total_time < 10.0  # 10 seconds for 5 queries
        assert len(responses) == len(queries)

    def test_query_response_time(self, test_client: TestClient):
        """Test that individual queries respond within acceptable time"""
        query_data = {"text": "What is the equipment setup process?"}

        start_time = time.time()
        response = test_client.post("/query", json=query_data)
        end_time = time.time()

        assert response.status_code == 200
        response_time = end_time - start_time

        # Should respond within 5 seconds
        assert response_time < 5.0
