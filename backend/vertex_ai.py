"""
Vertex AI integration for entity extraction using Gemini with Function Calling.
"""
import os
import json
import logging
from typing import Dict, Optional, Any
import vertexai
from vertexai.preview.generative_models import (
    GenerativeModel,
    FunctionDeclaration,
    Tool,
    GenerationConfig,
)

logger = logging.getLogger(__name__)

# Initialize Vertex AI
PROJECT_ID = os.getenv("PROJECT_ID", "helpful-charmer-485315-j7")
LOCATION = os.getenv("LOCATION", "us-central1")
MODEL_NAME = os.getenv("VERTEX_AI_MODEL", "gemini-2.5-pro")

vertexai.init(project=PROJECT_ID, location=LOCATION)


# Define the function schema for dataset extraction
extract_dataset_function = FunctionDeclaration(
    name="extract_dataset_info",
    description="Extract BigQuery dataset creation parameters from user message",
    parameters={
        "type": "object",
        "properties": {
            "dataset_name": {
                "type": "string",
                "description": "The name/identifier for the BigQuery dataset. Must contain only lowercase letters, numbers, and underscores.",
            },
            "location": {
                "type": "string",
                "description": "The GCP region or multi-region for the dataset (e.g., us-central1, EU, asia-northeast1)",
            },
            "labels": {
                "type": "string",
                "description": "Comma-separated key-value pairs for labeling the dataset (e.g., 'env:prod,team:marketing,cost-center:cc-001')",
            },
            "service_account": {
                "type": "string",
                "description": "The service account email that will own the dataset (e.g., sa-name@project.iam.gserviceaccount.com)",
            },
        },
    },
)

dataset_extraction_tool = Tool(function_declarations=[extract_dataset_function])


class VertexAIExtractor:
    """Handles entity extraction using Vertex AI Gemini."""

    def __init__(self):
        self.model = GenerativeModel(
            MODEL_NAME,
            tools=[dataset_extraction_tool],
        )
        self.generation_config = GenerationConfig(
            temperature=0.1,  # Low temperature for deterministic extraction
            top_p=0.95,
            top_k=20,
            max_output_tokens=1024,
        )

    def extract_entities(
        self, user_message: str, conversation_history: list = None
    ) -> Dict[str, Any]:
        """
        Extract dataset entities from user message.

        Args:
            user_message: The user's natural language input
            conversation_history: Previous messages for context

        Returns:
            Dictionary with extracted entities and metadata
        """
        try:
            # Build the prompt with context
            prompt = self._build_prompt(user_message, conversation_history)

            logger.info(f"Sending prompt to Vertex AI: {prompt[:200]}...")

            # Generate response with function calling
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config,
            )

            # Parse the function call response
            extracted_data = self._parse_response(response)

            logger.info(f"Extracted entities: {extracted_data}")
            return extracted_data

        except Exception as e:
            logger.error(f"Error extracting entities: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "entities": {},
            }

    def _build_prompt(self, user_message: str, conversation_history: list = None) -> str:
        """Build a contextualized prompt for entity extraction."""
        context = """You are a helpful assistant that extracts BigQuery dataset creation parameters from user messages.

Extract the following information:
1. dataset_name: The name of the dataset (lowercase letters, numbers, underscores only)
2. location: GCP region (e.g., us-central1, EU, asia-northeast1)
3. labels: Key-value pairs for labeling (format: "key:value" or "key=value")
4. service_account: Service account email for dataset ownership

Only extract fields that are explicitly mentioned. Leave fields empty if not provided.

"""
        if conversation_history:
            context += "\n**Previous conversation:**\n"
            for msg in conversation_history[-5:]:  # Last 5 messages for context
                role = msg.get("role", "user")
                content = msg.get("content", "")
                context += f"{role.upper()}: {content}\n"
            context += "\n"

        context += f"**Current user message:**\n{user_message}\n\n"
        context += "Extract all available dataset parameters from the conversation."

        return context

    def _parse_response(self, response) -> Dict[str, Any]:
        """Parse Vertex AI response and extract function call arguments."""
        try:
            # Check if response contains function calls
            if not response.candidates:
                return {
                    "success": False,
                    "error": "No response from model",
                    "entities": {},
                }

            candidate = response.candidates[0]
            
            # Check if there's a function call
            if candidate.content.parts:
                for part in candidate.content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        function_call = part.function_call
                        if function_call.name == "extract_dataset_info":
                            # Extract the arguments
                            entities = {}
                            for key, value in function_call.args.items():
                                entities[key] = value

                            return {
                                "success": True,
                                "entities": entities,
                            }

            # If no function call, try to extract from text
            if candidate.content.parts and candidate.content.parts[0].text:
                text_response = candidate.content.parts[0].text
                logger.warning(
                    f"No function call in response, got text: {text_response}"
                )
                return {
                    "success": False,
                    "error": "Model did not use function calling",
                    "text_response": text_response,
                    "entities": {},
                }

            return {
                "success": False,
                "error": "Unable to parse response",
                "entities": {},
            }

        except Exception as e:
            logger.error(f"Error parsing response: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Parsing error: {str(e)}",
                "entities": {},
            }

    def generate_follow_up_question(self, missing_fields: list) -> str:
        """Generate a natural follow-up question for missing fields."""
        prompts = {
            "dataset_name": "What would you like to name this dataset?",
            "location": "Which GCP region should the dataset be located in? (e.g., us-central1, EU, asia-northeast1)",
            "labels": "What labels would you like to add? Please provide them in the format 'key:value' (e.g., env:prod, team:marketing)",
            "service_account": "Which service account should own this dataset? Please provide the full email address.",
        }

        if len(missing_fields) == 1:
            field = missing_fields[0]
            return f"I still need one more thing: {prompts.get(field, f'the {field}')}"

        questions = [prompts.get(field, f"• {field}") for field in missing_fields]
        return "I still need the following information:\n" + "\n".join(
            f"• {q}" for q in questions
        )
