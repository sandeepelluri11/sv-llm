from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


class Settings(BaseModel):
    """Runtime configuration. Every field can be overridden with an SV_LLM_* variable."""

    model: str = Field(default_factory=lambda: _env("SV_LLM_MODEL", "gpt-4o-mini"))
    embedding_model: str = Field(
        default_factory=lambda: _env("SV_LLM_EMBEDDING_MODEL", "text-embedding-3-small")
    )
    temperature: float = Field(default_factory=lambda: float(_env("SV_LLM_TEMPERATURE", "0")))
    retriever_k: int = Field(default_factory=lambda: int(_env("SV_LLM_RETRIEVER_K", "6")))
    max_iterations: int = Field(default_factory=lambda: int(_env("SV_LLM_MAX_ITERATIONS", "2")))
    chunk_chars: int = Field(default_factory=lambda: int(_env("SV_LLM_CHUNK_CHARS", "1800")))
    examples_dir: Path = Field(
        default_factory=lambda: Path(_env("SV_LLM_EXAMPLES", str(REPO_ROOT / "examples/few_shot")))
    )
    designs_dir: Path = Field(
        default_factory=lambda: Path(_env("SV_LLM_DESIGNS", str(REPO_ROOT / "designs")))
    )


def get_settings() -> Settings:
    return Settings()
