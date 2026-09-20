from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from insights.inbox import Message
from insights.unanswered import Candidate, Verdict, selected, transcript

ASKED = datetime(2025, 3, 14, 21, 22, tzinfo=timezone.utc)
CONTEXT = SimpleNamespace(owner="you", now=datetime(2026, 9, 20, tzinfo=timezone.utc))


def candidate(thread_id: str, text: str, friend: str = "Mei Tanaka") -> Candidate:
    question = Message(f"{thread_id}-{text}", thread_id, friend, ASKED, text)
    before = (Message("b1", thread_id, "you", ASKED - timedelta(minutes=1), "had the interview thursday"),)
    after = (Message("a1", thread_id, "you", ASKED + timedelta(hours=11), "did you see the fire in studio"),)
    return Candidate(friend, question, before, after)


def verdict(importance: int, is_answered: bool = False) -> Verdict:
    return Verdict(is_answered=is_answered, importance=importance, reason="")


def test_transcript_marks_the_question_and_says_who_the_owner_is():
    assert transcript(candidate("mei_1", "how did the interview go??"), CONTEXT) == (
        "Today is 2026-09-20. Thread between you (the account owner) and Mei Tanaka.\n\n"
        "[2025-03-14 21:21] you: had the interview thursday\n"
        ">>> [2025-03-14 21:22] Mei Tanaka: how did the interview go??\n"
        "[2025-03-15 08:22] you: did you see the fire in studio"
    )


def test_answered_and_trivial_questions_are_dropped():
    verdicts = [
        (candidate("mei_1", "how did the interview go??"), verdict(5)),
        (candidate("dev_1", "who is presenting?"), verdict(4, is_answered=True)),
        (candidate("mei_1", "harvest of WHAT"), verdict(1)),
    ]
    assert [c.question.text for c, _ in selected(verdicts)] == ["how did the interview go??"]


def test_strongest_come_first_and_one_friend_cannot_flood_the_list():
    verdicts = [
        (candidate("mei_1", "minor one?"), verdict(3)),
        (candidate("mei_1", "big one?"), verdict(5)),
        (candidate("mei_1", "medium one?"), verdict(4)),
        (candidate("priya_1", "did you decide?", "Priya Raman"), verdict(4)),
    ]
    assert [c.question.text for c, _ in selected(verdicts)] == ["big one?", "medium one?", "did you decide?"]


def test_the_same_question_asked_twice_appears_once():
    verdicts = [(candidate("mei_1", "you ok?"), verdict(4)), (candidate("mei_1", "you ok?"), verdict(4))]
    assert len(selected(verdicts)) == 1


def test_list_is_capped_at_five():
    verdicts = [(candidate(f"friend_{n}", "you ok?", f"Friend {n}"), verdict(4)) for n in range(8)]
    assert len(selected(verdicts)) == 5
