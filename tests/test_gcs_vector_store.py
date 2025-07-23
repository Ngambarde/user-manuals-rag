import pytest
import os
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.rag_handler import RAGError, RAGConfig, RAGSystem


class TestGCSConfiguration:
    """Test cases for GCS configuration loading"""

    def test_gcs_config_environment_loading(self):
        """Test that GCS configuration is loaded correctly from environment"""
        with patch.dict(
            os.environ,
            {
                "GCP_PROJECT_ID": "test-project",
                "USE_GCS_VECTOR_STORE": "true",
                "VECTOR_STORE_BUCKET": "custom-bucket",
                "VECTOR_STORE_BLOB": "custom-blob",
            },
        ):
            # Mock the initialization to avoid actual GCS calls
            with patch.object(RAGSystem, "_initialize_components"):
                rag_system = RAGSystem()

                assert rag_system.config.use_gcs_vector_store is True
                assert rag_system.config.vector_store_bucket == "custom-bucket"
                assert rag_system.config.vector_store_blob == "custom-blob"

    def test_gcs_config_default_bucket(self):
        """Test that default bucket is constructed from project ID"""
        with patch.dict(
            os.environ,
            {
                "GCP_PROJECT_ID": "test-project",
                "USE_GCS_VECTOR_STORE": "true",
                # No VECTOR_STORE_BUCKET specified
            },
        ):
            # Mock the initialization to avoid actual GCS calls
            with patch.object(RAGSystem, "_initialize_components"):
                rag_system = RAGSystem()

                assert rag_system.config.use_gcs_vector_store is True
                assert (
                    rag_system.config.vector_store_bucket
                    == "test-project-vector-stores"
                )

    @pytest.mark.parametrize(
        "use_gcs,expected_bucket",
        [
            ("true", "test-project-vector-stores"),
            ("false", None),
            ("1", "test-project-vector-stores"),
            ("yes", "test-project-vector-stores"),
        ],
    )
    def test_gcs_config_various_boolean_values(
        self, use_gcs: str, expected_bucket: str
    ):
        """Test various boolean string values for GCS configuration"""
        with patch.dict(
            os.environ,
            {"GCP_PROJECT_ID": "test-project", "USE_GCS_VECTOR_STORE": use_gcs},
        ):
            # Mock the initialization to avoid actual GCS calls
            with patch.object(RAGSystem, "_initialize_components"):
                rag_system = RAGSystem()

                if expected_bucket:
                    assert rag_system.config.use_gcs_vector_store is True
                    assert rag_system.config.vector_store_bucket == expected_bucket
                else:
                    assert rag_system.config.use_gcs_vector_store is False


class TestGCSVectorStoreLoading:
    """Test cases for GCS vector store loading functionality"""

    def test_gcs_loading_success(
        self, mock_rag_system: MagicMock, test_client: TestClient
    ):
        """Test successful GCS vector store loading"""
        # Configure mock to simulate GCS loading
        mock_rag_system.get_system_info.return_value = {
            "config": {
                "use_gcs_vector_store": True,
                "vector_store_bucket": "test-bucket",
                "vector_store_blob": "test-blob",
            }
        }

        response = test_client.get("/system-info")
        assert response.status_code == 200

        data = response.json()
        assert data["config"]["use_gcs_vector_store"] is True
        assert data["config"]["vector_store_bucket"] == "test-bucket"

    def test_gcs_loading_with_storage_mock(self):
        """Test GCS loading with mocked storage client"""
        config = RAGConfig(
            project_id="test-project",
            use_gcs_vector_store=True,
            vector_store_bucket="test-bucket",
            vector_store_blob="test-blob",
        )

        # Create a mock RAG system with mocked initialization
        with patch.object(RAGSystem, "_initialize_components"):
            rag_system = RAGSystem(config)

            # Mock the entire GCS loading process
            with patch("google.cloud.storage.Client") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client

                mock_bucket = MagicMock()
                mock_client.bucket.return_value = mock_bucket

                mock_blob = MagicMock()
                mock_blob.exists.return_value = True
                mock_bucket.blob.return_value = mock_blob

                # Mock FAISS loading
                with patch(
                    "langchain_community.vectorstores.FAISS.load_local"
                ) as mock_faiss_load:
                    mock_db = MagicMock()
                    mock_db.index.ntotal = 1000
                    mock_faiss_load.return_value = mock_db

                    rag_system.embeddings = MagicMock()

                    # Test the GCS loading method
                    result = rag_system._load_vector_store_from_gcs()

                    # Verify GCS client was called correctly
                    mock_client_class.assert_called_once_with(project="test-project")
                    mock_client.bucket.assert_called_once_with("test-bucket")

                    # Verify blob operations
                    assert mock_bucket.blob.call_count == 2  # index.faiss and index.pkl
                    assert mock_blob.exists.call_count == 2
                    assert mock_blob.download_to_filename.call_count == 2

                    # Verify FAISS loading
                    mock_faiss_load.assert_called_once()
                    assert result == mock_db

    @pytest.mark.parametrize(
        "error_type,expected_error",
        [
            (Exception("GCS connection failed"), "GCS vector store loading failed"),
            (ValueError("Invalid bucket"), "GCS vector store loading failed"),
            (OSError("Permission denied"), "GCS vector store loading failed"),
        ],
    )
    def test_gcs_loading_error_handling(
        self, error_type: Exception, expected_error: str
    ):
        """Test error handling when GCS loading fails"""
        config = RAGConfig(
            project_id="test-project",
            use_gcs_vector_store=True,
            vector_store_bucket="test-bucket",
            vector_store_blob="test-blob",
        )

        # Create a mock RAG system with mocked initialization
        with patch.object(RAGSystem, "_initialize_components"):
            rag_system = RAGSystem(config)

            # Mock storage client to raise an error
            with patch("google.cloud.storage.Client") as mock_client_class:
                mock_client_class.side_effect = error_type

                rag_system.embeddings = MagicMock()

                # Test that the error is properly handled
                with pytest.raises(RAGError, match=expected_error):
                    rag_system._load_vector_store_from_gcs()

    def test_gcs_loading_without_bucket(self):
        """Test error when GCS is enabled but no bucket specified"""
        config = RAGConfig(
            project_id="test-project",
            use_gcs_vector_store=True,
            vector_store_bucket=None,  # No bucket specified
        )

        # Create a mock RAG system with mocked initialization
        with patch.object(RAGSystem, "_initialize_components"):
            rag_system = RAGSystem(config)

            # Test that appropriate error is raised
            with pytest.raises(RAGError, match="Vector store bucket not configured"):
                rag_system._load_vector_store_from_gcs()

    def test_gcs_loading_missing_files(self):
        """Test error when FAISS files don't exist in GCS"""
        config = RAGConfig(
            project_id="test-project",
            use_gcs_vector_store=True,
            vector_store_bucket="test-bucket",
            vector_store_blob="test-blob",
        )

        # Create a mock RAG system with mocked initialization
        with patch.object(RAGSystem, "_initialize_components"):
            rag_system = RAGSystem(config)

            # Mock storage client with missing files
            with patch("google.cloud.storage.Client") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client

                mock_bucket = MagicMock()
                mock_client.bucket.return_value = mock_bucket

                mock_blob = MagicMock()
                mock_blob.exists.return_value = False  # File doesn't exist
                mock_bucket.blob.return_value = mock_blob

                rag_system.embeddings = MagicMock()

                # Test that appropriate error is raised
                with pytest.raises(RAGError, match="FAISS file not found in GCS"):
                    rag_system._load_vector_store_from_gcs()


class TestBackwardCompatibility:
    """Test cases for backward compatibility with local storage"""

    def test_local_storage_still_works(self):
        """Test that local loading still works when GCS is disabled"""
        config = RAGConfig(
            project_id="test-project",
            use_gcs_vector_store=False,
            db_path="vector_store",
        )

        # Create a mock RAG system with mocked initialization
        with patch.object(RAGSystem, "_initialize_components"):
            rag_system = RAGSystem(config)

            # Mock FAISS loading to avoid actual loading
            with patch(
                "langchain_community.vectorstores.FAISS.load_local"
            ) as mock_load:
                mock_db = MagicMock()
                mock_db.index.ntotal = 500
                mock_load.return_value = mock_db

                rag_system.embeddings = MagicMock()
                rag_system._load_vector_store()
                mock_load.assert_called_once_with(
                    config.db_path,
                    rag_system.embeddings,
                    allow_dangerous_deserialization=True,
                )

    def test_system_info_includes_gcs_config(
        self, mock_rag_system: MagicMock, test_client: TestClient
    ):
        """Test that system info includes GCS configuration"""
        # Configure mock to include GCS config
        mock_rag_system.get_system_info.return_value = {
            "config": {
                "use_gcs_vector_store": True,
                "vector_store_bucket": "test-bucket",
                "vector_store_blob": "test-blob",
                "project_id": "test-project",
            }
        }

        response = test_client.get("/system-info")
        assert response.status_code == 200

        data = response.json()
        assert data["config"]["use_gcs_vector_store"] is True
        assert data["config"]["vector_store_bucket"] == "test-bucket"
        assert data["config"]["vector_store_blob"] == "test-blob"


class TestGCSIntegration:
    """Integration tests for GCS vector store functionality"""

    @pytest.mark.integration
    def test_gcs_config_in_system_info(
        self, mock_rag_system: MagicMock, test_client: TestClient
    ):
        """Test that GCS configuration appears in system info"""
        # Configure mock to include GCS config
        mock_rag_system.get_system_info.return_value = {
            "config": {
                "use_gcs_vector_store": True,
                "vector_store_bucket": "test-bucket",
                "vector_store_blob": "test-blob",
            }
        }

        response = test_client.get("/system-info")
        assert response.status_code == 200

        data = response.json()
        assert data["config"]["use_gcs_vector_store"] is True
        assert data["config"]["vector_store_bucket"] == "test-bucket"
        assert data["config"]["vector_store_blob"] == "test-blob"

    @pytest.mark.integration
    def test_gcs_health_check_includes_vector_store_info(
        self, mock_rag_system: MagicMock, test_client: TestClient
    ):
        """Test that health check includes vector store information"""
        # Configure mock health check
        mock_rag_system.health_check.return_value = {
            "status": "healthy",
            "components": {
                "vector_store": {
                    "status": "healthy",
                    "vector_count": 1000,
                    "source": "gcs://test-bucket/test-blob",
                },
                "embeddings": {"status": "healthy"},
                "llm": {"status": "healthy"},
            },
        }

        response = test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "vector_store" in data["components"]
        assert data["components"]["vector_store"]["status"] == "healthy"
