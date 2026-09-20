"""Elasticsearch indexes: one document per message, one per conversation window."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

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
    }
    windows = {
        **thread_fields,
        "start": {"type": "date"},
        "end": {"type": "date"},
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
        yield from (_action(names.messages, m.id, _message_document(m, thread, owner)) for m in thread.messages)
        yield from (_action(names.windows, w.id, _window_document(w, thread)) for w in windowed(thread))


def _action(index: str, document_id: str, source: dict) -> dict:
    return {"_index": index, "_id": document_id, "_source": source}


def _thread_fields(thread: Thread) -> dict:
    return {"thread_id": thread.id, "thread_name": thread.name, "is_group": thread.is_group}


def _message_document(message: Message, thread: Thread, owner: str) -> dict:
    return {
        **_thread_fields(thread),
        "sender": message.sender,
        "is_from_owner": message.sender == owner,
        "timestamp": message.timestamp.isoformat(),
        "hour": message.timestamp.hour,
        "text": message.text,
    }


def _window_document(window: Window, thread: Thread) -> dict:
    return {
        **_thread_fields(thread),
        "start": window.start.isoformat(),
        "end": window.end.isoformat(),
        "message_ids": list(window.message_ids),
        "message_count": len(window.message_ids),
        "text": window.text,
        "semantic": window.text,
    }
