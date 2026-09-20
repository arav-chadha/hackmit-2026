"""Splits a thread into conversation windows: runs of messages with no long silence between them."""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from insights.inbox import Message, Thread

default_gap = timedelta(hours=3)
default_max_messages = 40


@dataclass(frozen=True)
class Window:
    id: str
    thread_id: str
    start: datetime
    end: datetime
    first_sender: str
    message_ids: tuple[str, ...]
    text: str


def windowed(thread: Thread, gap: timedelta = default_gap, max_messages: int = default_max_messages) -> list[Window]:
    runs: list[list[Message]] = []
    for message in thread.messages:
        is_continuation = runs and message.timestamp - runs[-1][-1].timestamp <= gap and len(runs[-1]) < max_messages
        if is_continuation:
            runs[-1].append(message)
        else:
            runs.append([message])
    return [_window(thread.id, run) for run in runs]


def _window(thread_id: str, run: list[Message]) -> Window:
    # Keyed on the first message only, so a window that grows in a newer export keeps its id.
    window_id = hashlib.sha1(f"{thread_id}|{run[0].id}".encode()).hexdigest()[:16]
    text = "\n".join(f"{m.sender}: {m.text}" for m in run)
    return Window(window_id, thread_id, run[0].timestamp, run[-1].timestamp, run[0].sender, tuple(m.id for m in run), text)
