#!/bin/bash
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/src"
exec python3 -m smus_cicd.mcp_server 2>/tmp/smus_mcp_server.log
