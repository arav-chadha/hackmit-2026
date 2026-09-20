"""You Both Wanted This: a friend and the owner each said they want the same thing, in different conversations."""

from dataclasses import dataclass

from pydantic import BaseModel

from insights.cards import Action, Card, Evidence, Kind
from insights.context import Context
from insights.inbox import Message
from insights.index import message_from_hit
from insights.judge import judged

wish_phrases = (
    "want to try", "wanna try", "wanting to try", "been wanting", "always wanted", "i want to",
    "would love to", "i'd love to", "dying to", "on my bucket list", "someday", "sometime",
)  # fmt: skip
matches_per_wish = 3
list_size = 5
most_per_friend = 2
card_score = 0.9

judge_instructions = (
    "Two people each said they want to do something, in separate conversations. Decide whether they want the SAME "
    "activity or a clear equivalent: 'rock climbing' and 'bouldering' match; 'a pottery class' and 'a painting "
    "class' do not; 'run a marathon' and 'get into running' do not. If either message is not really a wish to do "
    "something (a joke, a figure of speech), they do not match. activity is a short name for the shared activity, "
    "lowercase, like 'rock climbing'."
)
writer_instructions = (
    "A friend and the account owner each said they want to do the same thing, in separate conversations, and as far "
    "as their DMs show it has never come up between the two of them. Write the text for a card addressed to the "
    "owner as 'you'.\n\n"
    "title: like 'You both want to try rock climbing'.\n"
    "body: who said it when (month and year), and if the owner said it to someone else, say so by first name. One "
    "or two short sentences. We only see DMs, so say it hasn't come up between them, not that the friend doesn't know.\n"
    "draft: a message the owner could send the friend to suggest doing it together. Match how the owner texts "
    "(casing, punctuation, emoji habits, length). Never use em dashes."
)


class Match(BaseModel):
    is_same_activity: bool
    activity: str


class Wording(BaseModel):
    title: str
    body: str
    draft: str


@dataclass(frozen=True)
class Wish:
    message: Message
    thread_name: str
    window_id: str


@dataclass(frozen=True)
class Pair:
    theirs: Wish
    yours: Wish


def both_wanted(context: Context) -> list[Card]:
    wishes = _wishes(context)
    yours = [wish for wish in wishes if wish.message.sender == context.owner]
    theirs = [wish for wish in wishes if wish.message.sender != context.owner]
    candidates = [pair for wish in theirs for pair in pairs(wish, yours, _nearest_windows(context, wish, yours))]
    confirmed = [(pair, match.activity) for pair in candidates if (match := _match(context, pair)).is_same_activity]
    fresh = [(pair, activity) for pair, activity in confirmed if not _has_come_up(context, pair, activity)]
    return [_card(context, pair, activity) for pair, activity in capped(fresh)]


def pairs(theirs: Wish, yours: list[Wish], nearest_window_ids: list[str]) -> list[Pair]:
    elsewhere = [window_id for window_id in nearest_window_ids if window_id != theirs.window_id]
    return [Pair(theirs, wish) for window_id in elsewhere for wish in yours if wish.window_id == window_id]


def capped(found: list[tuple[Pair, str]]) -> list[tuple[Pair, str]]:
    chosen: list[tuple[Pair, str]] = []
    for pair, activity in found:
        same_friend = [a for p, a in chosen if p.theirs.message.thread_id == pair.theirs.message.thread_id]
        if activity not in same_friend and len(same_friend) < most_per_friend:
            chosen.append((pair, activity))
    return chosen[:list_size]


def evidence(pair: Pair) -> tuple[Evidence, Evidence]:
    return (
        Evidence(pair.theirs.message, pair.theirs.thread_name, is_key=True),
        Evidence(pair.yours.message, pair.yours.thread_name, is_key=True),
    )


def _wishes(context: Context) -> list[Wish]:
    query = {
        "bool": {
            "filter": [{"term": {"is_group": False}}],
            "should": [{"match_phrase": {"text": phrase}} for phrase in wish_phrases],
            "minimum_should_match": 1,
        }
    }
    hits = context.search.search(index=context.names.messages, size=1000, query=query, sort=[{"timestamp": "asc"}])
    return [Wish(message_from_hit(h), h["_source"]["thread_name"], h["_source"]["window_id"]) for h in hits["hits"]["hits"]]


def _nearest_windows(context: Context, theirs: Wish, yours: list[Wish]) -> list[str]:
    your_windows = sorted({wish.window_id for wish in yours})
    if not your_windows:
        return []
    similar = {"bool": {"must": [{"semantic": {"field": "semantic", "query": theirs.message.text}}], "filter": [{"ids": {"values": your_windows}}]}}
    hits = context.search.search(index=context.names.windows, size=matches_per_wish, query=similar, source=False)
    return [hit["_id"] for hit in hits["hits"]["hits"]]


def _match(context: Context, pair: Pair) -> Match:
    return judged(context.llm, context.judge_model, judge_instructions, _material(context, pair), Match)


def _has_come_up(context: Context, pair: Pair, activity: str) -> bool:
    between_them = [
        {"term": {"thread_id": pair.theirs.message.thread_id}},
        {"term": {"is_from_owner": True}},
        {"match": {"text": {"query": activity, "operator": "and"}}},
    ]
    return context.search.count(index=context.names.messages, query={"bool": {"filter": between_them}})["count"] > 0


def _card(context: Context, pair: Pair, activity: str) -> Card:
    material = f"Today is {context.now:%Y-%m-%d}. Shared activity: {activity}.\n\n{_material(context, pair)}"
    wording = judged(context.llm, context.writer_model, writer_instructions, material, Wording)
    return Card(
        kind=Kind.both_wanted,
        thread_id=pair.theirs.message.thread_id,
        friend=pair.theirs.thread_name,
        title=wording.title,
        body=wording.body,
        score=card_score,
        evidence=evidence(pair),
        action=Action("Do It Together", wording.draft),
    )


def _material(context: Context, pair: Pair) -> str:
    theirs, yours = pair.theirs, pair.yours
    return (
        f"{theirs.message.sender}, in their chat with {context.owner} (the account owner), on {theirs.message.timestamp:%Y-%m-%d}:\n"
        f"  {theirs.message.text}\n\n"
        f"{context.owner}, in their chat with {yours.thread_name}, on {yours.message.timestamp:%Y-%m-%d}:\n"
        f"  {yours.message.text}"
    )
