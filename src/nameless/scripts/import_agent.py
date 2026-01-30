"""Import Nameless agent into a Letta instance.

Imports the agent file (.af) and restores archival memory passages.

Usage:
    nameless-import exports/nameless_20240115.af --target-url http://localhost:8283
    nameless-import exports/nameless_20240115.af --target-url https://api.letta.com --api-key <key>
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from letta_client import Letta

from nameless.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """Result of an agent import operation."""

    agent_id: str
    passages_imported: int
    name: str | None = None


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


def import_passages(client: Letta, agent_id: str, passages_file: Path) -> int:
    """Import archival memory passages for an agent.

    Args:
        client: Letta client
        agent_id: The agent ID to import passages into
        passages_file: Path to the passages JSON file

    Returns:
        Number of passages imported
    """
    if not passages_file.exists():
        logger.warning(f"Passages file not found: {passages_file}")
        return 0

    logger.info(f"Importing archival memory passages from {passages_file}")

    with open(passages_file) as f:
        data = json.load(f)

    passages = data.get("passages", [])
    if not passages:
        logger.info("No passages to import")
        return 0

    imported = 0
    for passage in passages:
        try:
            # Create passage in the new agent
            kwargs: dict = {"text": passage["text"]}
            if passage.get("tags"):
                kwargs["tags"] = passage["tags"]

            client.agents.passages.create(agent_id, **kwargs)
            imported += 1

            if imported % 50 == 0:
                logger.info(f"  Imported {imported}/{len(passages)} passages...")

        except Exception as e:
            logger.warning(f"Failed to import passage: {e}")

    logger.info(f"Imported {imported}/{len(passages)} passages")
    return imported


def import_agent(
    agent_file: Path,
    passages_file: Path | None = None,
    target_url: str | None = None,
    api_key: str | None = None,
    name: str | None = None,
    model: str | None = None,
    embedding: str | None = None,
) -> ImportResult:
    """Import an agent and its archival memory into Letta.

    Args:
        agent_file: Path to the .af agent file
        passages_file: Path to the passages JSON file (default: inferred from agent_file)
        target_url: Target Letta server URL (default: from settings)
        api_key: API key for target server (default: from settings)
        name: Override agent name
        model: Override LLM model
        embedding: Override embedding model

    Returns:
        ImportResult with the new agent ID
    """
    settings = get_settings()

    # Use provided URL or fall back to settings
    base_url = target_url or settings.letta.base_url
    if api_key is None:
        api_key = settings.letta.api_key

    # Infer passages file if not provided
    if passages_file is None:
        # Try to find matching passages file
        base_name = agent_file.stem
        if base_name.endswith(".af"):
            base_name = base_name[:-3]
        passages_file = agent_file.parent / f"{base_name}_passages.json"

    logger.info(f"Importing agent from {agent_file} to {base_url}")

    # Create client
    client = create_letta_client(base_url, api_key)

    # Import agent file
    logger.info("Importing agent file...")

    import_kwargs: dict = {}
    if name:
        import_kwargs["name"] = name
    if model:
        import_kwargs["model"] = model
    if embedding:
        import_kwargs["embedding"] = embedding

    with open(agent_file, "rb") as f:
        result = client.agents.import_file(file=f, **import_kwargs)

    if not result.agent_ids:
        raise RuntimeError("No agent ID returned from import")

    agent_id = result.agent_ids[0]
    logger.info(f"Agent imported with ID: {agent_id}")

    # Verify agent
    agent = client.agents.retrieve(agent_id)
    agent_name = agent.name if hasattr(agent, "name") else None
    logger.info(f"  - Name: {agent_name}")

    # Import passages
    passages_imported = import_passages(client, agent_id, passages_file)

    return ImportResult(
        agent_id=agent_id,
        passages_imported=passages_imported,
        name=agent_name,
    )


def verify_agent(client: Letta, agent_id: str) -> None:
    """Verify the imported agent is accessible and show details.

    Args:
        client: Letta client
        agent_id: The agent ID to verify
    """
    logger.info(f"Verifying agent {agent_id}...")

    agent = client.agents.retrieve(agent_id)
    logger.info(f"  - Name: {getattr(agent, 'name', 'Unknown')}")
    logger.info(f"  - Created: {getattr(agent, 'created_at', 'Unknown')}")

    # Check memory blocks
    blocks = list(client.agents.blocks.list(agent_id))
    logger.info(f"  - Memory blocks: {len(blocks)}")
    for block in blocks:
        logger.info(f"    - {block.label}: {len(block.value or '')} chars")

    # Check passages
    passages = list(client.agents.passages.list(agent_id, limit=1))
    # Can't easily get total count, but we can check if any exist
    has_passages = len(passages) > 0
    logger.info(f"  - Has archival memory: {has_passages}")


def main() -> None:
    """CLI entry point for agent import."""
    parser = argparse.ArgumentParser(
        description="Import Nameless agent to Letta",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import to local Letta server
  nameless-import exports/nameless_20240115.af

  # Import to Letta Cloud
  nameless-import exports/nameless_20240115.af --target-url https://api.letta.com --api-key $LETTA_API_KEY

  # Import with name override
  nameless-import exports/nameless_20240115.af --name "Nameless-Dev"

  # Import with explicit passages file
  nameless-import exports/nameless.af --passages exports/nameless_passages.json

  # Debug connection issues
  nameless-import exports/nameless.af --verbose
        """,
    )
    parser.add_argument("agent_file", type=Path, help="Path to .af agent file")
    parser.add_argument(
        "--passages",
        type=Path,
        help="Path to passages JSON file (default: inferred from agent file name)",
    )
    parser.add_argument(
        "--target-url",
        help="Target Letta server URL (default: from LETTA_BASE_URL env var)",
    )
    parser.add_argument(
        "--api-key",
        help="API key for target server (default: from LETTA_API_KEY env var)",
    )
    parser.add_argument(
        "-n",
        "--name",
        help="Override agent name",
    )
    parser.add_argument(
        "--model",
        help="Override LLM model (e.g., gpt-4, claude-3-opus)",
    )
    parser.add_argument(
        "--embedding",
        help="Override embedding model",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify agent after import",
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

    if not args.agent_file.exists():
        logger.error(f"Agent file not found: {args.agent_file}")
        sys.exit(1)

    try:
        result = import_agent(
            args.agent_file,
            passages_file=args.passages,
            target_url=args.target_url,
            api_key=args.api_key,
            name=args.name,
            model=args.model,
            embedding=args.embedding,
        )

        if args.verify:
            settings = get_settings()
            base_url = args.target_url or settings.letta.base_url
            client = create_letta_client(base_url, args.api_key)
            verify_agent(client, result.agent_id)

        print("\nImport complete!")
        print(f"  Agent ID: {result.agent_id}")
        if result.name:
            print(f"  Name: {result.name}")
        print(f"  Passages imported: {result.passages_imported}")
        print(f"\nAdd to .env: NAMELESS_AGENT_ID={result.agent_id}")

    except Exception as e:
        if args.verbose:
            logger.exception(f"Import failed: {e}")
        else:
            logger.error(f"Import failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
