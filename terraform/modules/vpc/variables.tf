variable "project_name" {}
variable "environment" {}
variable "vpc_cidr" {}
variable "availability_zones" { type = list(string) }
variable "enable_nat_gateway" { type = bool }
variable "single_nat_gateway" { type = bool }
variable "enable_dns_hostnames" { type = bool }
variable "enable_dns_support" { type = bool }
variable "tags" { type = map(string) }
