"""Knowledge Base retrieval using Bedrock Agent Runtime."""

from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError


class KnowledgeBaseRetriever:
    """Retrieve documents from Bedrock Knowledge Base."""

    def __init__(self, kb_id: str, region: str = "us-east-1"):
        self.kb_id = kb_id
        self.region = region
        self.client = boto3.client("bedrock-agent-runtime", region_name=region)

    def retrieve(
        self, query: str, max_results: int = 5, min_score: float = 0.5
    ) -> List[str]:
        """
        Retrieve relevant documents for a query.

        Args:
            query: Search query
            max_results: Maximum number of results
            min_score: Minimum relevance score (0-1)

        Returns:
            List of retrieved document texts
        """
        if not self.kb_id:
            return []

        try:
            response = self.client.retrieve(
                knowledgeBaseId=self.kb_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {"numberOfResults": max_results}
                },
            )

            # Extract and filter results
            documents = []
            for result in response.get("retrievalResults", []):
                score = result.get("score", 0)

                if score >= min_score:
                    content = result.get("content", {}).get("text", "")
                    if content:
                        documents.append(content)

            return documents

        except ClientError as e:
            error_code = e.response["Error"]["Code"]

            if error_code == "ResourceNotFoundException":
                print(f"⚠️  Knowledge Base not found: {self.kb_id}")
                return []

            print(f"⚠️  KB retrieval error: {e}")
            return []

    def retrieve_with_metadata(
        self, query: str, max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents with metadata.

        Returns:
            List of dicts with 'text', 'score', 'source' keys
        """
        if not self.kb_id:
            return []

        try:
            response = self.client.retrieve(
                knowledgeBaseId=self.kb_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {"numberOfResults": max_results}
                },
            )

            results = []
            for result in response.get("retrievalResults", []):
                results.append(
                    {
                        "text": result.get("content", {}).get("text", ""),
                        "score": result.get("score", 0),
                        "source": result.get("location", {})
                        .get("s3Location", {})
                        .get("uri", "unknown"),
                    }
                )

            return results

        except ClientError as e:
            print(f"⚠️  KB retrieval error: {e}")
            return []
