"""Cards are the output of the backend. The JSON shape is fixed by contract/CARDS_CONTRACT.md."""

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

from insights.inbox import Message


class Kind(StrEnum):
    your_people = "your_people"
    memory_lane = "memory_lane"
    reconnect = "reconnect"
    unfinished_plans = "unfinished_plans"
    unanswered = "unanswered"
    both_wanted = "both_wanted"
    recap = "recap"


@dataclass(frozen=True)
class Evidence:
    message: Message
    thread_name: str
    is_key: bool


@dataclass(frozen=True)
class Action:
    label: str
    draft: str | None = None


@dataclass(frozen=True)
class Hook:
    text: str
    source: str
    url: str
    date: str


@dataclass(frozen=True)
class Card:
    kind: Kind
    thread_id: str
    friend: str
    title: str
    body: str
    score: float
    rank: int | None = None
    stats: tuple[tuple[str, str], ...] = ()
    evidence: tuple[Evidence, ...] = ()
    action: Action | None = None
    context: Hook | None = None


def document(cards: Iterable[Card], owner: str, generated_at: datetime) -> dict:
    return {
        "generatedAt": _iso(generated_at),
        "owner": owner,
        "cards": [_card(card, owner) for card in cards],
    }


def write_cards(cards: Iterable[Card], owner: str, path: Path) -> None:
    content = document(cards, owner, datetime.now(timezone.utc))
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")


def _card(card: Card, owner: str) -> dict:
    evidence = sorted(card.evidence, key=lambda item: item.message.timestamp)
    return {
        "id": _card_id(card, evidence),
        "kind": card.kind.value,
        "score": round(card.score, 2),
        "rank": card.rank,
        "friend": {"name": card.friend, "threadId": card.thread_id},
        "title": card.title,
        "body": card.body,
        "stats": [{"label": label, "value": value} for label, value in card.stats],
        "evidence": [_evidence(item, owner) for item in evidence],
        "action": {"label": card.action.label, "draft": card.action.draft} if card.action else None,
        "context": asdict(card.context) if card.context else None,
    }


def _evidence(item: Evidence, owner: str) -> dict:
    message = item.message
    return {
        "id": message.id,
        "sender": message.sender,
        "isFromOwner": message.sender == owner,
        "isKey": item.is_key,
        "threadName": item.thread_name,
        "timestamp": _iso(message.timestamp),
        "text": message.text,
    }


def _card_id(card: Card, evidence: list[Evidence]) -> str:
    # Built from what the card is about, never from wording or time of generation,
    # so the frontend's dismissed/seen state survives a rerun.
    parts = [card.kind.value, card.thread_id, *(item.message.id for item in evidence)]
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:8]


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
