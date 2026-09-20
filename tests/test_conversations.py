from datetime import datetime, timezone

from insights.inbox import Message
from insights.conversations import Conversations


def said(ref: int, sender: str, day: str, text: str) -> Message:
    return Message(f"id{ref}", "mei_1", sender, datetime.fromisoformat(day).replace(tzinfo=timezone.utc), text)


CONVERSATIONS = Conversations(
    friend="Mei Tanaka",
    thread_id="mei_1",
    by_ref={
        "m1": (said(1, "Mei Tanaka", "2025-02-08", "we should do that pottery class on elm st"), "w1"),
        "m2": (said(2, "you", "2025-02-08", "omg yes"), "w1"),
        "m3": (said(3, "you", "2025-04-21", "ok we actually need to do the pottery thing soon"), "w2"),
        "m4": (said(4, "Mei Tanaka", "2025-08-30", "still thinking about that ceramics class lol"), "w3"),
    },
)


def test_transcript_groups_lines_by_conversation_with_refs():
    assert CONVERSATIONS.transcript() == (
        "--- conversation on 2025-02-08 ---\n"
        "[m1] Mei Tanaka: we should do that pottery class on elm st\n"
        "[m2] you: omg yes\n"
        "\n--- conversation on 2025-04-21 ---\n"
        "[m3] you: ok we actually need to do the pottery thing soon\n"
        "\n--- conversation on 2025-08-30 ---\n"
        "[m4] Mei Tanaka: still thinking about that ceramics class lol"
    )


def test_between_returns_the_messages_from_one_reference_to_another():
    assert [m.id for m in CONVERSATIONS.between("m2", "m4")] == ["id2", "id3", "id4"]


def test_references_are_understood_with_or_without_brackets():
    assert CONVERSATIONS.lookup("[m3]") == CONVERSATIONS.lookup("m3") == CONVERSATIONS.by_ref["m3"]
    assert [m.id for m in CONVERSATIONS.between("[m2]", " m3 ")] == ["id2", "id3"]


def test_between_with_a_reference_that_does_not_exist_is_empty():
    assert CONVERSATIONS.between("m2", "m99") == []
