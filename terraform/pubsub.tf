# Pub/Sub topic for dataset requests
resource "google_pubsub_topic" "dataset_requests" {
  name = "dataset-pr-requests"

  message_retention_duration = "86400s" # 24 hours
}

# Dead letter topic for failed messages
resource "google_pubsub_topic" "dead_letter" {
  name = "dataset-pr-requests-dead-letter"
}

# Pub/Sub subscription for worker (PUSH configuration)
resource "google_pubsub_subscription" "worker_subscription" {
  name  = "git-worker-sub"
  topic = google_pubsub_topic.dataset_requests.name

  ack_deadline_seconds       = 600
  message_retention_duration = "604800s" # 7 days

  # Retry policy with exponential backoff
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }

  expiration_policy {
    ttl = "2678400s" # 31 days
  }

  # Enable message ordering if needed
  enable_message_ordering = false


}

# IAM for dead letter topic
resource "google_pubsub_topic_iam_member" "dead_letter_publisher" {
  topic  = google_pubsub_topic.dead_letter.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "dead_letter_subscriber" {
  subscription = google_pubsub_subscription.worker_subscription.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# Data source for project
data "google_project" "project" {
  project_id = var.project_id
}
