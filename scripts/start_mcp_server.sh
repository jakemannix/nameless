#!/usr/bin/env bash
# Start the Letta MCP server for Nameless

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

# Defaults
LETTA_BASE_URL="${LETTA_BASE_URL:-http://localhost:8283}"

echo "Starting Letta MCP server..."
echo "  Letta URL: $LETTA_BASE_URL"
echo "  Agent ID: ${NAMELESS_AGENT_ID:-<not set>}"

cd "$PROJECT_ROOT"

# Run the MCP server
exec npx @letta-ai/letta-mcp-server
