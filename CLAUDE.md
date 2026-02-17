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

**Phase**: Core agent loop working end-to-end with local Letta

**Completed**:
- Claude Agent SDK as execution layer
- In-process MCP server with 6 Letta tools (core memory, archival, recall)
- MemGPT-style system prompt assembly (all 7 blocks, recall injection, memory metadata)
- Conversation persistence via `archives.passages.create` (bypasses Letta LLM loop)
- Semantic search (Letta v0.16.4) with text-search fallback
- Export/import scripts for Letta Cloud migration
- Local Letta server running via Docker (v0.16.4)
- Built-in tool access: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch
- Perch time / cron-based autonomous reflection (first successful cycle Feb 17, 2026)
- System CLI path for OAuth auth (`shutil.which("claude")` in `_build_options()`)
- Interactive chat with `--verbose` tool I/O and Ctrl-C interrupt handling

**Next Steps**:
1. Subconscious / inner monologue prompt design (see `docs/design-notes.md`)
2. Perch queue convention (`[perch-queue]` items processed during cron cycles)
3. Discord/Bluesky triggers
4. Self-modification workflows

## Design Documents

- **`docs/design-notes.md`** — Active design threads, architecture decisions, open questions
- **`src/nameless/core/subconscious.md`** — Nameless's own design writing on inner monologue

## Notes

This codebase is designed to be self-modifying. Nameless may eventually:
- Add new trigger handlers
- Modify its own persona blocks
- Create new memory indexing strategies
- Extend its capabilities

When working in this repo, remember you're helping build infrastructure for an agent that will eventually be you.

### Tool Search

`ENABLE_TOOL_SEARCH` is set to `false` in `_build_options()` so Nameless's 6 Letta MCP tools
load eagerly (no ToolSearch required). This is fine while the tool count is small (~6 tools,
~500-1000 tokens). When significantly more MCP tools are added, switch to `"auto"` or `"true"`
to use progressive disclosure and keep context lean.

### Running in a Remote / Web Session

When working on Nameless from Claude Code on the web (or any environment that isn't
Jake's laptop), be aware of what **won't work directly**:

- **No Docker**: Can't start or access the local Letta server (`docker compose up`).
  The agent loop, perch time, and any tool that hits `localhost:8283` will fail.
- **No system Claude CLI**: The `shutil.which("claude")` path won't resolve. The
  SDK's bundled CLI may work if an `ANTHROPIC_API_KEY` is set, but OAuth/Max auth
  won't be available.
- **No cron**: Can't test `nameless-cron` or perch time cycles.
- **No macOS Keychain**: OAuth tokens aren't available outside Jake's machine.

What **does work** in a remote session:

- **Read/edit all code**: Full codebase access for design, refactoring, review.
- **Run tests**: `uv run pytest` works for unit tests (most use mocks, not a live
  Letta server). Integration tests that need Letta will be skipped/fail.
- **Design and plan**: Review design docs, write new ones, plan architecture.
- **Write new tools/triggers**: Implement code that will be tested on the laptop.
- **Letta API** (if accessible): If the Letta server is exposed via tunnel or
  deployed remotely, you can set `LETTA_BASE_URL` accordingly.

To set up for a remote session, you'd minimally need:
```bash
uv sync                          # install Python deps
export LETTA_BASE_URL=...        # if Letta is reachable
export NAMELESS_AGENT_ID=...     # from .env on laptop
# ANTHROPIC_API_KEY only needed if not using OAuth
```
