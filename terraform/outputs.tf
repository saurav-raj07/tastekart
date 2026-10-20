output "ecr_repository_url" {
  description = "The ECR repository URL for pushing the TasteKart Docker image"
  value       = aws_ecr_repository.tastekart_backend.repository_url
}

output "ec2_public_ip" {
  description = "Static Elastic IP of the K3s host"
  value       = aws_eip.k3s_eip.public_ip
}

output "ec2_instance_id" {
  description = "EC2 Instance ID"
  value       = aws_instance.k3s_node.id
}

output "app_url" {
  description = "Direct Application Gateway URL (NodePort)"
  value       = "http://${aws_eip.k3s_eip.public_ip}:30001"
}

output "ssh_connection_command" {
  description = "Command to SSH into the instance if a key was provided"
  value       = var.ssh_key_name != "" ? "ssh -i <YOUR_KEY.pem> ubuntu@${aws_eip.k3s_eip.public_ip}" : "Access via AWS Systems Manager Session Manager or set ssh_key_name in terraform.tfvars"
}

output "ssm_session_manager_command" {
  description = "AWS CLI command to start a terminal session via SSM (zero open ports required)"
  value       = "aws ssm start-session --target ${aws_instance.k3s_node.id} --region ${var.aws_region}"
}
