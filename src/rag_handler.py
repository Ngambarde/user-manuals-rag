import os
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from contextlib import contextmanager

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from google.cloud import secretmanager
from google.api_core import retry

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class RAGConfig:
    """
    Configuration for RAG system
    """

    project_id: str
    db_path: str = "vector_store"
    vector_store_bucket: Optional[str] = None  # GCS bucket for vector store
    vector_store_blob: str = "faiss_index"  # Blob name in GCS bucket
    use_gcs_vector_store: bool = False  # Whether to load from GCS
    model_name: str = "gpt-4.1-nano-2025-04-14"
    max_retrieval_docs: int = 2
    temperature: float = 0.0
    max_retries: int = 3
    timeout_seconds: int = 30


class RAGError(Exception):
    """
    Custom exception for RAG system errors
    """

    pass


class SecretManagerError(Exception):
    """
    Custom exception for secret management errors
    """

    pass


@retry.Retry(predicate=retry.if_transient_error)
def get_gcp_secret(secret_id: str, project_id: str, version_id: str = "latest") -> str:
    """
    Retrieves a secret from Google Cloud Secret Manager with retry logic.
    Falls back to environment variables if GCP is unavailable.
    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(request={"name": name})
        logger.info(f"Secret {secret_id} retrieved successfully from GCP")
        return response.payload.data.decode("UTF-8").strip()
    except Exception as e:
        logger.warning(f"Failed to retrieve secret {secret_id} from GCP: {e}")
        logger.info(f"Falling back to environment variable '{secret_id}'")

        key = os.getenv(secret_id)
        if not key:
            raise SecretManagerError(
                f"Secret {secret_id} not found in environment variables or GCP"
            )
        return key.strip()


class RAGSystem:
    """
    RAG system, including robust error handling and monitoring
    """

    def __init__(self, config: Optional[RAGConfig] = None):
        """
        Initialize RAG system with configuration
        """
        self.config = config or self._load_config()
        self._initialize_components()

    def _load_config(self) -> RAGConfig:
        """
        Load configuration from environment variables
        """
        load_dotenv()

        project_id = os.getenv("GCP_PROJECT_ID")
        if not project_id:
            raise ValueError("GCP_PROJECT_ID environment variable is required")

        # Determine vector store configuration
        use_gcs = os.getenv("USE_GCS_VECTOR_STORE", "False").lower() in (
            "true",
            "1",
            "yes",
        )
        vector_store_bucket = os.getenv("VECTOR_STORE_BUCKET")

        # If GCS is enabled but no bucket specified, construct from project ID
        if use_gcs and not vector_store_bucket:
            vector_store_bucket = f"{project_id}-vector-stores"
            logger.info(f"Using default vector store bucket: {vector_store_bucket}")

        return RAGConfig(
            project_id=project_id,
            db_path=os.getenv("DB_FAISS_PATH", "vector_store"),
            vector_store_bucket=vector_store_bucket,
            vector_store_blob=os.getenv("VECTOR_STORE_BLOB", "faiss_index"),
            use_gcs_vector_store=use_gcs,
            model_name=os.getenv("OPENAI_MODEL", "gpt-4.1-nano-2025-04-14"),
            max_retrieval_docs=int(os.getenv("MAX_RETRIEVAL_DOCS", "2")),
            temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.0")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            timeout_seconds=int(os.getenv("TIMEOUT_SECONDS", "30")),
        )

    def _initialize_components(self):
        """
        Initialize all RAG system components with error handling
        """
        logger.info("Initializing RAG System...")

        try:
            # Set up API key
            api_key = get_gcp_secret("OPENAI_API_KEY", self.config.project_id)
            os.environ["OPENAI_API_KEY"] = api_key

            # Initialize embeddings
            logger.info("Initializing OpenAI embeddings...")
            self.embeddings = OpenAIEmbeddings()

            # Load vector store
            logger.info(f"Loading FAISS database from: {self.config.db_path}")
            self._load_vector_store()

            # Initialize LLM
            logger.info(f"Initializing LLM: {self.config.model_name}")
            self.llm = ChatOpenAI(
                model=self.config.model_name,
                temperature=self.config.temperature,
                timeout=self.config.timeout_seconds,
            )

            # Set up retriever
            self.retriever = self.db.as_retriever(
                search_kwargs={"k": self.config.max_retrieval_docs}
            )

            # Set up chains
            self._setup_chains()

            logger.info("RAG System initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize RAG system: {e}")
            raise RAGError(f"RAG system initialization failed: {e}")

    def _load_vector_store(self):
        """
        Load FAISS vector store with validation
        """
        if (
            not os.path.exists(self.config.db_path)
            and not self.config.use_gcs_vector_store
        ):
            raise RAGError(f"Vector store path does not exist: {self.config.db_path}")

        try:
            if self.config.use_gcs_vector_store:
                logger.info(
                    f"Loading FAISS database from GCS bucket: "
                    f"{self.config.vector_store_bucket}"
                )
                self.db = self._load_vector_store_from_gcs()
                logger.info(
                    f"Vector store loaded successfully from GCS with "
                    f"{self.db.index.ntotal} vectors"
                )
            else:
                self.db = FAISS.load_local(
                    self.config.db_path,
                    self.embeddings,
                    allow_dangerous_deserialization=True,
                )
                logger.info(
                    f"Vector store loaded successfully with "
                    f"{self.db.index.ntotal} vectors"
                )
        except Exception as e:
            logger.error(f"Failed to load vector store: {e}")
            raise RAGError(f"Vector store loading failed: {e}")

    def _load_vector_store_from_gcs(self):
        """
        Load FAISS vector store from Google Cloud Storage
        """
        import tempfile
        import shutil
        from google.cloud import storage

        if not self.config.vector_store_bucket:
            raise RAGError("Vector store bucket not configured for GCS loading")

        # Create temporary directory for downloading
        temp_dir = tempfile.mkdtemp()
        try:
            # Download from GCS with project specification
            storage_client = storage.Client(project=self.config.project_id)
            bucket = storage_client.bucket(self.config.vector_store_bucket)

            # Download the FAISS index files
            faiss_files = ["index.faiss", "index.pkl"]
            for filename in faiss_files:
                blob_name = f"{self.config.vector_store_blob}/{filename}"
                blob = bucket.blob(blob_name)

                if not blob.exists():
                    raise RAGError(f"FAISS file not found in GCS: {blob_name}")

                local_path = os.path.join(temp_dir, filename)
                logger.info(f"Downloading {blob_name} from GCS")
                blob.download_to_filename(local_path)

            # Load FAISS from temporary directory
            db = FAISS.load_local(
                temp_dir,
                self.embeddings,
                allow_dangerous_deserialization=True,
            )

            return db

        except Exception as e:
            logger.error(f"Failed to load vector store from GCS: {e}")
            raise RAGError(f"GCS vector store loading failed: {e}")
        finally:
            # Clean up temporary directory
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")

    def _setup_chains(self):
        """
        Set up LangChain retrieval and document chains
        """
        try:
            prompt = ChatPromptTemplate.from_template(
                """Answer the following question based only on the provided context.

                <context>
                {context}
                </context>

                Question: {input}

                Answer:"""
            )

            self.document_chain = create_stuff_documents_chain(self.llm, prompt)
            self.retrieval_chain = create_retrieval_chain(
                self.retriever, self.document_chain
            )

            logger.info("LangChain components initialized successfully")

        except Exception as e:
            logger.error(f"Failed to set up LangChain components: {e}")
            raise RAGError(f"Chain setup failed: {e}")

    @contextmanager
    def _query_context(self):
        """
        Context manager for query execution with timing and error handling
        """
        start_time = time.time()
        try:
            yield
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Query failed after {elapsed:.2f} seconds: {e}")
            raise
        else:
            elapsed = time.time() - start_time
            logger.info(f"Query completed in {elapsed:.2f} seconds")

    def _validate_query(self, query_text: str) -> str:
        """
        Validate and sanitize query input
        """
        if not query_text or not query_text.strip():
            raise RAGError("Query text cannot be empty")

        query = query_text.strip()
        if len(query) > 1000:  # Reasonable limit
            logger.warning(f"Query truncated from {len(query)} to 1000 characters")
            query = query[:1000]

        return query

    def _format_source_documents(self, documents: List[Document]) -> List[str]:
        """
        Format source documents for response
        """
        formatted_sources = []

        for i, doc in enumerate(documents, 1):
            source_info = {
                "rank": i,
                "source": doc.metadata.get("source", "Unknown"),
                "page": doc.metadata.get("page_number", "N/A"),
                "content_type": doc.metadata.get("content_type", "text"),
                "confidence": doc.metadata.get("score", "N/A"),
            }

            formatted_source = (
                f"Rank {i}: {source_info['source']} "
                f"(Page {source_info['page']}, Type: {source_info['content_type']})"
            )
            formatted_sources.append(formatted_source)

        return formatted_sources

    def get_rag_response(self, query_text: str) -> Dict[str, Any]:
        """
        Get RAG response with comprehensive error handling and monitoring
        """
        stats = {
            "query": query_text,
            "processing_time": 0,
            "documents_retrieved": 0,
            "success": False,
            "error": None,
        }

        try:
            with self._query_context():
                # Validate query
                validated_query = self._validate_query(query_text)

                # Execute retrieval chain
                logger.info(f"Processing query: {validated_query[:100]}...")
                response = self.retrieval_chain.invoke({"input": validated_query})

                # Extract and format results
                answer = response.get("answer", "No answer generated")
                context_docs = response.get("context", [])

                # This is the text the LLM sees
                retrieved_context = [doc.page_content for doc in context_docs]

                # Format source documents
                source_documents = self._format_source_documents(context_docs)

                stats.update(
                    {
                        "success": True,
                        "documents_retrieved": len(context_docs),
                        "answer_length": len(answer),
                        "source_count": len(source_documents),
                    }
                )

                logger.info(
                    f"Retrieved {len(context_docs)} documents, "
                    f"generated {len(answer)} character answer"
                )

                return {
                    "answer": answer,
                    "source_documents": source_documents,
                    "retrieved_context": retrieved_context,
                    "stats": stats,
                }

        except RAGError as e:
            stats["error"] = str(e)
            logger.error(f"RAG processing error: {e}")
            raise
        except Exception as e:
            stats["error"] = str(e)
            logger.error(f"Unexpected error during RAG processing: {e}")
            raise RAGError(f"Unexpected error: {e}")
        finally:
            pass

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on RAG system components
        """
        health_status = {
            "status": "healthy",
            "components": {},
            "timestamp": time.time(),
        }

        try:
            # Check vector store
            if hasattr(self, "db") and self.db.index.ntotal > 0:
                health_status["components"]["vector_store"] = {
                    "status": "healthy",
                    "vector_count": self.db.index.ntotal,
                }
            else:
                health_status["components"]["vector_store"] = {
                    "status": "unhealthy",
                    "error": "No vectors found",
                }
                health_status["status"] = "unhealthy"

            # Check embeddings
            if hasattr(self, "embeddings"):
                health_status["components"]["embeddings"] = {"status": "healthy"}
            else:
                health_status["components"]["embeddings"] = {
                    "status": "unhealthy",
                    "error": "Not initialized",
                }
                health_status["status"] = "unhealthy"

            # Check LLM
            if hasattr(self, "llm"):
                health_status["components"]["llm"] = {
                    "status": "healthy",
                    "model": self.config.model_name,
                }
            else:
                health_status["components"]["llm"] = {
                    "status": "unhealthy",
                    "error": "Not initialized",
                }
                health_status["status"] = "unhealthy"

        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
            logger.error(f"Health check failed: {e}")

        return health_status

    def get_system_info(self) -> Dict[str, Any]:
        """
        Get system information and configuration
        """
        return {
            "config": {
                "project_id": self.config.project_id,
                "db_path": self.config.db_path,
                "vector_store_bucket": self.config.vector_store_bucket,
                "vector_store_blob": self.config.vector_store_blob,
                "use_gcs_vector_store": self.config.use_gcs_vector_store,
                "model_name": self.config.model_name,
                "max_retrieval_docs": self.config.max_retrieval_docs,
                "temperature": self.config.temperature,
                "max_retries": self.config.max_retries,
                "timeout_seconds": self.config.timeout_seconds,
            },
            "vector_store_info": {
                "vector_count": self.db.index.ntotal if hasattr(self, "db") else 0,
                "dimension": self.db.index.d if hasattr(self, "db") else 0,
            },
            "initialization_time": getattr(self, "_init_time", time.time()),
        }


# Convenience function for backward compatibility
def get_rag_response(query_text: str) -> Dict[str, Any]:
    """
    Convenience function for simple RAG queries
    """
    rag_system = RAGSystem()
    return rag_system.get_rag_response(query_text)
