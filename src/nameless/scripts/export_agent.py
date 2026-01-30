"""Export Nameless agent from current Letta instance.

Creates an AgentFile that can be imported into the self-hosted Letta server.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import httpx

from nameless.config import get_settings

logger = logging.getLogger(__name__)


def export_agent(agent_id: str, output_path: Path | None = None) -> Path:
    """Export an agent from Letta to an AgentFile.

    Args:
        agent_id: The Letta agent ID to export
        output_path: Where to save the export (default: ./exports/<timestamp>.agent)

    Returns:
        Path to the exported AgentFile
    """
    settings = get_settings()

    if output_path is None:
        exports_dir = Path("exports")
        exports_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = exports_dir / f"nameless_{timestamp}.agent"

    logger.info(f"Exporting agent {agent_id} from {settings.letta.base_url}")

    # Build request
    headers = {}
    if settings.letta.password:
        headers["Authorization"] = f"Bearer {settings.letta.password}"

    # Export endpoint
    export_url = f"{settings.letta.base_url}/v1/agents/{agent_id}/export"

    with httpx.Client(timeout=60.0) as client:
        response = client.get(export_url, headers=headers)
        response.raise_for_status()

        agent_data = response.json()

    # Write to file
    with open(output_path, "w") as f:
        json.dump(agent_data, f, indent=2)

    logger.info(f"Agent exported to {output_path}")
    logger.info(f"  - Core memory blocks: {len(agent_data.get('memory', {}).get('blocks', []))}")
    logger.info(f"  - Tools: {len(agent_data.get('tools', []))}")

    return output_path


def main() -> None:
    """CLI entry point for agent export."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Export Nameless agent from Letta")
    parser.add_argument("agent_id", help="Letta agent ID to export")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output path for AgentFile (default: exports/<timestamp>.agent)",
    )
    args = parser.parse_args()

    try:
        output = export_agent(args.agent_id, args.output)
        print(f"Successfully exported to: {output}")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Export failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
