"""Import Nameless agent into self-hosted Letta server.

Imports an AgentFile and configures it for the new environment.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import httpx

from nameless.config import get_settings

logger = logging.getLogger(__name__)


def import_agent(agent_file: Path, agent_name: str | None = None) -> str:
    """Import an agent from an AgentFile into Letta.

    Args:
        agent_file: Path to the AgentFile to import
        agent_name: Optional name override for the imported agent

    Returns:
        The new agent ID
    """
    settings = get_settings()

    logger.info(f"Importing agent from {agent_file} to {settings.letta.base_url}")

    # Read agent file
    with open(agent_file) as f:
        agent_data = json.load(f)

    if agent_name:
        agent_data["name"] = agent_name

    # Build request
    headers = {"Content-Type": "application/json"}
    if settings.letta.password:
        headers["Authorization"] = f"Bearer {settings.letta.password}"

    # Import endpoint
    import_url = f"{settings.letta.base_url}/v1/agents/import"

    with httpx.Client(timeout=120.0) as client:
        response = client.post(import_url, headers=headers, json=agent_data)
        response.raise_for_status()

        result = response.json()

    agent_id = result.get("id")
    logger.info(f"Agent imported successfully with ID: {agent_id}")
    logger.info(f"  Add this to your .env: NAMELESS_AGENT_ID={agent_id}")

    return agent_id


def verify_agent(agent_id: str) -> bool:
    """Verify the imported agent is accessible.

    Args:
        agent_id: The agent ID to verify

    Returns:
        True if agent is accessible
    """
    settings = get_settings()

    headers = {}
    if settings.letta.password:
        headers["Authorization"] = f"Bearer {settings.letta.password}"

    agent_url = f"{settings.letta.base_url}/v1/agents/{agent_id}"

    with httpx.Client(timeout=30.0) as client:
        response = client.get(agent_url, headers=headers)
        response.raise_for_status()

        agent = response.json()

    logger.info(f"Agent verified: {agent.get('name', 'Unknown')}")
    logger.info(f"  - Model: {agent.get('llm_config', {}).get('model', 'Unknown')}")
    logger.info(f"  - Created: {agent.get('created_at', 'Unknown')}")

    return True


def main() -> None:
    """CLI entry point for agent import."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Import Nameless agent to Letta")
    parser.add_argument("agent_file", type=Path, help="Path to AgentFile to import")
    parser.add_argument(
        "-n",
        "--name",
        help="Override agent name",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify agent after import",
    )
    args = parser.parse_args()

    if not args.agent_file.exists():
        logger.error(f"Agent file not found: {args.agent_file}")
        sys.exit(1)

    try:
        agent_id = import_agent(args.agent_file, args.name)

        if args.verify:
            verify_agent(agent_id)

        print(f"\nAgent ID: {agent_id}")
        print(f"Add to .env: NAMELESS_AGENT_ID={agent_id}")

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
