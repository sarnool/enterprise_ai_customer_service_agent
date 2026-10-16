"""Prompt management and template loading."""
from typing import Dict, Any
from src.utils.config_loader import load_yaml_config

class PromptManager:
    """Manages prompt templates."""
    
    def __init__(self):
        self.prompts = load_yaml_config("config/prompts.yaml")
    
    def get_prompt(self, prompt_name: str) -> Dict[str, Any]:
        """Get prompt by name."""
        return self.prompts.get(prompt_name, {})
    
    def format_prompt(self, template: str, **kwargs) -> str:
        """Format prompt template with variables."""
        return template.format(**kwargs)
