"""Scores a cards file against data/corpus/answers.json.

Run with: python -m corpus.score cards.json
"""

import json
import sys
from pathlib import Path

from corpus.build import output_dir


def score(cards: list[dict], planted: list[dict]) -> list[tuple[str, str]]:
    key_texts = {(card["kind"], item["text"]) for card in cards for item in card["evidence"] if item["isKey"]}
    flagged_texts = {text for _, text in key_texts}
    return [(moment["label"], _outcome(moment, key_texts, flagged_texts)) for moment in planted]


def _outcome(moment: dict, key_texts: set[tuple[str, str]], flagged_texts: set[str]) -> str:
    texts = [key["text"] for key in moment["keys"]]
    if moment["kind"] == "control":
        return "WRONGLY FLAGGED" if any(text in flagged_texts for text in texts) else "correctly ignored"
    return "found" if any((moment["kind"], text) in key_texts for text in texts) else "MISSED"


def main() -> int:
    cards = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["cards"]
    planted = json.loads((output_dir / "answers.json").read_text(encoding="utf-8"))
    outcomes = score(cards, planted)
    for label, outcome in outcomes:
        print(f"{outcome:18} {label}")
    expected = {key["text"] for moment in planted for key in moment["keys"]}
    extras = [c for c in cards if c["evidence"] and not any(e["isKey"] and e["text"] in expected for e in c["evidence"])]
    for card in extras:
        print(f"{'NOT PLANTED':18} {card['kind']}: {card['title']}")
    failures = sum(outcome in ("MISSED", "WRONGLY FLAGGED") for _, outcome in outcomes)
    print(f"\n{len(outcomes) - failures}/{len(outcomes)} correct, {len(extras)} cards not in the answer key")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
