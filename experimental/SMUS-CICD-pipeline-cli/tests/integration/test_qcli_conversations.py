"""Integration tests for Q CLI conversation scenarios."""

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from smus_cicd.mcp import SMUSMCPServer

from .conversation_framework import ConversationSimulator, load_scenarios


@pytest.fixture
def mcp_server():
    """Create MCP server instance."""
    return SMUSMCPServer()


@pytest.fixture
def simulator(mcp_server):
    """Create conversation simulator."""
    return ConversationSimulator(mcp_server)


def test_glue_job_pipeline_conversation(simulator):
    """Test conversation: Create CICD for Glue job."""
    scenario_path = Path(__file__).parent / "mcp-chat-testing" / "glue_job_scenario.yaml"

    result = simulator.run_scenario(str(scenario_path))

    # Print errors if any
    if not result.passed:
        for error in result.errors:
            print(f"❌ {error}")

    assert result.passed, f"Conversation failed: {result.errors}"
    assert len(result.turns) > 0, "No turns executed"

    # Verify key context items were created
    assert "search_result" in result.context
    assert "pipeline_example" in result.context
    assert "github_search" in result.context


def test_all_conversation_scenarios(simulator):
    """Test all conversation scenarios in scenarios directory."""
    scenarios = load_scenarios()

    if not scenarios:
        pytest.skip("No conversation scenarios found")

    results = []
    for scenario_path in scenarios:
        result = simulator.run_scenario(scenario_path)
        results.append((Path(scenario_path).name, result))

    # Report results
    for name, result in results:
        if result.passed:
            print(f"✅ {name}")
        else:
            print(f"❌ {name}")
            for error in result.errors:
                print(f"   {error}")

    # Assert all passed
    failed = [name for name, result in results if not result.passed]
    assert not failed, f"Failed scenarios: {failed}"


def test_conversation_context_passing(simulator):
    """Test that context is passed between turns correctly."""
    # Manually create a simple scenario
    from .conversation_framework import ConversationResult

    # Turn 1: Call tool and save result
    turn1 = {
        "type": "tool_call",
        "tool": "query_smus_kb",
        "arguments": {"query": "pipeline"},
        "save_as": "search_result",
    }
    simulator._execute_turn(turn1, 0)

    # Verify context was saved
    assert "search_result" in simulator.context
    assert "content" in simulator.context["search_result"]


def test_conversation_assertions(simulator):
    """Test assertion types work correctly."""
    # Setup context
    simulator.context["test_result"] = {
        "content": [{"type": "text", "text": "This is a test message"}]
    }

    # Test contains assertion
    turn = {"type": "assertion", "check": "contains", "target": "test_result", "value": "test"}
    result = simulator._execute_turn(turn, 0)
    assert result["passed"]

    # Test not_contains assertion
    turn = {
        "type": "assertion",
        "check": "not_contains",
        "target": "test_result",
        "value": "missing",
    }
    result = simulator._execute_turn(turn, 0)
    assert result["passed"]


def test_conversation_variable_resolution(simulator):
    """Test ${var} syntax resolves from context."""
    simulator.context["my_query"] = "test query"

    args = {"query": "${my_query}"}
    resolved = simulator._resolve_arguments(args)

    assert resolved["query"] == "test query"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
