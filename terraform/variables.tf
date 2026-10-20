variable "aws_region" {
  description = "The AWS region to deploy resources into"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Project name prefix for tags and resources"
  type        = string
  default     = "tastekart"
}

variable "environment" {
  description = "Deployment environment (e.g., prod, staging, dev)"
  type        = string
  default     = "prod"
}

variable "instance_type" {
  description = "EC2 instance type for K3s host"
  type        = string
  default     = "t3.medium"
}

variable "root_volume_size" {
  description = "Root EBS volume size in GB"
  type        = number
  default     = 30
}

variable "allowed_ssh_cidr" {
  description = "CIDR block permitted to access SSH (Port 22) and K8s API (Port 6443)"
  type        = string
  default     = "0.0.0.0/0"
}

variable "ssh_key_name" {
  description = "Optional EC2 Key Pair name for SSH access (leave empty if using AWS SSM Session Manager)"
  type        = string
  default     = ""
}
