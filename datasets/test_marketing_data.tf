resource "google_bigquery_dataset" "test_marketing_data" {
  dataset_id = "test_marketing_data"
  location   = "us-central1"
  
  
  labels = {
    
    env = "prod"
    
    team = "marketing"
    
  }
  
  
  access {
    role          = "OWNER"
    user_by_email = "sa-bigquery@helpful-charmer-485315-j7.iam.gserviceaccount.com"
  }

  # Optional: Set default table expiration
  # default_table_expiration_ms = 3600000

  # Optional: Delete protection
  # deletion_protection = true
}