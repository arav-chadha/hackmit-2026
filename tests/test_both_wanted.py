from datetime import datetime, timezone

from insights.both_wanted import Pair, Wish, capped, evidence, pairs
from insights.inbox import Message


def wish(thread_id: str, thread_name: str, sender: str, window_id: str, text: str = "i want to try climbing") -> Wish:
    message = Message(f"{thread_id}-{window_id}", thread_id, sender, datetime(2025, 3, 2, tzinfo=timezone.utc), text)
    return Wish(message, thread_name, window_id)


priya = wish("priya_1", "Priya Raman", "Priya Raman", "w-priya")
to_rafa = wish("rafa_1", "Rafa Ortiz", "you", "w-rafa")
to_mei = wish("mei_1", "Mei Tanaka", "you", "w-mei", "i've always wanted to make a bad bowl")


def test_a_friends_wish_pairs_with_your_wishes_in_the_nearest_conversations():
    assert pairs(priya, [to_rafa, to_mei], ["w-rafa"]) == [Pair(priya, to_rafa)]


def test_wishes_said_in_the_same_conversation_are_not_a_pair():
    same_conversation = wish("priya_1", "Priya Raman", "you", "w-priya")
    assert pairs(priya, [same_conversation], ["w-priya"]) == []


def test_evidence_labels_each_message_with_the_chat_it_came_from():
    theirs, yours = evidence(Pair(priya, to_rafa))
    assert (theirs.thread_name, theirs.is_key) == ("Priya Raman", True)
    assert (yours.thread_name, yours.is_key) == ("Rafa Ortiz", True)


def test_the_same_activity_with_the_same_friend_appears_once():
    found = [(Pair(priya, to_rafa), "rock climbing"), (Pair(priya, to_mei), "rock climbing")]
    assert capped(found) == [(Pair(priya, to_rafa), "rock climbing")]


def test_one_friend_gets_at_most_two_cards():
    found = [(Pair(priya, to_rafa), activity) for activity in ("rock climbing", "pottery", "surfing")]
    assert [activity for _, activity in capped(found)] == ["rock climbing", "pottery"]
