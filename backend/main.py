"""
FastAPI backend service for AI chatbot.
Handles conversation, entity extraction, and workflow orchestration.
"""
import os
import logging
import uuid
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google.cloud.run_v2 import JobsClient, RunJobRequest
from dotenv import load_dotenv

from vertex_ai import VertexAIExtractor
from state_manager import StateManager
from pubsub_publisher import PubSubPublisher

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Dataset Chatbot API",
    description="AI-powered chatbot for creating BigQuery dataset PRs",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
vertex_extractor = VertexAIExtractor()
state_manager = StateManager()
pubsub_publisher = PubSubPublisher()

# ===== Request/Response Models =====


class ChatRequest(BaseModel):
    """Chat request from user."""
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None)


class ChatResponse(BaseModel):
    """Chat response to user."""
    message: str
    session_id: str
    status: str  # "collecting", "processing", "completed", "error"
    request_id: Optional[str] = None  # Added for tracking PR creation
    pr_url: Optional[str] = None
    extracted_entities: Optional[dict] = None


class StatusRequest(BaseModel):
    """Request to check PR creation status."""
    request_id: str


class StatusResponse(BaseModel):
    """PR creation status response."""
    request_id: str
    status: str
    pr_url: Optional[str] = None
    error: Optional[str] = None


# ===== Helper Functions =====

def parse_labels(labels_str: str) -> dict:
    """
    Parse labels string into dictionary.
    Supports formats: 'key:value,key2:value2' or 'key=value,key2=value2'
    """
    if not labels_str:
        return {}
    
    labels_dict = {}
    try:
        # Split by comma and parse key:value or key=value pairs
        pairs = [pair.strip() for pair in labels_str.split(',')]
        for pair in pairs:
            if ':' in pair:
                key, value = pair.split(':', 1)
            elif '=' in pair:
                key, value = pair.split('=', 1)
            else:
                continue  # Skip invalid pairs
            
            labels_dict[key.strip()] = value.strip()
    except Exception as e:
        logger.warning(f"Error parsing labels: {e}")
    
    return labels_dict


# ===== Endpoints =====


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Dataset Chatbot API",
        "status": "healthy",
        "version": "1.0.0",
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint. Handles conversation and entity extraction.
    
    Flow:
    1. Get/create conversation state
    2. Extract entities using Vertex AI
    3. Check if all required fields are present
    4. If complete, dispatch to worker via Pub/Sub
    5. Return appropriate response
    """
    try:
        # Generate or use existing session ID
        session_id = request.session_id or str(uuid.uuid4())
        
        logger.info(f"Processing chat request for session: {session_id}")
        
        # Get conversation state
        conversation_state = state_manager.get_conversation_state(session_id)
        
        # Check if previous conversation was completed - if so, start fresh
        if conversation_state.get("status") == "completed":
            logger.info(f"Previous conversation completed. Starting new conversation for session {session_id}")
            # Reset the conversation state for a new dataset request
            doc_ref = state_manager.conversations_collection.document(session_id)
            doc_ref.update({
                "status": "in_progress",
                "extracted_entities": {},
                "updated_at": datetime.utcnow(),
            })
            # Get the fresh state
            conversation_state = state_manager.get_conversation_state(session_id)
        
        conversation_history = conversation_state.get("messages", [])
        
        # Extract entities from user message
        extraction_result = vertex_extractor.extract_entities(
            request.message,
            conversation_history
        )
        
        if not extraction_result.get("success"):
            # Extraction failed, ask user to rephrase
            error_message = "I'm having trouble understanding. Could you please rephrase that?"
            
            state_manager.update_conversation_state(
                session_id,
                request.message,
                role="user"
            )
            state_manager.update_conversation_state(
                session_id,
                error_message,
                role="assistant"
            )
            
            return ChatResponse(
                message=error_message,
                session_id=session_id,
                status="collecting",
            )
        
        # Update conversation with extracted entities
        new_entities = extraction_result.get("entities", {})
        state_manager.update_conversation_state(
            session_id,
            request.message,
            role="user",
            extracted_entities=new_entities
        )
        
        # Get updated state with merged entities
        updated_state = state_manager.get_conversation_state(session_id)
        all_entities = updated_state.get("extracted_entities", {})

        
        # Check for required fields
        required_fields = ["dataset_name", "location", "labels", "service_account"]
        missing_fields = [
            field for field in required_fields
            if not all_entities.get(field)
        ]
        
        if missing_fields:
            # Still collecting information
            follow_up = vertex_extractor.generate_follow_up_question(missing_fields)
            
            # Show what we have so far
            collected = [field for field in required_fields if all_entities.get(field)]
            if collected:
                status_msg = "Great! I've collected:\\n"
                for field in collected:
                    value = all_entities[field]
                    if isinstance(value, dict):
                        value = ", ".join([f"{k}:{v}" for k, v in value.items()])
                    status_msg += f"✓ {field}: {value}\\n"
                status_msg += f"\\n{follow_up}"
            else:
                status_msg = f"I can help you create a BigQuery dataset! {follow_up}"
            
            state_manager.update_conversation_state(
                session_id,
                status_msg,
                role="assistant"
            )
            
            return ChatResponse(
                message=status_msg,
                session_id=session_id,
                status="collecting",
                extracted_entities=all_entities,
            )
        
        # All fields collected! Dispatch to worker
        request_id = str(uuid.uuid4())
        
        # Parse labels string to dictionary
        labels_dict = parse_labels(all_entities["labels"]) if isinstance(all_entities["labels"], str) else all_entities["labels"]
        
        # Create PR request record
        state_manager.create_pr_request(
            request_id=request_id,
            session_id=session_id,
            payload={
                "dataset_name": all_entities["dataset_name"],
                "location": all_entities["location"],
                "labels": labels_dict,
                "service_account": all_entities["service_account"],
            }
        )
        
        # Publish to Pub/Sub
        publish_success = pubsub_publisher.publish_dataset_request(
            request_id=request_id,
            session_id=session_id,
            dataset_name=all_entities["dataset_name"],
            location=all_entities["location"],
            labels=labels_dict,
            service_account=all_entities["service_account"],
        )
        
        if not publish_success:
            error_msg = "Sorry, I encountered an error while creating your request. Please try again."
            return ChatResponse(
                message=error_msg,
                session_id=session_id,
                status="error",
            )
        
        # Trigger the Cloud Run Job immediately for instant processing
        try:
            project_id = os.getenv("PROJECT_ID", "helpful-charmer-485315-j7")
            region = os.getenv("REGION", "us-central1")
            job_name = f"projects/{project_id}/locations/{region}/jobs/git-worker"
            
            jobs_client = JobsClient()
            request = RunJobRequest(name=job_name)
            
            # Trigger the job (async - don't wait for completion)
            operation = jobs_client.run_job(request=request)
            logger.info(f"Triggered Cloud Run Job: {job_name}")
            
        except Exception as e:
            # Log error but don't fail the request - Pub/Sub message is already queued
            # Scheduler will still pick it up as backup
            logger.error(f"Failed to trigger job directly: {e}", exc_info=True)
        
        # Mark conversation as complete
        state_manager.mark_conversation_complete(session_id, request_id)
        
        completion_message = (
            f"✅ Perfect! I have all the information I need.\n\n"
            f"Creating Pull Request for dataset '{all_entities['dataset_name']}'...\n\n"
            f"Request ID: {request_id}\n\n"
            f"You can check the status using the /status endpoint. "
            f"I'll update you once the PR is created!"
        )
        
        state_manager.update_conversation_state(
            session_id,
            completion_message,
            role="assistant"
        )
        
        return ChatResponse(
            message=completion_message,
            session_id=session_id,
            status="processing",
            request_id=request_id,  # Include request_id for polling
            extracted_entities=all_entities,
        )
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{request_id}", response_model=StatusResponse)
async def get_status(request_id: str):
    """Get the status of a PR creation request.
    
    NOTE: This endpoint is primarily kept for debugging and fallback purposes.
    The frontend now uses Firestore real-time listeners for instant status updates.
    """
    try:
        pr_request = state_manager.get_pr_request(request_id)
        
        if not pr_request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        return StatusResponse(
            request_id=request_id,
            status=pr_request.get("status", "unknown"),
            pr_url=pr_request.get("pr_url"),
            error=pr_request.get("error"),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/pr-ready")
async def pr_ready_webhook(request_id: str, pr_url: str, status: str = "completed"):
    """
    Webhook endpoint for worker to notify when PR is created.
    This allows real-time updates to the request status.
    """
    try:
        logger.info(f"Received webhook for request {request_id}: {status}")
        
        state_manager.update_pr_request_status(
            request_id=request_id,
            status=status,
            pr_url=pr_url if status == "completed" else None,
            error=pr_url if status == "failed" else None,
        )
        
        return {"success": True, "request_id": request_id}
    
    except Exception as e:
        logger.error(f"Error in webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
