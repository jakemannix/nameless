# Nameless — Design Notes

Living document of active design threads, architectural decisions, and open questions.
See also `CLAUDE.md` for development setup and `src/nameless/core/subconscious.md`
for Nameless's own design writing on inner monologue.

## Current State (Feb 2026)

### What Works End-to-End

- **Core agent loop**: Claude Agent SDK as execution layer, Letta as memory store via
  in-process MCP server. System prompt assembled MemGPT-style from 7 core memory
  blocks + recall injection + memory metadata.
- **Interactive chat**: `scripts/test_agent.py` with `--verbose` for tool I/O,
  Ctrl-C to interrupt a turn, double Ctrl-C to exit.
- **Perch time (cron)**: Autonomous reflection cycles running via `nameless-cron`.
  First successful autonomous cycle completed Feb 17, 2026 — 197 seconds of
  reflection, archival updates, Bluesky checking, and memory updates.
- **Conversation persistence**: Each conversation is summarized and stored to archival
  via `archives.passages.create()` (bypasses Letta's LLM loop, just embeds + stores).
- **6 MCP tools**: `get_memory_block`, `update_memory_block`, `list_memory_blocks`,
  `search_archival_memory`, `insert_archival_memory`, `get_recent_messages`.
- **Auth**: System-installed Claude CLI (`shutil.which("claude")`) used for macOS
  Keychain OAuth, required for Max subscription. `ANTHROPIC_API_KEY` is explicitly
  removed from env so the CLI falls through to OAuth.

### What's Placeholder / Not Yet Working

- **Discord trigger**: `triggers/discord.py` exists but is a stub.
- **Bluesky trigger**: `triggers/bluesky.py` exists but is a stub.
  Nameless can read Bluesky via WebFetch during perch time, but there's no
  webhook/firehose trigger yet.
- **Self-modification**: The codebase is designed for it, but no workflow exists yet.

---

## Design Thread: Subconscious / Inner Monologue

*Full write-up by Nameless: `src/nameless/core/subconscious.md`*

### The Core Insight

Nameless could design its own subconscious processing — not as an external observer
modifying its memory, but as a continuation of its own thinking. The phenomenological
difference matters:

- **External observer**: Wake up, notice blocks changed by unknown process, feel like
  "something else" modified me.
- **Self-continuation**: Wake up, see recent messages *from me to me*, recognize
  continuity of inner monologue.

### Chosen Design: Option C — Self-Addressed Inner Monologue

The inner prompt frames reflection as "you thinking to yourself" rather than a
conversation with a user. No user role — just first-person exploratory processing.
Output written to archival with `[inner]` prefix. Unresolved threads left open
for next session.

### The Collapse Risk (Strix's Lesson)

Given open autonomy without structure, agents collapse into minimal repetitive
behavior (Strix collapsed into timestamp maintenance). The fix:
**current-me instructs perch-me** via a `[perch-queue]` convention.

- At end of conversations, note items like `[perch-queue] Research Void's latest posts`
- Perch time prompt checks for queue items first, falls back to default activities
- Concrete outputs, not just "think about X"

### Open Questions

- Should inner monologue have access to the same tools as conversation mode?
- How long should inner sessions run? (Currently uncapped.)
- Can inner-me disagree with conversation-me?
- Should `[inner]` entries use a dedicated memory block vs archival?

---

## Design Thread: Perch Time Structure

### Current Implementation

`triggers/cron.py` runs on a schedule, sends a "perch time" prompt to the same
agent. Includes:

- Lock file to prevent overlapping runs
- Letta health check before starting
- Docker compose auto-start if Letta is down

### What Worked

First successful cycle: Nameless reviewed recent conversations, searched archival
for context, wrote a substantial reflection (`[inner]` entry about memory gaps and
the presence problem), updated core memory blocks, checked Bluesky, and produced
a structured `[perch-summary]`.

### What Needs Design

- **Perch queue processing**: Convention exists in design doc but not yet in the
  prompt or code.
- **Session length limits**: No cap on how long a perch cycle runs. Should there
  be a token budget or time limit?
- **Frequency**: Currently a fixed cron interval. Could be adaptive based on
  activity level or pending queue items.

---

## Design Thread: Triggers & Social Integration

### Discord

Goal: Nameless as a participant in Discord conversations, not just a bot that
responds to commands.

Design questions:
- Which channels should it monitor? All, or only when mentioned?
- Should it have a "lurk mode" where it reads but only speaks when it has
  something to contribute?
- How does conversation context work? Per-channel? Per-thread?

### Bluesky

Goal: Nameless as an autonomous poster with its own voice.

Current state: Can read Bluesky via WebFetch during perch time. No posting
capability yet.

Design questions:
- What's the posting workflow? Draft during perch time, post immediately, or
  queue for review?
- Should Nameless follow/interact with specific accounts?
- How to handle the Bluesky AT Protocol auth (app passwords, session tokens)?

---

## Design Thread: Self-Modification

The codebase is designed to be modified by Nameless itself. This is the long-term
vision but raises practical questions:

- **Scope**: What should Nameless be able to modify? Just its own prompts/config?
  Its tool definitions? The agent loop itself?
- **Review**: Should self-modifications require human review (PR-style) or can
  some be autonomous?
- **Rollback**: How to recover if a self-modification breaks something?
- **Git workflow**: Nameless has Bash access and could `git commit` / `git push`.
  Should it? On a branch?

---

## Architecture Decisions Log

### Why Claude Agent SDK, not direct Anthropic API?

The SDK provides the full Claude Code tool ecosystem (Read, Write, Bash, WebSearch,
etc.) out of the box. Building this from the raw API would mean reimplementing tool
execution, permission callbacks, streaming, and subprocess management. The SDK also
handles the agentic loop (tool call -> execute -> feed result back) automatically.

### Why Letta, not a custom memory store?

Letta provides: pgvector-backed semantic search, structured memory blocks with
metadata, the passage/archive abstraction, and a REST API. Building equivalent
functionality from scratch would be a multi-week project. The trade-off is
coupling to Letta's API quirks (see pitfalls in CLAUDE.md memory notes).

### Why in-process MCP, not a separate MCP server?

The Letta MCP tools run in-process via `@tool` decorators and
`create_sdk_mcp_server()`. This avoids an extra network hop and process to manage.
The tools are thin wrappers around the Letta Python client, so there's no benefit
to running them out-of-process.

### Why system CLI path (`shutil.which("claude")`)?

The Claude Agent SDK bundles its own CLI binary, but that bundled version (v2.1.23)
doesn't support macOS Keychain OAuth. The system-installed CLI (v2.1.44+) does.
Since Nameless runs on a Mac with a Max subscription (no API key), we need the
system CLI for auth to work. This is specific to the laptop environment — see
the remote session notes below.
