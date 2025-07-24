# --- Service URLs ---
output "service_url" {
  value       = var.environment == "prod" ? "https://${var.domain_name}" : google_cloud_run_v2_service.rag_api.uri
  description = "The public URL of the deployed RAG API service"
}

output "cloud_run_url" {
  value       = google_cloud_run_v2_service.rag_api.uri
  description = "The Cloud Run service URL"
}

# --- Load Balancer Information (Production Only) ---
output "load_balancer_ip" {
  value       = var.environment == "prod" ? google_compute_global_address.rag_ip[0].address : null
  description = "The IP address of the load balancer (production only)"
}

# --- Storage Information ---
output "vector_stores_bucket" {
  value       = google_storage_bucket.vector_stores.name
  description = "GCS bucket name for vector stores"
}

output "raw_documents_bucket" {
  value       = google_storage_bucket.raw_documents.name
  description = "GCS bucket name for raw documents"
}

output "bucket_prefix" {
  value       = local.prefix
  description = "Prefix used for bucket naming"
}

# --- Service Account Information ---
output "service_account_email" {
  value       = google_service_account.rag_service_account.email
  description = "Email of the service account used by Cloud Run"
}

output "service_account_name" {
  value       = google_service_account.rag_service_account.name
  description = "Name of the service account used by Cloud Run"
}

# --- Secret Information ---
output "openai_secret_id" {
  value       = google_secret_manager_secret.openai_api_key.secret_id
  description = "Secret Manager ID for OpenAI API key"
}

# --- Monitoring Information ---
output "monitoring_dashboard_url" {
  value       = "https://console.cloud.google.com/monitoring/dashboards/custom/${google_monitoring_dashboard.rag_dashboard.id}?project=${var.gcp_project_id}"
  description = "URL to the monitoring dashboard"
}

# --- Environment Configuration ---
output "environment" {
  value       = var.environment
  description = "Current environment"
}

output "gcp_region" {
  value       = var.gcp_region
  description = "GCP region where resources are deployed"
}

# --- Application Configuration ---
output "openai_model" {
  value       = var.openai_model
  description = "OpenAI model being used"
}

output "max_retrieval_docs" {
  value       = var.max_retrieval_docs
  description = "Maximum number of documents retrieved for RAG"
}

# --- Resource Counts ---
output "enabled_apis_count" {
  value       = length(google_project_service.required_apis)
  description = "Number of APIs enabled"
}

output "enabled_apis" {
  value       = [for api in google_project_service.required_apis : api.service]
  description = "List of enabled APIs"
}

# --- Security Information ---
output "public_access_enabled" {
  value       = var.environment == "dev"
  description = "Whether public access is enabled (dev only)"
}

# --- Health Check Endpoints ---
output "health_check_url" {
  value       = "${google_cloud_run_v2_service.rag_api.uri}/health"
  description = "URL for health check endpoint"
}

output "system_info_url" {
  value       = "${google_cloud_run_v2_service.rag_api.uri}/system-info"
  description = "URL for system info endpoint"
}

# --- Resource Labels ---
output "resource_labels" {
  value       = var.resource_labels
  description = "Labels applied to all resources"
}