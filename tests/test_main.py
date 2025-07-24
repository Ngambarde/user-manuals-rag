import logging
import sys
import os
from typing import Dict, Any
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

# Add project root to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Configure test logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TestLegacyFunctionality:
    """Legacy tests that haven't been migrated to focused modules yet"""

    def test_legacy_rag_system_error_handling(self, mock_rag_system: MagicMock):
        """Test RAG system error handling with custom app instance"""
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
        from typing import List, Dict, Any, Optional
        from src.rag_handler import RAGError
        import logging

        logger = logging.getLogger(__name__)

        # Define models
        class QueryRequest(BaseModel):
            text: str

        class QueryResponse(BaseModel):
            answer: str
            source_documents: List[str]
            retrieved_context: Optional[List[str]] = None
            stats: Optional[Dict[str, Any]] = None

        # Create app with custom error handling
        app = FastAPI()

        @app.post("/query", response_model=QueryResponse)
        async def handle_query(request: QueryRequest):
            """
            Custom endpoint with specific error handling for testing
            """
            # Additional validation for empty text
            if not request.text.strip():
                raise HTTPException(
                    status_code=400, detail="Query text cannot be empty"
                )

            try:
                response_data = mock_rag_system.get_rag_response(request.text)
                return QueryResponse(
                    answer=response_data["answer"],
                    source_documents=response_data["source_documents"],
                    retrieved_context=response_data.get("retrieved_context", []),
                    stats=response_data.get("stats", {}),
                )
            except RAGError as e:
                logger.error(f"RAG processing error: {e}")
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                logger.error(f"Unexpected error during query processing: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")

        # Test with custom client
        with TestClient(app) as client:
            # Test empty text validation
            response = client.post("/query", json={"text": ""})
            assert response.status_code == 400
            assert "Query text cannot be empty" in response.json()["detail"]

            # Test whitespace-only text
            response = client.post("/query", json={"text": "   "})
            assert response.status_code == 400
            assert "Query text cannot be empty" in response.json()["detail"]

            # Test valid query
            response = client.post("/query", json={"text": "valid query"})
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "source_documents" in data

    def test_legacy_error_handling_edge_cases(self, test_client: TestClient):
        """Test edge cases in error handling"""
        # Test with malformed JSON
        response = test_client.post(
            "/query", data="not json", headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

        # Test with missing Content-Type header - FastAPI accepts this as JSON
        response = test_client.post("/query", data='{"text": "test"}')
        assert response.status_code == 200  # FastAPI auto-detects JSON

        # Test with extra fields (should be ignored by Pydantic)
        response = test_client.post(
            "/query", json={"text": "test", "extra_field": "value"}
        )
        assert response.status_code == 200


# Legacy pytest hooks (now handled in conftest.py)
# These are kept for backward compatibility but should be removed in future
def pytest_configure(config):
    """
    Legacy pytest configuration - now handled in conftest.py
    """
    pass


def pytest_collection_modifyitems(config, items):
    """
    Legacy test collection modification - now handled in conftest.py
    """
    pass


# Legacy utility functions (now in conftest.py)
def assert_response_structure(response_data: Dict[str, Any]):
    """
    Legacy response structure assertion - now in conftest.py
    """
    from conftest import assert_response_structure as new_assert

    return new_assert(response_data)


def assert_stats_structure(stats: Dict[str, Any]):
    """
    Legacy stats structure assertion - now in conftest.py
    """
    from conftest import assert_stats_structure as new_assert

    return new_assert(stats)
