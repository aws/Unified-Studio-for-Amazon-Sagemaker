#!/bin/bash
cd "$(dirname "$0")/../.."
export PYTHONPATH="$(pwd)/src"
exec python3 -m smus_cicd.mcp.server ${SMUS_MCP_CONFIG:+--config "$SMUS_MCP_CONFIG"} 2>/tmp/smus_mcp_server.log
