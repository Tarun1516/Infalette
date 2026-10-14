# =============================================================================
# Module: rds — Postgres 18.6 on RDS
# Minimal production: private subnets, encrypted, backups, parameter group.
# Password via variable / Secrets Manager — never hardcoded.
#
# NOTE: Production is on Neon. This module is kept for environments that
# still self-host (e.g. compliance-mandated on-prem, single-tenant
# deployments, disaster-recovery warm spare). The defaults below match the
# Neon target version so a future migration off Neon is a no-op parameter
# change rather than a Postgres-major upgrade.
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
  description = "Private subnets for DB subnet group"
}

variable "instance_class" {
  type        = string
  description = "RDS instance class"
  default     = "db.t3.micro"
}

variable "db_name" {
  type        = string
  default     = "infalette"
}

variable "db_username" {
  type        = string
  default     = "infalette"
  sensitive   = true
}

variable "db_password" {
  type        = string
  description = "Master password — use TF_VAR or Secrets Manager"
  default     = null
  sensitive   = true
}

variable "engine_version" {
  type        = string
  default     = "18.6"
  description = "Postgres engine version (matches Neon target)"
}

variable "allocated_storage" {
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  type        = number
  default     = 100
  description = "Autoscaling max storage"
}

resource "aws_db_subnet_group" "main" {
  name       = "infalette-${var.env}-db-subnet"
  subnet_ids = var.private_subnet_ids
  tags       = { Name = "infalette-${var.env}-db-subnet" }
}

resource "aws_security_group" "rds" {
  name        = "infalette-${var.env}-rds-sg"
  description = "Allow Postgres from VPC"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"] # restrict to VPC; tighten as needed
    description = "Postgres from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "infalette-${var.env}-rds-sg" }
}

resource "aws_db_parameter_group" "main" {
  name   = "infalette-${var.env}-pg18"
  family = "postgres18"

  parameter {
    name  = "log_min_duration_statement"
    value = "1000" # log slow queries >1s
  }

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  tags = { Name = "infalette-${var.env}-pg18-params" }
}

# Optionally manage password in Secrets Manager if not provided
resource "random_password" "master" {
  count   = var.db_password == null ? 1 : 0
  length  = 24
  special = false
}

locals {
  effective_password = coalesce(var.db_password, try(random_password.master[0].result, ""))
}

resource "aws_secretsmanager_secret" "db_password" {
  name                    = "infalette/${var.env}/rds/master-password"
  recovery_window_in_days = 7
  tags                    = { Environment = var.env }
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = local.effective_password
}

resource "aws_db_instance" "main" {
  identifier             = "infalette-${var.env}-pg"
  engine                 = "postgres"
  engine_version         = var.engine_version
  instance_class         = var.instance_class
  allocated_storage      = var.allocated_storage
  max_allocated_storage  = var.max_allocated_storage
  storage_type           = "gp3"
  storage_encrypted      = true
  db_name                = var.db_name
  username               = var.db_username
  password               = local.effective_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.main.name

  backup_retention_period = var.env == "production" ? 7 : 1
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"
  deletion_protection     = var.env == "production"
  skip_final_snapshot     = var.env != "production"
  final_snapshot_identifier = var.env == "production" ? "infalette-${var.env}-final-${formatdate("YYYYMMDDhhmm", timestamp())}" : null
  copy_tags_to_snapshot   = true
  auto_minor_version_upgrade = true
  publicly_accessible     = false
  multi_az                = var.env == "production"

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = {
    Name        = "infalette-${var.env}-pg"
    Environment = var.env
  }

  lifecycle {
    ignore_changes = [final_snapshot_identifier]
  }
}

output "db_endpoint" {
  value       = aws_db_instance.main.endpoint
  description = "RDS endpoint (host:port)"
}

output "db_address" {
  value = aws_db_instance.main.address
}

output "db_port" {
  value = aws_db_instance.main.port
}

output "db_url" {
  # postgres://user:pass@host:5432/db — caller should inject password from Secrets Manager in app
  value       = "postgresql://${var.db_username}:${local.effective_password}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${var.db_name}"
  sensitive   = true
  description = "Full DB URL (sensitive)"
}

output "security_group_id" {
  value = aws_security_group.rds.id
}

output "secret_arn" {
  value = aws_secretsmanager_secret.db_password.arn
}
