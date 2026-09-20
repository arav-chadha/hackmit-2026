from datetime import datetime, timedelta, timezone

from insights.inbox import Message, Thread
from insights.index import IndexNames, bulk_actions, mappings

ASKED = datetime(2025, 3, 14, 21, 32, tzinfo=timezone.utc)
NAMES = IndexNames(prefix="test-")

question = Message("m1", "mei_1", "Mei Tanaka", ASKED, "wait how did the interview go??")
deflection = Message("m2", "mei_1", "you", ASKED + timedelta(hours=11), "did you see the fire in studio")
mei = Thread("mei_1", "Mei Tanaka", ("Mei Tanaka", "you"), (question, deflection))


def actions() -> list[dict]:
    return list(bulk_actions([mei], owner="you", names=NAMES))


def test_every_message_and_window_becomes_one_action_keyed_by_its_id():
    keys = [(action["_index"], action["_id"]) for action in actions()]
    assert keys[:2] == [("test-messages", "m1"), ("test-messages", "m2")]
    assert [index for index, _ in keys[2:]] == ["test-windows", "test-windows"]
    assert len(set(keys)) == len(keys)


def test_message_document_carries_what_the_insight_queries_filter_on():
    source = actions()[1]["_source"]
    assert source == {
        "thread_id": "mei_1",
        "thread_name": "Mei Tanaka",
        "is_group": False,
        "sender": "you",
        "is_from_owner": True,
        "timestamp": "2025-03-15T08:32:00+00:00",
        "hour": 8,
        "text": "did you see the fire in studio",
    }


def test_window_document_holds_the_conversation_for_both_kinds_of_search():
    source = actions()[2]["_source"]
    assert source["text"] == "Mei Tanaka: wait how did the interview go??"
    assert source["semantic"] == source["text"]
    assert (source["message_ids"], source["message_count"]) == (["m1"], 1)
    assert (source["start"], source["end"]) == ("2025-03-14T21:32:00+00:00", "2025-03-14T21:32:00+00:00")


def test_every_indexed_field_is_declared_in_the_mappings():
    declared = mappings(inference_id=".elser-2-elastic")
    by_index = {NAMES.messages: declared["messages"], NAMES.windows: declared["windows"]}
    for action in actions():
        assert action["_source"].keys() == by_index[action["_index"]]["properties"].keys()


def test_semantic_field_is_pinned_to_the_given_model():
    semantic = mappings(inference_id="my-endpoint")["windows"]["properties"]["semantic"]
    assert semantic == {"type": "semantic_text", "inference_id": "my-endpoint"}
