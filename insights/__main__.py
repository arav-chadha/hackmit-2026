"""Command line: python -m insights ingest <inbox folder>"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from elasticsearch import Elasticsearch

from insights.inbox import InboxError, read_inbox
from insights.index import IndexNames, ingest, recreate_indexes
from insights.settings import Settings, SettingsError


def main() -> int:
    parser = argparse.ArgumentParser(prog="insights")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest_command = commands.add_parser("ingest", help="parse an Instagram inbox folder and index it")
    ingest_command.add_argument("inbox", type=Path)
    arguments = parser.parse_args()

    load_dotenv(Path.cwd() / ".env")
    try:
        settings = Settings.from_env(os.environ)
        threads = read_inbox(arguments.inbox)
    except (SettingsError, InboxError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    client = Elasticsearch(settings.elastic_url, api_key=settings.elastic_api_key)
    names = IndexNames(settings.index_prefix)
    recreate_indexes(client, names, settings.inference_id)
    indexed = ingest(client, threads, settings.owner, names)
    print(f"indexed {indexed} documents from {len(threads)} threads into {names.messages} and {names.windows}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
