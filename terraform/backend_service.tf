# Service account for backend
resource "google_service_account" "backend" {
  account_id   = "chatbot-backend"
  display_name = "Chatbot Backend Service Account"
  description  = "Service account for FastAPI backend"
}

# Grant necessary permissions
resource "google_project_iam_member" "backend_vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_project_iam_member" "backend_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_project_iam_member" "backend_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

# Grant backend permission to trigger Cloud Run Jobs
resource "google_project_iam_member" "backend_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

# Allow public accesservice for backend
resource "google_cloud_run_v2_service" "backend" {
  name     = "chatbot-backend"
  location = var.region

  template {
    service_account = google_service_account.backend.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/chatbot/backend:latest"

      ports {
        container_port = 8080
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "LOCATION"
        value = var.region
      }

      env {
        name  = "PUBSUB_TOPIC"
        value = google_pubsub_topic.dataset_requests.name
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
}

# Allow unauthenticated access (configure as needed for production)
resource "google_cloud_run_v2_service_iam_member" "backend_public" {
  name     = google_cloud_run_v2_service.backend.name
  location = google_cloud_run_v2_service.backend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
