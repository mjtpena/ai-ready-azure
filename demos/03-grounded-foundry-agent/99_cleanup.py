"""Remove the demo artefacts: all versions of the Site Operations Advisor agent and, optionally, the search index.

Usage: python 99_cleanup.py [--index] [--yes]
"""

from __future__ import annotations

import argparse
import os

import _shared  # noqa: F401
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from foundry_util import agent_name, is_mock, load_env, project_client


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--index", action="store_true", help="also delete the AI Search index")
    parser.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    args = parser.parse_args()
    load_env()
    name = agent_name()
    index_name = os.environ.get("AI_SEARCH_INDEX", "hbl-site-knowledge")

    if is_mock():
        print(f"[MOCK] would delete agent '{name}' (all versions)" + (f" and index '{index_name}'" if args.index else ""))
        return
    if not args.yes and input(f"Delete agent '{name}'{' and index ' + index_name if args.index else ''}? [y/N] ").lower() != "y":
        return

    with project_client() as client:
        try:
            versions = [v.version for v in client.agents.list_versions(agent_name=name)]
            for version in versions:
                client.agents.delete_version(agent_name=name, agent_version=version, force=True)
                print(f"Deleted {name} version {version}")
            client.agents.delete(agent_name=name, force=True)
            print(f"Deleted agent {name}")
        except ResourceNotFoundError:
            print(f"Agent {name} not found; nothing to delete")

    if args.index:
        index_client = SearchIndexClient(endpoint=os.environ["AI_SEARCH_ENDPOINT"], credential=DefaultAzureCredential())
        try:
            index_client.delete_index(index_name)
            print(f"Deleted index {index_name}")
        except ResourceNotFoundError:
            print(f"Index {index_name} not found; nothing to delete")


if __name__ == "__main__":
    main()
