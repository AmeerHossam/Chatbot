resource "google_bigquery_dataset" "flow_test_dataset" {
  dataset_id = "flow_test_dataset"
  location   = "EU"
  
  
  labels = {
    
    env = "dev"
    
    team = "data"
    
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