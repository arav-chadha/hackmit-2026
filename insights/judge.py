"""The one place the backend calls an LLM: instructions and material in, a validated verdict out."""

import anthropic
from pydantic import BaseModel

max_output_tokens = 2000
max_output_tokens_with_search = 4000
web_search = {"type": "web_search_20250305", "name": "web_search", "max_uses": 2}


class JudgeError(Exception):
    pass


def judged[Verdict: BaseModel](
    client: anthropic.Anthropic, model: str, instructions: str, material: str, verdict_type: type[Verdict]
) -> Verdict:
    request = {"model": model, "max_tokens": max_output_tokens, "system": instructions, "output_format": verdict_type}
    return _parsed(client, request, material)


def searched[Verdict: BaseModel](
    client: anthropic.Anthropic, model: str, instructions: str, material: str, verdict_type: type[Verdict]
) -> Verdict:
    """Like judged, but the model may search the web before it answers."""
    request = {"model": model, "max_tokens": max_output_tokens_with_search, "system": instructions, "output_format": verdict_type}
    return _parsed(client, {**request, "tools": [web_search]}, material)


def _parsed(client: anthropic.Anthropic, request: dict, material: str):
    try:
        response = client.messages.parse(**request, messages=[{"role": "user", "content": material}])
    except anthropic.APIError as error:
        raise JudgeError(f"{request['model']} call failed: {error}") from error
    if response.parsed_output is None:
        raise JudgeError(f"{request['model']} returned no verdict (stop reason: {response.stop_reason})")
    return response.parsed_output
