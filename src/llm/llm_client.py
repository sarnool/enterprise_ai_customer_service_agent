"""OpenAI LLM client wrapper, configured from config/llm_config.yaml."""
import os
from typing import List, Dict, Any, Optional
from openai import OpenAI
from src.utils.config_loader import load_yaml_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class LLMClient:
    """Wrapper for OpenAI API calls.

    Model, temperature, and token settings come from config/llm_config.yaml
    by default. Pass explicit arguments to override the config for a specific
    instance (e.g. in tests) without editing the YAML file.
    """

    def __init__(self, model: Optional[str] = None, temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None):
        config = load_yaml_config("config/llm_config.yaml")
        models_config = config.get("models", {})
        chat_config = models_config.get("chat", {})
        api_config = config.get("api", {})

        # LLM_BASE_URL is optional - unset, this is a normal OpenAI client.
        # Set it (e.g. to https://openrouter.ai/api/v1) to route through an
        # OpenAI-API-compatible provider like OpenRouter instead, using the
        # same OPENAI_API_KEY variable for that provider's key. Model names
        # in config/llm_config.yaml need to match whichever provider is
        # active (OpenRouter uses provider-namespaced names like
        # "openai/gpt-4", plain OpenAI does not).
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL") or None,
            timeout=api_config.get("timeout", 60),
            max_retries=api_config.get("max_retries", 2),
        )

        self.model = model or chat_config.get("model_name", "gpt-4")
        self.temperature = temperature if temperature is not None else chat_config.get("temperature", 0.7)
        self.max_tokens = max_tokens if max_tokens is not None else chat_config.get("max_tokens", 2000)

        # Classification typically uses a lower temperature and a shorter
        # response budget than open-ended generation - config/llm_config.yaml
        # defines this separately under models.classification.
        classification_config = models_config.get("classification", {})
        self._classification_model = classification_config.get("model_name", self.model)
        self._classification_temperature = classification_config.get("temperature", 0.3)
        self._classification_max_tokens = classification_config.get("max_tokens", 500)

    def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate completion from messages."""
        try:
            response = self.client.chat.completions.create(
                model=kwargs.get("model", self.model),
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens)
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            raise

    def classify(self, query: str, system_prompt: str) -> str:
        """Classify user query, using the classification model settings from config/llm_config.yaml."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        return self.generate(
            messages,
            model=self._classification_model,
            temperature=self._classification_temperature,
            max_tokens=self._classification_max_tokens
        )
