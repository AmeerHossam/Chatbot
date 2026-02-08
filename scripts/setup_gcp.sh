#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  GCP Setup for Chatbot Application   ${NC}"
echo -e "${BLUE}========================================${NC}"

# Configuration
PROJECT_ID=${PROJECT_ID:-"helpful-charmer-485315-j7"}
REGION=${REGION:-"us-central1"}

echo -e "\n${GREEN}Using Project:${NC} $PROJECT_ID"
echo -e "${GREEN}Using Region:${NC} $REGION"

# Set the project
echo -e "\n${BLUE}Setting GCP project...${NC}"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo -e "\n${BLUE}Enabling required APIs...${NC}"
gcloud services enable \
    run.googleapis.com \
    aiplatform.googleapis.com \
    pubsub.googleapis.com \
    firestore.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com

echo -e "${GREEN}✓ APIs enabled${NC}"

# Create Firestore database if it doesn't exist
echo -e "\n${BLUE}Checking Firestore database...${NC}"
if ! gcloud firestore databases describe --location=$REGION 2>/dev/null; then
    echo -e "${YELLOW}Creating Firestore database...${NC}"
    gcloud firestore databases create --location=$REGION --type=firestore-native
    echo -e "${GREEN}✓ Firestore database created${NC}"
else
    echo -e "${GREEN}✓ Firestore database already exists${NC}"
fi

# Prompt for GitHub token
echo -e "\n${BLUE}GitHub Token Setup${NC}"
echo -e "${YELLOW}You need to provide a GitHub Personal Access Token with 'repo' permissions.${NC}"
echo -e "${YELLOW}Create one at: https://github.com/settings/tokens${NC}"
read -p "Enter your GitHub token (input hidden): " -s GITHUB_TOKEN
echo ""

# Store token in Secret Manager
echo -e "\n${BLUE}Storing GitHub token in Secret Manager...${NC}"
if gcloud secrets describe github-pat --project=$PROJECT_ID 2>/dev/null; then
    echo -e "${YELLOW}Secret already exists. Adding new version...${NC}"
    echo -n "$GITHUB_TOKEN" | gcloud secrets versions add github-pat --data-file=-
else
    echo -e "${YELLOW}Creating new secret...${NC}"
    echo -n "$GITHUB_TOKEN" | gcloud secrets create github-pat \
        --replication-policy="automatic" \
        --data-file=-
fi
echo -e "${GREEN}✓ GitHub token stored securely${NC}"

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  GCP Setup Complete!                  ${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\nNext steps:"
echo -e "  1. Review and run: ${BLUE}terraform init${NC}"
echo -e "  2. Deploy infrastructure: ${BLUE}terraform apply${NC}"
echo -e "  3. Build and deploy services: ${BLUE}./scripts/deploy.sh${NC}"
