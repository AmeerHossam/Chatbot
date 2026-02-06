resource "google_bigquery_dataset" "verified_instant" {
  dataset_id = "verified_instant"
  location   = "asia-east1"
  
  
  labels = {
    
    verified = "true"
    
    instant = "working"
    
  }
  
  
  access {
    role          = "OWNER"
    user_by_email = "sa-verified@helpful-charmer-485315-j7.iam.gserviceaccount.com"
  }

  # Optional: Set default table expiration
  # default_table_expiration_ms = 3600000

  # Optional: Delete protection
  # deletion_protection = true
}