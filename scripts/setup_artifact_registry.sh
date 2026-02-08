#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${PROJECT_ID:-helpful-charmer-485315-j7}"
REGION="${REGION:-us-central1}"
REPOSITORY_ID="chatbot"

echo -e "${YELLOW}=== Setting up Artifact Registry ===${NC}"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Repository: $REPOSITORY_ID"
echo ""

# Check if already exists
if gcloud artifacts repositories describe "$REPOSITORY_ID" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    &>/dev/null; then
    echo -e "${GREEN}✓ Artifact Registry repository already exists${NC}"
    echo ""
    gcloud artifacts repositories describe "$REPOSITORY_ID" \
        --location="$REGION" \
        --project="$PROJECT_ID" \
        --format="table(name,format,createTime)"
else
    echo -e "${YELLOW}Creating Artifact Registry repository...${NC}"
    
    gcloud artifacts repositories create "$REPOSITORY_ID" \
        --repository-format=docker \
        --location="$REGION" \
        --description="Docker images for chatbot services" \
        --project="$PROJECT_ID"
    
    echo -e "${GREEN}✓ Artifact Registry repository created successfully${NC}"
fi

echo ""
echo -e "${YELLOW}=== Configuring Docker authentication ===${NC}"

# Configure Docker to use gcloud as credential helper
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo -e "${GREEN}✓ Docker authentication configured${NC}"
echo ""
echo -e "${GREEN}=== Artifact Registry Setup Complete ===${NC}"
echo ""
echo "Repository URL: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_ID}"
echo ""
echo "You can now build and push Docker images:"
echo "  docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_ID}/backend:latest ./backend"
echo "  docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_ID}/backend:latest"
