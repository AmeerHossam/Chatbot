#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Deploying Chatbot Application       ${NC}"
echo -e "${BLUE}========================================${NC}"

# Configuration
PROJECT_ID=${PROJECT_ID:-"helpful-charmer-485315-j7"}
REGION=${REGION:-"us-central1"}
REPO_NAME="chatbot"

echo -e "\n${GREEN}Project:${NC} $PROJECT_ID"
echo -e "${GREEN}Region:${NC} $REGION"

# Get current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Set gcloud project
gcloud config set project $PROJECT_ID

echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}  Step 1: Setup Artifact Registry      ${NC}"
echo -e "${BLUE}========================================${NC}"

# Run artifact registry setup script
"$SCRIPT_DIR/setup_artifact_registry.sh"

# Get Artifact Registry URL
REGISTRY_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"

echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}  Step 2: Building Docker images       ${NC}"
echo -e "${BLUE}========================================${NC}"

# Build backend image
echo -e "${YELLOW}Building backend image for AMD64 (Cloud Run)...${NC}"
cd "$ROOT_DIR/backend"
docker build --platform linux/amd64 -t ${REGISTRY_URL}/backend:latest .
echo -e "${GREEN}✓ Backend image built${NC}"

# Build worker image
echo -e "${YELLOW}Building worker image for AMD64 (Cloud Run)...${NC}"
cd "$ROOT_DIR/worker"
docker build --platform linux/amd64 -t ${REGISTRY_URL}/worker:latest .
echo -e "${GREEN}✓ Worker image built${NC}"

# Build frontend image
echo -e "${YELLOW}Building frontend image for AMD64 (Cloud Run)...${NC}"
cd "$ROOT_DIR/frontend"
docker build --platform linux/amd64 -t ${REGISTRY_URL}/frontend:latest .
echo -e "${GREEN}✓ Frontend image built${NC}"

echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}  Step 3: Pushing images to Registry   ${NC}"
echo -e "${BLUE}========================================${NC}"


# Configure Docker for Artifact Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# Push backend
echo -e "${YELLOW}Pushing backend image...${NC}"
docker push ${REGISTRY_URL}/backend:latest
echo -e "${GREEN}✓ Backend image pushed${NC}"

# Push worker
echo -e "${YELLOW}Pushing worker image...${NC}"
docker push ${REGISTRY_URL}/worker:latest
echo -e "${GREEN}✓ Worker image pushed${NC}"

# Push frontend
echo -e "${YELLOW}Pushing frontend image...${NC}"
docker push ${REGISTRY_URL}/frontend:latest
echo -e "${GREEN}✓ Frontend image pushed${NC}"

echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}  Step 4: Deploying with Terraform     ${NC}"
echo -e "${BLUE}========================================${NC}"

cd "$ROOT_DIR/terraform"

# Initialize if needed
if [ ! -d ".terraform" ]; then
    echo -e "${YELLOW}Initializing Terraform...${NC}"
    terraform init
fi

# Apply Terraform
echo -e "${YELLOW}Applying Terraform configuration...${NC}"
terraform apply -auto-approve

# Get outputs
BACKEND_URL=$(terraform output -raw backend_url 2>/dev/null || echo "N/A")
FRONTEND_URL=$(terraform output -raw frontend_url 2>/dev/null || echo "N/A")

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment Complete!                 ${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "\n${BLUE}Service URLs:${NC}"
echo -e "  Backend:  ${BACKEND_URL}"
echo -e "  Frontend: ${FRONTEND_URL}"

echo -e "\n${GREEN}✓ All services deployed successfully!${NC}"
echo -e "\n${YELLOW}Note: If backend URL changed, update frontend/app.js manually${NC}"
