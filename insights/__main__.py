"""Command line.

python -m insights ingest <inbox folder>    parse an Instagram inbox and index it
python -m insights cards [--out cards.json] run the insights and write the cards file
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

from insights.cards import write_cards
from insights.context import Context
from insights.inbox import InboxError, read_inbox
from insights.index import IndexNames, ingest, recreate_indexes
from insights.judge import JudgeError
from insights.settings import Settings, SettingsError
from insights.unanswered import unanswered
from insights.unfinished_plans import unfinished_plans
from insights.your_people import your_people

insights = (your_people, unanswered, unfinished_plans)


def main() -> int:
    parser = argparse.ArgumentParser(prog="insights")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ingest").add_argument("inbox", type=Path)
    commands.add_parser("cards").add_argument("--out", type=Path, default=Path("cards.json"))
    arguments = parser.parse_args()

    load_dotenv(Path.cwd() / ".env")
    try:
        settings = Settings.from_env(os.environ)
        run = {"ingest": _ingest, "cards": _cards}[arguments.command]
        print(run(settings, arguments))
    except (SettingsError, InboxError, JudgeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


def _ingest(settings: Settings, arguments: argparse.Namespace) -> str:
    threads = read_inbox(arguments.inbox)
    client = _search_client(settings)
    names = IndexNames(settings.index_prefix)
    recreate_indexes(client, names, settings.inference_id)
    indexed = ingest(client, threads, settings.owner, names)
    return f"indexed {indexed} documents from {len(threads)} threads into {names.messages} and {names.windows}"


def _cards(settings: Settings, arguments: argparse.Namespace) -> str:
    context = Context(
        search=_search_client(settings),
        names=IndexNames(settings.index_prefix),
        llm=anthropic.Anthropic(),
        judge_model=settings.judge_model,
        writer_model=settings.writer_model,
        owner=settings.owner,
        now=datetime.now(timezone.utc),
    )
    cards = [card for insight in insights for card in insight(context)]
    write_cards(cards, settings.owner, arguments.out)
    return f"wrote {len(cards)} cards to {arguments.out}"


def _search_client(settings: Settings) -> Elasticsearch:
    return Elasticsearch(settings.elastic_url, api_key=settings.elastic_api_key, request_timeout=60)


if __name__ == "__main__":
    sys.exit(main())
