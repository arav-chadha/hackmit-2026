"""Reconnect: something two people used to talk about all the time, which faded while they kept talking."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from insights.cards import Action, Card, Evidence, Kind
from insights.context import Context
from insights.conversations import Conversations
from insights.inbox import Message
from insights.index import message_from_hit
from insights.judge import judged

faded_for = timedelta(days=183)
least_messages = 10
least_conversations = 3
most_words = 25
sampled_messages = 30
evidence_messages = 3
least_strength = 4
most_strength = 5
list_size = 5
most_per_friend = 2

judge_instructions = (
    "You will see words that two friends used often in their direct messages and then stopped using, even though "
    "they kept talking, followed by sample messages containing those words. Each message has a reference like [m12].\n\n"
    "Group the words into topics, merging anything that belongs to a larger topic into it: a character, place or "
    "item inside a game is part of the game, not its own topic. For each topic: name is what it was, like "
    "'Minecraft' or 'the NYT Mini crossword'. words are the listed words that belong to it. is_shared_interest is "
    "true only for something the two of them did or enjoyed TOGETHER: a game, a hobby, a show, a ritual, a running "
    "joke. It is false for classes, jobs, logistics, one person's own projects, and words that are just noise.\n\n"
    "strength, 1 to 5: 5 is a real shared activity they clearly loved and could start again tomorrow. 3 is a "
    "recurring bit or catchphrase with nothing to actually go and do. 1 is incidental. "
    "evidence_refs are the three most vivid sample messages about the topic."
)
writer_instructions = (
    "Two friends used to share something and it quietly dropped out of their conversations while they kept "
    "talking. Write the text for a card addressed to the account owner as 'you'.\n\n"
    "title: like 'You and John used to talk about Minecraft all the time'. Use the friend's first name.\n"
    "body: one short sentence on how long it has been, using the numbers given. Warm, not guilt-tripping.\n"
    "draft: a message the owner could send now to bring it back, referring to a specific detail from the samples. "
    "Match how the owner texts in the samples (casing, punctuation, emoji habits, length). Never use em dashes."
)


class Topic(BaseModel):
    name: str
    words: list[str]
    is_shared_interest: bool
    strength: Literal[1, 2, 3, 4, 5]
    evidence_refs: list[str]


class Topics(BaseModel):
    topics: list[Topic]


class Wording(BaseModel):
    title: str
    body: str
    draft: str


@dataclass(frozen=True)
class Word:
    text: str
    conversations: int
    mentions_near_the_end: int


@dataclass(frozen=True)
class Faded:
    name: str
    samples: Conversations
    evidence: tuple[Message, ...]
    strength: int
    mentions: int
    last_mentioned: datetime


def reconnect(context: Context) -> list[Card]:
    found = [topic for thread_id, last in _threads(context) for topic in _faded_in(context, thread_id, last)]
    strongest_first = sorted(found, key=lambda topic: (topic.strength, topic.mentions), reverse=True)
    return [_card(context, topic) for topic in capped(strongest_first)]


def faded_words(words: list[Word]) -> list[str]:
    return [w.text for w in words if w.mentions_near_the_end == 0 and w.conversations >= least_conversations]


def shared_interests(topics: list[Topic], allowed_words: list[str]) -> list[tuple[Topic, list[str]]]:
    checked = [(topic, [word for word in topic.words if word in allowed_words]) for topic in topics]
    return [(topic, words) for topic, words in checked if topic.is_shared_interest and topic.strength >= least_strength and words]


def capped(topics: list[Faded]) -> list[Faded]:
    chosen: list[Faded] = []
    for topic in topics:
        same_friend = sum(other.samples.thread_id == topic.samples.thread_id for other in chosen)
        if same_friend < most_per_friend:
            chosen.append(topic)
    return chosen[:list_size]


def _threads(context: Context) -> list[tuple[str, datetime]]:
    per_thread = {"terms": {"field": "thread_id", "size": 1000}, "aggs": {"last": {"max": {"field": "timestamp"}}}}
    found = context.search.search(index=context.names.messages, size=0, query={"term": {"is_group": False}}, aggs={"threads": per_thread})
    buckets = found["aggregations"]["threads"]["buckets"]
    return [(bucket["key"], datetime.fromisoformat(bucket["last"]["value_as_string"])) for bucket in buckets]


def _faded_in(context: Context, thread_id: str, thread_last: datetime) -> list[Faded]:
    words = faded_words(_distinctive_words(context, thread_id, thread_last - faded_for))
    if not words:
        return []
    samples = _samples(context, thread_id, words)
    material = f"Words that faded: {', '.join(words)}\n\nSample messages:\n{samples.transcript()}"
    verdict = judged(context.llm, context.judge_model, judge_instructions, material, Topics)
    return [_faded(context, topic, topic_words, samples) for topic, topic_words in shared_interests(verdict.topics, words)]


def _distinctive_words(context: Context, thread_id: str, cutoff: datetime) -> list[Word]:
    in_thread = {"term": {"thread_id": thread_id}}
    early = {"bool": {"filter": [in_thread, {"range": {"timestamp": {"lt": cutoff.isoformat()}}}]}}
    distinctive = {"significant_text": {"field": "text", "size": most_words, "min_doc_count": least_messages, "filter_duplicate_text": False}}
    found = context.search.search(index=context.names.messages, size=0, query=early, aggs={"words": distinctive})
    texts = [bucket["key"] for bucket in found["aggregations"]["words"]["buckets"]]
    if not texts:
        return []
    per_word = {
        text: {
            "filter": {"match": {"text": text}},
            "aggs": {
                "conversations": {"cardinality": {"field": "window_id"}},
                "near_the_end": {"filter": {"range": {"timestamp": {"gte": cutoff.isoformat()}}}},
            },
        }
        for text in texts
    }
    detail = context.search.search(index=context.names.messages, size=0, query=in_thread, aggs=per_word)["aggregations"]
    return [Word(text, detail[text]["conversations"]["value"], detail[text]["near_the_end"]["doc_count"]) for text in texts]


def _samples(context: Context, thread_id: str, words: list[str]) -> Conversations:
    about_them = {"bool": {"filter": [{"term": {"thread_id": thread_id}}, {"match": {"text": " ".join(words)}}]}}
    hits = context.search.search(
        index=context.names.messages,
        size=sampled_messages,
        query={"function_score": {"query": about_them, "random_score": {"seed": 7, "field": "_seq_no"}}},
    )["hits"]["hits"]
    in_order = sorted(hits, key=lambda hit: hit["_source"]["position"])
    by_ref = {f"m{number}": (message_from_hit(hit), hit["_source"]["window_id"]) for number, hit in enumerate(in_order, start=1)}
    return Conversations(in_order[0]["_source"]["thread_name"], thread_id, by_ref)


def _faded(context: Context, topic: Topic, words: list[str], samples: Conversations) -> Faded:
    about_topic = {"bool": {"filter": [{"term": {"thread_id": samples.thread_id}}, {"match": {"text": " ".join(words)}}]}}
    found = context.search.search(index=context.names.messages, size=0, query=about_topic, aggs={"last": {"max": {"field": "timestamp"}}}, track_total_hits=True)
    evidence = [entry[0] for ref in topic.evidence_refs if (entry := samples.lookup(ref))]
    last_mentioned = datetime.fromisoformat(found["aggregations"]["last"]["value_as_string"])
    mentions = found["hits"]["total"]["value"]
    return Faded(topic.name, samples, tuple(evidence[:evidence_messages]), topic.strength, mentions, last_mentioned)


def _card(context: Context, topic: Faded) -> Card:
    months = (context.now - topic.last_mentioned).days // 30
    material = (
        f"The account owner is {context.owner}; the friend is {topic.samples.friend}. The topic: {topic.name}.\n"
        f"It came up in {topic.mentions} messages and was last mentioned in {topic.last_mentioned:%B %Y}, {months} months ago.\n\n"
        f"Sample messages:\n{topic.samples.transcript()}"
    )
    wording = judged(context.llm, context.writer_model, writer_instructions, material, Wording)
    return Card(
        kind=Kind.reconnect,
        thread_id=topic.samples.thread_id,
        friend=topic.samples.friend,
        title=wording.title,
        body=wording.body,
        score=topic.strength / most_strength,
        stats=(("Mentions", str(topic.mentions)), ("Last mentioned", f"{topic.last_mentioned:%b %Y}")),
        evidence=tuple(Evidence(message, topic.samples.friend, is_key=True) for message in topic.evidence),
        action=Action("Reconnect", wording.draft),
    )
