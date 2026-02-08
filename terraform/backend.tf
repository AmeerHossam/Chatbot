terraform {
  backend "gcs" {
    bucket = "gh-be-bucket"
    prefix = "terraform/state"
  }
}
