"""Unanswered Moments: a friend asked something that mattered, you kept talking, and never answered."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from insights.cards import Action, Card, Evidence, Kind
from insights.context import Context
from insights.inbox import Message
from insights.index import message_from_hit
from insights.judge import judged
from insights.parallel import concurrently

messages_before, messages_after = 3, 15
evidence_after = 3
least_importance = 3
most_importance = 5
list_size = 5
most_per_friend = 2

judge_instructions = (
    "You will read part of a direct-message thread. One message, marked with >>>, is a question a friend asked "
    "the account owner (shown as the owner's name in the transcript header). The owner sent nothing more in that "
    "conversation and came back later.\n\n"
    "is_answered: true if the owner responded to the substance of the question anywhere in the messages that "
    "follow, even a day late or in passing. Replying about something else does not count.\n\n"
    "importance, 1 to 5: how much the friend would still appreciate an answer today. 5 is a sincere question about "
    "the owner's life or a request for help that was dropped. 3 is a real but minor question. 1 is rhetorical, a "
    "joke, a greeting, a reaction, or logistics whose moment has passed."
)
writer_instructions = (
    "A friend asked the account owner a question that never got answered. Write the text for a card that gently "
    "surfaces it, addressed to the owner as 'you'.\n\n"
    "title: what the friend asked, under 10 words, like 'Mei asked how your interview went'. Use the friend's first name.\n"
    "body: one or two short sentences on what happened. Plain and warm, no guilt-tripping.\n"
    "draft: a message the owner could send now to pick the thread back up. Match how the owner texts in the "
    "transcript (casing, punctuation, emoji habits, length). Acknowledge the lateness lightly. Do not invent the "
    "answer to the question; the owner will fill that in. Never use em dashes."
)


class Verdict(BaseModel):
    is_answered: bool
    importance: Literal[1, 2, 3, 4, 5]
    reason: str


class Wording(BaseModel):
    title: str
    body: str
    draft: str


@dataclass(frozen=True)
class Candidate:
    friend: str
    question: Message
    before: tuple[Message, ...]
    after: tuple[Message, ...]


def unanswered(context: Context) -> list[Card]:
    kept_talking = [c for c in candidates(context) if any(m.sender == context.owner for m in c.after)]
    verdicts = concurrently(lambda c: judged(context.llm, context.judge_model, judge_instructions, transcript(c, context), Verdict), kept_talking)
    return concurrently(lambda pair: _card(context, *pair), selected(list(zip(kept_talking, verdicts))))


def candidates(context: Context) -> list[Candidate]:
    left_hanging = [
        {"term": {"is_group": False}},
        {"term": {"is_from_owner": False}},
        {"term": {"is_question": True}},
        {"term": {"has_owner_reply_in_window": False}},
    ]
    found = context.search.search(
        index=context.names.messages, size=1000, query={"bool": {"filter": left_hanging}}, sort=[{"timestamp": "asc"}]
    )
    return [_candidate(context, hit) for hit in found["hits"]["hits"]]


def transcript(candidate: Candidate, context: Context) -> str:
    header = f"Today is {context.now:%Y-%m-%d}. Thread between {context.owner} (the account owner) and {candidate.friend}."
    lines = [_line(m) for m in candidate.before] + [">>> " + _line(candidate.question)] + [_line(m) for m in candidate.after]
    return header + "\n\n" + "\n".join(lines)


def selected(verdicts: list[tuple[Candidate, Verdict]]) -> list[tuple[Candidate, Verdict]]:
    worth_surfacing = [(c, v) for c, v in verdicts if not v.is_answered and v.importance >= least_importance]
    strongest_first = sorted(worth_surfacing, key=lambda pair: pair[1].importance, reverse=True)
    chosen: list[tuple[Candidate, Verdict]] = []
    for candidate, verdict in strongest_first:
        same_friend = [c for c, _ in chosen if c.question.thread_id == candidate.question.thread_id]
        is_repeat = any(c.question.text == candidate.question.text for c in same_friend)
        if len(same_friend) < most_per_friend and not is_repeat:
            chosen.append((candidate, verdict))
    return chosen[:list_size]


def _card(context: Context, candidate: Candidate, verdict: Verdict) -> Card:
    wording = judged(context.llm, context.writer_model, writer_instructions, transcript(candidate, context), Wording)
    evidence = [Evidence(candidate.question, candidate.friend, is_key=True)]
    evidence += [Evidence(m, candidate.friend, is_key=False) for m in candidate.after[:evidence_after]]
    return Card(
        kind=Kind.unanswered,
        thread_id=candidate.question.thread_id,
        friend=candidate.friend,
        title=wording.title,
        body=wording.body,
        score=verdict.importance / most_importance,
        stats=(("Asked", f"{candidate.question.timestamp:%b} {candidate.question.timestamp.day}, {candidate.question.timestamp.year}"),),
        evidence=tuple(evidence),
        action=Action("Respond", wording.draft),
    )


def _candidate(context: Context, hit: dict) -> Candidate:
    source = hit["_source"]
    position = source["position"]
    nearby = {"range": {"position": {"gte": position - messages_before, "lte": position + messages_after}}}
    around = context.search.search(
        index=context.names.messages,
        size=messages_before + messages_after + 1,
        query={"bool": {"filter": [{"term": {"thread_id": source["thread_id"]}}, nearby]}},
        sort=[{"position": "asc"}],
    )["hits"]["hits"]
    before = tuple(message_from_hit(h) for h in around if h["_source"]["position"] < position)
    after = tuple(message_from_hit(h) for h in around if h["_source"]["position"] > position)
    return Candidate(source["thread_name"], message_from_hit(hit), before, after)


def _line(message: Message) -> str:
    return f"[{message.timestamp:%Y-%m-%d %H:%M}] {message.sender}: {message.text}"
