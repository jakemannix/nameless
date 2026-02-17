"""Interactive chat with the Nameless agent.

Usage:
    uv run python scripts/test_agent.py                      # interactive chat
    uv run python scripts/test_agent.py "single message"     # one-shot mode
    uv run python scripts/test_agent.py --verbose             # show tool inputs/outputs
    uv run python scripts/test_agent.py --debug              # with debug logging
    uv run python scripts/test_agent.py --log out.txt        # log raw responses to file
"""

import asyncio
import json
import logging
import signal
import shutil
import sys
import textwrap
import time

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


def _format_tool_content(content: str | list | None, max_len: int = 500) -> str:
    """Extract and truncate tool result content for display."""
    if content is None:
        return "(empty)"
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            else:
                parts.append(str(item))
        text = "\n".join(parts)
    else:
        text = str(content)
    if len(text) > max_len:
        text = text[:max_len] + f"... ({len(text)} chars total)"
    return text


def display_msg(
    msg: object,
    agent: NamelessAgent | None = None,
    log_fh=None,
    verbose: bool = False,
    tool_names: dict[str, str] | None = None,
) -> None:
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

    # AssistantMessage / UserMessage — intermediate content
    if hasattr(msg, "content"):
        content = msg.content
        if isinstance(content, list):
            for item in content:
                if hasattr(item, "thinking"):
                    # ThinkingBlock
                    if verbose:
                        preview = item.thinking[:200]
                        if len(item.thinking) > 200:
                            preview += "..."
                        print(_dim(f"  [thinking: {preview}]"))
                elif hasattr(item, "name") and hasattr(item, "input"):
                    # ToolUseBlock
                    if tool_names is not None:
                        tool_names[item.id] = item.name
                    print(_dim(f"  [calling tool: {item.name}]"))
                    if verbose:
                        for line in json.dumps(item.input, indent=2).split("\n"):
                            print(_dim(f"    {line}"))
                elif hasattr(item, "tool_use_id"):
                    # ToolResultBlock
                    if verbose:
                        name = (tool_names or {}).get(item.tool_use_id, "?")
                        is_err = getattr(item, "is_error", False)
                        label = "error" if is_err else "result"
                        content_str = _format_tool_content(getattr(item, "content", None))
                        print(_dim(f"  [tool {label}: {name}]"))
                        for line in content_str.split("\n"):
                            print(_dim(f"    {line}"))
                    else:
                        print(_dim(f"  [tool result]"))
                elif hasattr(item, "text"):
                    # TextBlock — skip (shown in ResultMessage)
                    pass
        elif isinstance(content, str) and content.strip():
            print(_dim(f"  {cls}: {content[:200]}"))
        return

    # Anything else — show type name briefly
    print(_dim(f"  [{cls}]"))


async def run_interactive(
    agent: NamelessAgent, log_fh=None, verbose: bool = False,
) -> None:
    """Run an interactive chat loop.

    Ctrl-C during a response interrupts the current turn.
    Ctrl-C twice at the prompt exits.
    """
    print(_bold("Chat with Nameless") + _dim(" (Ctrl-C to interrupt, twice to exit)"))
    print()

    loop = asyncio.get_running_loop()
    last_prompt_interrupt = 0.0

    while True:
        # --- Input phase ---
        # Default SIGINT: input() raises KeyboardInterrupt on Ctrl-C
        try:
            user_input = input(_bold(_cyan("You: "))).strip()
        except EOFError:
            print("\n" + _dim("Goodbye."))
            break
        except KeyboardInterrupt:
            now = time.monotonic()
            if now - last_prompt_interrupt < 2.0:
                print("\n" + _dim("Goodbye."))
                break
            last_prompt_interrupt = now
            print(_dim("\n  [Ctrl-C again to exit]"))
            continue

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print(_dim("Goodbye."))
            break

        # --- Streaming phase ---
        # Custom SIGINT handler cancels the task instead of raising
        responses: list = []
        tool_names: dict[str, str] = {}
        current_task: asyncio.Task | None = None
        interrupted = False

        def on_sigint():
            if current_task and not current_task.done():
                current_task.cancel()

        loop.add_signal_handler(signal.SIGINT, on_sigint)
        try:
            async def stream():
                async for msg in agent.run(user_input):
                    responses.append(msg)
                    display_msg(
                        msg, agent=agent, log_fh=log_fh,
                        verbose=verbose, tool_names=tool_names,
                    )

            current_task = asyncio.create_task(stream())
            try:
                await current_task
            except asyncio.CancelledError:
                interrupted = True
                print("\n" + _dim("  [interrupted]"))
        finally:
            loop.remove_signal_handler(signal.SIGINT)
            current_task = None

        if not interrupted:
            await agent.persist_conversation(user_input, responses)

        # Reset prompt interrupt timer after a turn completes
        last_prompt_interrupt = 0.0
        print()


async def run_oneshot(
    agent: NamelessAgent, message: str, log_fh=None, verbose: bool = False,
) -> None:
    """Send a single message and display the response."""
    print(_bold(_cyan("You: ")) + message)

    responses: list = []
    tool_names: dict[str, str] = {}
    async for msg in agent.run(message):
        responses.append(msg)
        display_msg(msg, agent=agent, log_fh=log_fh, verbose=verbose, tool_names=tool_names)

    await agent.persist_conversation(message, responses)
    print()


async def main() -> None:
    args = sys.argv[1:]

    debug = "--debug" in args
    if debug:
        args.remove("--debug")
        logging.basicConfig(level=logging.DEBUG)

    verbose = "--verbose" in args or "-v" in args
    if "--verbose" in args:
        args.remove("--verbose")
    if "-v" in args:
        args.remove("-v")

    log_file = None
    if "--log" in args:
        idx = args.index("--log")
        log_file = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    agent = NamelessAgent()
    print(_dim(f"Agent ID: {agent.agent_id}"))
    if verbose:
        print(_dim("Verbose mode: showing tool inputs/outputs"))
    print(_dim("---"))

    fh = open(log_file, "w") if log_file else None
    try:
        if args:
            message = " ".join(args)
            await run_oneshot(agent, message, fh, verbose=verbose)
        else:
            await run_interactive(agent, fh, verbose=verbose)
    finally:
        if fh:
            fh.close()
            print(_dim(f"Raw log: {log_file}"))


if __name__ == "__main__":
    asyncio.run(main())
