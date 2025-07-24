import pytest
import sys
import os
import time
from pathlib import Path
from typing import Dict, Any
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# Configure pytest
def pytest_configure(config):
    """
    Configure pytest with custom markers and settings
    """
    # Add custom markers
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


def pytest_collection_modifyitems(config, items):
    """
    Automatically mark tests based on their names and classes
    """
    for item in items:
        # Mark performance tests as slow
        if "performance" in item.name.lower():
            item.add_marker(pytest.mark.slow)

        # Mark integration tests
        if "integration" in item.name.lower() or "TestIntegration" in str(item.cls):
            item.add_marker(pytest.mark.integration)

        # Mark unit tests
        if "TestHealthEndpoint" in str(item.cls) or "TestQueryEndpoint" in str(
            item.cls
        ):
            item.add_marker(pytest.mark.unit)


# Global test configuration
@pytest.fixture(scope="session")
def test_environment():
    """
    Set up test environment variables
    """
    # Set test environment variables
    os.environ["GCP_PROJECT_ID"] = "test-project"
    os.environ["OPENAI_API_KEY"] = "test-api-key"
    os.environ["DB_FAISS_PATH"] = "test_vector_store"

    yield

    # Clean up (if needed)
    pass


@pytest.fixture(scope="session")
def test_config() -> Dict[str, Any]:
    """
    Centralized test configuration fixture
    """
    return {
        "test_timeout": 30,
        "max_retries": 3,
        "mock_response": {
            "answer": "This is a mocked answer for testing purposes.",
            "source_documents": [
                "Rank 1: test_document.pdf (Page 1, Type: text)",
                "Rank 2: another_document.pdf (Page 3, Type: table)",
            ],
            "retrieved_context": [
                "This is the first retrieved document content that the LLM sees.",
                "This is the second retrieved document content.",
            ],
            "stats": {
                "query": "test query",
                "processing_time": 0.5,
                "documents_retrieved": 2,
                "success": True,
                "answer_length": 45,
                "source_count": 2,
            },
        },
        "health_response": {
            "status": "healthy",
            "components": {
                "vector_store": {"status": "healthy", "vector_count": 1000},
                "embeddings": {"status": "healthy"},
                "llm": {"status": "healthy", "model": "gpt-4.1-nano-2025-04-14"},
            },
            "timestamp": time.time(),
        },
        "system_info_response": {
            "config": {
                "project_id": "test-project",
                "model_name": "gpt-4.1-nano-2025-04-14",
                "max_retrieval_docs": 2,
            },
            "vector_store_info": {"vector_count": 1000, "dimension": 1536},
        },
    }


@pytest.fixture(scope="function")
def mock_rag_system(test_config: Dict[str, Any]) -> MagicMock:
    """
    Creates a mock RAG system with comprehensive behavior
    """
    mock_instance = MagicMock()

    # Configure successful response
    mock_instance.get_rag_response.return_value = test_config["mock_response"]

    # Configure health check
    mock_instance.health_check.return_value = test_config["health_response"]

    # Configure system info
    mock_instance.get_system_info.return_value = test_config["system_info_response"]

    return mock_instance


@pytest.fixture(scope="function")
def test_client(mock_rag_system: MagicMock) -> TestClient:
    """
    Create a test client with mocked RAG system using dependency override
    """
    from src.main import app, get_rag_system

    # Override the dependency with our mock
    app.dependency_overrides[get_rag_system] = lambda: mock_rag_system

    with TestClient(app) as client:
        yield client

    # Clean up dependency override
    app.dependency_overrides.clear()


# Shared test utilities
def assert_response_structure(response_data: Dict[str, Any]):
    """
    Assert that response has the expected structure
    """
    assert "answer" in response_data
    assert "source_documents" in response_data
    assert "retrieved_context" in response_data
    assert isinstance(response_data["answer"], str)
    assert isinstance(response_data["source_documents"], list)
    assert isinstance(response_data["retrieved_context"], list)


def assert_stats_structure(stats: Dict[str, Any]):
    """
    Assert that stats have the expected structure
    """
    if stats is None:
        return

    expected_fields = ["query", "processing_time", "documents_retrieved", "success"]
    for field in expected_fields:
        assert field in stats, f"Missing field: {field}"

    assert isinstance(stats["success"], bool)
    assert isinstance(stats["processing_time"], (int, float))
    assert isinstance(stats["documents_retrieved"], int)
