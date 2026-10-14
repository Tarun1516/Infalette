# =============================================================================
# Infalette — Root Terraform configuration
# =============================================================================
# Production-like but minimal: provider, backend, and module wiring.
# Secrets are passed via TF vars / SSM / Secrets Manager, never hardcoded.
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state — replace bucket/dynamodb_table per environment.
  # For local dev, comment this block out and use local backend.
  backend "s3" {
    bucket         = "infalette-terraform-state"
    key            = "infalette/terraform.tfstate"
    region         = "ap-south-1"
    encrypt        = true
    dynamodb_table = "infalette-terraform-locks"
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "infalette"
      Environment = var.env
      ManagedBy   = "terraform"
    }
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

# ---------------------------------------------------------------------------
# VPC
# ---------------------------------------------------------------------------
module "vpc" {
  source   = "./modules/vpc"
  env      = var.env
  vpc_cidr = var.vpc_cidr
  azs      = slice(data.aws_availability_zones.available.names, 0, 3)
}

# ---------------------------------------------------------------------------
# IAM — roles for ECS tasks, etc.
# ---------------------------------------------------------------------------
module "iam" {
  source = "./modules/iam"
  env    = var.env
}

# ---------------------------------------------------------------------------
# S3 + CloudFront (media bucket)
# ---------------------------------------------------------------------------
module "s3" {
  source   = "./modules/s3"
  env      = var.env
  region   = var.region
  domain   = var.domain
}

# CloudFront distribution in front of S3 (and optionally API)
module "cloudfront" {
  source            = "./modules/cloudfront"
  env               = var.env
  s3_bucket_domain  = module.s3.bucket_regional_domain_name
  s3_bucket_id      = module.s3.bucket_id
  domain            = var.domain
  acm_certificate_arn = var.acm_certificate_arn
}

# ---------------------------------------------------------------------------
# RDS Postgres 18.6 (only used for non-Neon environments — see module comment)
# ---------------------------------------------------------------------------
module "rds" {
  source            = "./modules/rds"
  env               = var.env
  vpc_id            = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  instance_class    = var.db_instance_class
  # Password is injected via var or Secrets Manager; never hardcoded.
  db_password       = var.db_password
  db_username       = var.db_username
  db_name           = var.db_name
}

# ---------------------------------------------------------------------------
# ElastiCache Redis 7
# ---------------------------------------------------------------------------
module "elasticache" {
  source             = "./modules/elasticache"
  env                = var.env
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  node_type          = var.redis_node_type
}

# ---------------------------------------------------------------------------
# ECS Fargate — API + workers
# ---------------------------------------------------------------------------
module "ecs" {
  source              = "./modules/ecs"
  env                 = var.env
  region              = var.region
  vpc_id              = module.vpc.vpc_id
  public_subnet_ids   = module.vpc.public_subnet_ids
  private_subnet_ids  = module.vpc.private_subnet_ids
  execution_role_arn  = module.iam.ecs_execution_role_arn
  task_role_arn       = module.iam.ecs_task_role_arn

  db_url              = module.rds.db_url
  redis_url           = module.elasticache.redis_url
  s3_bucket           = module.s3.bucket_id

  api_image           = var.api_image
  workers_image       = var.workers_image
  desired_count       = var.desired_count

  # Observability
  otel_endpoint       = var.otel_endpoint
  sentry_dsn          = var.sentry_dsn
}

# ---------------------------------------------------------------------------
# Route53 (optional — only if domain is set)
# ---------------------------------------------------------------------------
module "route53" {
  source                   = "./modules/route53"
  count                    = var.domain != "" ? 1 : 0
  domain                   = var.domain
  cloudfront_domain_name   = module.cloudfront.domain_name
  cloudfront_hosted_zone_id = module.cloudfront.hosted_zone_id
  alb_dns_name             = module.ecs.alb_dns_name
  alb_zone_id              = module.ecs.alb_zone_id
}
