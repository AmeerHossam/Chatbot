resource "google_bigquery_dataset" "final_success_test" {
  dataset_id = "final_success_test"
  location   = "us-west1"
  
  
  labels = {
    
    success = "true"
    
    instant = "working"
    
  }
  
  
  access {
    role          = "OWNER"
    user_by_email = "sa-final@helpful-charmer-485315-j7.iam.gserviceaccount.com"
  }

  # Optional: Set default table expiration
  # default_table_expiration_ms = 3600000

  # Optional: Delete protection
  # deletion_protection = true
}