"""Export Nameless agent from a Letta instance.

Exports the agent file (.af) which includes:
- Model configuration
- Message history (conversation history)
- System prompt
- Memory blocks (core memory)
- Tool rules and definitions

Archival memory (passages) is exported separately since it's not yet
included in the .af format.

Usage:
    nameless-export <agent_id> --source-url http://localhost:8283
    nameless-export <agent_id> --source-url https://api.letta.com --api-key <key>
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from letta_client import Letta

from nameless.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    """Result of an agent export operation."""

    agent_file_path: Path
    passages_file_path: Path
    agent_id: str
    passage_count: int
    message_count: int | None = None


def create_letta_client(base_url: str, api_key: str | None = None) -> Letta:
    """Create a Letta client for the specified server.

    Args:
        base_url: The Letta server URL
        api_key: Optional API key for authentication

    Returns:
        Configured Letta client
    """
    kwargs: dict = {"base_url": base_url}
    if api_key:
        kwargs["api_key"] = api_key
    return Letta(**kwargs)


def export_passages(client: Letta, agent_id: str, output_path: Path) -> int:
    """Export all archival memory passages for an agent.

    Args:
        client: Letta client
        agent_id: The agent ID
        output_path: Where to save the passages JSON

    Returns:
        Number of passages exported
    """
    logger.info(f"Exporting archival memory passages for agent {agent_id}")

    all_passages = []
    after_cursor = None
    limit = 100

    # Paginate through all passages
    while True:
        kwargs: dict = {"limit": limit}
        if after_cursor:
            kwargs["after"] = after_cursor

        passages_list = client.agents.passages.list(agent_id, **kwargs)

        # API returns a list directly
        if not passages_list:
            break

        for p in passages_list:
            passage_data = {
                "id": p.id,
                "text": p.text,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "metadata": p.metadata,
                "tags": p.tags,
            }
            all_passages.append(passage_data)

        # If we got fewer than limit, we're done
        if len(passages_list) < limit:
            break

        # Use last passage ID as cursor for next page
        after_cursor = passages_list[-1].id

    # Write passages to file
    with open(output_path, "w") as f:
        json.dump({"agent_id": agent_id, "passages": all_passages}, f, indent=2)

    logger.info(f"Exported {len(all_passages)} passages to {output_path}")
    return len(all_passages)


def export_agent(
    agent_id: str,
    source_url: str | None = None,
    api_key: str | None = None,
    output_dir: Path | None = None,
) -> ExportResult:
    """Export an agent and its archival memory from Letta.

    Args:
        agent_id: The Letta agent ID to export
        source_url: Source Letta server URL (default: from settings)
        api_key: API key for source server (default: from settings)
        output_dir: Directory for export files (default: ./exports)

    Returns:
        ExportResult with paths to exported files
    """
    settings = get_settings()

    # Use provided URL or fall back to settings
    base_url = source_url or settings.letta.base_url
    if api_key is None:
        api_key = settings.letta.api_key

    # Set up output directory
    if output_dir is None:
        output_dir = Path("exports")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    agent_file_path = output_dir / f"nameless_{timestamp}.af"
    passages_file_path = output_dir / f"nameless_{timestamp}_passages.json"

    logger.info(f"Exporting agent {agent_id} from {base_url}")

    # Create client
    client = create_letta_client(base_url, api_key)

    # Export agent file (.af)
    logger.info("Exporting agent file...")
    agent_file_content = client.agents.export_file(agent_id)

    with open(agent_file_path, "w") as f:
        f.write(agent_file_content)

    logger.info(f"Agent file exported to {agent_file_path}")

    # Parse agent file to get message count
    message_count = None
    try:
        agent_data = json.loads(agent_file_content)
        messages = agent_data.get("messages", [])
        message_count = len(messages)
        logger.info(f"  - Messages: {message_count}")
        logger.info(f"  - Memory blocks: {len(agent_data.get('memory', {}).get('blocks', []))}")
    except json.JSONDecodeError:
        logger.warning("Could not parse agent file for summary")

    # Export archival memory passages
    passage_count = export_passages(client, agent_id, passages_file_path)

    return ExportResult(
        agent_file_path=agent_file_path,
        passages_file_path=passages_file_path,
        agent_id=agent_id,
        passage_count=passage_count,
        message_count=message_count,
    )


def main() -> None:
    """CLI entry point for agent export."""
    parser = argparse.ArgumentParser(
        description="Export Nameless agent from Letta",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export from local Letta server
  nameless-export agent-123

  # Export from Letta Cloud
  nameless-export agent-123 --source-url https://api.letta.com --api-key $LETTA_API_KEY

  # Export to specific directory
  nameless-export agent-123 -o ./backups

  # Debug connection issues
  nameless-export agent-123 --verbose
        """,
    )
    parser.add_argument("agent_id", help="Letta agent ID to export")
    parser.add_argument(
        "--source-url",
        help="Source Letta server URL (default: from LETTA_BASE_URL env var)",
    )
    parser.add_argument(
        "--api-key",
        help="API key for source server (default: from LETTA_API_KEY env var)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Output directory for export files (default: ./exports)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output with full error tracebacks",
    )
    args = parser.parse_args()

    # Configure logging based on verbosity
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Enable debug logging for HTTP client when verbose
    if args.verbose:
        logging.getLogger("httpx").setLevel(logging.DEBUG)
        logging.getLogger("httpcore").setLevel(logging.DEBUG)

    try:
        result = export_agent(
            args.agent_id,
            source_url=args.source_url,
            api_key=args.api_key,
            output_dir=args.output_dir,
        )

        print("\nExport complete!")
        print(f"  Agent file: {result.agent_file_path}")
        print(f"  Passages:   {result.passages_file_path}")
        print(f"  Total passages exported: {result.passage_count}")
        if result.message_count is not None:
            print(f"  Total messages: {result.message_count}")

    except Exception as e:
        if args.verbose:
            logger.exception(f"Export failed: {e}")
        else:
            logger.error(f"Export failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
