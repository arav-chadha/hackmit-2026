"""Everything an insight needs to do its work, bundled so insight functions take one argument."""

from dataclasses import dataclass
from datetime import datetime

import anthropic
from elasticsearch import Elasticsearch

from insights.index import IndexNames


@dataclass(frozen=True)
class Context:
    search: Elasticsearch
    names: IndexNames
    llm: anthropic.Anthropic
    judge_model: str
    writer_model: str
    owner: str
    now: datetime
