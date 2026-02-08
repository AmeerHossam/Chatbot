"""
Worker job that pulls Pub/Sub messages and creates PRs.
Cloud Run Job pattern - pulls messages and processes until queue is empty.
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from google.cloud import pubsub_v1, secretmanager, firestore
from dotenv import load_dotenv

from git_operations import GitOperations
from terraform_generator import TerraformGenerator
from github_api import GitHubAPI

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.getenv("PROJECT_ID", "helpful-charmer-485315-j7")
SUBSCRIPTION_NAME = os.getenv("PUBSUB_SUBSCRIPTION", "git-worker-sub")
GITHUB_TOKEN_SECRET = os.getenv("GITHUB_TOKEN_SECRET_NAME", "github-pat")
GITHUB_REPO_URL = os.getenv("GITHUB_REPO_URL", "https://github.com/AmeerHossam/Chatbot.git")
GITHUB_REPO_OWNER = os.getenv("GITHUB_REPO_OWNER", "AmeerHossam")
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME", "Chatbot")
TERRAFORM_DIR = os.getenv("TERRAFORM_FILES_DIRECTORY", "datasets")


class Worker:
    """Main worker class for processing dataset PR requests."""

    def __init__(self):
        """Initialize worker with all necessary clients."""
        # Initialize clients
        self.subscriber = pubsub_v1.SubscriberClient()
        self.secret_client = secretmanager.SecretManagerServiceClient()
        self.firestore_client = firestore.Client(project=PROJECT_ID)
        
        # Get GitHub token from Secret Manager
        self.github_token = self._get_secret(GITHUB_TOKEN_SECRET)
        
        # Subscription path
        self.subscription_path = self.subscriber.subscription_path(
            PROJECT_ID, SUBSCRIPTION_NAME
        )

    def _get_secret(self, secret_name: str) -> str:
        """Fetch secret from Secret Manager."""
        try:
            name = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
            response = self.secret_client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            logger.info(f"Successfully retrieved secret: {secret_name}")
            return secret_value
        except Exception as e:
            logger.error(f"Error fetching secret {secret_name}: {e}", exc_info=True)
            raise

    def _update_request_status(self, request_id: str, status: str, pr_url: str = None, error: str = None):
        """Update request status in Firestore."""
        try:
            doc_ref = self.firestore_client.collection("pr_requests").document(request_id)
            
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow(),
            }
            
            if pr_url:
                update_data["pr_url"] = pr_url
            if error:
                update_data["error"] = error
            
            doc_ref.update(update_data)
            logger.info(f"Updated request {request_id} status to: {status}")
            
        except Exception as e:
            logger.error(f"Error updating request status: {e}", exc_info=True)

    def process_message_data(self, data: dict):
        """Process a single dataset request from message data."""
        request_id = data.get("request_id")
        dataset_name = data.get("dataset_name")
        location = data.get("location")
        labels = data.get("labels", {})
        service_account = data.get("service_account")

        logger.info(f"Processing request: {request_id}")
        
        # Validate required fields
        if not all([request_id, dataset_name, location, service_account]):
            raise ValueError(f"Missing required fields in request: {data}")

        # Update status to processing
        self._update_request_status(request_id, "processing")

        # Initialize helper classes
        git_ops = GitOperations(repo_url=GITHUB_REPO_URL)
        terraform_gen = TerraformGenerator()
        github_api = GitHubAPI(
            token=self.github_token,
            repo_owner=GITHUB_REPO_OWNER,
            repo_name=GITHUB_REPO_NAME,
        )

        # Step 1: Clone/update repository
        logger.info("Step 1: Cloning/updating repository...")
        if not git_ops.clone_or_update(token=self.github_token):
            raise Exception("Failed to clone/update repository")

        # Step 2: Create branch
        import time
        timestamp = int(time.time())
        branch_name = f"dataset/{dataset_name}-{timestamp}"
        logger.info(f"Step 2: Creating branch: {branch_name}")
        
        if not git_ops.create_branch(branch_name):
            raise Exception(f"Failed to create branch: {branch_name}")

        # Step 3: Generate Terraform file
        logger.info("Step 3: Generating Terraform configuration...")
        
        # Parse labels if it's a string
        if isinstance(labels, str):
            label_dict = {}
            if labels:
                for item in labels.split(','):
                    if ':' in item:
                        key, value = item.split(':', 1)
                        label_dict[key.strip()] = value.strip()
            labels = label_dict
        
        terraform_content = terraform_gen.generate_bigquery_dataset(
            dataset_name=dataset_name,
            location=location,
            labels=labels,
            service_account=service_account,
        )

        # Step 4: Write file to repository
        logger.info("Step 4: Writing Terraform file...")
        repo_path = git_ops.get_repo_path()
        terraform_dir = repo_path / TERRAFORM_DIR
        
        file_path = terraform_gen.write_to_file(
            content=terraform_content,
            target_dir=terraform_dir,
            filename=f"{dataset_name}.tf",
        )
        
        # Get relative path for git operations
        relative_path = f"{TERRAFORM_DIR}/{dataset_name}.tf"

        # Step 5: Commit changes
        logger.info("Step 5: Committing changes...")
        labels_str = ', '.join([f'{k}={v}' for k, v in labels.items()]) if labels else 'none'
        commit_message = f"""feat: Add BigQuery dataset {dataset_name}

Created via AI Chatbot
- Location: {location}
- Labels: {labels_str}
- Owner: {service_account}

Request ID: {request_id}
"""
        
        if not git_ops.commit_changes(relative_path, commit_message):
            raise Exception("Failed to commit changes")

        # Step 6: Push branch
        logger.info("Step 6: Pushing branch to remote...")
        if not git_ops.push_branch(branch_name, token=self.github_token):
            raise Exception("Failed to push branch")

        # Step 7: Create Pull Request
        logger.info("Step 7: Creating Pull Request...")
        pr_title = f"Add BigQuery Dataset: {dataset_name}"
        pr_body = github_api.format_pr_body(
            dataset_name=dataset_name,
            location=location,
            labels=labels,
            service_account=service_account,
            request_id=request_id,
        )
        
        pr_url = github_api.create_pull_request(
            title=pr_title,
            body=pr_body,
            head_branch=branch_name,
            base_branch=github_api.get_default_branch(),
        )

        if not pr_url:
            raise Exception("Failed to create Pull Request")

        # Update status to completed
        self._update_request_status(request_id, "completed", pr_url=pr_url)
        
        logger.info(f"✅ Successfully created PR: {pr_url}")
        
        # Cleanup
        git_ops.cleanup()

    def pull_and_process(self):
        """Pull messages from subscription and process them."""
        logger.info(f"Pulling messages from {self.subscription_path}...")
        
        try:
            # Pull messages (max 10 at a time)
            response = self.subscriber.pull(
                request={
                    "subscription": self.subscription_path,
                    "max_messages": 10,
                },
                timeout=30,
            )
            
            if not response.received_messages:
                logger.info("No messages found in queue.")
                return 0

            logger.info(f"Received {len(response.received_messages)} message(s)")
            
            # Process each message
            ack_ids = []
            for received_message in response.received_messages:
                try:
                    # Decode message data
                    data = json.loads(received_message.message.data.decode("utf-8"))
                    
                    # Process the request
                    self.process_message_data(data)
                    
                    # Add to ack list if successful
                    ack_ids.append(received_message.ack_id)
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    # Don't ack failed messages - they'll be retried
                    
            # Acknowledge successfully processed messages
            if ack_ids:
                self.subscriber.acknowledge(
                    request={
                        "subscription": self.subscription_path,
                        "ack_ids": ack_ids,
                    }
                )
                logger.info(f"Acknowledged {len(ack_ids)} message(s)")
                
            return len(ack_ids)
            
        except Exception as e:
            logger.error(f"Error in pull operation: {e}", exc_info=True)
            return 0


if __name__ == "__main__":
    logger.info("🚀 Starting Cloud Run Job - Git Worker")
    
    worker = Worker()
    
    # Process messages in a loop until queue is empty or timeout
    # Cloud Run Jobs have a max execution time, so we process what we can
    total_processed = 0
    max_iterations = 10  # Prevent infinite loops
    
    for iteration in range(max_iterations):
        logger.info(f"Iteration {iteration + 1}/{max_iterations}")
        
        processed = worker.pull_and_process()
        total_processed += processed
        
        if processed == 0:
            logger.info("No more messages to process. Job complete.")
            break
    
    logger.info(f"✅ Job execution completed. Processed {total_processed} message(s).")
