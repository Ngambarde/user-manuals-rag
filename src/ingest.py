import os
import shutil
import logging
import time
from typing import List, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager
import tempfile
from pathlib import Path

from google.cloud import storage
from google.api_core import retry
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from document_parser import parse_pdf_elements

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class IngestionConfig:
    """
    Configuration for document ingestion
    """

    project_id: str
    raw_docs_bucket: str
    vector_store_bucket: str
    chunk_size: int = 1000
    chunk_overlap: int = 100
    max_retries: int = 3
    batch_size: int = 10
    temp_dir: str = "/tmp/raw_docs"


class IngestionError(Exception):
    """
    Custom exception for ingestion errors
    """

    pass


class DocumentIngestionPipeline:
    """
    Document ingestion pipeline
    """

    def __init__(self, config: IngestionConfig):
        self.config = config
        self.storage_client = storage.Client()
        self.embeddings = OpenAIEmbeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap
        )

        self._validate_gcs_buckets()

    def _validate_gcs_buckets(self):
        """
        Validate that required GCS buckets exist and are accessible
        """
        try:
            # Check raw docs bucket
            raw_bucket = self.storage_client.bucket(self.config.raw_docs_bucket)
            if not raw_bucket.exists():
                raise IngestionError(
                    f"Raw docs bucket does not exist: {self.config.raw_docs_bucket}"
                )

            # Check vector store bucket
            vector_bucket = self.storage_client.bucket(self.config.vector_store_bucket)
            if not vector_bucket.exists():
                raise IngestionError(
                    f"Vector store bucket does not exist: "
                    f"{self.config.vector_store_bucket}"
                )

            logger.info("GCS buckets validated successfully")

        except Exception as e:
            logger.error(f"GCS bucket validation failed: {e}")
            raise IngestionError(f"GCS bucket validation failed: {e}")

    def _log_faiss_details(self, db_path: str):
        """
        Log details about the created FAISS index for debugging
        """
        try:
            if os.path.exists(db_path):
                total_size = 0
                file_count = 0
                for root, dirs, files in os.walk(db_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        file_count += 1
                        logger.debug(f"FAISS file: {file} ({file_size} bytes)")

                logger.info(
                    f"FAISS index contains {file_count} files, "
                    f"total size: {total_size} bytes"
                )
            else:
                logger.warning(f"FAISS index directory not found: {db_path}")
        except Exception as e:
            logger.warning(f"Could not log FAISS details: {e}")

    @contextmanager
    def temporary_directory(self):
        """
        Context manager for temporary directory cleanup
        """
        temp_dir = tempfile.mkdtemp()
        try:
            yield temp_dir
        finally:
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"Cleaned up temporary directory: {temp_dir}")
                except PermissionError as e:
                    logger.warning(
                        f"Could not clean up temporary directory {temp_dir}: {e}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Unexpected error cleaning up temporary directory "
                        f"{temp_dir}: {e}"
                    )

    @retry.Retry(predicate=retry.if_transient_error)
    def download_from_gcs(self, bucket_name: str, local_dir: str) -> List[str]:
        """
        Download files from GCS with retry logic
        """
        logger.info(f"Downloading documents from gs://{bucket_name}")

        try:
            bucket = self.storage_client.bucket(bucket_name)
            blobs = list(bucket.list_blobs())

            if not blobs:
                logger.warning(f"No files found in bucket {bucket_name}")
                return []

            downloaded_files = []
            for blob in blobs:
                if not blob.name.lower().endswith(".pdf"):
                    logger.warning(f"Skipping non-PDF file: {blob.name}")
                    continue

                local_path = os.path.join(local_dir, blob.name)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                logger.info(f"Downloading {blob.name}")
                blob.download_to_filename(local_path)
                downloaded_files.append(local_path)

            logger.info(f"Downloaded {len(downloaded_files)} PDF files")
            return downloaded_files

        except Exception as e:
            logger.error(f"Failed to download from GCS: {e}")
            raise IngestionError(f"GCS download failed: {e}")

    def validate_pdf_files(self, file_paths: List[str]) -> List[str]:
        """
        Validate PDF files exist and are readable
        """
        valid_files = []
        for file_path in file_paths:
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                continue

            if os.path.getsize(file_path) == 0:
                logger.warning(f"Empty file: {file_path}")
                continue

            valid_files.append(file_path)

        logger.info(f"Validated {len(valid_files)} out of {len(file_paths)} files")
        return valid_files

    def process_documents(self, pdf_files: List[str]) -> List[Document]:
        """
        Process PDF files and create document chunks
        """
        if not pdf_files:
            raise IngestionError("No valid PDF files to process")

        logger.info(f"Processing {len(pdf_files)} documents")

        try:
            all_elements = parse_pdf_elements(pdf_files)
            logger.info(f"Parsed {len(all_elements)} elements from documents")

            all_chunks = []
            for element in all_elements:
                category = element.metadata.get("category")

                if category == "Table":
                    table_html = element.metadata.get("text_as_html", "")
                    if table_html:
                        all_chunks.append(
                            Document(
                                page_content=table_html,
                                metadata={
                                    "source": element.metadata.get("filename"),
                                    "page_number": element.metadata.get("page_number"),
                                    "content_type": "table",
                                    "ingestion_timestamp": time.time(),
                                },
                            )
                        )
                elif category in ["Title", "NarrativeText", "ListItem"]:
                    chunks = self.text_splitter.split_documents([element])
                    for chunk in chunks:
                        original_filename = Path(chunk.metadata.get("source", "")).name
                        gcs_source_path = (
                            f"gs://{self.config.raw_docs_bucket}/{original_filename}"
                        )
                        chunk.metadata["source"] = gcs_source_path
                        chunk.metadata["content_type"] = "text"
                        chunk.metadata["ingestion_timestamp"] = time.time()
                        all_chunks.append(chunk)

            logger.info(f"Created {len(all_chunks)} chunks")
            return all_chunks

        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            raise IngestionError(f"Document processing failed: {e}")

    def create_vector_store(self, chunks: List[Document], local_dir: str) -> str:
        """
        Create FAISS vector store from document chunks
        """
        if not chunks:
            raise IngestionError("No chunks provided for vector store creation")

        logger.info(f"Creating vector store from {len(chunks)} chunks")

        try:
            db = FAISS.from_documents(chunks, self.embeddings)
            db_path = os.path.join(local_dir, "faiss_index")
            db.save_local(db_path)

            # Validate that the FAISS index was created successfully
            if not os.path.exists(db_path):
                raise IngestionError(
                    f"FAISS index directory was not created at {db_path}"
                )

            # Check for required FAISS files
            required_files = ["index.faiss", "index.pkl"]
            for filename in required_files:
                file_path = os.path.join(db_path, filename)
                if not os.path.exists(file_path):
                    raise IngestionError(f"Required FAISS file not found: {file_path}")
                if os.path.getsize(file_path) == 0:
                    raise IngestionError(f"FAISS file is empty: {file_path}")

            logger.info(f"Vector store saved to {db_path}")

            # Log FAISS index details for debugging
            self._log_faiss_details(db_path)

            return db_path

        except Exception as e:
            logger.error(f"Vector store creation failed: {e}")
            raise IngestionError(f"Vector store creation failed: {e}")

    @retry.Retry(predicate=retry.if_transient_error)
    def upload_to_gcs(self, local_path: str, bucket_name: str, blob_name: str):
        """
        Upload vector store to GCS with retry logic
        """
        logger.info(f"Uploading vector store to gs://{bucket_name}/{blob_name}")

        try:
            bucket = self.storage_client.bucket(bucket_name)

            if os.path.isdir(local_path):
                # Upload FAISS index files individually to match expected structure
                faiss_files = ["index.faiss", "index.pkl"]
                for filename in faiss_files:
                    local_file_path = os.path.join(local_path, filename)
                    if os.path.exists(local_file_path):
                        blob_path = f"{blob_name}/{filename}"
                        blob = bucket.blob(blob_path)
                        blob.upload_from_filename(local_file_path)
                        logger.info(
                            f"Uploaded {filename} to gs://{bucket_name}/{blob_path}"
                        )
                    else:
                        logger.warning(f"FAISS file not found: {local_file_path}")
            else:
                blob = bucket.blob(blob_name)
                blob.upload_from_filename(local_path)

            logger.info(f"Successfully uploaded to gs://{bucket_name}/{blob_name}")

        except Exception as e:
            logger.error(f"Failed to upload to GCS: {e}")
            raise IngestionError(f"GCS upload failed: {e}")

    def run(self) -> Dict[str, Any]:
        """
        Execute the complete ingestion pipeline
        """
        start_time = time.time()
        stats = {
            "files_processed": 0,
            "chunks_created": 0,
            "processing_time": 0,
            "success": False,
        }

        try:
            with self.temporary_directory() as temp_dir:
                # Download documents
                pdf_files = self.download_from_gcs(
                    self.config.raw_docs_bucket, temp_dir
                )
                stats["files_processed"] = len(pdf_files)

                # Validate files
                valid_files = self.validate_pdf_files(pdf_files)

                # Process documents
                chunks = self.process_documents(valid_files)
                stats["chunks_created"] = len(chunks)

                # Create vector store
                vector_store_path = self.create_vector_store(chunks, temp_dir)

                # Upload to GCS
                try:
                    self.upload_to_gcs(
                        vector_store_path,
                        self.config.vector_store_bucket,
                        "faiss_index",
                    )
                except Exception as e:
                    logger.error(f"Failed to upload vector store to GCS: {e}")
                    stats["upload_failed"] = True
                    stats["upload_error"] = str(e)

                stats["success"] = True
                stats["processing_time"] = time.time() - start_time

                logger.info(
                    f"Ingestion completed successfully in"
                    f"{stats['processing_time']:.2f} seconds"
                )
                return stats

        except Exception as e:
            stats["processing_time"] = time.time() - start_time
            logger.error(
                f"Ingestion failed after {stats['processing_time']:.2f} seconds: {e}"
            )
            raise


def run_ingestion():
    """Main ingestion function with proper configuration and error handling"""
    load_dotenv()

    # Validate required environment variables
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        raise ValueError("GCP_PROJECT_ID environment variable is required")

    environment = os.getenv("ENVIRONMENT", "dev")
    # Create configuration
    config = IngestionConfig(
        project_id=project_id,
        raw_docs_bucket=f"{project_id}-{environment}-raw-docs",
        vector_store_bucket=f"{project_id}-{environment}-vector-stores",
    )

    # Create and run pipeline
    pipeline = DocumentIngestionPipeline(config)

    try:
        stats = pipeline.run()

        # Check if upload failed but processing succeeded
        if stats.get("upload_failed"):
            logger.warning(
                f"Ingestion completed but upload failed: {stats.get('upload_error')}"
            )
            logger.warning("Vector store was created locally but not uploaded to GCS")
        else:
            logger.info(f"Ingestion completed successfully: {stats}")

        return stats
    except IngestionError as e:
        logger.error(f"Ingestion failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during ingestion: {e}")
        raise


if __name__ == "__main__":
    try:
        run_ingestion()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        exit(1)
