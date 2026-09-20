from datetime import datetime, timezone

from insights.cards import Card, Evidence, Kind
from insights.inbox import Message
from insights.recap import Summary, recap_card
from insights.your_people import Friendship

WHEN = datetime(2024, 7, 12, 2, 58, tzinfo=timezone.utc)
LATE_NIGHT = tuple(100 if hour in (22, 23, 0, 1) else 3 for hour in range(24))

rafa = Friendship("rafa_1", "Rafa Ortiz", 3276, WHEN, WHEN, 30, datetime(2024, 7, 1, tzinfo=timezone.utc), LATE_NIGHT, 372, 175)
ranked = Card(Kind.your_people, "rafa_1", "Rafa Ortiz", "Rafa Ortiz", "", score=0.96, rank=1)
summary = Summary(top_topic="Hackathons", body="Two years, mostly after midnight, mostly about hackathons.")


def about(kind: Kind, thread_id: str = "rafa_1", evidence: tuple[Evidence, ...] = ()) -> Card:
    return Card(kind, thread_id, "someone", "title", "body", score=1.0, evidence=evidence)


def line(message_id: str, is_key: bool) -> Evidence:
    return Evidence(Message(message_id, "rafa_1", "you", WHEN, "it is 3am"), "Rafa Ortiz", is_key)


def test_recap_carries_the_numbers_the_topic_and_the_share_button():
    produced = recap_card(rafa, ranked, summary, [])
    assert (produced.title, produced.body) == ("You + Rafa", "Two years, mostly after midnight, mostly about hackathons.")
    assert produced.stats == (
        ("Messages", "3,276"),
        ("Most active month", "July 2024"),
        ("Top topic", "Hackathons"),
        ("Most active time", "10 PM – 2 AM"),
    )
    assert (produced.action.label, produced.action.draft) == ("Share Recap", None)


def test_other_cards_about_the_same_friend_are_counted_and_zero_counts_are_left_out():
    cards = [about(Kind.memory_lane), about(Kind.memory_lane), about(Kind.unfinished_plans), about(Kind.unanswered, "mei_1")]
    labels = dict(recap_card(rafa, ranked, summary, cards).stats)
    assert (labels["Memories worth revisiting"], labels["Unfinished plans"]) == ("2", "1")
    assert "Unanswered questions" not in labels


def test_standout_messages_are_the_friends_memory_highlights():
    memory = about(Kind.memory_lane, evidence=(line("setup", False), line("punchline", True)))
    elsewhere = about(Kind.memory_lane, "mei_1", evidence=(line("other", True),))
    produced = recap_card(rafa, ranked, summary, [memory, elsewhere])
    assert [item.message.id for item in produced.evidence] == ["punchline"]


def test_recap_sits_below_the_friends_your_people_card_in_the_feed():
    assert recap_card(rafa, ranked, summary, []).score == 0.96 * 0.75
