"""Runs the insights against the index and returns their cards."""

import os
from datetime import datetime, timezone

import anthropic
from elasticsearch import Elasticsearch

from insights.both_wanted import both_wanted
from insights.cards import Card
from insights.context import Context
from insights.index import IndexNames
from insights.memory_lane import memory_lane
from insights.parallel import concurrently
from insights.recap import recap
from insights.reconnect import reconnect
from insights.settings import Settings
from insights.unanswered import unanswered
from insights.unfinished_plans import unfinished_plans
from insights.your_people import your_people

insights = {f.__name__: f for f in (your_people, unanswered, unfinished_plans, both_wanted, memory_lane, reconnect)}


def search_client(settings: Settings) -> Elasticsearch:
    return Elasticsearch(settings.elastic_url, api_key=settings.elastic_api_key, request_timeout=60)


def context_from_env() -> Context:
    settings = Settings.from_env(os.environ)
    return Context(
        search=search_client(settings),
        names=IndexNames(settings.index_prefix),
        llm=anthropic.Anthropic(max_retries=6),
        judge_model=settings.judge_model,
        writer_model=settings.writer_model,
        owner=settings.owner,
        now=datetime.now(timezone.utc),
    )


def run(context: Context, only: str | None = None) -> list[Card]:
    chosen = [insights[only]] if only else list(insights.values())
    per_insight = concurrently(lambda insight: insight(context), chosen, workers=len(chosen))
    cards = [card for cards in per_insight for card in cards]
    # The recap is built from the other insights' cards, so it only makes sense on a full run.
    return cards if only else cards + recap(context, cards)
