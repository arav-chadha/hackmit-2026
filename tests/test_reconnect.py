from dataclasses import replace
from datetime import date, datetime, timezone

from insights.conversations import Conversations
from insights.cards import Hook
from insights.reconnect import Faded, News, Topic, Word, capped, faded_words, shared_interests, usable

LAST = datetime(2024, 9, 3, tzinfo=timezone.utc)


def topic(name: str, words: list[str], is_shared_interest: bool = True, strength: int = 5) -> Topic:
    return Topic(name=name, words=words, is_shared_interest=is_shared_interest, strength=strength, is_public_interest=True, evidence_refs=[])


def test_a_word_still_in_use_near_the_end_of_the_friendship_has_not_faded():
    words = [Word("cobblestone", 14, 0), Word("castle", 29, 1), Word("bro", 200, 45)]
    assert faded_words(words) == ["cobblestone"]


def test_a_word_from_one_long_conversation_was_never_a_recurring_thing():
    assert faded_words([Word("trial", 2, 0), Word("diamonds", 17, 0)]) == ["diamonds"]


def test_only_shared_interests_are_kept():
    topics = [topic("Minecraft", ["cobblestone", "diamonds"]), topic("his thermodynamics class", ["dynamics"], False)]
    kept = shared_interests(topics, ["cobblestone", "diamonds", "dynamics"])
    assert [(t.name, words) for t, words in kept] == [("Minecraft", ["cobblestone", "diamonds"])]


def test_a_catchphrase_with_nothing_to_go_and_do_is_dropped():
    kept = shared_interests([topic("saying allegedly", ["allegedly"], strength=3)], ["allegedly"])
    assert kept == []


def test_words_the_judge_added_on_its_own_are_dropped():
    kept = shared_interests([topic("Minecraft", ["cobblestone", "creeper"]), topic("chess", ["rook"])], ["cobblestone"])
    assert [(t.name, words) for t, words in kept] == [("Minecraft", ["cobblestone"])]


TODAY = date(2026, 9, 20)


def news(**changes) -> News:
    found = {"has_hook": True, "text": "A new update came out.", "source": "GameSpot", "url": "https://www.gamespot.com/x", "date": "2026-09-15"}
    return News(**{**found, **changes})


def test_a_recent_sourced_hook_is_kept():
    assert usable(news(), TODAY) == Hook("A new update came out.", "GameSpot", "https://www.gamespot.com/x", "2026-09-15")


def test_hooks_that_cannot_be_checked_or_are_stale_are_dropped():
    unusable = [
        news(has_hook=False),
        news(text="  "),
        news(url="gamespot.com/x"),
        news(date="last week"),
        news(date="2026-03-01"),
        news(date="2026-10-01"),
    ]
    assert [usable(found, TODAY) for found in unusable] == [None] * len(unusable)


def test_one_friend_gets_at_most_two_cards():
    jonas = Faded("Minecraft", Conversations("Jonas Weber", "jonas_1", {}), (), 5, 120, LAST)
    priya = replace(jonas, name="crossword", samples=Conversations("Priya Raman", "priya_1", {}))
    assert [t.name for t in capped([jonas, jonas, jonas, priya])] == ["Minecraft", "Minecraft", "crossword"]
