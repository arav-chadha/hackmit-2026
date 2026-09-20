from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from insights.judge import JudgeError, judged, searched


class Verdict(BaseModel):
    is_answered: bool


class StubMessages:
    def __init__(self, response):
        self.response = response
        self.request = None

    def parse(self, **request):
        self.request = request
        return self.response


def client_returning(parsed_output, stop_reason="end_turn"):
    messages = StubMessages(SimpleNamespace(parsed_output=parsed_output, stop_reason=stop_reason))
    return SimpleNamespace(messages=messages)


def test_returns_the_parsed_verdict():
    client = client_returning(Verdict(is_answered=False))
    verdict = judged(client, "claude-haiku-4-5", "Decide.", "Question and reply", Verdict)
    assert verdict == Verdict(is_answered=False)


def test_sends_instructions_as_system_and_material_as_the_user_turn():
    client = client_returning(Verdict(is_answered=True))
    judged(client, "claude-haiku-4-5", "Decide.", "Question and reply", Verdict)
    request = client.messages.request
    assert (request["model"], request["system"], request["output_format"]) == ("claude-haiku-4-5", "Decide.", Verdict)
    assert request["messages"] == [{"role": "user", "content": "Question and reply"}]


def test_searching_gives_the_model_the_web_search_tool_and_judging_does_not():
    client = client_returning(Verdict(is_answered=True))
    judged(client, "claude-haiku-4-5", "Decide.", "Topic", Verdict)
    assert "tools" not in client.messages.request
    searched(client, "claude-haiku-4-5", "Decide.", "Topic", Verdict)
    assert [tool["name"] for tool in client.messages.request["tools"]] == ["web_search"]


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens", "pause_turn"])
def test_a_response_without_a_verdict_is_an_error_naming_why(stop_reason):
    client = client_returning(None, stop_reason)
    with pytest.raises(JudgeError, match=stop_reason):
        judged(client, "claude-haiku-4-5", "Decide.", "Question and reply", Verdict)
