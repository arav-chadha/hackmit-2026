"""Friendship Recap: one summary card for each of the closest friendships, built from the other insights."""

from pydantic import BaseModel

from insights.cards import Action, Card, Kind
from insights.context import Context
from insights.judge import judged
from insights.parallel import concurrently
from insights.your_people import Friendship, friendships, usual_hours

list_size = 3
distinctive_words = 20
sampled_conversations = 5
most_standout_messages = 3
score_share = 0.75
counted_kinds = (
    (Kind.unfinished_plans, "Unfinished plans"),
    (Kind.unanswered, "Unanswered questions"),
    (Kind.memory_lane, "Memories worth revisiting"),
    (Kind.reconnect, "Things you've drifted from"),
)

writer_instructions = (
    "You will see facts about one friendship from the account owner's direct messages: numbers, the words most "
    "distinctive of this chat compared with the owner's other chats, and a few sampled conversations.\n\n"
    "top_topic: the broad subject that runs through the most of their conversations, one to three words, like "
    "'Hackathons' or 'Design school'. Distinctive words can be inflated by one repeated joke, so never pick a "
    "single food, catchphrase or one-off event.\n"
    "body: one sentence capturing the character of the friendship from the facts, addressed to the owner as 'you', "
    "like 'Four years, mostly after midnight, mostly about hackathons.' No advice. Never use em dashes."
)


class Summary(BaseModel):
    top_topic: str
    body: str


def recap(context: Context, cards: list[Card]) -> list[Card]:
    closest = sorted((card for card in cards if card.kind == Kind.your_people), key=lambda card: card.rank or 0)[:list_size]
    by_thread = {friendship.thread_id: friendship for friendship in friendships(context)}
    return concurrently(lambda ranked: _recap(context, by_thread[ranked.thread_id], ranked, cards), closest)


def recap_card(friendship: Friendship, ranked: Card, summary: Summary, cards: list[Card]) -> Card:
    about_them = [card for card in cards if card.thread_id == friendship.thread_id]
    counts = [(label, sum(card.kind == kind for card in about_them)) for kind, label in counted_kinds]
    memories = [item for card in about_them if card.kind == Kind.memory_lane for item in card.evidence if item.is_key]
    stats = [
        ("Messages", f"{friendship.messages:,}"),
        ("Most active month", f"{friendship.busiest_month:%B %Y}"),
        ("Top topic", summary.top_topic),
        ("Most active time", usual_hours(friendship.hour_counts)),
        *((label, str(count)) for label, count in counts if count),
    ]
    return Card(
        kind=Kind.recap,
        thread_id=friendship.thread_id,
        friend=friendship.name,
        title=f"You + {friendship.name.split()[0]}",
        body=summary.body,
        score=ranked.score * score_share,
        stats=tuple(stats),
        evidence=tuple(memories[:most_standout_messages]),
        action=Action("Share Recap"),
    )


def _recap(context: Context, friendship: Friendship, ranked: Card, cards: list[Card]) -> Card:
    summary = judged(context.llm, context.writer_model, writer_instructions, _material(context, friendship), Summary)
    return recap_card(friendship, ranked, summary, cards)


def _material(context: Context, friendship: Friendship) -> str:
    in_thread = {"term": {"thread_id": friendship.thread_id}}
    distinctive = {"significant_text": {"field": "text", "size": distinctive_words, "filter_duplicate_text": False}}
    words = context.search.search(index=context.names.messages, size=0, query=in_thread, aggs={"words": distinctive})
    sample = context.search.search(
        index=context.names.windows,
        size=sampled_conversations,
        query={"function_score": {"query": in_thread, "random_score": {"seed": 11, "field": "_seq_no"}}},
        source=["text"],
    )
    return (
        f"The account owner is {context.owner}; the friend is {friendship.name}. Today is {context.now:%Y-%m-%d}.\n"
        f"{friendship.messages:,} messages since {friendship.first:%B %Y}, in {friendship.active_months} different months. "
        f"Last message {friendship.last:%B %Y}. Most active hours: {usual_hours(friendship.hour_counts)}.\n"
        f"Distinctive words: {', '.join(bucket['key'] for bucket in words['aggregations']['words']['buckets'])}\n\n"
        + "\n\n---\n\n".join(hit["_source"]["text"] for hit in sample["hits"]["hits"])
    )
