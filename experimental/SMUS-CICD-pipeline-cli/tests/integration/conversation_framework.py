"""Framework for simulating Q CLI conversations with MCP server."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml


@dataclass
class ConversationResult:
    """Result of a conversation scenario."""

    turns: List[Dict[str, Any]]
    context: Dict[str, Any]
    passed: bool
    errors: List[str]


class ConversationSimulator:
    """Simulates Q CLI conversations by calling MCP tools in sequence."""

    def __init__(self, server):
        """Initialize simulator with MCP server."""
        self.server = server
        self.context = {}

    def run_scenario(self, scenario_path: str) -> ConversationResult:
        """Execute conversation scenario from YAML file."""
        scenario = yaml.safe_load(Path(scenario_path).read_text())

        turns = []
        errors = []

        for i, turn in enumerate(scenario.get("turns", [])):
            try:
                result = self._execute_turn(turn, i)
                turns.append(result)
            except AssertionError as e:
                errors.append(f"Turn {i}: {str(e)}")
            except Exception as e:
                errors.append(f"Turn {i}: Unexpected error: {str(e)}")

        return ConversationResult(
            turns=turns, context=self.context, passed=len(errors) == 0, errors=errors
        )

    def _execute_turn(self, turn: Dict[str, Any], turn_num: int) -> Dict[str, Any]:
        """Execute a single conversation turn."""
        turn_type = turn.get("type")

        if turn_type == "user_input":
            return self._handle_user_input(turn)
        elif turn_type == "tool_call":
            return self._handle_tool_call(turn)
        elif turn_type == "assertion":
            return self._handle_assertion(turn)
        else:
            raise ValueError(f"Unknown turn type: {turn_type}")

    def _handle_user_input(self, turn: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user input turn."""
        message = turn.get("message", "")
        self.context["last_user_input"] = message
        return {"type": "user_input", "message": message}

    def _handle_tool_call(self, turn: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP tool call turn."""
        tool_name = turn.get("tool")
        arguments = self._resolve_arguments(turn.get("arguments", {}))

        result = self.server.call_tool({"name": tool_name, "arguments": arguments})

        # Save result to context if specified
        save_as = turn.get("save_as")
        if save_as:
            self.context[save_as] = result

        return {"type": "tool_call", "tool": tool_name, "result": result}

    def _handle_assertion(self, turn: Dict[str, Any]) -> Dict[str, Any]:
        """Handle assertion turn."""
        check_type = turn.get("check")
        target = turn.get("target")
        expected = turn.get("value")

        # Get target value from context
        target_value = self.context.get(target)
        if target_value is None:
            raise AssertionError(f"Target '{target}' not found in context")

        # Extract text from MCP response
        if isinstance(target_value, dict) and "content" in target_value:
            text = target_value["content"][0]["text"]
        else:
            text = str(target_value)

        # Perform assertion
        if check_type == "contains":
            assert expected.lower() in text.lower(), f"'{expected}' not found in response"
        elif check_type == "not_contains":
            assert expected.lower() not in text.lower(), f"'{expected}' found in response"
        elif check_type == "valid_yaml":
            yaml.safe_load(text)  # Will raise if invalid
        elif check_type == "regex":
            assert re.search(expected, text), f"Pattern '{expected}' not found"
        else:
            raise ValueError(f"Unknown check type: {check_type}")

        return {"type": "assertion", "check": check_type, "passed": True}

    def _resolve_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve argument values from context using ${var} syntax."""
        resolved = {}
        for key, value in arguments.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                var_path = value[2:-1]
                resolved[key] = self._get_nested_value(var_path)
            else:
                resolved[key] = value
        return resolved

    def _get_nested_value(self, path: str) -> Any:
        """Get nested value from context using dot notation."""
        parts = path.split(".")
        value = self.context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                raise ValueError(f"Cannot access '{part}' in {type(value)}")
        return value


def load_scenarios(scenarios_dir: str = "tests/integration/mcp-chat-testing") -> List[str]:
    """Load all scenario files from directory."""
    scenarios_path = Path(scenarios_dir)
    if not scenarios_path.exists():
        return []
    return [str(f) for f in scenarios_path.glob("*.yaml")]
