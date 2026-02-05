# AI Chatbot with Terraform PR Automation

An intelligent chatbot powered by Vertex AI that collects BigQuery dataset requirements through natural language conversation and automatically generates Infrastructure-as-Code Pull Requests.

## 🏗️ Architecture

Event-driven architecture using:
- **Frontend**: Simple HTML/CSS/JS chat interface
- **Backend**: FastAPI on Cloud Run (handles conversations and Vertex AI)
- **Worker**: Cloud Run Job (performs Git operations and PR creation)
- **Message Bus**: Cloud Pub/Sub (decouples chat from Git operations)
- **AI**: Vertex AI (Gemini 1.5 Flash for entity extraction)
- **State**: Firestore (conversation and request tracking)

## 🚀 Quick Start

### Prerequisites

1. **GCP Project**: `helpful-charmer-485315-j7`
2. **GitHub Personal Access Token** with `repo` permissions
3. **Enabled APIs**:
   - Cloud Run
   - Vertex AI
   - Pub/Sub
   - Firestore
   - Secret Manager

### Initial Setup

```bash
# 1. Clone the repository
git clone https://github.com/AmeerHossam/Chatbot.git
cd chatbot

# 2. Set up GCP environment
./scripts/setup_gcp.sh

# 3. Create GitHub PAT and store in Secret Manager
echo -n "YOUR_GITHUB_TOKEN" | gcloud secrets create github-pat \
  --data-file=- \
  --project=helpful-charmer-485315-j7

# 4. Deploy infrastructure
cd terraform
terraform init
terraform apply -var="project_id=helpful-charmer-485315-j7"

# 5. Deploy services
./scripts/deploy.sh
```

### Local Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8080

# Worker (in another terminal)
cd worker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 📖 Usage

### Via API

```bash
# Start conversation
curl -X POST https://YOUR_BACKEND_URL/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a BigQuery dataset named analytics_data in us-central1",
    "session_id": "user-123"
  }'

# Bot will ask follow-up questions for missing fields
# Continue the conversation until all fields are collected
```

### Via Web Interface

Open `frontend/index.html` in your browser or navigate to the deployed Cloud Run URL.

**Example conversation:**
```
User: I need a dataset for marketing analytics
Bot:  I can help! What should we name this dataset?

User: marketing_prod
Bot:  Got it! Which GCP region should it be in?

User: us-central1
Bot:  Perfect! What labels should I add? (e.g., env:prod, team:marketing)

User: env:production, team:marketing, cost-center:mk001
Bot:  Almost there! Which service account should own this dataset?

User: sa-marketing@helpful-charmer-485315-j7.iam.gserviceaccount.com
Bot:  ✅ Creating your Pull Request...
      🔗 https://github.com/AmeerHossam/Chatbot/pull/42
      
      Your dataset will be created once the PR is reviewed and merged!
```

## 🔧 Configuration

### Required Fields

The chatbot collects these 4 required fields:

1. **Dataset Name**: Valid BigQuery dataset identifier (`[a-z0-9_]+`)
2. **Location**: GCP region (e.g., `us-central1`, `eu`, `asia-northeast1`)
3. **Labels**: Key-value pairs (e.g., `env:prod, team:data`)
4. **Service Account**: Email of service account for dataset ownership

### Terraform Output

Generated files follow this structure:

```hcl
# datasets/marketing_prod.tf
resource "google_bigquery_dataset" "marketing_prod" {
  dataset_id = "marketing_prod"
  location   = "us-central1"
  
  labels = {
    env         = "production"
    team        = "marketing"
    cost-center = "mk001"
  }
  
  access {
    role          = "OWNER"
    user_by_email = "sa-marketing@helpful-charmer-485315-j7.iam.gserviceaccount.com"
  }
}
```

## 🧪 Testing

```bash
# Run backend tests
cd backend
pytest tests/ -v

# Run worker tests
cd worker
pytest tests/ -v

# End-to-end test
python scripts/test_e2e.py
```

## 📊 Monitoring

View logs in Cloud Console:
```bash
# Backend logs
gcloud run services logs read chatbot-backend --project=helpful-charmer-485315-j7

# Worker logs
gcloud run jobs logs read git-worker --project=helpful-charmer-485315-j7
```

## 🔒 Security

- ✅ GitHub PAT stored in Secret Manager (never in code)
- ✅ Service accounts use least-privilege IAM
- ✅ Input validation prevents injection attacks
- ✅ All PRs require manual review before merge
- ✅ Cloud Run services use private networking

## 📁 Project Structure

```
chatbot/
├── backend/              # FastAPI service
│   ├── main.py          # API endpoints
│   ├── vertex_ai.py     # Vertex AI integration
│   ├── state_manager.py # Firestore state
│   └── requirements.txt
├── worker/              # Git automation worker
│   ├── main.py          # Pub/Sub handler
│   ├── git_operations.py
│   ├── terraform_generator.py
│   ├── github_api.py
│   └── templates/       # Terraform templates
├── terraform/           # Infrastructure as Code
│   ├── backend_service.tf
│   ├── worker_service.tf
│   ├── pubsub.tf
│   └── ...
├── frontend/            # Chat UI
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── scripts/             # Deployment scripts
    ├── setup_gcp.sh
    └── deploy.sh
```

## 🚦 Roadmap

- [x] MVP: Single dataset type support
- [ ] Multi-resource support (GCS buckets, Pub/Sub topics)
- [ ] Slack/Teams integration
- [ ] Approval workflows in chat
- [ ] Cost estimation before PR creation
- [ ] Rollback capabilities

## 📄 License

MIT

## 🤝 Contributing

PRs welcome! Please run tests before submitting.

---

**Built with ❤️ using Vertex AI and Google Cloud Platform**
