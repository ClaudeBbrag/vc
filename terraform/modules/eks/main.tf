# EKS Module - Uses AWS EKS Terraform module

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnet_ids

  enable_irsa = var.enable_irsa

  # GPU Node Group
  eks_managed_node_groups = {
    gpu_nodes = {
      name            = "gpu-nodes"
      instance_types  = var.gpu_node_group_config.instance_types
      capacity_type   = "ON_DEMAND"  # or "SPOT" for cost savings

      min_size     = var.gpu_node_group_config.min_size
      max_size     = var.gpu_node_group_config.max_size
      desired_size = var.gpu_node_group_config.desired_size

      ami_type = var.gpu_node_group_config.ami_type
      disk_size = var.gpu_node_group_config.disk_size

      labels = {
        role = "gpu"
        "nvidia.com/gpu" = "true"
      }

      taints = [{
        key    = "nvidia.com/gpu"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }

    cpu_nodes = {
      name           = "cpu-nodes"
      instance_types = var.cpu_node_group_config.instance_types
      capacity_type  = "ON_DEMAND"

      min_size     = var.cpu_node_group_config.min_size
      max_size     = var.cpu_node_group_config.max_size
      desired_size = var.cpu_node_group_config.desired_size

      ami_type  = var.cpu_node_group_config.ami_type
      disk_size = var.cpu_node_group_config.disk_size

      labels = {
        role = "cpu"
      }
    }
  }

  tags = var.tags
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_certificate_authority_data" {
  value = module.eks.cluster_certificate_authority_data
}
