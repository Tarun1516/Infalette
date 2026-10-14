# =============================================================================
# Module: iam — Roles & policies for ECS, etc.
# Uses least-privilege; execution role can pull images + write logs,
# task role can access S3 media + Secrets Manager.
# =============================================================================

variable "env" {
  type        = string
  description = "Environment name"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ---------------------------------------------------------------------------
# ECS Execution Role — used by ECS agent to pull images, write logs
# ---------------------------------------------------------------------------
resource "aws_iam_role" "ecs_execution" {
  name = "infalette-${var.env}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "infalette-${var.env}-ecs-execution" }
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow reading secrets (if you store DB password / API keys in Secrets Manager)
resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "infalette-${var.env}-ecs-execution-secrets"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
        Resource = ["arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:infalette/${var.env}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameters", "ssm:GetParameter"]
        Resource = ["arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/infalette/${var.env}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = ["*"]
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${data.aws_region.current.name}.amazonaws.com"
          }
        }
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# ECS Task Role — used by the application itself
# ---------------------------------------------------------------------------
resource "aws_iam_role" "ecs_task" {
  name = "infalette-${var.env}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "infalette-${var.env}-ecs-task" }
}

resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "infalette-${var.env}-ecs-task-s3"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "MediaBucketRW"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket", "s3:HeadObject"]
        Resource = [
          "arn:aws:s3:::infalette-media-${var.env}-${data.aws_caller_identity.current.account_id}",
          "arn:aws:s3:::infalette-media-${var.env}-${data.aws_caller_identity.current.account_id}/*"
        ]
      },
      {
        Sid      = "MediaBucketKMS"
        Effect   = "Allow"
        Action   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"]
        Resource = ["*"]
      },
      {
        # For SES email sending
        Sid      = "SESSend"
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = ["*"]
      },
      {
        # For CloudWatch metrics / X-Ray / OTEL
        Sid      = "Observability"
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData", "xray:PutTraceSegments", "xray:PutTelemetryRecords", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["*"]
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Optional: CI deploy role (GitHub Actions OIDC)
# ---------------------------------------------------------------------------
# Uncomment if you use GitHub OIDC to deploy from CI.
# resource "aws_iam_openid_connect_provider" "github" { ... }
# resource "aws_iam_role" "github_deploy" { ... }

output "ecs_execution_role_arn" {
  value = aws_iam_role.ecs_execution.arn
}

output "ecs_task_role_arn" {
  value = aws_iam_role.ecs_task.arn
}
