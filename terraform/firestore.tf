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

