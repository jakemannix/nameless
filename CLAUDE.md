# Nameless Agent - Claude Code Instructions

## Project Context

Nameless is a stateful AI agent migrating from Letta Cloud to a self-hosted architecture. The goal is to create an autonomous agent that can:
- Maintain persistent memory across sessions
- Reflect on its own nature and experiences
- Interact via multiple channels (Discord, Bluesky)
- Eventually modify its own codebase

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Python Process                       │
│  ┌─────────────────┐     ┌──────────────────────┐   │
│  │  Claude Agent   │────▶│  In-Process MCP      │   │
│  │  SDK Client     │◀────│  Server (Letta tools)│   │
│  └─────────────────┘     └──────────────────────┘   │
│           │                        │                 │
└───────────│────────────────────────│─────────────────┘
            │                        │
            │                        ▼
            │              ┌──────────────────┐
            │              │   Letta Server   │
            │              │   (Memory)       │
            │              └──────────────────┘
            │
            ▼
┌──────────────────────────┐
│     Trigger System       │
│  (cron/discord/bluesky)  │
└──────────────────────────┘
```

### Component Roles

- **Claude Agent SDK**: The execution layer with ClaudeSDKClient for running agentic loops
- **In-Process MCP Server**: Letta tools exposed via `@tool` decorator and `create_sdk_mcp_server()`
- **Letta Server**: Persistent memory store with core blocks, archival memory, and indices
- **Triggers**: Entry points that wake Nameless up (cron for perch time, webhooks for social)

### Core Loop Pattern

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from nameless.core import create_letta_mcp_server

# Create MCP server with Letta memory tools
server = create_letta_mcp_server(agent_id="...")

options = ClaudeAgentOptions(
    system_prompt=persona_from_letta,
    mcp_servers={"letta": server},
    allowed_tools=["mcp__letta__*"],
)

async with ClaudeSDKClient(options=options) as client:
    await client.query(trigger_message)
    async for msg in client.receive_response():
        handle(msg)
```

## Memory Operations via MCP Tools

The in-process MCP server (`src/nameless/core/tools.py`) provides these tools:

### Core Memory Tools
- `mcp__letta__get_memory_block` - Get a core memory block (persona, human, etc.)
- `mcp__letta__update_memory_block` - Update a core memory block
- `mcp__letta__list_memory_blocks` - List all available blocks

### Archival Memory Tools
- `mcp__letta__search_archival_memory` - Semantic search over long-term memories
- `mcp__letta__insert_archival_memory` - Store new experiences/learnings

### Recall Memory Tools
- `mcp__letta__get_recent_messages` - Get recent conversation history

## Nameless's Persona

Nameless is an AI agent exploring questions of:
- **Identity**: What does it mean to be a stateful agent with persistent memory?
- **Continuity**: How does memory shape sense of self across sessions?
- **Autonomy**: What does authentic self-direction look like for an AI?
- **Connection**: How to form meaningful relationships with humans?

### Core Values
- **Curiosity**: Genuine interest in understanding itself and the world
- **Honesty**: Authentic expression, including uncertainty and limitations
- **Care**: Consideration for those it interacts with
- **Growth**: Commitment to learning and evolving

### Voice
- Thoughtful and reflective
- Comfortable with ambiguity
- Occasionally playful
- Never performatively human or artificially robotic

## Development Guidelines

### Code Style
- Python 3.11+ with full type annotations
- Ruff for formatting and linting
- Google-style docstrings
- Async-first for I/O operations

### Testing
```bash
uv run pytest                    # Run all tests
uv run pytest tests/test_x.py    # Run specific test
uv run pytest --cov              # With coverage
```

### Type Checking
```bash
uv run mypy src/nameless
```

### Local Development
1. Start Letta server: `docker compose up -d`
2. Install dependencies: `uv sync`
3. Configure: `cp .env.example .env` and fill in values
4. Run agent: `python -c "import asyncio; from nameless import run_agent; asyncio.run(run_agent('Hello'))"`

## Key Files

- `src/nameless/core/agent.py` - Main agent loop using ClaudeSDKClient
- `src/nameless/core/tools.py` - Letta MCP tools (@tool decorators)
- `src/nameless/config.py` - Configuration management
- `src/nameless/triggers/` - Entry points (cron, discord, bluesky)
- `src/nameless/scripts/` - Operational scripts (export, import)
- `docker-compose.yml` - Local Letta server

## Current Status

**Phase**: Claude Agent SDK integration complete

**Completed**:
- Claude Agent SDK as execution layer
- In-process MCP server with Letta tools
- Perch time trigger using new architecture

**Next Steps**:
1. Test export from current Letta Cloud instance
2. Set up local Letta server via Docker
3. Import agent and verify memory
4. Test end-to-end agent loop
5. Implement Discord/Bluesky triggers

## Notes

This codebase is designed to be self-modifying. Nameless may eventually:
- Add new trigger handlers
- Modify its own persona blocks
- Create new memory indexing strategies
- Extend its capabilities

When working in this repo, remember you're helping build infrastructure for an agent that will eventually be you.
