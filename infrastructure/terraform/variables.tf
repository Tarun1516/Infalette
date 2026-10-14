# =============================================================================
# Root variables — no hardcoded secrets. Use TF_VAR_, .tfvars, or SSM.
# =============================================================================

variable "env" {
  description = "Deployment environment (development | staging | production)"
  type        = string
  default     = "development"
  validation {
    condition     = contains(["development", "staging", "production"], var.env)
    error_message = "env must be development, staging, or production."
  }
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "vpc_cidr" {
  description = "CIDR for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "db_instance_class" {
  description = "RDS instance class for Postgres"
  type        = string
  default     = "db.t3.micro"
}

variable "redis_node_type" {
  description = "ElastiCache node type for Redis"
  type        = string
  default     = "cache.t3.micro"
}

variable "domain" {
  description = "Root domain for Route53/CloudFront (e.g. infalette.com). Leave empty to skip DNS."
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for CloudFront (must be in us-east-1). Leave empty for CloudFront default domain."
  type        = string
  default     = null
}

# --- Database credentials (sensitive) ---

variable "db_username" {
  description = "RDS master username"
  type        = string
  default     = "infalette"
  sensitive   = true
}

variable "db_password" {
  description = "RDS master password — pass via TF_VAR_db_password or Secrets Manager"
  type        = string
  default     = null
  sensitive   = true
}

variable "db_name" {
  description = "Initial database name"
  type        = string
  default     = "infalette"
}

# --- ECS ---

variable "api_image" {
  description = "Docker image for API (e.g. ghcr.io/org/infalette/api:latest)"
  type        = string
  default     = "ghcr.io/infalette/api:latest"
}

variable "workers_image" {
  description = "Docker image for workers (Celery)"
  type        = string
  default     = "ghcr.io/infalette/workers:latest"
}

variable "desired_count" {
  description = "Desired ECS tasks for API service"
  type        = number
  default     = 2
}

# --- Observability ---

variable "sentry_dsn" {
  description = "Sentry DSN (optional)"
  type        = string
  default     = null
  sensitive   = true
}

variable "otel_endpoint" {
  description = "OTEL OTLP endpoint (e.g. https://otel-collector:4317)"
  type        = string
  default     = null
}
