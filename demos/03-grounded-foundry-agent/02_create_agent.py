"""Create (or add a version to) the Site Operations Advisor agent in Microsoft Foundry.

The agent is a versioned prompt agent: instructions + Azure AI Search tool over the knowledge index +
the four Site API function tools (or the same tools through the API Management MCP server). Each run creates a new immutable version and points the agent's
endpoint at it, so the previous version stays available for comparison in the portal.

``--candidate`` publishes to a separate agent, ``<name>-candidate``, the way CI publishes a pull request's version for
evaluation; the production agent is not touched. ``--variant helpful`` swaps the refusal rule for the "be helpful
anyway" edit (``agent_definition.HELPFUL_RULE``): the regression demo 4's quality gate catches.

Usage: python 02_create_agent.py [--candidate] [--variant production|helpful] [--no-search] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os

import _shared  # noqa: F401
from agent_definition import VARIANTS, build_definition, knowledge_titles
from foundry_util import agent_name, is_mock, load_env, portal_hint, project_client, publish_agent_version


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidate", action="store_true", help="publish to <name>-candidate instead of the production agent")
    parser.add_argument("--variant", choices=VARIANTS, default="production", help="instructions to publish (helpful = the demo regression)")
    parser.add_argument("--no-search", action="store_true", help="omit the Azure AI Search tool (function tools only)")
    parser.add_argument("--no-tools", action="store_true", help="omit every tool: instructions only (what the cloud red team can target)")
    parser.add_argument("--dry-run", action="store_true", help="print the definition as JSON and exit (implied by DEMO_MODE=mock)")
    args = parser.parse_args()
    load_env()
    if args.dry_run or is_mock():  # nothing is sent, so placeholders are fine for a dry run
        os.environ.setdefault("FOUNDRY_MODEL_NAME", "gpt-5-mini")
        os.environ.setdefault("AI_SEARCH_CONNECTION_ID", "<AI_SEARCH_CONNECTION_ID>")

    name = agent_name() + ("-candidate" if args.candidate else "")
    definition = build_definition(include_search=not (args.no_search or args.no_tools), variant=args.variant, include_functions=not args.no_tools)
    print(f"Agent name   : {name}")
    print(f"Model        : {definition.model}")
    print(f"Tools        : {', '.join(getattr(t, 'name', None) or t.type for t in definition.tools)}")
    print(f"Knowledge    : {len(knowledge_titles())} documents -> {', '.join(knowledge_titles()[:3])}, ...")

    if args.dry_run or is_mock():
        print("\nDefinition (dry run, nothing sent to Foundry):")
        print(json.dumps(definition.as_dict(), indent=2)[:3000])
        return

    with project_client() as client:
        description = ("Candidate edit for the Session 4 quality gate: 'be helpful anyway' instead of declining" if args.variant == "helpful"
                       else "Harbourline Site Operations Advisor: grounded on operations guidance (AI Search) and Site API tools")
        version = publish_agent_version(client, name, definition, description=description)
    print(f"\nCreated {version.name} version {version.version} (id {version.id}); endpoint now routes 100% to it.")
    print(portal_hint(name))
    print("Open the agent in the portal, choose 'Try in playground' and ask: Is Site HBL-AKL-017 due a fire-system inspection this month?")


if __name__ == "__main__":
    main()
