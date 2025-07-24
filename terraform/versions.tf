terraform {
  required_version = ">= 1.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.30"
    }
  }

  # Backend configuration - will be configured per environment
  # backend "gcs" {
  #   bucket          = "PROJECT_ID-terraform-state"
  #   prefix          = "rag-system/ENVIRONMENT"
  #   encryption_key  = "projects/PROJECT_ID/locations/REGION/keyRings/terraform-keyring/cryptoKeys/terraform-key"
  # }
} 