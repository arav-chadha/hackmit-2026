"""Elasticsearch indexes: one document per message, one per conversation window."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime

from elasticsearch import Elasticsearch, helpers

from insights.inbox import Message, Thread
from insights.windows import Window, windowed


@dataclass(frozen=True)
class IndexNames:
    prefix: str = ""

    @property
    def messages(self) -> str:
        return f"{self.prefix}messages"

    @property
    def windows(self) -> str:
        return f"{self.prefix}windows"


def mappings(inference_id: str) -> dict[str, dict]:
    thread_fields = {
        "thread_id": {"type": "keyword"},
        "thread_name": {"type": "keyword"},
        "is_group": {"type": "boolean"},
    }
    messages = {
        **thread_fields,
        "sender": {"type": "keyword"},
        "is_from_owner": {"type": "boolean"},
        "timestamp": {"type": "date"},
        "hour": {"type": "byte"},
        "text": {"type": "text"},
        "position": {"type": "integer"},
        "window_id": {"type": "keyword"},
        "is_question": {"type": "boolean"},
        "has_owner_reply_in_window": {"type": "boolean"},
    }
    windows = {
        **thread_fields,
        "start": {"type": "date"},
        "end": {"type": "date"},
        "is_started_by_owner": {"type": "boolean"},
        "message_ids": {"type": "keyword"},
        "message_count": {"type": "integer"},
        "text": {"type": "text"},
        "semantic": {"type": "semantic_text", "inference_id": inference_id},
    }
    return {"messages": {"properties": messages}, "windows": {"properties": windows}}


def recreate_indexes(client: Elasticsearch, names: IndexNames, inference_id: str) -> None:
    declared = mappings(inference_id)
    for index, mapping in ((names.messages, declared["messages"]), (names.windows, declared["windows"])):
        client.indices.delete(index=index, ignore_unavailable=True)
        client.indices.create(index=index, mappings=mapping)


def ingest(client: Elasticsearch, threads: Iterable[Thread], owner: str, names: IndexNames) -> int:
    indexed, _ = helpers.bulk(client, bulk_actions(threads, owner, names), chunk_size=500, request_timeout=120)
    client.indices.refresh(index=[names.messages, names.windows])
    return indexed


def bulk_actions(threads: Iterable[Thread], owner: str, names: IndexNames) -> Iterator[dict]:
    for thread in threads:
        windows = windowed(thread)
        yield from (_action(names.messages, m.id, source) for m, source in _message_documents(thread, windows, owner))
        yield from (_action(names.windows, w.id, _window_document(w, thread, owner)) for w in windows)


def _action(index: str, document_id: str, source: dict) -> dict:
    return {"_index": index, "_id": document_id, "_source": source}


def _thread_fields(thread: Thread) -> dict:
    return {"thread_id": thread.id, "thread_name": thread.name, "is_group": thread.is_group}


def message_from_hit(hit: dict) -> Message:
    source = hit["_source"]
    timestamp = datetime.fromisoformat(source["timestamp"])
    return Message(hit["_id"], source["thread_id"], source["sender"], timestamp, source["text"])


def _message_documents(thread: Thread, windows: list[Window], owner: str) -> Iterator[tuple[Message, dict]]:
    positioned = {message.id: (position, message) for position, message in enumerate(thread.messages)}
    for window in windows:
        members = [positioned[message_id] for message_id in window.message_ids]
        last_owner_position = max((position for position, m in members if m.sender == owner), default=-1)
        yield from (
            (m, {**_message_document(m, thread, owner), **_placement(window, position, last_owner_position)})
            for position, m in members
        )


def _placement(window: Window, position: int, last_owner_position: int) -> dict:
    return {"position": position, "window_id": window.id, "has_owner_reply_in_window": position < last_owner_position}


def _message_document(message: Message, thread: Thread, owner: str) -> dict:
    return {
        **_thread_fields(thread),
        "sender": message.sender,
        "is_from_owner": message.sender == owner,
        "timestamp": message.timestamp.isoformat(),
        "hour": message.timestamp.hour,
        "text": message.text,
        "is_question": "?" in message.text,
    }


def _window_document(window: Window, thread: Thread, owner: str) -> dict:
    return {
        **_thread_fields(thread),
        "start": window.start.isoformat(),
        "end": window.end.isoformat(),
        "is_started_by_owner": window.first_sender == owner,
        "message_ids": list(window.message_ids),
        "message_count": len(window.message_ids),
        "text": window.text,
        "semantic": window.text,
    }
