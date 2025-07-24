from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from functools import lru_cache
from src.rag_handler import RAGSystem, RAGError
import logging

logger = logging.getLogger(__name__)


# Ensures incoming data has a text field and is a string
class QueryRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Query text cannot be empty")


# Defines the structure of the JSON response
class QueryResponse(BaseModel):
    answer: str
    source_documents: List[str]
    retrieved_context: Optional[List[str]] = None
    stats: Optional[Dict[str, Any]] = None


app = FastAPI(title="RAG API")


@lru_cache()
def get_rag_system() -> RAGSystem:
    """
    Get or initialize the RAG system using dependency injection
    """
    try:
        rag_system = RAGSystem()
        logger.info("RAG system initialized successfully")
        return rag_system
    except Exception as e:
        logger.error(f"Failed to initialize RAG system: {e}")
        raise HTTPException(status_code=503, detail="RAG system initialization failed")


# --- API Endpoint ---
@app.post("/query", response_model=QueryResponse)
async def handle_query(
    request: QueryRequest, rag_system: RAGSystem = Depends(get_rag_system)
):
    """
    Accepts a user's query and returns the RAG model's answer
    """
    # Additional validation for whitespace-only queries
    if not request.text.strip():
        raise HTTPException(
            status_code=400, detail="Query text cannot be empty or whitespace only"
        )

    try:
        response_data = rag_system.get_rag_response(request.text)

        # Extract stats if present
        stats = response_data.get("stats", {})
        retrieved_context = response_data.get("retrieved_context", [])

        return QueryResponse(
            answer=response_data["answer"],
            source_documents=response_data["source_documents"],
            retrieved_context=retrieved_context,
            stats=stats,
        )

    except RAGError as e:
        logger.error(f"RAG processing error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during query processing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
def health_check(rag_system: RAGSystem = Depends(get_rag_system)):
    """
    Returns a health check response
    """
    try:
        health_status = rag_system.health_check()
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


@app.get("/system-info")
def get_system_info(rag_system: RAGSystem = Depends(get_rag_system)):
    """
    Returns system information and configuration
    """
    try:
        return rag_system.get_system_info()
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve system information"
        )
