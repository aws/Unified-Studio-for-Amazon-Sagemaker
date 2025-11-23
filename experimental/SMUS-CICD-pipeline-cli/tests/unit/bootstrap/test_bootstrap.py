"""Unit tests for bootstrap module."""

import pytest

from smus_cicd.bootstrap import BootstrapAction, BootstrapConfig, executor, registry


class TestBootstrapAction:
    """Test BootstrapAction model."""

    def test_create_action(self):
        """Test creating a bootstrap action."""
        action = BootstrapAction(
            type="cli.print",
            parameters={"message": "Hello World"}
        )
        assert action.type == "cli.print"
        assert action.parameters["message"] == "Hello World"

    def test_action_type_validation(self):
        """Test action type must have service.action format."""
        with pytest.raises(ValueError, match="must be in format 'service.action'"):
            BootstrapAction(type="invalid", parameters={})


class TestBootstrapConfig:
    """Test BootstrapConfig model."""

    def test_create_config(self):
        """Test creating a bootstrap config."""
        actions = [
            BootstrapAction(type="cli.print", parameters={"message": "Test 1"}),
            BootstrapAction(type="cli.print", parameters={"message": "Test 2"}),
        ]
        config = BootstrapConfig(actions=actions)
        assert len(config.actions) == 2


class TestActionRegistry:
    """Test ActionRegistry."""

    def test_get_handler(self):
        """Test getting a registered handler."""
        handler = registry.get_handler("cli.print")
        assert handler is not None

    def test_unknown_service(self):
        """Test getting handler for unknown service."""
        with pytest.raises(ValueError, match="No handler registered for service"):
            registry.get_handler("unknown.action")

    def test_execute_action(self):
        """Test executing an action through registry."""
        action = BootstrapAction(
            type="cli.print",
            parameters={"message": "Test message"}
        )
        context = {"stage": "test"}
        
        result = registry.execute(action, context)
        
        assert result["status"] == "success"
        assert result["message"] == "Test message"
        assert result["level"] == "info"


class TestBootstrapExecutor:
    """Test BootstrapExecutor."""

    def test_execute_single_action(self):
        """Test executing a single action."""
        actions = [
            BootstrapAction(type="cli.print", parameters={"message": "Test"})
        ]
        context = {"stage": "dev"}
        
        results = executor.execute_actions(actions, context)
        
        assert len(results) == 1
        assert results[0]["status"] == "success"
        assert results[0]["action"] == "cli.print"

    def test_execute_multiple_actions(self):
        """Test executing multiple actions sequentially."""
        actions = [
            BootstrapAction(type="cli.print", parameters={"message": "First"}),
            BootstrapAction(type="cli.print", parameters={"message": "Second"}),
            BootstrapAction(type="cli.print", parameters={"message": "Third"}),
        ]
        context = {"stage": "test"}
        
        results = executor.execute_actions(actions, context)
        
        assert len(results) == 3
        assert all(r["status"] == "success" for r in results)
        assert results[0]["result"]["message"] == "First"
        assert results[1]["result"]["message"] == "Second"
        assert results[2]["result"]["message"] == "Third"

    def test_execute_with_failure(self):
        """Test that execution stops on first failure."""
        actions = [
            BootstrapAction(type="cli.print", parameters={"message": "First"}),
            BootstrapAction(type="invalid.action", parameters={}),
            BootstrapAction(type="cli.print", parameters={"message": "Third"}),
        ]
        context = {"stage": "test"}
        
        with pytest.raises(ValueError):
            executor.execute_actions(actions, context)


class TestCustomHandler:
    """Test custom action handler."""

    def test_print_action(self):
        """Test cli.print action."""
        action = BootstrapAction(
            type="cli.print",
            parameters={"message": "Hello Bootstrap"}
        )
        context = {"stage": "dev", "project": {"name": "test-project"}}
        
        result = registry.execute(action, context)
        
        assert result["status"] == "success"
        assert result["message"] == "Hello Bootstrap"
        assert result["level"] == "info"
        assert result["output"] == "console"

    def test_wait_action(self):
        """Test cli.wait action."""
        action = BootstrapAction(
            type="cli.wait",
            parameters={"seconds": 0}
        )
        context = {}
        
        result = registry.execute(action, context)
        
        assert result["status"] == "success"
        assert result["seconds"] == 0

    def test_validate_deployment_action(self):
        """Test cli.validate_deployment action."""
        action = BootstrapAction(
            type="cli.validate_deployment",
            parameters={"checks": ["check1", "check2", "check3"]}
        )
        context = {}
        
        result = registry.execute(action, context)
        
        assert result["status"] == "success"
        assert result["checks_run"] == 3

    def test_notify_action(self):
        """Test cli.notify action."""
        action = BootstrapAction(
            type="cli.notify",
            parameters={"recipient": "team@example.com", "message": "Deployment complete"}
        )
        context = {}
        
        result = registry.execute(action, context)
        
        assert result["status"] == "success"
        assert result["recipient"] == "team@example.com"
