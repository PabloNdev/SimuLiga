"""Shared name normalization for football data providers."""

from __future__ import annotations

import re
import unicodedata


def normalize_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_name = decomposed.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", ascii_name).strip()


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize_name(name)).strip("-")
