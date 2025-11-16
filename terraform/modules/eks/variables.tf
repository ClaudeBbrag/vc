variable "cluster_name" {}
variable "cluster_version" {}
variable "vpc_id" {}
variable "private_subnet_ids" { type = list(string) }
variable "enable_irsa" { type = bool }
variable "gpu_node_group_config" { type = object({
  instance_types = list(string)
  min_size      = number
  max_size      = number
  desired_size  = number
  ami_type      = string
  disk_size     = number
}) }
variable "cpu_node_group_config" { type = object({
  instance_types = list(string)
  min_size      = number
  max_size      = number
  desired_size  = number
  ami_type      = string
  disk_size     = number
}) }
variable "tags" { type = map(string) }
