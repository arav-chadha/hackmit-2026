"""Command line.

python -m insights ingest <inbox folder>                  parse an Instagram inbox and index it
python -m insights cards [--out FILE] [--only INSIGHT]    run the insights and write the cards file
python -m insights serve [--port 8000]                    serve the cards to the dashboard
"""

import argparse
import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from insights.cards import write_cards
from insights.inbox import InboxError, read_inbox
from insights.index import IndexNames, ingest, recreate_indexes
from insights.judge import JudgeError
from insights.pipeline import context_from_env, insights, run, search_client
from insights.settings import Settings, SettingsError


def main() -> int:
    parser = argparse.ArgumentParser(prog="insights")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ingest").add_argument("inbox", type=Path)
    cards_command = commands.add_parser("cards")
    cards_command.add_argument("--out", type=Path, default=Path("cards.json"))
    cards_command.add_argument("--only", choices=sorted(insights), help="run a single insight")
    commands.add_parser("serve").add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args()

    load_dotenv(Path.cwd() / ".env")
    try:
        settings = Settings.from_env(os.environ)
        command = {"ingest": _ingest, "cards": _cards, "serve": _serve}[arguments.command]
        print(command(settings, arguments))
    except (SettingsError, InboxError, JudgeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


def _ingest(settings: Settings, arguments: argparse.Namespace) -> str:
    threads = read_inbox(arguments.inbox)
    client = search_client(settings)
    names = IndexNames(settings.index_prefix)
    recreate_indexes(client, names, settings.inference_id)
    indexed = ingest(client, threads, settings.owner, names)
    return f"indexed {indexed} documents from {len(threads)} threads into {names.messages} and {names.windows}"


def _cards(settings: Settings, arguments: argparse.Namespace) -> str:
    cards = run(context_from_env(), arguments.only)
    write_cards(cards, settings.owner, arguments.out)
    return f"wrote {len(cards)} cards to {arguments.out}"


def _serve(settings: Settings, arguments: argparse.Namespace) -> str:
    uvicorn.run("insights.server:app", port=arguments.port)
    return "server stopped"


if __name__ == "__main__":
    sys.exit(main())
