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
        assert "retrieved_context" in data
        assert "stats" in data

        # Verify answer content
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

        # Verify source documents
        assert isinstance(data["source_documents"], list)
        assert len(data["source_documents"]) > 0

        # Verify retrieved context
        assert isinstance(data["retrieved_context"], list)
        assert len(data["retrieved_context"]) > 0

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
            assert "retrieved_context" in data
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
            assert "retrieved_context" in response

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


class TestRetrievedContext:
    """Test cases specifically for the retrieved_context field"""

    def test_retrieved_context_in_response(self, test_client: TestClient):
        """Test that retrieved_context field is present and properly formatted"""
        query_data = {"text": "What is the equipment setup process?"}
        response = test_client.post("/query", json=query_data)

        assert response.status_code == 200
        data = response.json()

        # Verify retrieved_context field exists
        assert "retrieved_context" in data
        assert isinstance(data["retrieved_context"], list)

        # Verify it contains the actual document content
        retrieved_context = data["retrieved_context"]
        assert len(retrieved_context) > 0

        # Each item should be a string (the actual document content)
        for context_item in retrieved_context:
            assert isinstance(context_item, str)
            assert len(context_item) > 0

    def test_retrieved_context_matches_source_count(self, test_client: TestClient):
        """Test that retrieved_context count matches source_documents count"""
        query_data = {"text": "How do I troubleshoot the system?"}
        response = test_client.post("/query", json=query_data)

        assert response.status_code == 200
        data = response.json()

        source_documents = data["source_documents"]
        retrieved_context = data["retrieved_context"]

        assert len(retrieved_context) == len(source_documents)

    def test_retrieved_context_content_quality(self, test_client: TestClient):
        """Test that retrieved_context contains meaningful content"""
        query_data = {"text": "What are the safety procedures?"}
        response = test_client.post("/query", json=query_data)

        assert response.status_code == 200
        data = response.json()

        retrieved_context = data["retrieved_context"]

        # Verify that the content is not just empty strings or whitespace
        for context_item in retrieved_context:
            assert isinstance(context_item, str)
            assert len(context_item.strip()) > 0
            # Content should be substantial (not just a few characters)
            assert len(context_item) > 10

    def test_retrieved_context_with_empty_response(
        self, mock_rag_system, test_client: TestClient
    ):
        """Test retrieved_context when no documents are retrieved"""

        # Configure mock to return empty context
        mock_rag_system.get_rag_response.return_value = {
            "answer": "No relevant information found.",
            "source_documents": [],
            "retrieved_context": [],
            "stats": {
                "query": "test query",
                "processing_time": 0.1,
                "documents_retrieved": 0,
                "success": True,
                "answer_length": 25,
                "source_count": 0,
            },
        }

        query_data = {"text": "Query with no results"}
        response = test_client.post("/query", json=query_data)

        assert response.status_code == 200
        data = response.json()

        # Should still have the retrieved_context field, even if empty
        assert "retrieved_context" in data
        assert isinstance(data["retrieved_context"], list)
        assert len(data["retrieved_context"]) == 0

    def test_retrieved_context_structure_consistency(self, test_client: TestClient):
        """Test that retrieved_context structure
        is consistent across multiple queries"""
        queries = [
            "What is the equipment setup process?",
            "How do I maintain the equipment?",
            "What are the technical specifications?",
        ]

        for query in queries:
            query_data = {"text": query}
            response = test_client.post("/query", json=query_data)

            assert response.status_code == 200
            data = response.json()

            # Verify consistent structure
            assert "retrieved_context" in data
            assert isinstance(data["retrieved_context"], list)

            # Verify that source_documents and retrieved_context have matching counts
            assert len(data["retrieved_context"]) == len(data["source_documents"])

    def test_retrieved_context_in_mock_response(self, test_config: Dict[str, Any]):
        """Test that the mock response includes retrieved_context"""
        mock_response = test_config["mock_response"]

        # Verify mock response has the new field
        assert "retrieved_context" in mock_response
        assert isinstance(mock_response["retrieved_context"], list)
        assert len(mock_response["retrieved_context"]) > 0

        # Verify content quality in mock
        for context_item in mock_response["retrieved_context"]:
            assert isinstance(context_item, str)
            assert len(context_item) > 0
