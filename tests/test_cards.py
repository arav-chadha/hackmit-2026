import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from insights.cards import Action, Card, Evidence, Kind, document, write_cards
from insights.inbox import Message, Thread

CONTRACT = json.loads((Path(__file__).parent.parent / "contract" / "cards.example.json").read_text())
NOW = datetime(2026, 9, 20, 2, 30, tzinfo=timezone.utc)
ASKED = datetime(2025, 3, 14, 21, 32, tzinfo=timezone.utc)

question = Message("m1", "mei_1", "Mei Tanaka", ASKED, "wait how did the interview go??")
deflection = Message("m2", "mei_1", "you", ASKED + timedelta(hours=11), "omg did you see what happened in studio today")
mei = Thread("mei_1", "Mei Tanaka", ("Mei Tanaka", "you"), (question, deflection))


def unanswered(*evidence: Evidence) -> Card:
    return Card(
        kind=Kind.unanswered,
        thread=mei,
        title="Mei asked how your interview went",
        body="You kept talking afterward, but you never told her.",
        score=0.91,
        stats=(("Asked", "Mar 14, 2025"),),
        evidence=evidence,
        action=Action("Respond", "I never told you how that interview went 😭"),
    )


def full_card() -> Card:
    return unanswered(Evidence(question, "Mei Tanaka", is_key=True), Evidence(deflection, "Mei Tanaka", is_key=False))


def test_output_has_exactly_the_contract_fields():
    produced = document([full_card()], owner="you", generated_at=NOW)
    example_card = next(c for c in CONTRACT["cards"] if c["kind"] == "unanswered")
    card = produced["cards"][0]
    assert produced.keys() == CONTRACT.keys()
    assert card.keys() == example_card.keys()
    assert card["friend"].keys() == example_card["friend"].keys()
    assert card["stats"][0].keys() == example_card["stats"][0].keys()
    assert card["evidence"][0].keys() == example_card["evidence"][0].keys()
    assert card["action"].keys() == example_card["action"].keys()


def test_every_kind_in_the_contract_is_supported():
    assert {c["kind"] for c in CONTRACT["cards"]} == {kind.value for kind in Kind}


def test_evidence_is_written_oldest_first_with_owner_flag():
    late_first = unanswered(Evidence(deflection, "Mei Tanaka", is_key=False), Evidence(question, "Mei Tanaka", is_key=True))
    evidence = document([late_first], owner="you", generated_at=NOW)["cards"][0]["evidence"]
    assert [e["id"] for e in evidence] == ["m1", "m2"]
    assert [e["isFromOwner"] for e in evidence] == [False, True]
    assert evidence[0]["timestamp"] == "2025-03-14T21:32:00Z"


def test_a_bare_card_uses_null_and_empty_lists():
    bare = Card(kind=Kind.your_people, thread=mei, title="Mei Tanaka", body="Quiet lately.", score=0.5, rank=3)
    card = document([bare], owner="you", generated_at=NOW)["cards"][0]
    assert (card["stats"], card["evidence"], card["action"], card["rank"]) == ([], [], None, 3)


def test_id_is_stable_and_depends_on_the_evidence():
    first = document([full_card()], owner="you", generated_at=NOW)["cards"][0]["id"]
    again = document([full_card()], owner="you", generated_at=NOW + timedelta(days=1))["cards"][0]["id"]
    other = document([unanswered(Evidence(question, "Mei Tanaka", is_key=True))], owner="you", generated_at=NOW)["cards"][0]["id"]
    assert first == again
    assert first != other


def test_written_file_is_readable_json_with_emoji_intact(tmp_path):
    path = tmp_path / "cards.json"
    write_cards([full_card()], owner="you", path=path)
    assert "😭" in path.read_text(encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8"))["cards"][0]["kind"] == "unanswered"
