from dataclasses import replace
from datetime import datetime, timedelta, timezone

from insights.your_people import Friendship, card, ranked, usual_hours

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)
LATE_NIGHT = tuple(100 if hour in (22, 23, 0, 1) else 3 for hour in range(24))

rafa = Friendship(
    thread_id="rafa_1",
    name="Rafa Ortiz",
    messages=3000,
    first=datetime(2024, 4, 5, tzinfo=timezone.utc),
    last=NOW - timedelta(days=4),
    active_months=30,
    busiest_month=datetime(2024, 7, 1, tzinfo=timezone.utc),
    hour_counts=LATE_NIGHT,
    conversations=300,
    started_by_owner=150,
)


def test_equal_history_ranks_the_friend_you_still_talk_to_first():
    faded = replace(rafa, thread_id="mei_1", name="Mei Tanaka", last=NOW - timedelta(days=300))
    assert [f.name for f, _ in ranked([faded, rafa], NOW)] == ["Rafa Ortiz", "Mei Tanaka"]


def test_silence_costs_a_quarter_after_a_year_and_never_more_than_half():
    (_, fresh), (_, year_quiet), (_, decade_quiet) = (
        ranked([replace(rafa, last=NOW - timedelta(days=days))], NOW)[0] for days in (0, 365, 3650)
    )
    assert round(year_quiet / fresh, 2) == 0.75
    assert 0.5 <= decade_quiet / fresh < 0.51


def test_a_long_history_outranks_a_short_recent_one():
    brief = replace(rafa, thread_id="new_1", name="New Friend", messages=150, active_months=2)
    faded = replace(rafa, thread_id="mei_1", name="Mei Tanaka", last=NOW - timedelta(days=300))
    assert [f.name for f, _ in ranked([brief, faded], NOW)] == ["Mei Tanaka", "New Friend"]


def test_who_starts_conversations_is_shown_but_does_not_move_the_rank():
    one_sided = replace(rafa, thread_id="priya_1", name="Priya Raman", started_by_owner=90)
    (_, balanced_score), (_, one_sided_score) = ranked([rafa], NOW)[0], ranked([one_sided], NOW)[0]
    produced = card(one_sided, one_sided_score, 2, NOW)
    assert balanced_score == one_sided_score
    assert "Priya starts most of your conversations." in produced.body
    assert ("Who starts conversations", "Priya, 70% of the time") in produced.stats


def test_an_active_balanced_friendship_gets_no_extra_lines():
    produced = card(rafa, 0.97, 1, NOW)
    assert produced.body == "You've talked in 30 different months since April 2024. Your most active stretch was July 2024."
    assert [label for label, _ in produced.stats] == ["Messages", "Talking since", "Most active month", "Usual hours"]
    assert (produced.title, produced.rank, produced.stats[0]) == ("Rafa Ortiz", 1, ("Messages", "3,000"))


def test_a_quiet_friendship_says_since_when():
    faded = replace(rafa, last=datetime(2025, 11, 23, tzinfo=timezone.utc))
    produced = card(faded, 0.7, 3, NOW)
    assert produced.body.endswith("It has been quiet since November 2025.")
    assert ("Quiet since", "Nov 2025") in produced.stats


def test_usual_hours_wrap_past_midnight():
    assert usual_hours(LATE_NIGHT) == "10 PM – 2 AM"


def test_no_friendships_means_no_ranking():
    assert ranked([], NOW) == []
