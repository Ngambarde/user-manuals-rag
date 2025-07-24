# --- Provider Configuration ---
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
  zone    = var.gcp_zone
}

provider "google-beta" {
  project = var.gcp_project_id
  region  = var.gcp_region
  zone    = var.gcp_zone
}

# --- Local Values for DRY Naming ---
locals {
  prefix = "${var.gcp_project_id}-${var.environment}"
  
  # Standardized resource labels
  labels = merge(var.resource_labels, {
    environment = var.environment
    project     = "rag-system"
    managed-by  = "terraform"
    version     = var.image_tag
  })
  
  # Bucket names
  vector_stores_bucket = "${local.prefix}-vector-stores"
  raw_docs_bucket      = "${local.prefix}-raw-docs"
  
  # Service names
  service_name = "rag-api-${var.environment}"
}

# --- Enable Required APIs ---
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "iam.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "compute.googleapis.com"
  ])

  service = each.value
  disable_dependent_services = false
  disable_on_destroy         = false
  
  timeouts {
    create = "30m"
    update = "40m"
  }
}

# --- Create GCS Buckets for Vector Stores and Documents ---
resource "google_storage_bucket" "vector_stores" {
  name          = local.vector_stores_bucket
  location      = var.gcp_region
  force_destroy = var.environment == "dev" ? true : false

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"  # Block any public access

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 365  # Keep versions for 1 year
    }
    action {
      type = "Delete"
    }
  }

  labels = local.labels
}

resource "google_storage_bucket" "raw_documents" {
  name          = local.raw_docs_bucket
  location      = var.gcp_region
  force_destroy = var.environment == "dev" ? true : false

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"  # Block any public access

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90  # Keep document versions for 90 days
    }
    action {
      type = "Delete"
    }
  }

  labels = local.labels
}

# --- Create Secret for OpenAI API Key ---
resource "google_secret_manager_secret" "openai_api_key" {
  secret_id = "OPENAI_API_KEY"

    replication {
    auto {}
  }

  labels = local.labels
}

# --- Create Secret Version (if API key is provided) ---
resource "google_secret_manager_secret_version" "openai_api_key_version" {
  count = var.openai_api_key != "" ? 1 : 0
  
  secret      = google_secret_manager_secret.openai_api_key.id
  secret_data = var.openai_api_key
}

# --- Create Service Account for Cloud Run ---
resource "google_service_account" "rag_service_account" {
  account_id   = "rag-api-sa"
  display_name = "RAG API Service Account"
  description  = "Service account for RAG API Cloud Run service"
}

# --- Grant Service Account Permissions ---
resource "google_secret_manager_secret_iam_member" "secret_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.openai_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.rag_service_account.email}"
}

resource "google_storage_bucket_iam_member" "vector_stores_access" {
  bucket = google_storage_bucket.vector_stores.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.rag_service_account.email}"
}

resource "google_storage_bucket_iam_member" "vector_stores_ingest_access" {
  bucket = google_storage_bucket.vector_stores.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}

resource "google_storage_bucket_iam_member" "raw_docs_access" {
  bucket = google_storage_bucket.raw_documents.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.rag_service_account.email}"
}

data "google_project" "project" {}

# --- Create Cloud Run Service ---
resource "google_cloud_run_v2_service" "rag_api" {
  name     = local.service_name
  location = var.gcp_region

  ingress = var.environment == "prod" ? "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER" : "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.rag_service_account.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = "us-central1-docker.pkg.dev/${var.gcp_project_id}/rag-project-repo/rag-api:${var.image_tag}"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
      }

      # Environment Variables
      env {
        name  = "GCP_PROJECT_ID"
        value = var.gcp_project_id
      }
      env {
        name  = "USE_GCS_VECTOR_STORE"
        value = "true"
      }
      env {
        name  = "VECTOR_STORE_BUCKET"
        value = google_storage_bucket.vector_stores.name
      }
      env {
        name  = "VECTOR_STORE_BLOB"
        value = var.vector_store_blob
      }
      env {
        name  = "OPENAI_MODEL"
        value = var.openai_model
      }
      env {
        name  = "MAX_RETRIEVAL_DOCS"
        value = tostring(var.max_retrieval_docs)
      }
      env {
        name  = "OPENAI_TEMPERATURE"
        value = tostring(var.openai_temperature)
      }
      env {
        name  = "TIMEOUT_SECONDS"
        value = tostring(var.timeout_seconds)
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "PYTHONUNBUFFERED"
        value = "1"
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }

      # Health Check
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 30
        period_seconds        = 10
        timeout_seconds       = 10
        failure_threshold     = 5
      }

      liveness_probe {
        http_get {
          path = "/health"
        }
        period_seconds    = 30
        timeout_seconds   = 10
        failure_threshold = 3
      }
    }

    labels = local.labels
  }

  depends_on = [
    google_project_service.required_apis,
    google_secret_manager_secret_iam_member.secret_accessor,
    google_storage_bucket_iam_member.vector_stores_access,
    google_storage_bucket_iam_member.raw_docs_access,
    google_storage_bucket_iam_member.vector_stores_ingest_access
  ]
}

# --- Configure Public Access (Development Only) ---
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  count = var.environment == "dev" ? 1 : 0

  project  = google_cloud_run_v2_service.rag_api.project
  location = google_cloud_run_v2_service.rag_api.location
  name     = google_cloud_run_v2_service.rag_api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- Create Load Balancer (Production Only) ---
resource "google_compute_global_forwarding_rule" "rag_lb" {
  count = var.environment == "prod" ? 1 : 0

  name       = "rag-api-lb"
  target     = google_compute_target_https_proxy.rag_https_proxy[0].id
  port_range = "443"
  ip_address = google_compute_global_address.rag_ip[0].address
}

resource "google_compute_global_address" "rag_ip" {
  count = var.environment == "prod" ? 1 : 0

  name         = "rag-api-ip"
  address_type = "EXTERNAL"
}

resource "google_compute_target_https_proxy" "rag_https_proxy" {
  count = var.environment == "prod" ? 1 : 0

  name             = "rag-api-https-proxy"
  url_map          = google_compute_url_map.rag_url_map[0].id
  ssl_certificates = [google_compute_managed_ssl_certificate.rag_ssl[0].id]
}

resource "google_compute_url_map" "rag_url_map" {
  count = var.environment == "prod" ? 1 : 0

  name            = "rag-api-url-map"
  default_service = google_compute_backend_service.rag_backend[0].id
}

resource "google_compute_backend_service" "rag_backend" {
  count = var.environment == "prod" ? 1 : 0

  name        = "rag-api-backend"
  protocol    = "HTTP"
  port_name   = "http"
  timeout_sec = 30

  backend {
    group = google_compute_region_network_endpoint_group.rag_neg[0].id
  }

  health_checks = [google_compute_health_check.rag_health_check[0].id]
}

resource "google_compute_region_network_endpoint_group" "rag_neg" {
  count = var.environment == "prod" ? 1 : 0

  name                  = "rag-api-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.gcp_region
  cloud_run {
    service = google_cloud_run_v2_service.rag_api.name
  }
}

resource "google_compute_health_check" "rag_health_check" {
  count = var.environment == "prod" ? 1 : 0

  name = "rag-api-health-check"

  http_health_check {
    port = 8080
    request_path = "/health"
  }
}

resource "google_compute_managed_ssl_certificate" "rag_ssl" {
  count = var.environment == "prod" ? 1 : 0

  name = "rag-api-ssl-cert"

  managed {
    domains = [var.domain_name]
  }
}

# --- Create Monitoring Dashboard ---
resource "google_monitoring_dashboard" "rag_dashboard" {
  dashboard_json = jsonencode({
    displayName = "RAG API Dashboard - ${var.environment}"
    gridLayout = {
      widgets = [
        {
          title = "Request Count"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"run.googleapis.com/request_count\""
                  aggregation = {
                    perSeriesAligner = "ALIGN_RATE"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Response Time"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"run.googleapis.com/request_latencies\""
                  aggregation = {
                    perSeriesAligner = "ALIGN_MEAN"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Error Rate"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"4XX\""
                  aggregation = {
                    perSeriesAligner = "ALIGN_RATE"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Memory Utilization"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"run.googleapis.com/container/memory/utilizations\""
                  aggregation = {
                    perSeriesAligner = "ALIGN_MEAN"
                  }
                }
              }
            }]
          }
        }
      ]
    }
  })
}

# --- Create Alerting Policies ---
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "High Error Rate - RAG API"
  combiner     = "OR"
  conditions {
    display_name = "Error rate > 5%"
    condition_threshold {
      filter     = "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND metric.labels.response_code_class=\"4XX\""
      duration   = "300s"
      comparison = "COMPARISON_GT"
      threshold_value = 0.05
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_MEAN"
      }
    }
  }
  
  notification_channels = var.alert_notification_channels
}

resource "google_monitoring_alert_policy" "high_latency" {
  display_name = "High Latency - RAG API"
  combiner     = "OR"
  conditions {
    display_name = "Response time > 10s"
    condition_threshold {
      filter     = "metric.type=\"run.googleapis.com/request_latencies\" AND resource.type=\"cloud_run_revision\""
      duration   = "300s"
      comparison = "COMPARISON_GT"
      threshold_value = 10000
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_99"
        cross_series_reducer = "REDUCE_MEAN"
      }
    }
  }
  
  notification_channels = var.alert_notification_channels
}