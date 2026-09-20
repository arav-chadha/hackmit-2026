from datetime import datetime, timezone

from insights.inbox import Message
from insights.unfinished_plans import Conversations, Plan, Unfinished, capped, unfinished


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


def test_a_plan_raised_in_several_conversations_is_kept_with_its_mentions():
    (plan,) = unfinished([Plan(name="the pottery class", mention_refs=["m1", "m3", "m4"], did_it_happen=False)], CONVERSATIONS)
    assert (plan.name, [m.id for m in plan.mentions]) == ("the pottery class", ["id1", "id3", "id4"])


def test_a_plan_that_happened_is_dropped():
    assert unfinished([Plan(name="tacos", mention_refs=["m1", "m3"], did_it_happen=True)], CONVERSATIONS) == []


def test_two_mentions_in_the_same_conversation_are_one_mention():
    assert unfinished([Plan(name="the pottery class", mention_refs=["m1", "m2"], did_it_happen=False)], CONVERSATIONS) == []


def test_references_the_judge_made_up_are_ignored():
    assert unfinished([Plan(name="the pottery class", mention_refs=["m1", "m99"], did_it_happen=False)], CONVERSATIONS) == []


def test_one_friend_cannot_fill_the_list():
    plans = [Unfinished(f"plan {n}", CONVERSATIONS, ()) for n in range(4)]
    assert [plan.name for plan in capped(plans)] == ["plan 0", "plan 1"]
