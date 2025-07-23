# Equipment RAG Project

This project is a Retrieval-Augmented Generation (RAG) system to assist in troubleshooting, setup, and information retrieval for equipment based on user manuals and work instructions.

## Features

- **Document Ingestion**: Process PDF manuals and create vector embeddings
- **GCS Integration**: Store and retrieve vector stores from Google Cloud Storage
- **FastAPI API**: RESTful API for querying the RAG system
- **Comprehensive Testing**: Full test suite with mocking and integration tests
- **Production Ready**: Error handling, logging, and monitoring
- **Docker Support**: Containerized deployment with multi-stage builds

## Quick Start with Docker

### 1. Environment Configuration

Create a `.env` file in the root of the project:

```bash
# Required
OPENAI_API_KEY="your_api_key_here"
GCP_PROJECT_ID="your_gcp_project_id"

# Optional - Vector Store Configuration
USE_GCS_VECTOR_STORE="false"  # Set to "true" to use GCS
VECTOR_STORE_BUCKET="your-bucket-name"  # Auto-constructed if not specified
VECTOR_STORE_BLOB="faiss_index"  # Default blob name
DB_FAISS_PATH="vector_store"  # Local path (when not using GCS)

# Optional - Model Configuration
OPENAI_MODEL="gpt-4.1-nano-2025-04-14"
MAX_RETRIEVAL_DOCS="2"
OPENAI_TEMPERATURE="0.0"
MAX_RETRIES="3"
TIMEOUT_SECONDS="30"
```

### 2. Build and Run with Docker

```bash
# Build the Docker image
docker build -t equipment-rag .

# Run the container
docker run -p 8000:8080 --env-file .env equipment-rag
```

The API will be available at `http://localhost:8000`

### 3. Docker Compose (Recommended)

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  rag-api:
    build: .
    ports:
      - "8000:8080"
    env_file:
      - .env
    volumes:
      - ./documents:/app/documents:ro  # Mount documents for ingestion
      - ./vector_store:/app/vector_store  # Persist local vector store
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Run with:
```bash
docker-compose up -d
```

## Local Development Setup

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. GCP Setup (Optional)

If using GCS for vector store storage:

1. **Enable APIs**:
   ```bash
   gcloud services enable storage.googleapis.com
   gcloud services enable secretmanager.googleapis.com
   ```

2. **Set up authentication**:
   ```bash
   gcloud auth application-default login
   ```

3. **Create buckets** (if not using auto-construction):
   ```bash
   gsutil mb gs://your-project-id-raw-docs
   gsutil mb gs://your-project-id-vector-stores
   ```

## Usage

### Document Ingestion

The ingestion process downloads PDFs from GCS, processes them, and uploads the vector store back to GCS.

#### With Docker:
```bash
# Run ingestion in a separate container
docker run --env-file .env equipment-rag python src/ingest.py
```

#### Local Development:
```bash
python src/ingest.py
```

**Ingestion Flow**:
1. Downloads PDFs from `{project_id}-raw-docs` bucket
2. Processes documents using LangChain and FAISS
3. Creates vector embeddings and stores them
4. Uploads vector store to `{project_id}-vector-stores` bucket

### Querying the System

#### Option 1: FastAPI Server

**Docker:**
```bash
# Server is already running from docker run command
curl -X POST "http://localhost:8000/query" \
     -H "Content-Type: application/json" \
     -d '{"text": "How do I troubleshoot the equipment?"}'
```

**Local Development:**
```bash
# Start the server
uvicorn src.main:app --reload

# Query via API
curl -X POST "http://localhost:8000/query" \
     -H "Content-Type: application/json" \
     -d '{"text": "How do I troubleshoot the equipment?"}'
```

#### Option 2: Direct Script (Local Only)
```bash
python src/query.py
```

#### Option 3: Health Check
```bash
curl http://localhost:8000/health
```

#### Option 4: System Info
```bash
curl http://localhost:8000/system-info
```

## Vector Store Configuration

### Local Storage (Default)
- Vector stores are stored locally in the `vector_store/` directory
- Suitable for development and single-instance deployments
- Set `USE_GCS_VECTOR_STORE=false` or omit the variable

### Google Cloud Storage
- Vector stores are stored in GCS buckets
- Suitable for production and multi-instance deployments
- Set `USE_GCS_VECTOR_STORE=true`

**Automatic Bucket Naming**:
- If `VECTOR_STORE_BUCKET` is not specified, it defaults to `{project_id}-vector-stores`
- Example: If `GCP_PROJECT_ID=my-project`, bucket becomes `my-project-vector-stores`

**Manual Bucket Configuration**:
```bash
USE_GCS_VECTOR_STORE="true"
VECTOR_STORE_BUCKET="my-custom-bucket"
VECTOR_STORE_BLOB="my-faiss-index"
```

## Testing

### With Docker:
```bash
# Run tests in container
docker run --env-file .env equipment-rag pytest

# Run with coverage
docker run --env-file .env equipment-rag pytest --cov=src
```

### Local Development:
```bash
# Run all tests
pytest

# Run specific test categories
pytest -m unit      # Unit tests only
pytest -m integration  # Integration tests only
pytest -m "not slow"   # Skip slow tests

# Run with coverage
pytest --cov=src
```

## Docker Development

### Development with Docker

For development with hot reloading:

```bash
# Build development image
docker build -t equipment-rag:dev .

# Run with volume mounts for live code changes
docker run -p 8000:8080 --env-file .env \
  -v $(pwd)/src:/app/src \
  -v $(pwd)/tests:/app/tests \
  equipment-rag:dev uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

### Docker Compose for Development

Create `docker-compose.dev.yml`:

```yaml
version: '3.8'

services:
  rag-api-dev:
    build: .
    ports:
      - "8000:8080"
    env_file:
      - .env
    volumes:
      - ./src:/app/src
      - ./tests:/app/tests
      - ./documents:/app/documents:ro
      - ./vector_store:/app/vector_store
    command: uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
    restart: unless-stopped
```

Run with:
```bash
docker-compose -f docker-compose.dev.yml up
```

## Architecture

### Components
- **`src/ingest.py`**: Document processing and vector store creation
- **`src/rag_handler.py`**: Core RAG system with GCS support
- **`src/main.py`**: FastAPI application with dependency injection
- **`tests/`**: Comprehensive test suite with mocking
- **`Dockerfile`**: Multi-stage Docker build for production deployment

### Data Flow
1. **Ingestion**: PDFs → Processing → Vector Store → GCS
2. **Query**: User Query → Vector Search → LLM → Response
3. **Storage**: Local (dev) or GCS (prod) vector stores

## Production Deployment

### Environment Variables
```bash
# Production settings
USE_GCS_VECTOR_STORE="true"
OPENAI_MODEL="gpt-4"  # Use production model
MAX_RETRIEVAL_DOCS="5"  # Increase for better results
TIMEOUT_SECONDS="60"  # Increase for complex queries
```

### Docker Production Deployment

```bash
# Build production image
docker build -t equipment-rag:prod .

# Run with production settings
docker run -d \
  --name rag-production \
  -p 8000:8080 \
  --env-file .env.prod \
  --restart unless-stopped \
  equipment-rag:prod
```

### Kubernetes Deployment

Create `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: equipment-rag
spec:
  replicas: 3
  selector:
    matchLabels:
      app: equipment-rag
  template:
    metadata:
      labels:
        app: equipment-rag
    spec:
      containers:
      - name: rag-api
        image: equipment-rag:prod
        ports:
        - containerPort: 8080
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: rag-secrets
              key: openai-api-key
        - name: GCP_PROJECT_ID
          valueFrom:
            configMapKeyRef:
              name: rag-config
              key: gcp-project-id
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: equipment-rag-service
spec:
  selector:
    app: equipment-rag
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer
```

## Troubleshooting

### Common Issues

1. **Docker Build Issues**:
   ```bash
   # Clean build cache
   docker system prune -a
   docker build --no-cache -t equipment-rag .
   ```

2. **GCS Authentication Error**:
   ```bash
   # For local development
   gcloud auth application-default login
   
   # For Docker, ensure service account key is mounted
   docker run -v /path/to/key.json:/app/key.json --env-file .env equipment-rag
   ```

3. **Vector Store Not Found**:
   - Check if ingestion completed successfully
   - Verify bucket permissions
   - Ensure correct blob path
   - Check volume mounts in Docker

4. **OpenAI API Errors**:
   - Verify API key is valid
   - Check rate limits
   - Ensure sufficient credits

### Logs

**Docker Logs**:
```bash
# View container logs
docker logs <container_name>

# Follow logs in real-time
docker logs -f <container_name>
```

**Application Logs**:
The system provides comprehensive logging:
- Ingestion logs: Document processing status
- Query logs: Request/response details
- Error logs: Detailed error information
- Performance logs: Timing and metrics

### Health Checks

```bash
# Check API health
curl http://localhost:8000/health

# Check system info
curl http://localhost:8000/system-info
```
