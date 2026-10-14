# =============================================================================
# Module: cloudfront — Distribution for S3 media (and optionally API)
# Uses Origin Access Control (OAC) for S3 — no public bucket. Minimal prod.
# =============================================================================

variable "env" {
  type        = string
  description = "Environment name"
}

variable "s3_bucket_domain" {
  type        = string
  description = "S3 bucket regional domain name (e.g. bucket.s3.ap-south-1.amazonaws.com)"
}

variable "s3_bucket_id" {
  type        = string
  description = "S3 bucket ID / name"
}

variable "domain" {
  type        = string
  description = "Root domain for aliases (optional)"
  default     = ""
}

variable "acm_certificate_arn" {
  type        = string
  description = "ACM cert ARN in us-east-1 for CloudFront (optional)"
  default     = null
}

variable "price_class" {
  type        = string
  default     = "PriceClass_100"
  description = "CloudFront price class"
}

resource "aws_cloudfront_origin_access_control" "s3" {
  name                              = "infalette-${var.env}-s3-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "main" {
  comment             = "Infalette ${var.env} media distribution"
  enabled             = true
  is_ipv6_enabled     = true
  price_class         = var.price_class
  default_root_object = null

  # Aliases only if domain + cert provided
  aliases = var.domain != "" && var.acm_certificate_arn != null ? ["media.${var.domain}", "cdn.${var.domain}"] : []

  origin {
    domain_name              = var.s3_bucket_domain
    origin_id                = "s3-media"
    origin_access_control_id = aws_cloudfront_origin_access_control.s3.id
  }

  default_cache_behavior {
    target_origin_id       = "s3-media"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    cache_policy_id          = "658327ea-f89d-4fab-a63d-7e88639e58f6" # CachingOptimized (managed)
    origin_request_policy_id = "88a5eaf4-2fd4-4709-b370-b4c650ea3fcf" # CORS-S3Origin (managed)
    # Alternatively use legacy forwarded_values { ... } if policy IDs not available in region.
  }

  # Optional: cache behavior for API if you want CloudFront in front of ALB
  # Uncomment and wire `var.alb_domain_name` if needed.
  # ordered_cache_behavior {
  #   path_pattern           = "/api/*"
  #   target_origin_id       = "alb-api"
  #   viewer_protocol_policy = "https-only"
  #   allowed_methods        = ["GET","HEAD","OPTIONS","PUT","PATCH","POST","DELETE"]
  #   cached_methods         = ["GET","HEAD"]
  #   cache_policy_id        = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # CachingDisabled
  #   origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac" # AllViewerExceptHostHeader
  # }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    # Use ACM if provided, otherwise default CloudFront cert
    acm_certificate_arn            = var.acm_certificate_arn
    ssl_support_method             = var.acm_certificate_arn != null ? "sni-only" : null
    minimum_protocol_version       = var.acm_certificate_arn != null ? "TLSv1.2_2021" : null
    cloudfront_default_certificate = var.acm_certificate_arn == null
  }

  # Logging (optional) — set to an S3 bucket if you want access logs
  # logging_config {
  #   include_cookies = false
  #   bucket          = "${var.s3_bucket_id}.s3.amazonaws.com"
  #   prefix          = "cloudfront-logs/"
  # }

  tags = {
    Name        = "infalette-${var.env}-media-cdn"
    Environment = var.env
  }
}

# Allow CloudFront OAC to read from S3
resource "aws_s3_bucket_policy" "media" {
  bucket = var.s3_bucket_id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontOAC"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "arn:aws:s3:::${var.s3_bucket_id}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.main.arn
          }
        }
      }
    ]
  })
}

output "distribution_id" {
  value = aws_cloudfront_distribution.main.id
}

output "domain_name" {
  value = aws_cloudfront_distribution.main.domain_name
}

output "hosted_zone_id" {
  value = aws_cloudfront_distribution.main.hosted_zone_id
}

output "arn" {
  value = aws_cloudfront_distribution.main.arn
}
