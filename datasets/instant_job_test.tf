resource "google_bigquery_dataset" "instant_job_test" {
  dataset_id = "instant_job_test"
  location   = "us-central1"
  
  
  labels = {
    
    env = "test"
    
    trigger = "instant"
    
  }
  
  
  access {
    role          = "OWNER"
    user_by_email = "sa-instant@helpful-charmer-485315-j7.iam.gserviceaccount.com"
  }

  # Optional: Set default table expiration
  # default_table_expiration_ms = 3600000

  # Optional: Delete protection
  # deletion_protection = true
}