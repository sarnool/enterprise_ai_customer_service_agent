"""Embedding generation utilities, configured from config/llm_config.yaml."""
import os
from typing import List, Optional
from openai import OpenAI
from src.utils.config_loader import load_yaml_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class EmbeddingGenerator:
    """Generate embeddings using OpenAI.

    The embedding model comes from config/llm_config.yaml's models.embedding
    section by default. Pass an explicit model to override the config for a
    specific instance without editing the YAML file.
    """

    def __init__(self, model: Optional[str] = None):
        config = load_yaml_config("config/llm_config.yaml")
        api_config = config.get("api", {})

        # See src/llm/llm_client.py for what LLM_BASE_URL does - the same
        # provider switch applies here, and OpenRouter's /embeddings
        # endpoint lives at the same base URL as its chat endpoint.
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL") or None,
            timeout=api_config.get("timeout", 60),
            max_retries=api_config.get("max_retries", 2),
        )
        embedding_config = config.get("models", {}).get("embedding", {})
        self.model = model or embedding_config.get("model_name", "text-embedding-3-small")

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            raise

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Batch embedding generation error: {e}")
            raise
