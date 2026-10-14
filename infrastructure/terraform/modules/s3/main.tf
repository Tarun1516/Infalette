# =============================================================================
# Module: s3 — Media bucket + CloudFront origin helpers
# Bucket is private, encrypted, versioned, with CORS for direct uploads.
# CloudFront OAC is configured in the cloudfront module; this module outputs
# bucket attributes needed there. No hardcoded secrets.
# =============================================================================

variable "env" {
  type        = string
  description = "Environment name"
}

variable "region" {
  type        = string
  description = "AWS region"
}

variable "domain" {
  type        = string
  description = "Root domain (optional)"
  default     = ""
}

variable "bucket_name" {
  type        = string
  description = "Override bucket name; defaults to infalette-media-{env}-{account_id}"
  default     = null
}

variable "force_destroy" {
  type        = bool
  default     = false
  description = "Allow bucket destroy even if not empty (false in prod)"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  bucket_name = coalesce(var.bucket_name, "infalette-media-${var.env}-${data.aws_caller_identity.current.account_id}")
}

resource "aws_s3_bucket" "media" {
  bucket        = local.bucket_name
  force_destroy = var.force_destroy

  tags = {
    Name        = local.bucket_name
    Environment = var.env
  }
}

resource "aws_s3_bucket_versioning" "media" {
  bucket = aws_s3_bucket.media.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms" # use KMS; falls back to AES256 if no key
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket = aws_s3_bucket.media.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_cors_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "DELETE", "HEAD"]
    allowed_origins = var.domain != "" ? ["https://${var.domain}", "https://*.${var.domain}"] : ["*"]
    expose_headers  = ["ETag", "x-amz-request-id"]
    max_age_seconds = 3000
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"
    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    # Optionally move old versions to cheaper storage
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  # Example: expire tmp/ uploads after 1 day if you use that prefix
  rule {
    id     = "expire-tmp"
    status = "Enabled"
    filter {
      prefix = "tmp/"
    }
    expiration {
      days = 1
    }
  }
}

# Optional: bucket policy will be managed by CloudFront module (OAC)
# We leave it empty here so that module can attach policy after distribution is created.
# Alternatively, you can pre-create a policy that denies non-OAC access.

output "bucket_id" {
  value       = aws_s3_bucket.media.id
  description = "S3 bucket name / ID"
}

output "bucket_arn" {
  value = aws_s3_bucket.media.arn
}

output "bucket_regional_domain_name" {
  value = aws_s3_bucket.media.bucket_regional_domain_name
}

output "bucket_domain_name" {
  value = aws_s3_bucket.media.bucket_domain_name
}

output "bucket_region" {
  value = var.region
}
