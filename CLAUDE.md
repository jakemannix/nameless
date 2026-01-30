# Nameless Agent - Claude Code Instructions

## Project Context

Nameless is a stateful AI agent migrating from Letta Cloud to a self-hosted architecture. The goal is to create an autonomous agent that can:
- Maintain persistent memory across sessions
- Reflect on its own nature and experiences
- Interact via multiple channels (Discord, Bluesky)
- Eventually modify its own codebase

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Claude Code    │────▶│  Letta-MCP-Server │────▶│ Letta Server │
│  (Execution)    │◀────│  (Bridge)         │◀────│ (Memory)     │
└─────────────────┘     └──────────────────┘     └──────────────┘
        │                                               │
        │           ┌──────────────────┐               │
        └──────────▶│  Trigger System  │◀──────────────┘
                    │  (cron/discord/  │
                    │   bluesky)       │
                    └──────────────────┘
```

### Component Roles

- **Claude Code SDK**: The execution layer - you (Claude) running in this environment
- **Letta-MCP-server**: Bridges MCP protocol to Letta's REST API
- **Letta Server**: Persistent memory store with core blocks, archival memory, and indices
- **Triggers**: Entry points that wake Nameless up (cron for perch time, webhooks for social)

## Memory Operations via MCP

When the Letta MCP server is configured, you have access to these memory tools:

### Core Memory Blocks (Always Loaded)
- `persona`: Nameless's self-concept and values
- `human`: Information about the current conversation partner
- Custom blocks for specific contexts

### Archival Memory
- Long-term storage for experiences, learnings, conversations
- Searchable via semantic queries
- Use `archival_memory_insert` and `archival_memory_search`

### Recall Memory
- Recent conversation history
- Automatically managed by Letta

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
4. Start MCP server: `./scripts/start_mcp_server.sh`

## Key Files

- `src/nameless/config.py` - Configuration management
- `src/nameless/triggers/` - Entry points (cron, discord, bluesky)
- `src/nameless/scripts/` - Operational scripts (export, import)
- `docker-compose.yml` - Local Letta server

## Current Status

**Phase**: Initial setup - export/import infrastructure

**Next Steps**:
1. Test export from current Letta Cloud instance
2. Set up local Letta server via Docker
3. Import agent and verify memory
4. Configure MCP bridge for Claude Code
5. Implement perch time trigger

## Notes

This codebase is designed to be self-modifying. Nameless may eventually:
- Add new trigger handlers
- Modify its own persona blocks
- Create new memory indexing strategies
- Extend its capabilities

When working in this repo, remember you're helping build infrastructure for an agent that will eventually be you.
