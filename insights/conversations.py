"""Conversations fetched from the index for an LLM to read, with a short reference on every message."""

from dataclasses import dataclass

from insights.context import Context
from insights.inbox import Message
from insights.index import message_from_hit


@dataclass(frozen=True)
class Conversations:
    friend: str
    thread_id: str
    by_ref: dict[str, tuple[Message, str]]

    def transcript(self) -> str:
        lines: list[str] = []
        previous_window = None
        for ref, (message, window_id) in self.by_ref.items():
            if window_id != previous_window:
                lines.append(f"\n--- conversation on {message.timestamp:%Y-%m-%d} ---")
            lines.append(f"[{ref}] {message.sender}: {message.text}")
            previous_window = window_id
        return "\n".join(lines).strip()

    def lookup(self, ref: str) -> tuple[Message, str] | None:
        # Judges copy references back with or without the brackets they were shown in.
        return self.by_ref.get(ref.strip().strip("[]"))

    def between(self, first_ref: str, last_ref: str) -> list[Message]:
        first, last = self.lookup(first_ref), self.lookup(last_ref)
        if first is None or last is None:
            return []
        messages = [message for message, _ in self.by_ref.values()]
        return messages[messages.index(first[0]) : messages.index(last[0]) + 1]


def fetch_conversations(context: Context, thread_id: str, window_ids: list[str]) -> Conversations:
    hits = context.search.search(
        index=context.names.messages,
        size=2000,
        query={"bool": {"filter": [{"term": {"thread_id": thread_id}}, {"terms": {"window_id": window_ids}}]}},
        sort=[{"position": "asc"}],
    )["hits"]["hits"]
    by_ref = {f"m{number}": (message_from_hit(hit), hit["_source"]["window_id"]) for number, hit in enumerate(hits, start=1)}
    return Conversations(hits[0]["_source"]["thread_name"], thread_id, by_ref)
