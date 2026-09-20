"""Your People: the friendships that have mattered most, ranked by history with a penalty for silence."""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from insights.cards import Card, Kind
from insights.context import Context
from insights.judge import judged
from insights.parallel import concurrently

list_size = 5
sampled_conversations = 5
volume_weight, consistency_weight = 0.6, 0.4
silence_half_life_days = 365
one_sided_share = 0.65
quiet_after_days = 60

relationship_instructions = (
    "You will read a few sampled conversations from one direct-message thread. Decide what kind of "
    "relationship it is. 'personal' means a friendship: they share their lives, joke, check in on each other. "
    "'logistics' means the thread exists to coordinate work or tasks (project partners, landlords, group "
    "organizers) with little or no personal content. Judge the relationship, not the volume of messages."
)


class Relationship(BaseModel):
    kind: Literal["personal", "logistics"]
    reason: str


@dataclass(frozen=True)
class Friendship:
    thread_id: str
    name: str
    messages: int
    first: datetime
    last: datetime
    active_months: int
    busiest_month: datetime
    hour_counts: tuple[int, ...]
    conversations: int
    started_by_owner: int


def your_people(context: Context) -> list[Card]:
    everyone = friendships(context)
    verdicts = concurrently(lambda f: is_personal(context, f), everyone)
    personal = [f for f, is_friend in zip(everyone, verdicts) if is_friend]
    top = ranked(personal, context.now)[:list_size]
    return [card(friendship, score, rank, context.now) for rank, (friendship, score) in enumerate(top, start=1)]


def friendships(context: Context) -> list[Friendship]:
    one_to_one = {"term": {"is_group": False}}
    per_thread = {"terms": {"field": "thread_id", "size": 1000}}
    message_aggs = {
        "name": {"terms": {"field": "thread_name", "size": 1}},
        "first": {"min": {"field": "timestamp"}},
        "last": {"max": {"field": "timestamp"}},
        "months": {"date_histogram": {"field": "timestamp", "calendar_interval": "month", "min_doc_count": 1}},
        "hours": {"terms": {"field": "hour", "size": 24}},
    }
    window_aggs = {"started_by_owner": {"filter": {"term": {"is_started_by_owner": True}}}}
    messages = context.search.search(
        index=context.names.messages, size=0, query=one_to_one, aggs={"threads": {**per_thread, "aggs": message_aggs}}
    )
    windows = context.search.search(
        index=context.names.windows, size=0, query=one_to_one, aggs={"threads": {**per_thread, "aggs": window_aggs}}
    )
    conversations = {bucket["key"]: bucket for bucket in windows["aggregations"]["threads"]["buckets"]}
    return [_friendship(bucket, conversations[bucket["key"]]) for bucket in messages["aggregations"]["threads"]["buckets"]]


def is_personal(context: Context, friendship: Friendship) -> bool:
    substantial = {"bool": {"filter": [{"term": {"thread_id": friendship.thread_id}}, {"range": {"message_count": {"gte": 6}}}]}}
    sample = context.search.search(
        index=context.names.windows,
        size=sampled_conversations,
        query={"function_score": {"query": substantial, "random_score": {"seed": 7, "field": "_seq_no"}}},
        source=["text"],
    )
    material = "\n\n---\n\n".join(hit["_source"]["text"] for hit in sample["hits"]["hits"])
    verdict = judged(context.llm, context.judge_model, relationship_instructions, material, Relationship)
    return verdict.kind == "personal"


def ranked(friendships: list[Friendship], now: datetime) -> list[tuple[Friendship, float]]:
    if not friendships:
        return []
    most_messages = max(f.messages for f in friendships)
    most_months = max(f.active_months for f in friendships)
    scored = [(f, _score(f, most_messages, most_months, now)) for f in friendships]
    return sorted(scored, key=lambda pair: pair[1], reverse=True)


def card(friendship: Friendship, score: float, rank: int, now: datetime) -> Card:
    first_name = friendship.name.split()[0]
    friend_share = 1 - friendship.started_by_owner / friendship.conversations
    is_quiet = (now - friendship.last).days > quiet_after_days
    body = (
        f"You've talked in {friendship.active_months} different months since {friendship.first:%B %Y}. "
        f"Your most active stretch was {friendship.busiest_month:%B %Y}."
    )
    stats = [
        ("Messages", f"{friendship.messages:,}"),
        ("Talking since", f"{friendship.first:%b %Y}"),
        ("Most active month", f"{friendship.busiest_month:%B %Y}"),
        ("Usual hours", usual_hours(friendship.hour_counts)),
    ]
    if friend_share >= one_sided_share:
        body += f" {first_name} starts most of your conversations."
        stats.append(("Who starts conversations", f"{first_name}, {friend_share:.0%} of the time"))
    if is_quiet:
        body += f" It has been quiet since {friendship.last:%B %Y}."
        stats.append(("Quiet since", f"{friendship.last:%b %Y}"))
    return Card(Kind.your_people, friendship.thread_id, friendship.name, friendship.name, body, score, rank, tuple(stats))


def usual_hours(hour_counts: tuple[int, ...], span: int = 4) -> str:
    busiest_start = max(range(24), key=lambda start: sum(hour_counts[(start + n) % 24] for n in range(span)))
    return f"{_clock(busiest_start)} – {_clock((busiest_start + span) % 24)}"


def _score(friendship: Friendship, most_messages: int, most_months: int, now: datetime) -> float:
    volume = math.log(friendship.messages) / math.log(most_messages)
    consistency = friendship.active_months / most_months
    history = volume_weight * volume + consistency_weight * consistency
    freshness = 0.5 ** (max((now - friendship.last).days, 0) / silence_half_life_days)
    return history * (0.5 + 0.5 * freshness)


def _friendship(messages: dict, conversations: dict) -> Friendship:
    months = messages["months"]["buckets"]
    busiest = max(months, key=lambda bucket: bucket["doc_count"])
    hours = {bucket["key"]: bucket["doc_count"] for bucket in messages["hours"]["buckets"]}
    return Friendship(
        thread_id=messages["key"],
        name=messages["name"]["buckets"][0]["key"],
        messages=messages["doc_count"],
        first=datetime.fromisoformat(messages["first"]["value_as_string"]),
        last=datetime.fromisoformat(messages["last"]["value_as_string"]),
        active_months=len(months),
        busiest_month=datetime.fromisoformat(busiest["key_as_string"]),
        hour_counts=tuple(hours.get(hour, 0) for hour in range(24)),
        conversations=conversations["doc_count"],
        started_by_owner=conversations["started_by_owner"]["doc_count"],
    )


def _clock(hour: int) -> str:
    return f"{hour % 12 or 12} {'PM' if hour >= 12 else 'AM'}"
