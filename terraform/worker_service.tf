# Service account for worker
resource "google_service_account" "worker" {
  account_id   = "git-worker"
  display_name = "Git Worker Service Account"
  description  = "Service account for Git operations worker"
}

# Grant necessary permissions
resource "google_project_iam_member" "worker_pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

# Cloud Run Job for worker
resource "google_cloud_run_v2_job" "worker" {
  name     = "git-worker"
  location = var.region

  template {
    template {
      service_account = google_service_account.worker.email

      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/chatbot/worker:latest"

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "PUBSUB_SUBSCRIPTION"
          value = "git-worker-sub"
        }

        env {
          name  = "GITHUB_TOKEN_SECRET_NAME"
          value = var.github_token_secret_name
        }

        env {
          name  = "GITHUB_REPO_URL"
          value = var.github_repo_url
        }

        env {
          name  = "GITHUB_REPO_OWNER"
          value = var.github_repo_owner
        }

        env {
          name  = "GITHUB_REPO_NAME"
          value = var.github_repo_name
        }

        env {
          name  = "TERRAFORM_FILES_DIRECTORY"
          value = var.terraform_files_directory
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
      }
    }
  }

  # depends_on = [
  #   google_artifact_registry_repository.chatbot
  # ]
}
