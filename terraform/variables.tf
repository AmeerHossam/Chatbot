variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "helpful-charmer-485315-j7"
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "github_token_secret_name" {
  description = "Name of the secret in Secret Manager containing GitHub PAT"
  type        = string
  default     = "github-pat"
}

variable "github_repo_url" {
  description = "GitHub repository URL"
  type        = string
  default     = "https://github.com/AmeerHossam/Chatbot.git"
}

variable "github_repo_owner" {
  description = "GitHub repository owner"
  type        = string
  default     = "AmeerHossam"
}

variable "github_repo_name" {
  description = "GitHub repository name"
  type        = string
  default     = "Chatbot"
}

variable "terraform_files_directory" {
  description = "Directory in repo where Terraform files will be created"
  type        = string
  default     = "datasets"
}
