from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """Return the repository root for the agent workflow package."""
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def get_data_dir() -> Path:
    """Return the data directory shipped with the agent workflow package."""
    return get_project_root() / "data"


@lru_cache(maxsize=1)
def get_rag_index_dir() -> Path:
    return get_data_dir() / "rag" / "index"


@lru_cache(maxsize=1)
def get_support_data_dir() -> Path:
    return get_data_dir() / "support"
