"""Bedrock API client wrapper."""

import json
from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError


class BedrockClient:
    """Wrapper for Bedrock Runtime API."""

    def __init__(self, model_id: str, region: str = "us-east-1"):
        self.model_id = model_id
        self.region = region
        self.client = boto3.client("bedrock-runtime", region_name=region)

    def invoke(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """
        Invoke Bedrock model with messages.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text response
        """
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        if system_prompt:
            body["system"] = system_prompt

        try:
            response = self.client.invoke_model(
                modelId=self.model_id, body=json.dumps(body)
            )

            result = json.loads(response["body"].read())
            return result["content"][0]["text"]

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_msg = e.response["Error"]["Message"]
            raise Exception(f"Bedrock API error ({error_code}): {error_msg}")

    def invoke_with_context(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        system_prompt: str = None,
        retrieved_context: List[str] = None,
    ) -> str:
        """
        Invoke model with conversation history and retrieved context.

        Args:
            user_message: Current user message
            conversation_history: Previous messages
            system_prompt: System prompt
            retrieved_context: Retrieved documents from KB

        Returns:
            Generated response
        """
        # Build messages with context
        messages = conversation_history.copy()

        # Add retrieved context to user message if available
        if retrieved_context:
            context_text = "\n\n".join(
                [f"[Document {i+1}]\n{doc}" for i, doc in enumerate(retrieved_context)]
            )

            enhanced_message = f"""Based on the following documentation:

{context_text}

User question: {user_message}"""

            messages.append({"role": "user", "content": enhanced_message})
        else:
            messages.append({"role": "user", "content": user_message})

        return self.invoke(messages=messages, system_prompt=system_prompt)
