"""Memory Lane: funny or warm conversations from long enough ago to have been forgotten."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from insights.cards import Action, Card, Evidence, Kind
from insights.context import Context
from insights.conversations import Conversations, fetch_conversations
from insights.inbox import Message
from insights.judge import judged
from insights.parallel import concurrently

least_age = "now-6M"
least_messages = 12
most_candidates = 25
least_rating = 4
most_rating = 5
most_excerpt_messages = 8
list_size = 5
most_per_friend = 2

judge_instructions = (
    "You will read one conversation between the account owner and a friend. Each message has a reference like "
    "[m12]. Rate how much the two of them would enjoy being reminded of it years later.\n\n"
    "rating, 1 to 5: 5 is a genuinely funny, warm or exciting shared moment with a story to it (something "
    "happened, a ridiculous plan was hatched, a win was celebrated). 3 is pleasant everyday chat. 1 is logistics, "
    "small talk or a conversation that is mostly about making plans.\n\n"
    f"excerpt_first_ref and excerpt_last_ref bound the best consecutive stretch that works on its own, including "
    f"any setup the punchline needs. It must be {most_excerpt_messages} messages or fewer: count them. Do not return "
    "the whole conversation. highlight_refs are the two or three best lines, all inside that stretch."
)
writer_instructions = (
    "You will read an old conversation between the account owner and a friend that is worth remembering. Write the "
    "text for a card addressed to the owner as 'you'.\n\n"
    "title: a short name for the memory, like 'The 3 AM road trip plan'. No friend name needed.\n"
    "body: one or two sentences starting from 'Remember when', specific to what actually happened. Always second "
    "person: the owner is 'you', the friend is their first name. Never 'I', 'me' or 'we'.\n"
    "draft: a message the owner could send the friend now to share the memory. Match how the owner texts in the "
    "conversation (casing, punctuation, emoji habits, length). Never use em dashes."
)


class Rating(BaseModel):
    rating: Literal[1, 2, 3, 4, 5]
    excerpt_first_ref: str
    excerpt_last_ref: str
    highlight_refs: list[str]


class Wording(BaseModel):
    title: str
    body: str
    draft: str


@dataclass(frozen=True)
class Memory:
    conversation: Conversations
    rating: int
    excerpt: tuple[Message, ...]
    highlight_ids: frozenset[str]


def memory_lane(context: Context) -> list[Card]:
    conversations = old_long_conversations(context)
    ratings = concurrently(lambda conversation: _rating(context, conversation), conversations)
    memories = [memory(conversation, rating) for conversation, rating in zip(conversations, ratings)]
    best_first = sorted(memories, key=lambda found: found.rating, reverse=True)
    return concurrently(lambda found: _card(context, found), capped(best_first))


def old_long_conversations(context: Context) -> list[Conversations]:
    old_and_long = [
        {"term": {"is_group": False}},
        {"range": {"end": {"lt": least_age}}},
        {"range": {"message_count": {"gte": least_messages}}},
    ]
    hits = context.search.search(
        index=context.names.windows,
        size=most_candidates,
        query={"bool": {"filter": old_and_long}},
        sort=[{"message_count": "desc"}, {"start": "asc"}],
        source=["thread_id"],
    )["hits"]["hits"]
    return [fetch_conversations(context, hit["_source"]["thread_id"], [hit["_id"]]) for hit in hits]


def memory(conversation: Conversations, rating: Rating) -> Memory:
    everything = [message for message, _ in conversation.by_ref.values()]
    excerpt = conversation.between(rating.excerpt_first_ref, rating.excerpt_last_ref) or everything
    found = [conversation.lookup(ref) for ref in rating.highlight_refs]
    highlights = frozenset(entry[0].id for entry in found if entry)
    return Memory(conversation, rating.rating, tuple(_richest_stretch(excerpt, highlights)), highlights)


def _richest_stretch(excerpt: list[Message], highlight_ids: frozenset[str]) -> list[Message]:
    # The judge sometimes returns more than it was asked for. Keep the stretch holding the most
    # highlights, since cutting from the front loses the punchline.
    starts = range(max(1, len(excerpt) - most_excerpt_messages + 1))
    stretches = [excerpt[start : start + most_excerpt_messages] for start in starts]
    return max(stretches, key=lambda stretch: sum(message.id in highlight_ids for message in stretch))


def capped(memories: list[Memory]) -> list[Memory]:
    chosen: list[Memory] = []
    for found in memories:
        same_friend = sum(other.conversation.thread_id == found.conversation.thread_id for other in chosen)
        if found.rating >= least_rating and same_friend < most_per_friend:
            chosen.append(found)
    return chosen[:list_size]


def _rating(context: Context, conversation: Conversations) -> Rating:
    return judged(context.llm, context.judge_model, judge_instructions, conversation.transcript(), Rating)


def _card(context: Context, found: Memory) -> Card:
    conversation = found.conversation
    material = f"The account owner is {context.owner}; the friend is {conversation.friend}.\n\n{conversation.transcript()}"
    wording = judged(context.llm, context.writer_model, writer_instructions, material, Wording)
    happened = found.excerpt[0].timestamp
    return Card(
        kind=Kind.memory_lane,
        thread_id=conversation.thread_id,
        friend=conversation.friend,
        title=wording.title,
        body=wording.body,
        score=found.rating / most_rating,
        stats=(("When", f"{happened:%B} {happened.day}, {happened.year}"),),
        evidence=tuple(Evidence(m, conversation.friend, is_key=m.id in found.highlight_ids) for m in found.excerpt),
        action=Action("Send this memory", wording.draft),
    )
