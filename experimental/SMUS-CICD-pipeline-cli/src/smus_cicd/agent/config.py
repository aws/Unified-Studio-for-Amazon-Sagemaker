"""Configuration management for SMUS CLI Agent."""

import os
from pathlib import Path
from typing import Dict, Any
import yaml


def get_config_path() -> Path:
    """Get path to agent config file."""
    config_dir = Path.home() / '.smus-cli'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / 'config.yaml'


def load_config() -> Dict[str, Any]:
    """Load agent configuration, creating default if needed."""
    config_path = get_config_path()
    
    if not config_path.exists():
        # Create default config
        create_default_config()
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def save_config(config: Dict[str, Any]) -> None:
    """Save agent configuration."""
    config_path = get_config_path()
    
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def create_default_config() -> None:
    """Create default configuration file."""
    # Read template from package
    template_path = Path(__file__).parent / 'config_template.yaml'
    
    with open(template_path, 'r') as f:
        template = f.read()
    
    # Expand ~ in paths
    template = template.replace('~/', str(Path.home()) + '/')
    
    # Write to user config
    config_path = get_config_path()
    with open(config_path, 'w') as f:
        f.write(template)
    
    # Create logs directory
    logs_dir = Path.home() / '.smus-cli' / 'agent-logs'
    logs_dir.mkdir(parents=True, exist_ok=True)


def get_model_id(config: Dict[str, Any] = None) -> str:
    """Get configured model ID."""
    if config is None:
        config = load_config()
    
    return config.get('interactive', {}).get(
        'default_model',
        'us.anthropic.claude-3-5-haiku-20241022-v1:0'
    )


def get_kb_id(config: Dict[str, Any] = None) -> str:
    """Get Knowledge Base ID."""
    if config is None:
        config = load_config()
    
    return config.get('bedrock', {}).get('knowledge_base_id')


def set_kb_id(kb_id: str, data_source_id: str = None) -> None:
    """Save Knowledge Base ID to config."""
    config = load_config()
    
    if 'bedrock' not in config:
        config['bedrock'] = {}
    
    config['bedrock']['knowledge_base_id'] = kb_id
    
    if data_source_id:
        config['bedrock']['data_source_id'] = data_source_id
    
    save_config(config)
