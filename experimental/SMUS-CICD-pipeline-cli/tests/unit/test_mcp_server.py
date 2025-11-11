"""Unit tests for MCP server."""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from smus_cicd.mcp_server import SMUSMCPServer


class TestSMUSMCPServer:
    """Test SMUS MCP Server functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.server = SMUSMCPServer()

    def test_initialization(self):
        """Test server initialization."""
        assert self.server is not None
        assert hasattr(self.server, "docs")
        assert isinstance(self.server.docs, dict)

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_load_local_docs_with_readme(self, mock_read, mock_exists):
        """Test loading README from filesystem."""
        mock_exists.return_value = True
        mock_read.return_value = "# SMUS CLI README"

        server = SMUSMCPServer()
        assert "readme" in server.docs
        assert server.docs["readme"] == "# SMUS CLI README"

    @patch("pathlib.Path.exists")
    def test_load_local_docs_no_readme(self, mock_exists):
        """Test when README doesn't exist."""
        mock_exists.return_value = False

        server = SMUSMCPServer()
        assert "readme" not in server.docs

    def test_handle_initialize_request(self):
        """Test handling initialize request."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }

        response = self.server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["protocolVersion"] == "2024-11-05"
        assert "serverInfo" in response["result"]
        assert response["result"]["serverInfo"]["name"] == "smus-cli"

    def test_handle_tools_list_request(self):
        """Test handling tools/list request."""
        request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        response = self.server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert "result" in response
        assert "tools" in response["result"]

        tools = response["result"]["tools"]
        tool_names = [tool["name"] for tool in tools]
        assert "get_pipeline_example" in tool_names
        assert "query_smus_kb" in tool_names
        assert "validate_pipeline" in tool_names

    def test_handle_get_pipeline_example_tool(self):
        """Test get_pipeline_example tool."""
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_pipeline_example",
                "arguments": {"pipeline_type": "notebooks"},
            },
        }

        response = self.server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 3
        assert "result" in response
        assert "content" in response["result"]

    def test_handle_query_smus_kb_tool(self):
        """Test query_smus_kb tool."""
        self.server.docs["readme"] = "# SMUS CLI\nThis is about pipelines"

        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "query_smus_kb", "arguments": {"query": "pipeline"}},
        }

        response = self.server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 4
        assert "result" in response
        assert "content" in response["result"]

    @pytest.mark.xfail(reason="Dependency issue with rfc3987 module")
    @patch("smus_cicd.pipeline.validation.validate_manifest_schema")
    @patch("smus_cicd.pipeline.validation.load_schema")
    @patch("builtins.open")
    def test_handle_validate_pipeline_tool_valid(
        self, mock_open_file, mock_load_schema, mock_validate
    ):
        """Test validate_pipeline tool with valid manifest."""
        mock_open_file.return_value.__enter__.return_value.read.return_value = (
            "pipelineName: Test"
        )
        mock_load_schema.return_value = {}
        mock_validate.return_value = (True, [])

        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "validate_pipeline",
                "arguments": {"manifest_path": "/path/to/pipeline.yaml"},
            },
        }

        response = self.server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 5
        assert "result" in response
        content = response["result"]["content"][0]["text"]
        assert "✅ Valid" in content

    @pytest.mark.xfail(reason="Dependency issue with rfc3987 module")
    @patch("smus_cicd.pipeline.validation.validate_manifest_schema")
    @patch("smus_cicd.pipeline.validation.load_schema")
    @patch("builtins.open")
    def test_handle_validate_pipeline_tool_invalid(
        self, mock_open_file, mock_load_schema, mock_validate
    ):
        """Test validate_pipeline tool with invalid manifest."""
        mock_open_file.return_value.__enter__.return_value.read.return_value = (
            "pipelineName: Test"
        )
        mock_load_schema.return_value = {}
        mock_validate.return_value = (False, ["Missing required field: targets"])

        request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "validate_pipeline",
                "arguments": {"manifest_path": "/path/to/pipeline.yaml"},
            },
        }

        response = self.server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 6
        assert "result" in response
        content = response["result"]["content"][0]["text"]
        assert "❌ Invalid" in content
        assert "Missing required field: targets" in content

    def test_handle_unknown_method(self):
        """Test handling unknown method."""
        request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "unknown/method",
            "params": {},
        }

        response = self.server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 7
        assert "error" in response
        assert response["error"]["code"] == -32601

    def test_handle_unknown_tool(self):
        """Test calling unknown tool."""
        request = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {"name": "unknown_tool", "arguments": {}},
        }

        response = self.server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 8
        # MCP server returns error in result, not as top-level error
        assert "result" in response
        assert "error" in response["result"]

    def test_handle_tool_with_missing_arguments(self):
        """Test calling tool with missing required arguments."""
        request = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {"name": "get_pipeline_example", "arguments": {}},
        }

        response = self.server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 9
        # Should handle gracefully, either with error or default behavior

    @patch("pathlib.Path.rglob")
    @patch("pathlib.Path.exists")
    def test_load_examples_from_filesystem(self, mock_exists, mock_rglob):
        """Test loading pipeline examples from filesystem."""
        mock_exists.return_value = True

        # Mock example files
        mock_file1 = MagicMock()
        mock_file1.name = "notebooks_pipeline.yaml"
        mock_file1.read_text.return_value = "pipelineName: NotebooksPipeline"

        mock_file2 = MagicMock()
        mock_file2.name = "etl_pipeline.yaml"
        mock_file2.read_text.return_value = "pipelineName: ETLPipeline"

        mock_rglob.return_value = [mock_file1, mock_file2]

        server = SMUSMCPServer()

        assert "examples" in server.docs
        assert "notebooks_pipeline.yaml" in server.docs["examples"]
        assert "etl_pipeline.yaml" in server.docs["examples"]

    def test_query_smus_kb_no_docs(self):
        """Test query_smus_kb when no docs loaded."""
        server = SMUSMCPServer()
        server.docs = {}

        request = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "query_smus_kb", "arguments": {"query": "test"}},
        }

        response = server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 10
        assert "result" in response
        content = response["result"]["content"][0]["text"]
        # Should return some response even with no docs
        assert "No results found" in content or "Search results" in content
