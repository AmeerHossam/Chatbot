resource "google_firestore_database" "chatbot" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  # Prevent accidental deletion - database will not be deleted when running terraform destroy
  # Change to "DELETE" only if you want to allow Terraform to delete the database
  # ABANDON removes the firestore from statefile only but not remove the firestore from the cloud
  deletion_policy = "ABANDON"
}

# Firestore Security Rules for real-time listeners
resource "google_firebaserules_ruleset" "firestore" {
  project = var.project_id
  source {
    files {
      name    = "firestore.rules"
      content = <<-EOT
        rules_version = '2';
        service cloud.firestore {
          match /databases/{database}/documents {
            // Allow read-only access to PR requests
            // Frontend can subscribe to status updates
            match /pr_requests/{requestId} {
              allow read: if true;  // Anyone with request_id can read status
              allow write: if false; // Only backend/worker can write
            }
            
            // Deny access to conversations (backend only)
            match /conversations/{sessionId} {
              allow read, write: if false;
            }
            
            // Deny all other access
            match /{document=**} {
              allow read, write: if false;
            }
          }
        }
      EOT
    }
  }
}

# Deploy the security rules to Firestore
resource "google_firebaserules_release" "firestore" {
  project      = var.project_id
  name         = "cloud.firestore"
  ruleset_name = google_firebaserules_ruleset.firestore.name
}

