# --- Required Variables ---
variable "gcp_project_id" {
  type        = string
  description = "The GCP project ID to deploy resources into"
  
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.gcp_project_id))
    error_message = "Project ID must be 6-30 characters long, start with a letter, and contain only lowercase letters, numbers, and hyphens."
  }
}

variable "image_tag" {
  type        = string
  description = "The Docker image tag (Git commit SHA) to deploy"
  
  validation {
    condition     = length(var.image_tag) > 0
    error_message = "Image tag cannot be empty."
  }
}

# --- Secret Management ---
variable "openai_api_key" {
  type        = string
  description = "OpenAI API key to store in Secret Manager (leave empty to manage manually)"
  default     = ""
  sensitive   = true
  
  validation {
    condition     = var.openai_api_key == "" || can(regex("^sk-[a-zA-Z0-9]{32,}$", var.openai_api_key))
    error_message = "OpenAI API key must start with 'sk-' and be at least 32 characters long."
  }
}

# --- Environment Configuration ---
variable "environment" {
  type        = string
  description = "Environment name (dev, staging, prod)"
  default     = "dev"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

# --- GCP Region and Zone ---
variable "gcp_region" {
  type        = string
  description = "GCP region for resource deployment"
  default     = "us-central1"
  
  # Loosened regex to support multi-digit regions
  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]+$", var.gcp_region))
    error_message = "Region must be in the format: region-zone (e.g., us-central1, europe-north1)."
  }
}

variable "gcp_zone" {
  type        = string
  description = "GCP zone for zonal resources"
  default     = "us-central1-a"
  
  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]+-[a-z]$", var.gcp_zone))
    error_message = "Zone must be in the format: region-zone-zone (e.g., us-central1-a)."
  }
}

# --- Application Configuration ---
variable "openai_model" {
  type        = string
  description = "OpenAI model to use for RAG responses"
  default     = "gpt-4"
  
  validation {
    condition     = contains(["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"], var.openai_model)
    error_message = "OpenAI model must be one of: gpt-3.5-turbo, gpt-4, gpt-4-turbo, gpt-4o."
  }
}

variable "max_retrieval_docs" {
  type        = number
  description = "Maximum number of documents to retrieve for RAG"
  default     = 5
  
  validation {
    condition     = var.max_retrieval_docs >= 1 && var.max_retrieval_docs <= 20
    error_message = "Max retrieval docs must be between 1 and 20."
  }
}

variable "openai_temperature" {
  type        = number
  description = "Temperature for OpenAI model responses"
  default     = 0.0
  
  validation {
    condition     = var.openai_temperature >= 0.0 && var.openai_temperature <= 2.0
    error_message = "Temperature must be between 0.0 and 2.0."
  }
}

variable "timeout_seconds" {
  type        = number
  description = "Timeout for API requests in seconds"
  default     = 60
  
  validation {
    condition     = var.timeout_seconds >= 10 && var.timeout_seconds <= 300
    error_message = "Timeout must be between 10 and 300 seconds."
  }
}

variable "vector_store_blob" {
  type        = string
  description = "Blob name for vector store in GCS"
  default     = "faiss_index"
  
  validation {
    condition     = length(var.vector_store_blob) > 0
    error_message = "Vector store blob name cannot be empty."
  }
}

# --- Cloud Run Configuration ---
variable "min_instances" {
  type        = number
  description = "Minimum number of Cloud Run instances"
  default     = 0
  
  validation {
    condition     = var.min_instances >= 0 && var.min_instances <= 10
    error_message = "Min instances must be between 0 and 10."
  }
}

variable "max_instances" {
  type        = number
  description = "Maximum number of Cloud Run instances"
  default     = 10
  
  validation {
    condition     = var.max_instances >= 1 && var.max_instances <= 100
    error_message = "Max instances must be between 1 and 100."
  }
  
  validation {
    condition     = var.max_instances >= var.min_instances
    error_message = "Max instances must be greater than or equal to min instances."
  }
}

variable "cpu_request" {
  type        = string
  description = "CPU request for Cloud Run container"
  default     = "1000m"
  
  validation {
    condition     = can(regex("^[0-9]+m$", var.cpu_request))
    error_message = "CPU request must be in format: 1000m."
  }
}

variable "cpu_limit" {
  type        = string
  description = "CPU limit for Cloud Run container"
  default     = "2000m"
  
  validation {
    condition     = can(regex("^[0-9]+m$", var.cpu_limit))
    error_message = "CPU limit must be in format: 2000m."
  }
}

variable "memory_request" {
  type        = string
  description = "Memory request for Cloud Run container"
  default     = "1Gi"
  
  validation {
    condition     = can(regex("^[0-9]+[MG]i$", var.memory_request))
    error_message = "Memory request must be in format: 1Gi or 1000Mi."
  }
}

variable "memory_limit" {
  type        = string
  description = "Memory limit for Cloud Run container"
  default     = "2Gi"
  
  validation {
    condition     = can(regex("^[0-9]+[MG]i$", var.memory_limit))
    error_message = "Memory limit must be in format: 2Gi or 2000Mi."
  }
}

# --- Production Configuration ---
variable "domain_name" {
  type        = string
  description = "Domain name for SSL certificate (production only)"
  default     = ""
  
  validation {
    condition     = var.domain_name == "" || can(regex("^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\\.[a-zA-Z]{2,}$", var.domain_name))
    error_message = "Domain name must be a valid domain format."
  }
  
  validation {
    condition     = var.environment != "prod" || var.domain_name != ""
    error_message = "Domain name is required for production environment."
  }
}

variable "vpc_connector" {
  type        = string
  description = "VPC connector for private networking (production only)"
  default     = ""
  
  validation {
    condition     = var.vpc_connector == "" || can(regex("^projects/[^/]+/locations/[^/]+/connectors/[^/]+$", var.vpc_connector))
    error_message = "VPC connector must be in format: projects/PROJECT/locations/REGION/connectors/NAME."
  }
}

# --- Monitoring and Alerting ---
variable "alert_notification_channels" {
  type        = list(string)
  description = "List of notification channel names for alerts"
  default     = []
  
  validation {
    condition = alltrue([
      for channel in var.alert_notification_channels : 
      length(channel) > 0
    ])
    error_message = "Notification channel names cannot be empty."
  }
}

# --- Resource Labels ---
variable "resource_labels" {
  type        = map(string)
  description = "Labels to apply to all resources"
  default = {
    environment = "dev"
    project     = "rag-system"
    managed-by  = "terraform"
  }
  
  validation {
    condition = alltrue([
      for key, value in var.resource_labels : 
      length(key) <= 63 && length(value) <= 63
    ])
    error_message = "Label keys and values must be 63 characters or less."
  }
}