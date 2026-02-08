# Cloud Run service for frontend
resource "google_cloud_run_v2_service" "frontend" {
  name     = "chatbot-frontend"
  location = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/chatbot/frontend:latest"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

#   depends_on = [
#     google_artifact_registry_repository.chatbot
#   ]
}

# Make frontend publicly accessible
resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  project  = google_cloud_run_v2_service.frontend.project
  location = google_cloud_run_v2_service.frontend.location
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
