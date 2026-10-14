# =============================================================================
# Root outputs
# =============================================================================

output "api_url" {
  description = "API URL (ALB DNS or CloudFront)"
  value       = "https://${module.ecs.alb_dns_name}"
}

output "alb_dns_name" {
  description = "ALB DNS name for the API"
  value       = module.ecs.alb_dns_name
}

output "db_endpoint" {
  description = "RDS Postgres endpoint"
  value       = module.rds.db_endpoint
  sensitive   = true
}

output "db_url" {
  description = "Database connection URL (without password)"
  value       = module.rds.db_url
  sensitive   = true
}

output "redis_endpoint" {
  description = "ElastiCache Redis primary endpoint"
  value       = module.elasticache.redis_endpoint
}

output "redis_url" {
  description = "Redis connection URL"
  value       = module.elasticache.redis_url
  sensitive   = true
}

output "s3_bucket" {
  description = "S3 media bucket name"
  value       = module.s3.bucket_id
}

output "s3_bucket_arn" {
  description = "S3 media bucket ARN"
  value       = module.s3.bucket_arn
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain"
  value       = module.cloudfront.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = module.cloudfront.distribution_id
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}
