# =============================================================================
# Module: elasticache — Redis 7
# Uses ElastiCache for Redis (or Serverless). Minimal prod: private subnets,
# encrypted at-rest/in-transit, auto-failover in production.
# =============================================================================

variable "env" {
  type        = string
  description = "Environment name"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets"
}

variable "node_type" {
  type        = string
  default     = "cache.t3.micro"
  description = "Cache node type"
}

variable "engine_version" {
  type        = string
  default     = "7.0"
  description = "Redis engine version"
}

variable "num_cache_nodes" {
  type        = number
  default     = 1
  description = "Number of cache nodes (1 for dev, 2+ for prod with replication)"
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "infalette-${var.env}-redis-subnet"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "redis" {
  name        = "infalette-${var.env}-redis-sg"
  description = "Allow Redis from VPC"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
    description = "Redis from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "infalette-${var.env}-redis-sg" }
}

resource "aws_elasticache_parameter_group" "main" {
  name   = "infalette-${var.env}-redis7"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }
}

# Replication group gives HA; for single-node dev we still use replication_group
# with one shard. For true single-node without replication, use aws_elasticache_cluster.
resource "aws_elasticache_replication_group" "main" {
  replication_group_id          = "infalette-${var.env}-redis"
  description                   = "Infalette ${var.env} Redis"
  engine                        = "redis"
  engine_version                = var.engine_version
  node_type                     = var.node_type
  num_cache_clusters            = var.env == "production" ? 2 : 1
  parameter_group_name          = aws_elasticache_parameter_group.main.name
  subnet_group_name             = aws_elasticache_subnet_group.main.name
  security_group_ids            = [aws_security_group.redis.id]
  port                          = 6379

  at_rest_encryption_enabled    = true
  transit_encryption_enabled    = var.env == "production" ? true : false
  # auth_token requires transit_encryption — manage via variable if enabled
  automatic_failover_enabled    = var.env == "production" ? true : false
  multi_az_enabled              = var.env == "production" ? true : false

  snapshot_retention_limit      = var.env == "production" ? 7 : 1
  snapshot_window               = "02:00-03:00"
  maintenance_window            = "sun:03:00-sun:04:00"
  auto_minor_version_upgrade    = true
  apply_immediately             = var.env != "production"

  tags = {
    Name        = "infalette-${var.env}-redis"
    Environment = var.env
  }
}

output "redis_endpoint" {
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
  description = "Redis primary endpoint hostname"
}

output "reader_endpoint" {
  value = aws_elasticache_replication_group.main.reader_endpoint_address
}

output "redis_url" {
  # Note: if transit_encryption + auth_token is enabled, URL becomes rediss://
  value       = "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0"
  description = "Redis URL (add password if auth_token enabled)"
  sensitive   = true
}

output "security_group_id" {
  value = aws_security_group.redis.id
}
