resource "google_bigquery_dataset" "my_data" {
  dataset_id = "my_data"
  location   = "us-central1"
  
  
  labels = {
    
    env = "dev"
    
    team = "eng"
    
  }
  
  
  access {
    role          = "OWNER"
    user_by_email = "sa-test@helpful-charmer-485315-j7.iam.gserviceaccount.com"
  }

  # Optional: Set default table expiration
  # default_table_expiration_ms = 3600000

  # Optional: Delete protection
  # deletion_protection = true
}