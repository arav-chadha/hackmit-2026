import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from insights.server import Draft, app, cards_path, context

DOCUMENT = {
    "generatedAt": "2026-09-20T02:30:00Z",
    "owner": "you",
    "cards": [
        {
            "id": "a3f9c2e1",
            "kind": "unanswered",
            "title": "Mei asked how your interview went",
            "body": "You never told her.",
            "friend": {"name": "Mei Tanaka", "threadId": "mei_1"},
            "evidence": [{"sender": "Mei Tanaka", "text": "wait how did the interview go??"}],
            "action": {"label": "Respond", "draft": "i never told you how it went 😭"},
        },
        {
            "id": "2ac6e7d0",
            "kind": "recap",
            "title": "You + Rafa",
            "body": "Two years, mostly after midnight.",
            "friend": {"name": "Rafa Ortiz", "threadId": "rafa_1"},
            "evidence": [],
            "action": {"label": "Share Recap", "draft": None},
        },
    ],
}


class StubMessages:
    def __init__(self):
        self.request = None

    def parse(self, **request):
        self.request = request
        return SimpleNamespace(parsed_output=Draft(draft="ok so about that interview"), stop_reason="end_turn")


@pytest.fixture
def served(tmp_path):
    path = tmp_path / "cards.json"
    path.write_text(json.dumps(DOCUMENT), encoding="utf-8")
    llm = SimpleNamespace(messages=StubMessages())
    app.dependency_overrides[cards_path] = lambda: path
    app.dependency_overrides[context] = lambda: SimpleNamespace(llm=llm, writer_model="claude-opus-5", owner="you")
    yield SimpleNamespace(client=TestClient(app), path=path, llm=llm)
    app.dependency_overrides.clear()


def test_the_frontend_is_served_at_the_root_and_reads_cards_from_this_server(served):
    response = served.client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "fetch('/cards'" in response.text
    assert "const DATA = {" not in response.text


def test_cards_are_served_as_written(served):
    response = served.client.get("/cards")
    assert (response.status_code, response.json()) == (200, DOCUMENT)


def test_the_dashboard_origin_is_allowed_to_read_them(served):
    response = served.client.get("/cards", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_no_cards_file_yet_says_how_to_make_one(served):
    served.path.unlink()
    response = served.client.get("/cards")
    assert response.status_code == 404
    assert "refresh" in response.json()["detail"]


def test_regenerate_returns_a_new_draft_and_keeps_it(served):
    response = served.client.post("/cards/a3f9c2e1/regenerate")
    assert response.status_code == 200
    assert response.json()["action"] == {"label": "Respond", "draft": "ok so about that interview"}
    kept = json.loads(served.path.read_text(encoding="utf-8"))["cards"][0]["action"]["draft"]
    assert kept == "ok so about that interview"


def test_regenerate_shows_the_writer_the_evidence_and_the_draft_to_avoid(served):
    served.client.post("/cards/a3f9c2e1/regenerate")
    material = served.llm.messages.request["messages"][0]["content"]
    assert "wait how did the interview go??" in material
    assert "i never told you how it went 😭" in material


def test_regenerate_for_an_unknown_card_is_not_found(served):
    assert served.client.post("/cards/nope/regenerate").status_code == 404


def test_regenerate_for_a_card_without_a_draft_is_refused(served):
    assert served.client.post("/cards/2ac6e7d0/regenerate").status_code == 409
