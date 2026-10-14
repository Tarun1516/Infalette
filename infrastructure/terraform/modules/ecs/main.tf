# =============================================================================
# Module: ecs — Fargate for api + workers
# Creates ECS cluster, ALB, task definitions, services, log groups.
# Minimal production: ALB in public subnets, tasks in private, autoscaling.
# Secrets injected via env vars / Secrets Manager ARNs.
# =============================================================================

variable "env" {
  type        = string
  description = "Environment name"
}

variable "region" {
  type        = string
  description = "AWS region"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnets for ALB"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets for tasks"
}

variable "execution_role_arn" {
  type        = string
  description = "ECS execution role ARN (from iam module)"
}

variable "task_role_arn" {
  type        = string
  description = "ECS task role ARN"
}

variable "api_image" {
  type        = string
  description = "API Docker image"
}

variable "workers_image" {
  type        = string
  description = "Workers Docker image"
}

variable "desired_count" {
  type        = number
  default     = 2
}

variable "api_cpu" {
  type        = number
  default     = 512
}

variable "api_memory" {
  type        = number
  default     = 1024
}

variable "workers_cpu" {
  type        = number
  default     = 512
}

variable "workers_memory" {
  type        = number
  default     = 1024
}

variable "db_url" {
  type        = string
  description = "Database URL (sensitive)"
  default     = ""
  sensitive   = true
}

variable "redis_url" {
  type        = string
  description = "Redis URL (sensitive)"
  default     = ""
  sensitive   = true
}

variable "s3_bucket" {
  type        = string
  description = "S3 media bucket name"
  default     = ""
}

variable "otel_endpoint" {
  type        = string
  default     = null
}

variable "sentry_dsn" {
  type        = string
  default     = null
  sensitive   = true
}

# ---------------------------------------------------------------------------
# ECS Cluster
# ---------------------------------------------------------------------------
resource "aws_ecs_cluster" "main" {
  name = "infalette-${var.env}"

  setting {
    name  = "containerInsights"
    value = var.env == "production" ? "enabled" : "disabled"
  }

  tags = { Name = "infalette-${var.env}-cluster" }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/infalette-${var.env}-api"
  retention_in_days = var.env == "production" ? 30 : 7
  tags              = { Environment = var.env }
}

resource "aws_cloudwatch_log_group" "workers" {
  name              = "/ecs/infalette-${var.env}-workers"
  retention_in_days = var.env == "production" ? 30 : 7
  tags              = { Environment = var.env }
}

# ---------------------------------------------------------------------------
# ALB
# ---------------------------------------------------------------------------
resource "aws_security_group" "alb" {
  name        = "infalette-${var.env}-alb-sg"
  description = "ALB security group"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP"
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "infalette-${var.env}-alb-sg" }
}

resource "aws_security_group" "ecs_tasks" {
  name        = "infalette-${var.env}-ecs-tasks-sg"
  description = "Allow traffic from ALB to ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
    description     = "API from ALB"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "infalette-${var.env}-ecs-tasks-sg" }
}

resource "aws_lb" "main" {
  name               = "infalette-${var.env}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = var.env == "production"

  tags = { Name = "infalette-${var.env}-alb" }
}

resource "aws_lb_target_group" "api" {
  name        = "infalette-${var.env}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = { Name = "infalette-${var.env}-api-tg" }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  # In production, redirect HTTP -> HTTPS. For simplicity we forward to API;
  # replace with redirect block when ACM cert is attached.
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# Uncomment when ACM cert is available:
# resource "aws_lb_listener" "https" {
#   load_balancer_arn = aws_lb.main.arn
#   port              = 443
#   protocol          = "HTTPS"
#   certificate_arn   = var.acm_certificate_arn
#   ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
#   default_action {
#     type             = "forward"
#     target_group_arn = aws_lb_target_group.api.arn
#   }
# }

# ---------------------------------------------------------------------------
# Task Definitions
# ---------------------------------------------------------------------------
locals {
  api_env = [
    { name = "NODE_ENV", value = var.env },
    { name = "AWS_REGION", value = var.region },
    { name = "S3_BUCKET", value = var.s3_bucket },
    # Add OTEL / Sentry if provided
    { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = coalesce(var.otel_endpoint, "") },
    { name = "SENTRY_DSN", value = coalesce(var.sentry_dsn, "") },
  ]

  # Filter out empty values so container doesn't get blank env vars
  api_env_filtered = [for e in local.api_env : e if e.value != "" && e.value != null]
}

resource "aws_ecs_task_definition" "api" {
  family                   = "infalette-${var.env}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = var.api_image
    essential = true
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]
    environment = concat(local.api_env_filtered, [
      # DB/Redis are sensitive — prefer Secrets Manager ARNs via `secrets` block in prod.
      # For minimal example we pass as env vars (valueFrom Secrets Manager is better).
      { name = "DATABASE_URL", value = var.db_url },
      { name = "REDIS_URL", value = var.redis_url },
    ])
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.api.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "api"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }
  }])

  tags = { Name = "infalette-${var.env}-api-task" }
}

resource "aws_ecs_task_definition" "workers" {
  family                   = "infalette-${var.env}-workers"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.workers_cpu
  memory                   = var.workers_memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([{
    name      = "workers"
    image     = var.workers_image
    essential = true
    environment = concat(local.api_env_filtered, [
      { name = "DATABASE_URL", value = var.db_url },
      { name = "REDIS_URL", value = var.redis_url },
    ])
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.workers.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "workers"
      }
    }
  }])

  tags = { Name = "infalette-${var.env}-workers-task" }
}

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
resource "aws_ecs_service" "api" {
  name            = "infalette-${var.env}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  # Allow external changes without Terraform drift (e.g. CodeDeploy)
  lifecycle {
    ignore_changes = [desired_count]
  }

  depends_on = [aws_lb_listener.http]
}

resource "aws_ecs_service" "workers" {
  name            = "infalette-${var.env}-workers"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.workers.arn
  desired_count   = var.env == "production" ? 2 : 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }
}

# ---------------------------------------------------------------------------
# Autoscaling for API
# ---------------------------------------------------------------------------
resource "aws_appautoscaling_target" "api" {
  max_capacity       = var.env == "production" ? 10 : 4
  min_capacity       = var.desired_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "infalette-${var.env}-api-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 70
    scale_in_cooldown  = 60
    scale_out_cooldown = 60

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "alb_zone_id" {
  value = aws_lb.main.zone_id
}

output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}

output "workers_service_name" {
  value = aws_ecs_service.workers.name
}
