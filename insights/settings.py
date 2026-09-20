"""Configuration read from environment variables (loaded from .env by the command line)."""

from collections.abc import Mapping
from dataclasses import dataclass, field

required = ("ELASTIC_URL", "ELASTIC_API_KEY")


class SettingsError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    elastic_url: str
    elastic_api_key: str = field(repr=False)
    owner: str
    index_prefix: str
    inference_id: str
    judge_model: str
    writer_model: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        missing = [name for name in required if not env.get(name, "").strip()]
        if missing:
            raise SettingsError(f"set {', '.join(missing)} in .env (see .env.example)")
        return cls(
            elastic_url=env["ELASTIC_URL"].strip(),
            elastic_api_key=env["ELASTIC_API_KEY"].strip(),
            owner=env.get("OWNER_NAME", "you"),
            index_prefix=env.get("ELASTIC_INDEX_PREFIX", ""),
            inference_id=env.get("ELASTIC_INFERENCE_ID", ".elser-2-elastic"),
            judge_model=env.get("JUDGE_MODEL", "claude-haiku-4-5"),
            writer_model=env.get("WRITER_MODEL", "claude-opus-5"),
        )
