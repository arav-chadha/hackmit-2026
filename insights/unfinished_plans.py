"""Unfinished Plans: things two people kept saying they would do together and, as far as the DMs show, never did."""

from collections import defaultdict
from dataclasses import dataclass

from pydantic import BaseModel

from insights.cards import Action, Card, Evidence, Kind
from insights.context import Context
from insights.conversations import Conversations, fetch_conversations
from insights.inbox import Message
from insights.judge import judged

commitment_phrases = (
    "we should", "we need to", "we have to", "we gotta", "let's", "lets", "wanna",
    "when are we", "still haven't", "we never", "we always talk about",
)  # fmt: skip
neighbours_per_seed = 5
most_conversations_per_thread = 15
least_conversations = 2
list_size = 5
most_per_friend = 2
mentions_for_full_score = 5

judge_instructions = (
    "You will read conversations from one direct-message thread between the account owner and a friend. Each "
    "message has a reference like [m12]. Find plans to do something TOGETHER that came up and, as far as these "
    "messages show, never happened.\n\n"
    "For each plan: name is a short noun phrase ('the pottery class on Elm St'). The same plan is often worded "
    "differently each time ('the noodle place', 'that ramen spot'); treat those as one plan. mention_refs must "
    "cover EVERY conversation in which the plan comes up, including ones that only lament not having done it: go "
    "through the conversations one by one, and for each that touches the plan add the reference of the message "
    "that says it most clearly. A plan that comes up in four conversations has four references. "
    "did_it_happen is true if any later message shows they actually did it.\n\n"
    "Ignore things only one person wants, one person's solo intentions, and work logistics. Return an empty list "
    "if there are none."
)
writer_instructions = (
    "Two friends kept bringing up a plan in their DMs and it does not look like they ever did it. Write the text "
    "for a card that nudges the account owner, addressed as 'you'.\n\n"
    "title: a punchy noun phrase naming the plan and the friend's first name, like 'The ramen place with Sarah'.\n"
    "body: how many times it came up, and that it doesn't look like it happened. We can only see the DMs, so never "
    "state as fact that they didn't do it. One or two short sentences, warm, no guilt-tripping.\n"
    "draft: a message the owner could send now to make it happen. Match how the owner texts in the transcript "
    "(casing, punctuation, emoji habits, length). If the messages show the friend moved away, fit the suggestion "
    "to that. Never use em dashes."
)


class Plan(BaseModel):
    name: str
    mention_refs: list[str]
    did_it_happen: bool


class Plans(BaseModel):
    plans: list[Plan]


class Wording(BaseModel):
    title: str
    body: str
    draft: str


@dataclass(frozen=True)
class Unfinished:
    name: str
    conversations: Conversations
    mentions: tuple[Message, ...]


def unfinished_plans(context: Context) -> list[Card]:
    found = [plan for conversations in plan_conversations(context) for plan in _unfinished_in(context, conversations)]
    most_mentioned_first = sorted(found, key=lambda plan: len(plan.mentions), reverse=True)
    return [_card(context, plan) for plan in capped(most_mentioned_first)]


def plan_conversations(context: Context) -> list[Conversations]:
    seeds = context.search.search(
        index=context.names.messages,
        size=1000,
        query={
            "bool": {
                "filter": [{"term": {"is_group": False}}],
                "should": [{"match_phrase": {"text": phrase}} for phrase in commitment_phrases],
                "minimum_should_match": 1,
            }
        },
    )["hits"]["hits"]
    window_ids: dict[str, dict[str, None]] = defaultdict(dict)
    for seed in seeds:
        source = seed["_source"]
        related = [source["window_id"], *_neighbours(context, source["thread_id"], source["text"])]
        window_ids[source["thread_id"]].update(dict.fromkeys(related))
    return [fetch_conversations(context, thread_id, list(ids)[:most_conversations_per_thread]) for thread_id, ids in window_ids.items()]


def unfinished(plans: list[Plan], conversations: Conversations) -> list[Unfinished]:
    kept = []
    for plan in plans:
        known = [entry for ref in plan.mention_refs if (entry := conversations.lookup(ref))]
        one_per_conversation = {window_id: message for message, window_id in known}
        if not plan.did_it_happen and len(one_per_conversation) >= least_conversations:
            kept.append(Unfinished(plan.name, conversations, tuple(one_per_conversation.values())))
    return kept


def capped(plans: list[Unfinished]) -> list[Unfinished]:
    chosen: list[Unfinished] = []
    for plan in plans:
        same_friend = sum(other.conversations.thread_id == plan.conversations.thread_id for other in chosen)
        if same_friend < most_per_friend:
            chosen.append(plan)
    return chosen[:list_size]


def _unfinished_in(context: Context, conversations: Conversations) -> list[Unfinished]:
    verdict = judged(context.llm, context.judge_model, judge_instructions, conversations.transcript(), Plans)
    return unfinished(verdict.plans, conversations)


def _card(context: Context, plan: Unfinished) -> Card:
    mentions = sorted(plan.mentions, key=lambda message: message.timestamp)
    material = (
        f"Today is {context.now:%Y-%m-%d}. The account owner is {context.owner}; the friend is {plan.conversations.friend}.\n"
        f"The plan: {plan.name}. It came up in {len(mentions)} separate conversations.\n\n{plan.conversations.transcript()}"
    )
    wording = judged(context.llm, context.writer_model, writer_instructions, material, Wording)
    return Card(
        kind=Kind.unfinished_plans,
        thread_id=plan.conversations.thread_id,
        friend=plan.conversations.friend,
        title=wording.title,
        body=wording.body,
        score=min(1.0, len(mentions) / mentions_for_full_score),
        stats=(("Times mentioned", str(len(mentions))), ("First mentioned", f"{mentions[0].timestamp:%b %Y}")),
        evidence=tuple(Evidence(message, plan.conversations.friend, is_key=True) for message in mentions),
        action=Action("Make It Happen", wording.draft),
    )


def _neighbours(context: Context, thread_id: str, seed_text: str) -> list[str]:
    similar = {"bool": {"must": [{"semantic": {"field": "semantic", "query": seed_text}}], "filter": [{"term": {"thread_id": thread_id}}]}}
    hits = context.search.search(index=context.names.windows, size=neighbours_per_seed, query=similar, source=False)
    return [hit["_id"] for hit in hits["hits"]["hits"]]
