from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from src.rag_handler import RAGSystem

# Ensures incoming data has a text field and is a string
class QueryRequest(BaseModel):
    text: str

# Defines the structure of the JSON response
class QueryResponse(BaseModel):
    answer: str
    source_documents: list[str]

app = FastAPI(title = "RAG API")

rag_system = RAGSystem()

# --- API Endpoint ---
@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    """
    Accepts a user's query and returns the RAG model's answer
    """
    response_data = rag_system.get_rag_response(request.text)
    return QueryResponse(**response_data)

@app.get("/health")
def health_check():
    """
    Returns a simple health check response
    """
    return {"status": "ok"}