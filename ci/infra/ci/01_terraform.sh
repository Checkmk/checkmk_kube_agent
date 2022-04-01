cd terraform
terraform plan -out plan
terraform destroy -auto-approve

terraform plan -out plan
terraform apply -auto-approve plan
