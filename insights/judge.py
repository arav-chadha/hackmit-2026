"""The one place the backend calls an LLM: instructions and material in, a validated verdict out."""

import anthropic
from pydantic import BaseModel

max_output_tokens = 2000


class JudgeError(Exception):
    pass


def judged[Verdict: BaseModel](
    client: anthropic.Anthropic, model: str, instructions: str, material: str, verdict_type: type[Verdict]
) -> Verdict:
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=max_output_tokens,
            system=instructions,
            messages=[{"role": "user", "content": material}],
            output_format=verdict_type,
        )
    except anthropic.APIError as error:
        raise JudgeError(f"{model} call failed: {error}") from error
    if response.parsed_output is None:
        raise JudgeError(f"{model} returned no verdict (stop reason: {response.stop_reason})")
    return response.parsed_output
