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

echo -e "${RED}=== Deleting Artifact Registry ===${NC}"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Repository: $REPOSITORY_ID"
echo ""

# Check if exists
if ! gcloud artifacts repositories describe "$REPOSITORY_ID" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    &>/dev/null; then
    echo -e "${YELLOW}⚠ Artifact Registry repository does not exist${NC}"
    exit 0
fi

# Show what will be deleted
echo -e "${YELLOW}Repository details:${NC}"
gcloud artifacts repositories describe "$REPOSITORY_ID" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --format="table(name,format,sizeBytes,createTime)"
echo ""

# List images that will be deleted
echo -e "${YELLOW}Images in repository:${NC}"
if gcloud artifacts docker images list \
    "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_ID}" \
    --project="$PROJECT_ID" \
    --limit=10 \
    2>/dev/null; then
    echo ""
else
    echo "No images found"
    echo ""
fi

# Confirm deletion
read -p "Are you sure you want to delete this repository and ALL its images? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}Deletion cancelled${NC}"
    exit 0
fi

echo -e "${RED}Deleting Artifact Registry repository...${NC}"

gcloud artifacts repositories delete "$REPOSITORY_ID" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --quiet

echo -e "${GREEN}✓ Artifact Registry repository deleted successfully${NC}"
