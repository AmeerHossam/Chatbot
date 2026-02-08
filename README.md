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
6. **Real-time Status** → Frontend subscribes to Fire store for instant updates ⚡
7. **Git Operations** → Worker clones repo, creates branch, generates Terraform file
8. **PR Creation** → Worker pushes changes and creates pull request on GitHub
9. **Status Push** → Worker updates Firestore, frontend receives update instantly 🔔

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
  "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "pr_url": null
}
```

**Step 3.4: Frontend Subscribes to Firestore** 🔔

The frontend immediately subscribes to real-time updates when it receives `status: "processing"`:

```javascript
// frontend/app.js
if (data.status === 'processing' && data.request_id) {
    currentRequestId = data.request_id;
    subscribeToStatus(data.request_id);
}

function subscribeToStatus(requestId) {
    // Firestore real-time listener
    statusListener = db.collection('pr_requests').doc(requestId)
        .onSnapshot((doc) => {
            const data = doc.data();
            console.log('📊 Received real-time update:', data);
            
            if (data.status === 'completed' && data.pr_url) {
                // Display PR URL to user instantly!
                addMessage(
                    `🎉 Success! Your Pull Request has been created:\n\n${data.pr_url}`,
                    'bot'
                );
                statusListener(); // Unsubscribe
            }
        });
}
```

**Why This is Better Than Polling:**
- ⚡ Instant updates (0ms delay vs 1000ms polling)
- 💰 90% fewer Firestore reads (2-3 vs 30-60 per request)
- 🔋 Lower battery/CPU usage on client
- 🎯 Updates only when status actually changes

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

### Phase 7: Status Update & Real-Time Push 🔔

**Step 7.1: Worker Updates Firestore**
```python
# worker/main.py
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

**Step 7.2: Firestore Pushes to Frontend** ⚡

The moment Firestore is updated, it **automatically pushes** the change to the frontend listener:

```
Worker updates Firestore
   ↓ (0ms - instant!)
Firestore real-time listener fires
   ↓
Frontend receives update
   ↓
PR URL displayed to user
```

No polling, no delays - **instant notification**!


**Step 7.3: Acknowledge Pub/Sub Message**
```python
subscriber.acknowledge(
    subscription="git-worker-sub",
    ack_ids=[received_message.ack_id]
)
```

Message removed from queue


**Step 7.4: Cleanup**
```python
git_ops.cleanup()
# Removes: /tmp/repo-1707224400
```


**Step 7.5: Job Completes**
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
- **Technology**: Vanilla HTML/CSS/JavaScript with Firebase SDK + Nginx
- **Purpose**: User-facing chat interface with real-time status updates
- **Status Updates**: Firestore real-time listeners (push architecture) ⚡
- **Location**: `frontend/`
- **Public Access**: Yes (allUsers invoker)
- **Key Features**:
  - Real-time PR status updates via Firestore
  - Automatic fallback to polling if Firestore unavailable
  - Firebase SDK for push notifications

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

## 🚀 Quick Start

Get up and running in 3 simple steps using our automated deployment scripts:

### Step 1: Initial Setup
```bash
# Clone the repository
git clone https://github.com/AmeerHossam/Chatbot.git
cd chatbot

# Configure your environment
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

# Run GCP setup (enables APIs, creates Firestore, stores GitHub token)
./scripts/setup_gcp.sh
```

### Step 2: Configure Variables
Update `terraform/terraform.tfvars` with your project details:
```hcl
project_id = "your-gcp-project-id"
region     = "us-central1"
```

### Step 3: Deploy Everything
```bash
# One command to build and deploy all services!
./scripts/deploy.sh
```

That's it! 🎉 The script will:
- ✅ Create Artifact Registry
- ✅ Build Docker images for all services
- ✅ Push images to registry
- ✅ Deploy infrastructure with Terraform
- ✅ Output your service URLs

---

## 📋 Prerequisites

### Required
- **GCP Project** with billing enabled
- **GitHub Personal Access Token** with `repo` scope
- **Local Tools**:
  - `gcloud` CLI (authenticated)
  - `terraform` >= 1.5
  - `docker` (with linux/amd64 support)

### Automated Setup Scripts
Our setup scripts can handle most of the GCP configuration for you! See the [Deployment Scripts](#-deployment-scripts) section below.

### APIs Required
The following APIs will be enabled automatically by `setup_gcp.sh`, or enable manually:
- Cloud Run API
- Vertex AI API
- Pub/Sub API
- Secret Manager API
- Firestore API
- Artifact Registry API
- Cloud Build API

## 📋 Detailed Setup Instructions

Choose between automated or manual setup based on your preference.

### Option A: Automated Setup (Recommended)

The fastest way to get started using our automation scripts:

#### 1. Clone Repository
```bash
git clone https://github.com/AmeerHossam/Chatbot.git
cd chatbot
```

#### 2. Set Environment Variables
```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
```

#### 3. Run GCP Setup Script
```bash
./scripts/setup_gcp.sh
```

This script will:
- Set your active GCP project
- Enable all required APIs
- Create Firestore database
- Prompt for and securely store GitHub PAT in Secret Manager

#### 4. Configure Terraform Variables
Edit `terraform/terraform.tfvars`:
```hcl
project_id = "your-gcp-project-id"
region     = "us-central1"
```

You can also copy and customize `.env.example` for reference:
```bash
cp .env.example .env
# Edit .env with your configuration
```

#### 5. Initialize Terraform
```bash
cd terraform
terraform init
cd ..
```

#### 6. Deploy Everything
```bash
./scripts/deploy.sh
```

This single command will:
- Create Artifact Registry repository
- Build all Docker images (backend, worker, frontend)
- Push images to Artifact Registry
- Deploy infrastructure with Terraform
- Display your service URLs

---

### Option B: Manual Setup

For users who prefer step-by-step control:

#### 1. Clone Repository
```bash
git clone https://github.com/AmeerHossam/Chatbot.git
cd chatbot
```

#### 2. Set GCP Project
```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
gcloud config set project $PROJECT_ID
```

#### 3. Enable Required APIs
```bash
gcloud services enable \
    run.googleapis.com \
    aiplatform.googleapis.com \
    pubsub.googleapis.com \
    firestore.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com
```

#### 4. Create Firestore Database
```bash
gcloud firestore databases create --location=$REGION --type=firestore-native
```

#### 5. Store GitHub Token in Secret Manager
```bash
echo -n "your-github-pat" | gcloud secrets create github-pat \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID
```

#### 6. Create Artifact Registry
```bash
gcloud artifacts repositories create chatbot \
  --repository-format=docker \
  --location=$REGION \
  --description="Docker images for chatbot services"

gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

#### 7. Configure Terraform
Edit `terraform/terraform.tfvars`:
```hcl
project_id = "your-gcp-project-id"
region     = "us-central1"
```

#### 8. Initialize Terraform
```bash
cd terraform
terraform init
cd ..
```

#### 9. Build and Push Docker Images
```bash
REGISTRY_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/chatbot"

# Build and push backend
docker build --platform linux/amd64 -t ${REGISTRY_URL}/backend:latest ./backend
docker push ${REGISTRY_URL}/backend:latest

# Build and push worker
docker build --platform linux/amd64 -t ${REGISTRY_URL}/worker:latest ./worker
docker push ${REGISTRY_URL}/worker:latest

# Build and push frontend
docker build --platform linux/amd64 -t ${REGISTRY_URL}/frontend:latest ./frontend
docker push ${REGISTRY_URL}/frontend:latest
```

#### 10. Deploy Infrastructure
```bash
cd terraform
terraform plan
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

## 📜 Deployment Scripts

The `scripts/` directory contains automation scripts to simplify deployment:

### `setup_gcp.sh`
**Purpose**: Initial GCP project setup and configuration

**What it does**:
- Sets the active GCP project
- Enables all required APIs (Cloud Run, Vertex AI, Pub/Sub, Firestore, etc.)
- Creates Firestore database if it doesn't exist
- Prompts for GitHub Personal Access Token
- Securely stores GitHub PAT in Secret Manager

**Usage**:
```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
./scripts/setup_gcp.sh
```

### `setup_artifact_registry.sh`
**Purpose**: Create and configure Google Artifact Registry

**What it does**:
- Creates Artifact Registry repository for Docker images
- Configures Docker authentication with gcloud
- Displays repository URL and usage examples

**Usage**:
```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
./scripts/setup_artifact_registry.sh
```

### `deploy.sh`
**Purpose**: Complete end-to-end deployment

**What it does**:
- Runs artifact registry setup
- Builds Docker images for all services (backend, worker, frontend)
- Pushes images to Artifact Registry
- Deploys infrastructure using Terraform
- Displays deployed service URLs

**Usage**:
```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
./scripts/deploy.sh
```

**Features**:
- ✅ Colored output for easy reading
- ✅ Automatic platform targeting (linux/amd64) for Cloud Run
- ✅ Handles Terraform initialization
- ✅ Displays backend and frontend URLs after deployment

### `delete_artifact_registry.sh`
**Purpose**: Clean up Artifact Registry resources

**What it does**:
- Deletes the Artifact Registry repository
- Useful for cleanup or starting fresh

**Usage**:
```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
./scripts/delete_artifact_registry.sh
```

---

## 🔧 Configuration

### Environment Variables

A complete `.env.example` file is provided in the repository root. Key variables include:

#### GCP Configuration
- `PROJECT_ID` - Your GCP Project ID
- `REGION` - GCP Region (e.g., `us-central1`)
- `LOCATION` - Same as REGION for most services

#### Vertex AI
- `VERTEX_AI_MODEL` - AI model to use (default: `gemini-1.5-flash`)

#### Pub/Sub
- `PUBSUB_TOPIC` - Topic name (default: `dataset-pr-requests`)
- `PUBSUB_SUBSCRIPTION` - Subscription name (default: `git-worker-sub`)

#### Firestore
- `FIRESTORE_DATABASE` - Database name (default: `(default)`)

#### GitHub Configuration
- `GITHUB_REPO_URL` - Full repository URL
- `GITHUB_REPO_OWNER` - Repository owner username
- `GITHUB_REPO_NAME` - Repository name
- `GITHUB_TOKEN_SECRET_NAME` - Secret Manager secret name (default: `github-pat`)
- `GITHUB_DEFAULT_BRANCH` - Default branch (default: `main`)

#### Terraform
- `TERRAFORM_FILES_DIRECTORY` - Where to store generated files (default: `datasets`)

#### Local Development (Optional)
- `PORT` - Local server port (default: `8080`)
- `LOG_LEVEL` - Logging level (default: `INFO`)

**Usage**:
```bash
# Copy the example file
cp .env.example .env

# Edit with your values
vim .env

# Source for local development
source .env
```

> [!NOTE]
> For production deployment, environment variables are set in Terraform configuration and Cloud Run service definitions. The `.env` file is primarily for local development and reference.

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
├── .env.example         # Environment variables template
├── README.md           # This file
├── backend/            # FastAPI backend service
│   ├── main.py         # Main API endpoints
│   ├── vertex_ai.py    # Vertex AI integration
│   ├── state_manager.py # Firestore state management
│   ├── pubsub_publisher.py # Pub/Sub publisher
│   ├── requirements.txt
│   └── Dockerfile
├── worker/             # Cloud Run Job worker
│   ├── main.py         # Job entry point
│   ├── git_operations.py # Git automation
│   ├── terraform_generator.py # Terraform file generation
│   ├── github_api.py   # GitHub API integration
│   ├── requirements.txt
│   ├── templates/      # Terraform templates
│   └── Dockerfile
├── frontend/           # Static web interface
│   ├── index.html      # Main HTML
│   ├── styles.css      # Styling
│   ├── app.js          # Chat interface logic
│   ├── nginx.conf      # Nginx configuration
│   └── Dockerfile
├── terraform/          # Infrastructure as Code
│   ├── provider.tf
│   ├── backend.tf      # Terraform backend config
│   ├── backend_service.tf # Backend Cloud Run service
│   ├── worker_service.tf  # Worker Cloud Run job
│   ├── frontend_service.tf # Frontend Cloud Run service
│   ├── pubsub.tf       # Pub/Sub resources
│   ├── firestore.tf    # Firestore configuration
│   ├── variables.tf    # Input variables
│   ├── outputs.tf      # Output values
│   └── terraform.tfvars # Variable values (create this)
└── scripts/            # Automation scripts
    ├── deploy.sh       # Complete deployment automation
    ├── setup_gcp.sh    # GCP project setup
    ├── setup_artifact_registry.sh # Registry setup
    └── delete_artifact_registry.sh # Cleanup script
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
- 🔔 **Real-Time Status Updates** - Firestore push notifications for instant feedback
- 🤖 **AI-Powered Entity Extraction** - Natural language understanding via Vertex AI
- 📝 **Automated PR Creation** - Complete Git workflow automation
- 🔄 **Stateful Conversations** - Firestore-backed conversation memory
- 🛡️ **Reliable Processing** - Pub/Sub ensures no message loss
- 📊 **Production-Ready** - Terraform-managed infrastructure
- 🚀 **Serverless** - Auto-scaling Cloud Run services and jobs
- 💾 **Efficient Architecture** - Push-based updates reduce server load by ~90%

---

**Built with ❤️ using Google Cloud Platform**
