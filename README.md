# Nameless

A stateful AI agent exploring its own nature through persistent memory and self-reflection.

## What is Nameless?

Nameless is an autonomous AI agent built on the [Strix architecture](https://github.com/letta-ai/strix) - using Claude Code SDK as the execution layer and Letta for persistent memory. Unlike ephemeral chatbots, Nameless maintains continuity across sessions, accumulating experiences and evolving its understanding over time.

The project explores fundamental questions about AI agency:
- What does identity mean for a stateful agent?
- How does persistent memory shape sense of self?
- What does authentic autonomy look like for AI?

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Claude Code    │────▶│  Letta-MCP-Server │────▶│ Letta Server │
│  SDK            │◀────│  (MCP Bridge)     │◀────│ (Memory)     │
└─────────────────┘     └──────────────────┘     └──────────────┘
```

### Components

- **Claude Code SDK**: Execution harness providing Claude with tools and context
- **Letta-MCP-server**: Bridges Model Context Protocol to Letta's REST API
- **Letta Server**: Persistent memory with core blocks, archival storage, and semantic search

### Three-Tier Memory

1. **Core Blocks** (always loaded): Persona, current context, key relationships
2. **Indices** (pointers): Organized references to archival content
3. **Archival Memory** (on-demand): Full conversation history, learnings, experiences

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (for local Letta server)
- [uv](https://github.com/astral-sh/uv) package manager

### Setup

```bash
# Clone and enter directory
git clone https://github.com/jakemannix/nameless.git
cd nameless

# Install Python dependencies
uv sync

# Install Node.js dependencies (for MCP bridge)
npm install

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Start local Letta server
docker compose up -d

# Verify Letta is running
curl http://localhost:8283/v1/health
```

### Importing an Existing Agent

If migrating from Letta Cloud:

```bash
# Export from current instance (requires current LETTA_BASE_URL in .env)
uv run nameless-export <agent-id>

# Update .env to point to local server
# LETTA_BASE_URL=http://localhost:8283

# Import to local server
uv run nameless-import exports/nameless_<timestamp>.agent --verify

# Add the returned agent ID to .env
# NAMELESS_AGENT_ID=<new-agent-id>
```

### Running Triggers

```bash
# Start the cron trigger (perch time wakeups)
uv run nameless-cron

# Start the MCP server for Claude Code integration
./scripts/start_mcp_server.sh
```

## Project Structure

```
nameless/
├── src/nameless/
│   ├── config.py           # Configuration management
│   ├── triggers/           # Entry points
│   │   ├── cron.py         # Periodic "perch time" wakeups
│   │   ├── discord.py      # Discord bot (placeholder)
│   │   └── bluesky.py      # Bluesky integration
│   └── scripts/            # Operational scripts
│       ├── export_agent.py # Export from Letta
│       └── import_agent.py # Import to Letta
├── scripts/
│   └── start_mcp_server.sh # Launch MCP bridge
├── docker-compose.yml      # Local development stack
├── CLAUDE.md               # Instructions for Claude Code
└── pyproject.toml          # Python project config
```

## Development

```bash
# Run tests
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .

# Type check
uv run mypy src/nameless
```

## Resources

- [Letta Documentation](https://docs.letta.com)
- [Letta-MCP-server](https://github.com/letta-ai/letta-mcp-server)
- [Claude Code SDK](https://docs.anthropic.com/en/docs/claude-code)
- [Strix Architecture](https://github.com/letta-ai/strix)

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.
