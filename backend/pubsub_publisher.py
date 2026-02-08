"""
Pub/Sub publisher for dispatching complete dataset requests to the worker.
"""
import os
import json
import logging
from typing import Dict, Any
from google.cloud import pubsub_v1

logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("PROJECT_ID", "helpful-charmer-485315-j7")
TOPIC_NAME = os.getenv("PUBSUB_TOPIC", "dataset-pr-requests")


class PubSubPublisher:
    """Publishes messages to Cloud Pub/Sub."""

    def __init__(self):
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(PROJECT_ID, TOPIC_NAME)
        logger.info(f"Initialized Pub/Sub publisher for topic: {self.topic_path}")

    def publish_dataset_request(
        self,
        request_id: str,
        dataset_name: str,
        location: str,
        labels: Dict[str, str],
        service_account: str,
        session_id: str = None,
    ) -> bool:
        """
        Publish a complete dataset request to Pub/Sub.

        Args:
            request_id: Unique identifier for this request
            dataset_name: BigQuery dataset name
            location: GCP region
            labels: Dict of labels
            service_account: Service account email
            session_id: Session ID for tracking

        Returns:
            True if published successfully, False otherwise
        """
        try:
            payload = {
                "request_id": request_id,
                "session_id": session_id,
                "dataset_name": dataset_name,
                "location": location,
                "labels": labels,
                "service_account": service_account,
            }

            # Convert to JSON bytes
            message_data = json.dumps(payload).encode("utf-8")

            # Publish with attributes for filtering/routing
            future = self.publisher.publish(
                self.topic_path,
                message_data,
                request_id=request_id,
                dataset_name=dataset_name,
            )

            # Wait for publish to complete
            message_id = future.result(timeout=10)
            
            logger.info(
                f"Published request {request_id} to Pub/Sub. Message ID: {message_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error publishing to Pub/Sub: {e}", exc_info=True)
            return False
