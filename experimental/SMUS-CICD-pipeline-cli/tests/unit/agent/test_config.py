"""Unit tests for agent configuration management."""

import pytest
from pathlib import Path
import tempfile
import shutil
import yaml

from smus_cicd.agent.config import (
    get_config_path,
    load_config,
    save_config,
    create_default_config,
    get_model_id,
    get_kb_id,
    set_kb_id
)


@pytest.fixture
def temp_home(monkeypatch, tmp_path):
    """Create temporary home directory for testing."""
    temp_home_dir = tmp_path / "home"
    temp_home_dir.mkdir()
    monkeypatch.setenv("HOME", str(temp_home_dir))
    return temp_home_dir


def test_get_config_path(temp_home):
    """Test config path is correct."""
    config_path = get_config_path()
    assert config_path == temp_home / ".smus-cli" / "config.yaml"


def test_create_default_config(temp_home):
    """Test default config creation."""
    create_default_config()
    
    config_path = temp_home / ".smus-cli" / "config.yaml"
    assert config_path.exists()
    
    # Check logs directory created
    logs_dir = temp_home / ".smus-cli" / "agent-logs"
    assert logs_dir.exists()
    
    # Check config content
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    assert 'interactive' in config
    assert 'bedrock' in config
    assert 'agent' in config
    assert config['interactive']['default_model'] == 'anthropic.claude-3-5-haiku-20241022-v1:0'


def test_load_config_creates_if_missing(temp_home):
    """Test load_config creates default if missing."""
    config = load_config()
    
    assert config is not None
    assert 'interactive' in config
    
    # Check file was created
    config_path = temp_home / ".smus-cli" / "config.yaml"
    assert config_path.exists()


def test_save_config(temp_home):
    """Test saving config."""
    config = {
        'interactive': {'default_model': 'test-model'},
        'bedrock': {'knowledge_base_id': 'kb-123'}
    }
    
    save_config(config)
    
    # Load and verify
    loaded = load_config()
    assert loaded['interactive']['default_model'] == 'test-model'
    assert loaded['bedrock']['knowledge_base_id'] == 'kb-123'


def test_get_model_id_default(temp_home):
    """Test getting default model ID."""
    model_id = get_model_id()
    assert model_id == 'anthropic.claude-3-5-haiku-20241022-v1:0'


def test_get_model_id_custom(temp_home):
    """Test getting custom model ID."""
    config = load_config()
    config['interactive']['default_model'] = 'custom-model'
    save_config(config)
    
    model_id = get_model_id()
    assert model_id == 'custom-model'


def test_get_kb_id_none(temp_home):
    """Test getting KB ID when not set."""
    kb_id = get_kb_id()
    assert kb_id is None


def test_set_kb_id(temp_home):
    """Test setting KB ID."""
    set_kb_id('kb-abc123', 'ds-xyz789')
    
    config = load_config()
    assert config['bedrock']['knowledge_base_id'] == 'kb-abc123'
    assert config['bedrock']['data_source_id'] == 'ds-xyz789'


def test_get_kb_id_after_set(temp_home):
    """Test getting KB ID after setting."""
    set_kb_id('kb-test')
    
    kb_id = get_kb_id()
    assert kb_id == 'kb-test'
