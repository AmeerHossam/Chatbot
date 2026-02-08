"""
State management using Firestore for conversation and request tracking.
"""
import os
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from google.cloud import firestore

logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("PROJECT_ID", "helpful-charmer-485315-j7")
FIRESTORE_DB = os.getenv("FIRESTORE_DATABASE", "(default)")


class StateManager:
    """Manages conversation state and request tracking in Firestore."""

    def __init__(self):
        self.db = firestore.Client(project=PROJECT_ID, database=FIRESTORE_DB)
        self.conversations_collection = self.db.collection("conversations")
        self.requests_collection = self.db.collection("pr_requests")

    # ===== Conversation State Management =====

    def get_conversation_state(self, session_id: str) -> Dict[str, Any]:
        """Retrieve conversation state for a session."""
        try:
            doc_ref = self.conversations_collection.document(session_id)
            doc = doc_ref.get()

            if doc.exists:
                return doc.to_dict()
            else:
                # Initialize new conversation
                initial_state = {
                    "session_id": session_id,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "messages": [],
                    "extracted_entities": {},
                    "status": "in_progress",
                }
                doc_ref.set(initial_state)
                return initial_state

        except Exception as e:
            logger.error(f"Error getting conversation state: {e}", exc_info=True)
            return {
                "session_id": session_id,
                "messages": [],
                "extracted_entities": {},
                "status": "error",
            }

    def update_conversation_state(
        self,
        session_id: str,
        message: str,
        role: str = "user",
        extracted_entities: Dict = None,
    ) -> bool:
        """Update conversation state with new message and entities."""
        try:
            doc_ref = self.conversations_collection.document(session_id)

            # Add message to history
            new_message = {
                "role": role,
                "content": message,
                "timestamp": datetime.utcnow(),
            }

            update_data = {
                "messages": firestore.ArrayUnion([new_message]),
                "updated_at": datetime.utcnow(),
            }

            # Merge extracted entities
            if extracted_entities:
                current_state = self.get_conversation_state(session_id)
                merged_entities = current_state.get("extracted_entities", {})
                
                # Update only non-empty fields
                for key, value in extracted_entities.items():
                    if value:  # Only update if value is not None or empty
                        merged_entities[key] = value
                
                update_data["extracted_entities"] = merged_entities

            doc_ref.update(update_data)
            logger.info(f"Updated conversation state for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating conversation state: {e}", exc_info=True)
            return False

    def get_conversation_history(self, session_id: str, limit: int = 10) -> list:
        """Get recent conversation messages."""
        state = self.get_conversation_state(session_id)
        messages = state.get("messages", [])
        return messages[-limit:]  # Return last N messages

    def mark_conversation_complete(self, session_id: str, request_id: str) -> bool:
        """Mark conversation as complete and link to PR request."""
        try:
            doc_ref = self.conversations_collection.document(session_id)
            doc_ref.update({
                "status": "completed",
                "request_id": request_id,
                "completed_at": datetime.utcnow(),
            })
            return True
        except Exception as e:
            logger.error(f"Error marking conversation complete: {e}", exc_info=True)
            return False

    # ===== PR Request Tracking =====

    def create_pr_request(
        self,
        request_id: str,
        session_id: str,
        payload: Dict[str, Any],
    ) -> bool:
        """Create a new PR request record."""
        try:
            doc_ref = self.requests_collection.document(request_id)
            
            request_data = {
                "request_id": request_id,
                "session_id": session_id,
                "payload": payload,
                "status": "pending",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            
            doc_ref.set(request_data)
            logger.info(f"Created PR request: {request_id}")
            return True

        except Exception as e:
            logger.error(f"Error creating PR request: {e}", exc_info=True)
            return False

    def update_pr_request_status(
        self,
        request_id: str,
        status: str,
        pr_url: str = None,
        error: str = None,
    ) -> bool:
        """Update PR request status."""
        try:
            doc_ref = self.requests_collection.document(request_id)
            
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow(),
            }
            
            if pr_url:
                update_data["pr_url"] = pr_url
            if error:
                update_data["error"] = error
            
            doc_ref.update(update_data)
            logger.info(f"Updated PR request {request_id} to status: {status}")
            return True

        except Exception as e:
            logger.error(f"Error updating PR request status: {e}", exc_info=True)
            return False

    def get_pr_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get PR request details."""
        try:
            doc_ref = self.requests_collection.document(request_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            return None

        except Exception as e:
            logger.error(f"Error getting PR request: {e}", exc_info=True)
            return None
