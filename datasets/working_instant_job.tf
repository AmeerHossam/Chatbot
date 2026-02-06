resource "google_bigquery_dataset" "working_instant_job" {
  dataset_id = "working_instant_job"
  location   = "europe-west1"
  
  
  labels = {
    
    test = "working"
    
    mode = "instant"
    
  }
  
  
  access {
    role          = "OWNER"
    user_by_email = "sa-test-working@helpful-charmer-485315-j7.iam.gserviceaccount.com"
  }

  # Optional: Set default table expiration
  # default_table_expiration_ms = 3600000

  # Optional: Delete protection
  # deletion_protection = true
}