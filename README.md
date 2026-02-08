# AI-Powered Dataset Management Chatbot

An intelligent chatbot that automates BigQuery dataset creation through conversational AI, automatically generating pull requests with Terraform configurations.

## 🏗️ Architecture

```mermaid
graph TB
    User[👤 User] -->|Sends Request| Frontend[🖥️ Frontend<br/>Cloud Run Service]
    Frontend -->|HTTP POST| Backend[⚙️ Backend API<br/>Cloud Run Service]
    
    Backend -->|Extract Entities| Vertex[🧠 Vertex AI<br/>Gemini Model]
    Vertex -->|Extracted Data| Backend
    
    Backend -->|Store State| Firestore[(🗄️ Firestore)]
    Backend -->|Publish Message| PubSub[📬 Pub/Sub Topic]
    Backend -->|Trigger Job| JobsAPI[☁️ Cloud Run Jobs API]
    
    JobsAPI -->|Execute| Worker[🔧 Git Worker<br/>Cloud Run Job]
    Worker -->|Pull Messages| PubSub
    Worker -->|Read Secret| SecretManager[🔐 Secret Manager<br/>GitHub PAT]
    Worker -->|Clone/Branch/Push| GitHub[📦 GitHub Repository]
    Worker -->|Create PR| GitHub
    Worker -->|Update Status| Firestore
    
    GitHub -->|PR Created| GitHubPR[✅ Pull Request]
    
    style Frontend fill:#4285f4,color:#fff
    style Backend fill:#34a853,color:#fff
    style Worker fill:#fbbc04,color:#000
    style Vertex fill:#ea4335,color:#fff
    style Firestore fill:#4285f4,color:#fff
    style PubSub fill:#34a853,color:#fff
    style GitHub fill:#181717,color:#fff
```

## 🔄 Request Flow (High-Level)

1. **User Interaction** → User sends dataset request via chat interface
2. **Backend Processing** → Extracts entities using Vertex AI (Gemini)
3. **State Management** → Stores conversation state in Firestore
4. **Message Queue** → Publishes request to Pub/Sub topic
5. **Instant Trigger** → Backend calls Jobs API to execute worker immediately
6. **Git Operations** → Worker clones repo, creates branch, generates Terraform file
7. **PR Creation** → Worker pushes changes and creates pull request on GitHub
8. **Status Update** → Worker updates Firestore with PR URL and completion status

## 🔍 Detailed Request Flow

### Phase 1: User Interaction & Frontend

**Step 1.1: User Sends Message**
```
User types: "Create a dataset named analytics_prod in us-central1"
Frontend: app.js captures message
```

**Step 1.2: Frontend → Backend Request**
```http
POST https://<backend-url>/chat
Content-Type: application/json

{
  "message": "Create a dataset named analytics_prod in us-central1",
  "session_id": "user-abc-123"
}
```

### Phase 2: Backend Processing

**Step 2.1: Request Received**
- FastAPI endpoint `/chat` receives request ([main.py](file:///Users/amirabdelmoneim/chatbot/backend/main.py))
- Validates session_id and message

**Step 2.2: Vertex AI Entity Extraction**
- Backend calls `VertexAIExtractor.extract_entities()` ([vertex_ai.py](file:///Users/amirabdelmoneim/chatbot/backend/vertex_ai.py))
- Sends message to Gemini 1.5 Flash with function calling schema
- Gemini extracts: `dataset_name`, `location`, `labels`, `service_account`
- Returns extracted entities as structured JSON

**Step 2.3: State Management**
- `StateManager.merge_entities()` combines new entities with previous conversation ([state_manager.py](file:///Users/amirabdelmoneim/chatbot/backend/state_manager.py))
- Stores in Firestore collection: `conversations/{session_id}`
```json
{
  "session_id": "user-abc-123",
  "status": "collecting",
  "extracted_entities": {
    "dataset_name": "analytics_prod",
    "location": "us-central1",
    "labels": null,
    "service_account": null
  },
  "messages": [...]
}
```

**Step 2.4: Check Completeness**
- Backend checks if all 4 required fields are collected
- **If incomplete**: Generate follow-up question, return to user
- **If complete**: Proceed to Step 2.5

**Step 2.5: Create PR Request Record**
```python
request_id = uuid.uuid4()  # e.g., "f47ac10b-58cc-4372-a567-0e02b2c3d479"

state_manager.create_pr_request(
    request_id=request_id,
    session_id=session_id,
    payload={
        "dataset_name": "analytics_prod",
        "location": "us-central1",
        "labels": {"env": "prod", "team": "analytics"},
        "service_account": "sa-analytics@project.iam.gserviceaccount.com"
    }
)
```

Firestore document created: `pr_requests/{request_id}`
```json
{
  "request_id": "f47ac10b...",
  "session_id": "user-abc-123",
  "status": "pending",
  "payload": {...},
  "created_at": "2026-02-06T12:00:00Z",
  "pr_url": null
}
```

### Phase 3: Message Publishing & Job Triggering

**Step 3.1: Publish to Pub/Sub**
- `PubSubPublisher.publish_dataset_request()` ([pubsub_publisher.py](file:///Users/amirabdelmoneim/chatbot/backend/pubsub_publisher.py))
- Publishes message to topic: `dataset-pr-requests`

```json
{
  "request_id": "f47ac10b...",
  "session_id": "user-abc-123",
  "dataset_name": "analytics_prod",
  "location": "us-central1",
  "labels": {"env": "prod", "team": "analytics"},
  "service_account": "sa-analytics@project.iam.gserviceaccount.com"
}
```

**Step 3.2: Instant Job Trigger** ⚡
```python
from google.cloud.run_v2 import JobsClient, RunJobRequest

jobs_client = JobsClient()
job_name = f"projects/{project_id}/locations/{region}/jobs/git-worker"
request = RunJobRequest(name=job_name)

operation = jobs_client.run_job(request=request)
# Job execution starts immediately (1-3 seconds)
```

**Step 3.3: Response to User**
```json
{
  "message": "✅ Perfect! Creating Pull Request for 'analytics_prod'...\nRequest ID: f47ac10b...",
  "session_id": "user-abc-123",
  "status": "processing",
  "pr_url": null
}
```

### Phase 4: Worker Job Execution

**Step 4.1: Job Starts**
- Cloud Run Job `git-worker` starts execution
- Container runs `python main.py` ([worker/main.py](file:///Users/amirabdelmoneim/chatbot/worker/main.py))
- Execution name: `git-worker-xyz123`

**Step 4.2: Pull Pub/Sub Messages**
```python
subscriber = pubsub_v1.SubscriberClient()
response = subscriber.pull(
    subscription="git-worker-sub",
    max_messages=10
)
```

Receives the message published in Step 3.1

**Step 4.3: Fetch GitHub Token**
```python
secret_client = secretmanager.SecretManagerServiceClient()
secret_name = "projects/{project}/secrets/github-pat/versions/latest"
github_token = secret_client.access_secret_version(secret_name)
```

**Step 4.4: Initialize Git Operations**
- `GitOperations.__init__()` ([git_operations.py](file:///Users/amirabdelmoneim/chatbot/worker/git_operations.py))
- Sets up local Git configuration
- Configures authentication with GitHub token

### Phase 5: Git Workflow

**Step 5.1: Clone Repository**
```python
git_ops.clone_or_update(token=github_token)
# Clones to: /tmp/repo-{timestamp}
# URL: https://oauth2:{token}@github.com/owner/repo.git
```

**Step 5.2: Create Feature Branch**
```python
timestamp = int(time.time())
branch_name = f"dataset/analytics_prod-{timestamp}"
# e.g., "dataset/analytics_prod-1707224400"

git_ops.create_branch(branch_name)
# Executes: git checkout -b dataset/analytics_prod-1707224400
```

**Step 5.3: Generate Terraform File**
- `TerraformGenerator.generate_bigquery_dataset()` ([terraform_generator.py](file:///Users/amirabdelmoneim/chatbot/worker/terraform_generator.py))

Creates file: `datasets/analytics_prod.tf`
```hcl
resource "google_bigquery_dataset" "analytics_prod" {
  dataset_id = "analytics_prod"
  location   = "us-central1"
  
  labels = {
    env  = "prod"
    team = "analytics"
  }
  
  access {
    role          = "OWNER"
    user_by_email = "sa-analytics@project.iam.gserviceaccount.com"
  }
  
  lifecycle {
    prevent_destroy = true
  }
}
```

**Step 5.4: Commit Changes**
```python
git_ops.commit_changes(
    file_path="datasets/analytics_prod.tf",
    message="""feat: Add BigQuery dataset analytics_prod

Created via AI Chatbot
- Location: us-central1
- Labels: env=prod, team=analytics
- Owner: sa-analytics@project.iam.gserviceaccount.com

Request ID: f47ac10b-58cc-4372-a567-0e02b2c3d479
"""
)
# Executes: git add datasets/analytics_prod.tf
#           git commit -m "..."
```

**Step 5.5: Push to GitHub**
```python
git_ops.push_branch(branch_name, token=github_token)
# Executes: git push origin dataset/analytics_prod-1707224400
```

### Phase 6: Pull Request Creation

**Step 6.1: Create PR via GitHub API**
- `GitHubAPI.create_pull_request()` ([github_api.py](file:///Users/amirabdelmoneim/chatbot/worker/github_api.py))

```python
pr_title = "Add BigQuery Dataset: analytics_prod"
pr_body = """
## Dataset Configuration

- **Name**: analytics_prod
- **Location**: us-central1
- **Labels**: 
  - env: prod
  - team: analytics
- **Owner**: sa-analytics@project.iam.gserviceaccount.com

---
🤖 Auto-generated by AI Chatbot
Request ID: f47ac10b-58cc-4372-a567-0e02b2c3d479
"""

github_api.create_pull_request(
    title=pr_title,
    body=pr_body,
    head_branch="dataset/analytics_prod-1707224400",
    base_branch="main"
)
```

**Step 6.2: PR Created**
- GitHub creates PR: `https://github.com/owner/repo/pull/123`
- Returns PR URL and number

### Phase 7: Status Update & Cleanup

**Step 7.1: Update Firestore**
```python
state_manager.update_request_status(
    request_id="f47ac10b...",
    status="completed",
    pr_url="https://github.com/owner/repo/pull/123"
)
```

Firestore document updated: `pr_requests/{request_id}`
```json
{
  "request_id": "f47ac10b...",
  "status": "completed",
  "pr_url": "https://github.com/owner/repo/pull/123",
  "updated_at": "2026-02-06T12:00:30Z"
}
```

**Step 7.2: Acknowledge Pub/Sub Message**
```python
subscriber.acknowledge(
    subscription="git-worker-sub",
    ack_ids=[received_message.ack_id]
)
```

Message removed from queue

**Step 7.3: Cleanup**
```python
git_ops.cleanup()
# Removes: /tmp/repo-1707224400
```

**Step 7.4: Job Completes**
```
2026-02-06 12:00:30 - main - INFO - ✅ Successfully created PR: https://github.com/owner/repo/pull/123
2026-02-06 12:00:30 - main - INFO - ✅ Job execution completed. Processed 1 message(s).
```

Cloud Run Job exits with code 0

---

## 📊 Visual Flow Diagram

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Vertex as Vertex AI<br/>(Gemini)
    participant Firestore
    participant PubSub as Pub/Sub
    participant JobsAPI as Jobs API
    participant Worker as Worker Job
    participant SecretMgr as Secret Manager
    participant Git as GitHub

    User->>Frontend: 1. Types message:<br/>"Create dataset analytics_prod"
    Frontend->>Backend: 2. POST /chat<br/>{message, session_id}
    
    Note over Backend: Phase 2: Processing
    Backend->>Vertex: 3. Extract entities<br/>from message
    Vertex-->>Backend: 4. Return entities:<br/>{dataset_name, location, ...}
    
    Backend->>Firestore: 5. Store conversation state
    Firestore-->>Backend: 6. State saved
    
    alt Missing Fields
        Backend-->>Frontend: Ask follow-up question
        Frontend-->>User: "Which region?"
        Note over User,Backend: Loop until all fields collected
    end
    
    Note over Backend: All fields collected!
    Backend->>Firestore: 7. Create PR request record<br/>{request_id, status: "pending"}
    
    Backend->>PubSub: 8. Publish message<br/>to dataset-pr-requests
    PubSub-->>Backend: 9. Message published
    
    Note over Backend: Phase 3: Instant Trigger
    Backend->>JobsAPI: 10. run_job()<br/>⚡ Trigger git-worker
    JobsAPI-->>Backend: 11. Job execution started
    
    Backend-->>Frontend: 12. Response:<br/>"Creating PR..."<br/>Request ID: xxx
    Frontend-->>User: 13. Show status message
    
    Note over JobsAPI,Worker: Phase 4: Job Starts (1-3s)
    JobsAPI->>Worker: Start execution
    
    Note over Worker: Phase 4-7: Worker Processing
    Worker->>PubSub: 14. Pull messages<br/>(max 10)
    PubSub-->>Worker: 15. Return message(s)
    
    Worker->>SecretMgr: 16. Get GitHub token
    SecretMgr-->>Worker: 17. Return PAT
    
    Note over Worker: Phase 5: Git Operations
    Worker->>Git: 18. Clone repository<br/>with token auth
    Git-->>Worker: 19. Repo cloned
    
    Worker->>Worker: 20. Create branch:<br/>dataset/analytics_prod-{timestamp}
    Worker->>Worker: 21. Generate Terraform file:<br/>datasets/analytics_prod.tf
    Worker->>Worker: 22. Git commit<br/>"feat: Add dataset..."
    
    Worker->>Git: 23. Push branch
    Git-->>Worker: 24. Branch pushed
    
    Note over Worker: Phase 6: PR Creation
    Worker->>Git: 25. Create Pull Request<br/>via GitHub API
    Git-->>Worker: 26. PR created<br/>URL: github.com/.../pull/123
    
    Note over Worker: Phase 7: Finalize
    Worker->>Firestore: 27. Update status:<br/>"completed", pr_url
    Firestore-->>Worker: 28. Status updated
    
    Worker->>PubSub: 29. Acknowledge message<br/>(remove from queue)
    PubSub-->>Worker: 30. Message acked
    
    Worker->>Worker: 31. Cleanup temp files
    
    Note over Worker: Job Complete ✅<br/>Exit code 0
    
    Note over User,Git: Total Time: ~15-30 seconds
```

## ⏱️ Timing Breakdown

| Phase | Duration | Notes |
|-------|----------|-------|
| User → Frontend → Backend | ~100-300ms | Network latency |
| Vertex AI Entity Extraction | ~1-2s | Gemini API call |
| Firestore Write | ~50-100ms | State storage |
| Pub/Sub Publish | ~50-100ms | Message queue |
| **Job Trigger** | **1-3s** | ⚡ Instant via Jobs API |
| Job Cold Start | ~5-10s | Container initialization |
| Git Clone | ~2-5s | Depends on repo size |
| Terraform Generation | ~10-50ms | File creation |
| Git Push | ~1-2s | Network to GitHub |
| PR Creation | ~500ms-1s | GitHub API |
| Firestore Update | ~50-100ms | Status update |
| **Total End-to-End** | **~15-30s** | From complete data to PR created |

> [!NOTE]
> The instant job triggering (Phase 3.2) eliminates the previous 2-minute Cloud Scheduler delay, reducing total time from **2+ minutes** to **~15-30 seconds**!

## 📦 Components

### Frontend (Cloud Run Service)
- **Technology**: Vanilla HTML/CSS/JavaScript with Nginx
- **Purpose**: User-facing chat interface
- **Location**: `frontend/`
- **Public Access**: Yes (allUsers invoker)

### Backend (Cloud Run Service)
- **Technology**: FastAPI + Python
- **Purpose**: 
  - Handle chat requests
  - Extract entities using Vertex AI
  - Manage conversation state
  - Publish to Pub/Sub
  - **Trigger Cloud Run Jobs instantly**
- **Location**: `backend/`
- **Key Dependencies**:
  - `google-cloud-aiplatform` - Vertex AI integration
  - `google-cloud-firestore` - State storage
  - `google-cloud-pubsub` - Message publishing
  - `google-cloud-run` - **Job triggering**
  - `fastapi` - Web framework

### Worker (Cloud Run Job)
- **Technology**: Python
- **Purpose**:
  - Pull messages from Pub/Sub
  - Clone/update GitHub repository
  - Generate Terraform configuration
  - Create branches and pull requests
- **Location**: `worker/`
- **Execution**: Triggered instantly by backend via Jobs API
- **Key Dependencies**:
  - `google-cloud-pubsub` - Message queue
  - `GitPython` - Git operations
  - `PyGithub` - GitHub API integration

### Infrastructure (Terraform)
- **Location**: `terraform/`
- **Manages**:
  - Cloud Run services (Backend, Frontend)
  - Cloud Run job (Worker)
  - Pub/Sub topic and subscription
  - IAM roles and permissions
  - Artifact Registry
  - Service accounts

## 🚀 Prerequisites

- **GCP Project** with billing enabled
- **APIs Enabled**:
  - Cloud Run API
  - Vertex AI API
  - Pub/Sub API
  - Secret Manager API
  - Firestore API
  - Artifact Registry API
- **GitHub Personal Access Token** with `repo` scope
- **Local Tools**:
  - `gcloud` CLI (authenticated)
  - `terraform` >= 1.5
  - `docker` (with linux/amd64 support)

## 📋 Setup Instructions

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd chatbot
```

### 2. Configure Environment
Update the following in `terraform/variables.tf` or export as environment variables:

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export GITHUB_REPO_URL="https://github.com/owner/repo.git"
export GITHUB_REPO_OWNER="owner"
export GITHUB_REPO_NAME="repo"
```

### 3. Store GitHub Token in Secret Manager
```bash
echo -n "your-github-pat" | gcloud secrets create github-pat \
  --data-file=- \
  --project=$PROJECT_ID
```

### 4. Configure Terraform Variables
Edit `terraform/terraform.tfvars`:

```hcl
project_id = "your-gcp-project-id"
region     = "us-central1"
```

### 5. Deploy Infrastructure
```bash
# Initialize Terraform
cd terraform
terraform init

# Review plan
terraform plan

# Apply
terraform apply
```

### 6. Build and Deploy Services (Alternative: Use Deploy Script)
```bash
# Run automated deployment
./scripts/deploy.sh
```

Or manually:
```bash
# Authenticate Docker with Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build and push images
docker build --platform linux/amd64 -t us-central1-docker.pkg.dev/$PROJECT_ID/chatbot/backend:latest ./backend
docker push us-central1-docker.pkg.dev/$PROJECT_ID/chatbot/backend:latest

docker build --platform linux/amd64 -t us-central1-docker.pkg.dev/$PROJECT_ID/chatbot/worker:latest ./worker
docker push us-central1-docker.pkg.dev/$PROJECT_ID/chatbot/worker:latest

docker build --platform linux/amd64 -t us-central1-docker.pkg.dev/$PROJECT_ID/chatbot/frontend:latest ./frontend
docker push us-central1-docker.pkg.dev/$PROJECT_ID/chatbot/frontend:latest

# Deploy with Terraform
cd terraform
terraform apply
```

## 🎯 Usage

### Access the Chatbot
After deployment, Terraform outputs the frontend URL:

```bash
terraform output frontend_url
```

Visit the URL and start chatting!

### Example Conversation

**User**: "I need a BigQuery dataset"

**Bot**: "I can help you create a BigQuery dataset! What would you like to name it?"

**User**: "Call it analytics_prod"

**Bot**: "Great! Which region should I create analytics_prod in?"

**User**: "us-central1"

**Bot**: "What labels would you like? (format: key:value,key:value)"

**User**: "env:prod,team:analytics"

**Bot**: "Finally, which service account should own this dataset?"

**User**: "sa-analytics@project.iam.gserviceaccount.com"

**Bot**: "✅ Perfect! Creating Pull Request for dataset 'analytics_prod'... Request ID: abc-123"

### Behind the Scenes
1. Backend extracts all entities (dataset name, location, labels, service account)
2. Publishes message to Pub/Sub
3. **Instantly triggers Cloud Run Job** via Jobs API
4. Worker pulls message, creates Terraform file, and opens PR
5. **Total time: ~10-30 seconds** ⚡

### Check Request Status
```bash
curl https://<backend-url>/status/<request-id>
```

### Manual Job Execution
```bash
gcloud run jobs execute git-worker \
  --region=us-central1 \
  --project=$PROJECT_ID
```

## 🔧 Configuration

### Environment Variables

#### Backend
- `PROJECT_ID` - GCP Project ID
- `REGION` - GCP Region
- `PUBSUB_TOPIC` - Pub/Sub topic name (default: `dataset-pr-requests`)

#### Worker
- `PROJECT_ID` - GCP Project ID
- `PUBSUB_SUBSCRIPTION` - Subscription name (default: `git-worker-sub`)
- `GITHUB_TOKEN_SECRET_NAME` - Secret Manager secret name (default: `github-pat`)
- `GITHUB_REPO_URL` - Full GitHub repository URL
- `GITHUB_REPO_OWNER` - Repository owner
- `GITHUB_REPO_NAME` - Repository name
- `TERRAFORM_FILES_DIRECTORY` - Directory for Terraform files (default: `datasets`)

## 📊 Monitoring & Logs

### View Backend Logs
```bash
gcloud run services logs read chatbot-backend \
  --project=$PROJECT_ID \
  --region=$REGION
```

### View Worker Job Logs
```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=git-worker" \
  --project=$PROJECT_ID \
  --limit=50
```

### List Job Executions
```bash
gcloud run jobs executions list \
  --job=git-worker \
  --region=$REGION \
  --project=$PROJECT_ID
```

### Check Pub/Sub Subscription
```bash
gcloud pubsub subscriptions describe git-worker-sub \
  --project=$PROJECT_ID
```

## 🏛️ IAM Permissions

### Backend Service Account
- `roles/aiplatform.user` - Vertex AI access
- `roles/pubsub.publisher` - Publish messages
- `roles/datastore.user` - Firestore access
- **`roles/run.developer`** - **Trigger Cloud Run Jobs**

### Worker Service Account
- `roles/pubsub.subscriber` - Pull messages
- `roles/secretmanager.secretAccessor` - Read GitHub token
- `roles/datastore.user` - Update request status

## 🎨 Customization

### Modify Terraform Template
Edit `worker/terraform_generator.py` to customize the Terraform configuration template.

### Change AI Model
Edit `backend/vertex_ai.py` to use different Vertex AI models:
```python
model = GenerativeModel("gemini-1.5-flash-002")  # or gemini-pro, etc.
```

### Adjust Job Timeout
Edit `terraform/worker_service.tf`:
```hcl
template {
  timeout = "1800s"  # 30 minutes
  # ...
}
```

## � Troubleshooting

### Job Not Triggering
Check backend logs for "Triggered Cloud Run Job" message:
```bash
gcloud logging read "Triggered Cloud Run Job" \
  --limit=5 \
  --project=$PROJECT_ID
```

### Permission Errors
Verify service account IAM roles:
```bash
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:chatbot-backend@*"
```

### PR Not Created
1. Check worker logs for errors
2. Verify GitHub token in Secret Manager
3. Ensure repository permissions are correct

## 📁 Project Structure

```
chatbot/
├── backend/              # FastAPI backend service
│   ├── main.py          # Main API endpoints
│   ├── vertex_ai.py     # Vertex AI integration
│   ├── state_manager.py # Firestore state management
│   ├── pubsub_publisher.py
│   ├── requirements.txt
│   └── Dockerfile
├── worker/              # Cloud Run Job worker
│   ├── main.py         # Job entry point
│   ├── git_operations.py
│   ├── terraform_generator.py
│   ├── github_api.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/           # Static web interface
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   ├── nginx.conf
│   └── Dockerfile
├── terraform/          # Infrastructure as Code
│   ├── provider.tf
│   ├── backend_service.tf
│   ├── worker_service.tf
│   ├── frontend_service.tf
│   ├── pubsub.tf
│   ├── service_accounts.tf
│   ├── artifact_registry.tf
│   ├── variables.tf
│   └── outputs.tf
└── scripts/
    └── deploy.sh      # Automated deployment script
```

## 🔐 Security Best Practices

- ✅ GitHub token stored in Secret Manager (not in code)
- ✅ Service accounts with least-privilege IAM roles
- ✅ Backend validates all user inputs
- ✅ Pub/Sub provides reliable message queue
- ✅ Cloud Run services use non-root containers
- ✅ All secrets injected at runtime via environment variables

## 🌟 Key Features

- ⚡ **Instant Job Execution** - No Cloud Scheduler delay, jobs trigger in 1-3 seconds
- 🤖 **AI-Powered Entity Extraction** - Natural language understanding via Vertex AI
- 📝 **Automated PR Creation** - Complete Git workflow automation
- 🔄 **Stateful Conversations** - Firestore-backed conversation memory
- 🛡️ **Reliable Processing** - Pub/Sub ensures no message loss
- 📊 **Production-Ready** - Terraform-managed infrastructure
- 🚀 **Serverless** - Auto-scaling Cloud Run services and jobs

---

**Built with ❤️ using Google Cloud Platform**
