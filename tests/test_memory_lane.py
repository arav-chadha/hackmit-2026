from dataclasses import replace
from datetime import datetime, timedelta, timezone

from insights.conversations import Conversations
from insights.inbox import Message
from insights.memory_lane import Memory, Rating, capped, memory

START = datetime(2024, 7, 12, 1, 41, tzinfo=timezone.utc)


def conversation(thread_id: str = "rafa_1", length: int = 12) -> Conversations:
    by_ref = {
        f"m{n}": (Message(f"id{n}", thread_id, "you" if n % 2 else "Rafa Ortiz", START + timedelta(minutes=n), f"line {n}"), "w1")
        for n in range(1, length + 1)
    }
    return Conversations("Rafa Ortiz", thread_id, by_ref)


def rating(first: str, last: str, highlights: list[str], stars: int = 5) -> Rating:
    return Rating(rating=stars, excerpt_first_ref=first, excerpt_last_ref=last, highlight_refs=highlights)


def test_excerpt_is_the_stretch_the_judge_chose_with_its_highlights():
    found = memory(conversation(), rating("m3", "m6", ["m4", "m6"]))
    assert [m.id for m in found.excerpt] == ["id3", "id4", "id5", "id6"]
    assert found.highlight_ids == {"id4", "id6"}


def test_an_overlong_excerpt_is_cut_to_eight_messages():
    found = memory(conversation(), rating("m1", "m12", []))
    assert [m.id for m in found.excerpt] == [f"id{n}" for n in range(1, 9)]


def test_an_overlong_excerpt_keeps_the_stretch_with_the_punchlines():
    found = memory(conversation(), rating("m1", "m12", ["m10", "m12"]))
    assert [m.id for m in found.excerpt] == [f"id{n}" for n in range(5, 13)]


def test_made_up_references_fall_back_to_the_start_of_the_conversation():
    found = memory(conversation(), rating("m40", "m50", ["m99"]))
    assert [m.id for m in found.excerpt] == [f"id{n}" for n in range(1, 9)]
    assert found.highlight_ids == frozenset()


def test_only_highly_rated_memories_are_kept_and_one_friend_gets_at_most_two():
    great = Memory(conversation(), 5, (), frozenset())
    pleasant = replace(great, rating=3)
    other_friend = replace(great, conversation=conversation("mei_1"), rating=4)
    assert capped([great, great, great, other_friend, pleasant]) == [great, great, other_friend]
