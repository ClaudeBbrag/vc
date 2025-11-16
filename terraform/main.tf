# Main Terraform configuration for Seed-VC deployment on AWS
# This creates an EKS cluster with GPU nodes for real-time voice conversion

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }

  # Backend configuration for state storage
  # Uncomment and configure for production
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "seedvc/terraform.tfstate"
  #   region         = "us-west-2"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Seed-VC"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# Local variables
locals {
  cluster_name = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# VPC Module
module "vpc" {
  source = "./modules/vpc"

  project_name         = var.project_name
  environment          = var.environment
  vpc_cidr             = var.vpc_cidr
  availability_zones   = slice(data.aws_availability_zones.available.names, 0, 3)
  enable_nat_gateway   = var.enable_nat_gateway
  single_nat_gateway   = var.single_nat_gateway
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = local.common_tags
}

# EKS Cluster Module
module "eks" {
  source = "./modules/eks"

  cluster_name    = local.cluster_name
  cluster_version = var.eks_cluster_version

  vpc_id              = module.vpc.vpc_id
  private_subnet_ids  = module.vpc.private_subnet_ids
  enable_irsa         = true

  # Node groups
  gpu_node_group_config = {
    instance_types  = var.gpu_instance_types
    desired_size    = var.gpu_nodes_desired
    min_size        = var.gpu_nodes_min
    max_size        = var.gpu_nodes_max
    disk_size       = 100
    ami_type        = "AL2_x86_64_GPU"  # Amazon Linux 2 with GPU support
  }

  cpu_node_group_config = {
    instance_types  = var.cpu_instance_types
    desired_size    = var.cpu_nodes_desired
    min_size        = var.cpu_nodes_min
    max_size        = var.cpu_nodes_max
    disk_size       = 50
    ami_type        = "AL2_x86_64"
  }

  tags = local.common_tags
}

# NVIDIA Device Plugin (for GPU support)
resource "kubernetes_daemonset" "nvidia_device_plugin" {
  depends_on = [module.eks]

  metadata {
    name      = "nvidia-device-plugin-daemonset"
    namespace = "kube-system"
  }

  spec {
    selector {
      match_labels = {
        name = "nvidia-device-plugin-ds"
      }
    }

    template {
      metadata {
        labels = {
          name = "nvidia-device-plugin-ds"
        }
      }

      spec {
        toleration {
          key      = "nvidia.com/gpu"
          operator = "Exists"
          effect   = "NoSchedule"
        }

        container {
          image = "nvcr.io/nvidia/k8s-device-plugin:v0.14.0"
          name  = "nvidia-device-plugin-ctr"

          security_context {
            allow_privilege_escalation = false
            capabilities {
              drop = ["ALL"]
            }
          }

          volume_mount {
            name       = "device-plugin"
            mount_path = "/var/lib/kubelet/device-plugins"
          }
        }

        volume {
          name = "device-plugin"
          host_path {
            path = "/var/lib/kubelet/device-plugins"
          }
        }
      }
    }
  }
}

# Application Load Balancer for Janus/Seed-VC
resource "aws_lb" "seedvc" {
  name               = "${local.cluster_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnet_ids

  enable_deletion_protection = var.environment == "production" ? true : false
  enable_http2               = true

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cluster_name}-alb"
    }
  )
}

# Security Group for ALB
resource "aws_security_group" "alb" {
  name        = "${local.cluster_name}-alb-sg"
  description = "Security group for Seed-VC ALB"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "WebSocket (Janus)"
    from_port   = 8088
    to_port     = 8088
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cluster_name}-alb-sg"
    }
  )
}

# Network Load Balancer for RTP/UDP traffic
resource "aws_lb" "seedvc_nlb" {
  name               = "${local.cluster_name}-nlb"
  internal           = false
  load_balancer_type = "network"
  subnets            = module.vpc.public_subnet_ids

  enable_deletion_protection       = var.environment == "production" ? true : false
  enable_cross_zone_load_balancing = true

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cluster_name}-nlb"
    }
  )
}

# S3 bucket for model storage
resource "aws_s3_bucket" "models" {
  bucket = "${local.cluster_name}-models"

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cluster_name}-models"
    }
  )
}

resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id

  versioning_configuration {
    status = "Enabled"
  }
}

# ECR Repository for Docker images
resource "aws_ecr_repository" "seedvc" {
  name                 = "${local.cluster_name}/seedvc"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "seedvc" {
  name              = "/aws/eks/${local.cluster_name}/seedvc"
  retention_in_days = var.log_retention_days

  tags = local.common_tags
}

# Route53 (DNS) - Optional
resource "aws_route53_zone" "seedvc" {
  count = var.domain_name != "" ? 1 : 0

  name = var.domain_name

  tags = local.common_tags
}

resource "aws_route53_record" "seedvc_alb" {
  count = var.domain_name != "" ? 1 : 0

  zone_id = aws_route53_zone.seedvc[0].zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_lb.seedvc.dns_name
    zone_id                = aws_lb.seedvc.zone_id
    evaluate_target_health = true
  }
}

# ACM Certificate for HTTPS - Optional
resource "aws_acm_certificate" "seedvc" {
  count = var.domain_name != "" ? 1 : 0

  domain_name       = var.domain_name
  validation_method = "DNS"

  subject_alternative_names = [
    "*.${var.domain_name}"
  ]

  lifecycle {
    create_before_destroy = true
  }

  tags = local.common_tags
}

# Outputs
output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "alb_dns_name" {
  description = "ALB DNS name"
  value       = aws_lb.seedvc.dns_name
}

output "nlb_dns_name" {
  description = "NLB DNS name for RTP traffic"
  value       = aws_lb.seedvc_nlb.dns_name
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.seedvc.repository_url
}

output "s3_models_bucket" {
  description = "S3 bucket for models"
  value       = aws_s3_bucket.models.bucket
}

output "configure_kubectl" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}
