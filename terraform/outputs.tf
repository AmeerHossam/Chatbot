output "backend_url" {
  description = "URL of the backend Cloud Run service"
  value       = google_cloud_run_v2_service.backend.uri
}

output "frontend_url" {
  description = "URL of the frontend Cloud Run service"
  value       = google_cloud_run_v2_service.frontend.uri
}

output "pubsub_topic" {
  description = "Pub/Sub topic name"
  value       = google_pubsub_topic.dataset_requests.name
}

# output "artifact_registry_url" {
#   description = "Artifact Registry repository URL"
#   value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.chatbot.repository_id}"
# }

output "backend_service_account" {
  description = "Backend service account email"
  value       = google_service_account.backend.email
}

output "worker_service_account" {
  description = "Worker service account email"
  value       = google_service_account.worker.email
}
