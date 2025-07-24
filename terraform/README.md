# Terraform Infrastructure for RAG System

This directory contains the Terraform configuration for deploying the RAG system to Google Cloud Platform.

## Architecture Overview

The infrastructure includes:

- **Cloud Run Service**: Hosts the RAG API
- **GCS Buckets**: Store vector stores and raw documents
- **Secret Manager**: Stores OpenAI API key securely
- **Load Balancer**: Production-grade HTTPS endpoint (production only)
- **Monitoring**: Cloud Monitoring dashboard
- **IAM**: Service accounts with minimal required permissions

## Prerequisites

1. **Google Cloud SDK** installed and configured
2. **Terraform** >= 1.0 installed
3. **GCP Project** with billing enabled
4. **Artifact Registry** repository for Docker images
5. **Cloud KMS** keyring and key for state encryption (production)
6. **VPC Network** with connector (production)

## Quick Start

### 1. Initialize Terraform

```bash
cd terraform

# For development (local state)
terraform init

# For production (remote state with encryption)
cp backend.tf.example backend.tf
# Edit backend.tf with your project details
terraform init
```

### 2. Configure Variables

Copy the example configuration:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:

```hcl
gcp_project_id = "your-actual-project-id"
image_tag      = "latest"
environment    = "dev"
```

### 3. Plan and Apply

```bash
# Review the plan
terraform plan

# Apply the configuration
terraform apply
```

## Environment-Specific Deployments

### Development Environment

```bash
terraform apply -var="environment=dev" -var="image_tag=dev-latest"
```

### Production Environment

```bash
terraform apply \
  -var="environment=prod" \
  -var="image_tag=v1.0.0" \
  -var="domain_name=api.yourdomain.com" \
  -var="min_instances=1" \
  -var="max_instances=20"
```

## Security Features

### Service Account Permissions

The service account has minimal required permissions:
- `roles/secretmanager.secretAccessor` - Access to OpenAI API key
- `roles/storage.objectViewer` - Read access to GCS buckets

### Network Security

- **Development**: Public access enabled for testing
- **Production**: Load balancer with SSL certificate and domain validation

### Secret Management

- OpenAI API key stored in Secret Manager
- **Automatic rotation** every 30 days
- **Encrypted at rest** with CMEK
- **Audit logging** enabled
- **Version management** for rollback capability

## Monitoring and Observability

### Cloud Monitoring Dashboard

Automatically creates a dashboard with:
- Request count metrics
- Response time metrics
- Error rates
- Resource utilization

### Health Checks

- Startup probe: `/health` endpoint
- Liveness probe: Continuous health monitoring
- Readiness probe: Service availability

## Resource Management

### GCS Buckets

- **Vector Stores**: Long-term storage with versioning
- **Raw Documents**: Document storage with lifecycle policies
- **Uniform bucket-level access**: Enhanced security
- **Public access prevention**: Enforced blocking of public access
- **Encryption**: Customer-managed encryption keys
- **Lifecycle policies**: Automatic cleanup of old versions

### Cloud Run Configuration

- **Auto-scaling**: 0-10 instances (dev) or 1-20 instances (prod)
- **Resource limits**: Configurable CPU and memory
- **Health checks**: Startup, liveness, and readiness probes
- **Network security**: Private egress in production
- **VPC integration**: Secure networking for production

## Cost Optimization

### Development Environment

- `min_instances = 0`: Scale to zero when not in use
- `force_destroy = true`: Easy cleanup of resources

### Production Environment

- `min_instances = 1`: Always available
- `force_destroy = false`: Prevent accidental deletion
- Load balancer for high availability

## Troubleshooting

### Common Issues

1. **API Not Enabled**
   ```bash
   gcloud services enable run.googleapis.com
   gcloud services enable secretmanager.googleapis.com
   ```

2. **Permission Denied**
   ```bash
   gcloud auth application-default login
   gcloud config set project YOUR_PROJECT_ID
   ```

3. **Image Not Found**
   - Ensure Docker image is pushed to Artifact Registry
   - Verify image tag matches `image_tag` variable

### Useful Commands

```bash
# View outputs
terraform output

# Check service status
gcloud run services describe rag-api-dev --region=us-central1

# View logs
gcloud logging read "resource.type=cloud_run_revision" --limit=50

# Test health endpoint
curl $(terraform output -raw service_url)/health
```

## Cleanup

### Development Environment

```bash
terraform destroy -var="environment=dev"
```

### Production Environment

```bash
# Be careful - this will delete all resources
terraform destroy -var="environment=prod"
```

## Best Practices

1. **Use Workspaces**: Separate state for different environments
2. **Version Control**: Commit Terraform files to version control
3. **Review Plans**: Always review `terraform plan` before applying
4. **Backup State**: Use remote state storage with locking and encryption
5. **Tag Resources**: Use consistent labeling for cost tracking
6. **Secret Rotation**: Enable automatic secret rotation
7. **Network Security**: Use private networking in production
8. **Monitoring**: Set up alerts for critical metrics
9. **Resource Validation**: Use input validation for all variables
10. **Provider Pinning**: Pin provider versions to tested releases

## Variables Reference

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `gcp_project_id` | string | - | GCP Project ID (required) |
| `image_tag` | string | - | Docker image tag (required) |
| `environment` | string | "dev" | Environment name |
| `gcp_region` | string | "us-central1" | GCP region |
| `openai_model` | string | "gpt-4" | OpenAI model to use |
| `max_retrieval_docs` | number | 5 | Max documents to retrieve |
| `min_instances` | number | 0 | Min Cloud Run instances |
| `max_instances` | number | 10 | Max Cloud Run instances |
| `domain_name` | string | "" | Domain for SSL (prod only) |

## Outputs

After successful deployment, Terraform will output:

- `service_url`: Public URL of the API
- `cloud_run_url`: Direct Cloud Run URL
- `vector_stores_bucket`: GCS bucket for vector stores
- `raw_documents_bucket`: GCS bucket for documents
- `monitoring_dashboard_url`: Cloud Monitoring dashboard
- `health_check_url`: Health check endpoint
- `system_info_url`: System information endpoint 