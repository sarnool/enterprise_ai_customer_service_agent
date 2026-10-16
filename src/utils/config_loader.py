"""Configuration loader for YAML files."""
import yaml
from pathlib import Path
from typing import Dict, Any

def load_yaml_config(config_path: str) -> Dict[str, Any]:
    """Load YAML configuration file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_all_configs() -> Dict[str, Dict[str, Any]]:
    """Load all configuration files."""
    config_dir = Path("config")
    return {
        "agent": load_yaml_config(config_dir / "agent_config.yaml"),
        "llm": load_yaml_config(config_dir / "llm_config.yaml"),
        "prompts": load_yaml_config(config_dir / "prompts.yaml")
    }
