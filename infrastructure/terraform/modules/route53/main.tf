# =============================================================================
# Module: route53 — DNS records for CloudFront + ALB
# Assumes a hosted zone for var.domain already exists (or create one).
# Creates alias records: media/cdn -> CloudFront, api -> ALB.
# =============================================================================

variable "domain" {
  type        = string
  description = "Root domain (e.g. infalette.com)"
}

variable "cloudfront_domain_name" {
  type        = string
  description = "CloudFront distribution domain (e.g. d123.cloudfront.net)"
}

variable "cloudfront_hosted_zone_id" {
  type        = string
  description = "CloudFront hosted zone ID (always Z2FDTNDATAQYW2)"
  default     = "Z2FDTNDATAQYW2"
}

variable "alb_dns_name" {
  type        = string
  description = "ALB DNS name"
}

variable "alb_zone_id" {
  type        = string
  description = "ALB hosted zone ID"
}

variable "create_hosted_zone" {
  type        = bool
  default     = false
  description = "If true, create a new hosted zone; else look up existing"
}

# Try to look up existing zone; create if requested
data "aws_route53_zone" "existing" {
  count        = var.create_hosted_zone ? 0 : 1
  name         = var.domain
  private_zone = false
}

resource "aws_route53_zone" "main" {
  count = var.create_hosted_zone ? 1 : 0
  name  = var.domain
  tags  = { Name = var.domain }
}

locals {
  zone_id = var.create_hosted_zone ? aws_route53_zone.main[0].zone_id : data.aws_route53_zone.existing[0].zone_id
}

# Root domain -> CloudFront (optional, if you want apex to CDN)
# resource "aws_route53_record" "apex" {
#   zone_id = local.zone_id
#   name    = var.domain
#   type    = "A"
#   alias {
#     name                   = var.cloudfront_domain_name
#     zone_id                = var.cloudfront_hosted_zone_id
#     evaluate_target_health = false
#   }
# }

resource "aws_route53_record" "media" {
  zone_id = local.zone_id
  name    = "media.${var.domain}"
  type    = "A"
  alias {
    name                   = var.cloudfront_domain_name
    zone_id                = var.cloudfront_hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "cdn" {
  zone_id = local.zone_id
  name    = "cdn.${var.domain}"
  type    = "A"
  alias {
    name                   = var.cloudfront_domain_name
    zone_id                = var.cloudfront_hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "api" {
  zone_id = local.zone_id
  name    = "api.${var.domain}"
  type    = "A"
  alias {
    name                   = var.alb_dns_name
    zone_id                = var.alb_zone_id
    evaluate_target_health = true
  }
}

# Health check for API (optional)
resource "aws_route53_health_check" "api" {
  fqdn              = "api.${var.domain}"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30
  tags              = { Name = "api-${var.domain}-health" }
}

output "zone_id" {
  value = local.zone_id
}

output "media_fqdn" {
  value = aws_route53_record.media.fqdn
}

output "api_fqdn" {
  value = aws_route53_record.api.fqdn
}
