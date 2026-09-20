"""Scores a cards file against data/corpus/answers.json.

Run with: python -m corpus.score cards.json
"""

import json
import sys
from pathlib import Path

from corpus.build import output_dir


def score(cards: list[dict], planted: list[dict]) -> list[tuple[str, str]]:
    return [(moment["label"], _outcome(moment, cards)) for moment in planted]


def unplanted(cards: list[dict], planted: list[dict]) -> list[dict]:
    real = [moment for moment in planted if moment["kind"] != "control"]
    return [card for card in cards if card["evidence"] and not any(_shows(card, moment) for moment in real)]


def _outcome(moment: dict, cards: list[dict]) -> str:
    if moment["kind"] == "control":
        texts = {key["text"] for key in moment["keys"]}
        is_flagged = any(item["isKey"] and item["text"] in texts for card in cards for item in card["evidence"])
        return "WRONGLY FLAGGED" if is_flagged else "correctly ignored"
    return "found" if any(_shows(card, moment) for card in cards) else "MISSED"


def _shows(card: dict, moment: dict) -> bool:
    # Same kind, and some evidence comes from the same chat on the same day as a planted line.
    # Matching on exact text would fail a memory whose judge chose different highlight lines.
    planted_days = {(key["thread"], key["timestamp"][:10]) for key in moment["keys"]}
    shown_days = {(item["threadName"], item["timestamp"][:10]) for item in card["evidence"]}
    if card["kind"] != moment["kind"]:
        return False
    if card["kind"] == "reconnect":
        # A faded topic spans months; any of its messages is fair evidence, so match on the chat alone.
        return card["friend"]["name"] in {thread for thread, _ in planted_days}
    return bool(planted_days & shown_days)


def main() -> int:
    cards = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["cards"]
    planted = json.loads((output_dir / "answers.json").read_text(encoding="utf-8"))
    outcomes = score(cards, planted)
    for label, outcome in outcomes:
        print(f"{outcome:18} {label}")
    extras = unplanted(cards, planted)
    for card in extras:
        print(f"{'NOT PLANTED':18} {card['kind']}: {card['title']}")
    failures = sum(outcome in ("MISSED", "WRONGLY FLAGGED") for _, outcome in outcomes)
    print(f"\n{len(outcomes) - failures}/{len(outcomes)} correct, {len(extras)} cards not in the answer key")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
