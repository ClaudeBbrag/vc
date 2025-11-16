# Variables for Seed-VC AWS Infrastructure

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "seedvc"
}

# VPC Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway"
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Use single NAT Gateway (cost saving for dev)"
  type        = bool
  default     = false
}

# EKS Configuration
variable "eks_cluster_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.28"
}

# GPU Node Group
variable "gpu_instance_types" {
  description = "EC2 instance types for GPU nodes"
  type        = list(string)
  default     = ["g4dn.xlarge"]  # NVIDIA T4 GPU, 4 vCPUs, 16 GB RAM
  # Other options:
  # g4dn.2xlarge  - 1x T4, 8 vCPUs, 32 GB RAM
  # g4dn.4xlarge  - 1x T4, 16 vCPUs, 64 GB RAM
  # g5.xlarge     - 1x A10G, 4 vCPUs, 16 GB RAM (newer, faster)
  # p3.2xlarge    - 1x V100, 8 vCPUs, 61 GB RAM (expensive but powerful)
}

variable "gpu_nodes_desired" {
  description = "Desired number of GPU nodes"
  type        = number
  default     = 3
}

variable "gpu_nodes_min" {
  description = "Minimum number of GPU nodes"
  type        = number
  default     = 3
}

variable "gpu_nodes_max" {
  description = "Maximum number of GPU nodes"
  type        = number
  default     = 20
}

# CPU Node Group (for Janus, support services)
variable "cpu_instance_types" {
  description = "EC2 instance types for CPU nodes"
  type        = list(string)
  default     = ["t3.medium"]  # 2 vCPUs, 4 GB RAM
}

variable "cpu_nodes_desired" {
  description = "Desired number of CPU nodes"
  type        = number
  default     = 2
}

variable "cpu_nodes_min" {
  description = "Minimum number of CPU nodes"
  type        = number
  default     = 2
}

variable "cpu_nodes_max" {
  description = "Maximum number of CPU nodes"
  type        = number
  default     = 10
}

# Logging
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

# Domain (optional)
variable "domain_name" {
  description = "Domain name for Seed-VC (optional, leave empty to skip)"
  type        = string
  default     = ""
}

# Cost Optimization Options
variable "spot_instances_enabled" {
  description = "Use spot instances for GPU nodes (cost saving but may be interrupted)"
  type        = bool
  default     = false
}

variable "spot_max_price" {
  description = "Maximum price for spot instances (empty = on-demand price)"
  type        = string
  default     = ""
}

# Tags
variable "additional_tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
