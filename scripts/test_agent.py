"""Interactive chat with the Nameless agent.

Usage:
    uv run python scripts/test_agent.py                      # interactive chat
    uv run python scripts/test_agent.py "single message"     # one-shot mode
    uv run python scripts/test_agent.py --debug              # with debug logging
    uv run python scripts/test_agent.py --log out.txt        # log raw responses to file
"""

import asyncio
import logging
import shutil
import sys
import textwrap

from nameless import NamelessAgent


# --- Display helpers ---

def _terminal_width() -> int:
    return shutil.get_terminal_size((80, 24)).columns


def _wrap(text: str, indent: str = "  ", width: int | None = None) -> str:
    """Word-wrap text to terminal width with indent."""
    w = (width or _terminal_width()) - len(indent)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
        else:
            lines.extend(textwrap.wrap(paragraph, width=w) or [""])
    return "\n".join(indent + line for line in lines)


def _dim(text: str) -> str:
    return f"\033[2m{text}\033[0m"


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def _cyan(text: str) -> str:
    return f"\033[36m{text}\033[0m"


def _green(text: str) -> str:
    return f"\033[32m{text}\033[0m"


def _yellow(text: str) -> str:
    return f"\033[33m{text}\033[0m"


def display_msg(msg: object, agent: NamelessAgent | None = None, log_fh=None) -> None:
    """Pretty-print a single response message."""
    cls = type(msg).__name__

    if log_fh:
        log_fh.write(f"{msg!r}\n\n")

    # ResultMessage — the final answer
    if hasattr(msg, "result") and hasattr(msg, "duration_ms"):
        result_text = getattr(msg, "result", "") or ""
        if result_text:
            print()
            print(_bold(_green("Nameless:")))
            print(_wrap(result_text))
            print()

        # Show stats on one line
        duration = getattr(msg, "duration_ms", 0) or 0
        cost = getattr(msg, "total_cost_usd", 0) or 0
        turns = getattr(msg, "num_turns", 0) or 0
        prompt_len = agent.last_prompt_length if agent else 0
        stats = f"{duration/1000:.1f}s | {turns} turn{'s' if turns != 1 else ''}"
        if cost:
            stats += f" | ${cost:.4f}"
        if prompt_len:
            stats += f" | prompt {prompt_len:,} chars"
        print(_dim(f"  [{stats}]"))
        return

    # AssistantMessage — intermediate text (tool use, thinking, etc.)
    if hasattr(msg, "content"):
        content = msg.content
        if isinstance(content, list):
            for item in content:
                if hasattr(item, "text"):
                    # Only show if it's NOT the same as the final result
                    # (AssistantMessage duplicates ResultMessage text)
                    pass  # We'll show it in ResultMessage instead
                elif hasattr(item, "name"):
                    print(_dim(f"  [calling tool: {item.name}]"))
                elif hasattr(item, "tool_use_id"):
                    print(_dim(f"  [tool result]"))
        elif isinstance(content, str) and content.strip():
            print(_dim(f"  {cls}: {content[:200]}"))
        return

    # Anything else — show type name briefly
    print(_dim(f"  [{cls}]"))


async def run_interactive(agent: NamelessAgent, log_fh=None) -> None:
    """Run an interactive chat loop."""
    print(_bold("Chat with Nameless") + _dim(" (type 'quit' or Ctrl-C to exit)"))
    print()

    while True:
        try:
            user_input = input(_bold(_cyan("You: "))).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n" + _dim("Goodbye."))
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print(_dim("Goodbye."))
            break

        responses: list = []
        async for msg in agent.run(user_input):
            responses.append(msg)
            display_msg(msg, agent=agent, log_fh=log_fh)

        await agent.persist_conversation(user_input, responses)
        print()


async def run_oneshot(agent: NamelessAgent, message: str, log_fh=None) -> None:
    """Send a single message and display the response."""
    print(_bold(_cyan("You: ")) + message)

    responses: list = []
    async for msg in agent.run(message):
        responses.append(msg)
        display_msg(msg, agent=agent, log_fh=log_fh)

    await agent.persist_conversation(message, responses)
    print()


async def main() -> None:
    args = sys.argv[1:]

    debug = "--debug" in args
    if debug:
        args.remove("--debug")
        logging.basicConfig(level=logging.DEBUG)

    log_file = None
    if "--log" in args:
        idx = args.index("--log")
        log_file = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    agent = NamelessAgent()
    print(_dim(f"Agent ID: {agent.agent_id}"))
    print(_dim("---"))

    fh = open(log_file, "w") if log_file else None
    try:
        if args:
            # One-shot mode: single message from command line
            message = " ".join(args)
            await run_oneshot(agent, message, fh)
        else:
            # Interactive mode
            await run_interactive(agent, fh)
    finally:
        if fh:
            fh.close()
            print(_dim(f"Raw log: {log_file}"))


if __name__ == "__main__":
    asyncio.run(main())
