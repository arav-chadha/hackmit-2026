"""HTTP API the dashboard talks to. Run with: python -m insights serve"""

import json
import os
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from insights.cards import document, write_cards
from insights.context import Context
from insights.judge import JudgeError, judged
from insights.pipeline import context_from_env, run

dashboard_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
frontend_page = Path(__file__).parent.parent / "frontend" / "index.html"

regenerate_instructions = (
    "You will see a card shown to the account owner about one of their friendships, the messages it is based on, "
    "and the suggested message currently on the card. Write a different suggested message for the same purpose: "
    "a new angle or opening, not a rewording. Match how the owner texts in the messages shown (casing, punctuation, "
    "emoji habits, length). Do not invent facts that are not in the card or messages. Never use em dashes."
)


class Draft(BaseModel):
    draft: str


app = FastAPI(title="insights")
app.add_middleware(CORSMiddleware, allow_origins=dashboard_origins, allow_methods=["GET", "POST"], allow_headers=["*"])


def cards_path() -> Path:
    return Path(os.environ.get("CARDS_PATH", "cards.json"))


def context() -> Context:
    load_dotenv(Path.cwd() / ".env")
    return context_from_env()


CardsPath = Annotated[Path, Depends(cards_path)]
Insights = Annotated[Context, Depends(context)]


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(frontend_page, media_type="text/html")


@app.get("/cards")
def read_cards(path: CardsPath) -> dict:
    return _load(path)


@app.post("/cards/refresh")
def refresh_cards(path: CardsPath, insights: Insights) -> dict:
    try:
        cards = run(insights)
    except JudgeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    write_cards(cards, insights.owner, path)
    return document(cards, insights.owner, insights.now)


@app.post("/cards/{card_id}/regenerate")
def regenerate_draft(card_id: str, path: CardsPath, insights: Insights) -> dict:
    content = _load(path)
    card = next((card for card in content["cards"] if card["id"] == card_id), None)
    if card is None:
        raise HTTPException(status_code=404, detail=f"no card with id {card_id}")
    if not card["action"] or card["action"]["draft"] is None:
        raise HTTPException(status_code=409, detail="this card has no suggested message to regenerate")
    try:
        rewritten = judged(insights.llm, insights.writer_model, regenerate_instructions, _material(card, insights.owner), Draft)
    except JudgeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    card["action"]["draft"] = rewritten.draft
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    return card


def _load(path: Path) -> dict:
    if not path.is_file():
        raise HTTPException(status_code=404, detail="no cards yet: POST /cards/refresh or run `python -m insights cards`")
    return json.loads(path.read_text(encoding="utf-8"))


def _material(card: dict, owner: str) -> str:
    messages = "\n".join(f"{item['sender']}: {item['text']}" for item in card["evidence"])
    return (
        f"The account owner is {owner}; the friend is {card['friend']['name']}.\n"
        f"Card: {card['title']}\n{card['body']}\n\n"
        f"Messages:\n{messages}\n\n"
        f"Current suggested message (write something different):\n{card['action']['draft']}"
    )
