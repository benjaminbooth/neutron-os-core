"""Embedding generation via the OpenAI embeddings API.

Uses ``text-embedding-3-small`` (1536 dimensions) by default.
Requires ``OPENAI_API_KEY`` in the environment.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests

log = logging.getLogger(__name__)

_API_URL = "https://api.openai.com/v1/embeddings"
_BATCH_SIZE = 100  # OpenAI limit per request
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds


def embed_texts(
    texts: list[str],
    model: str = "text-embedding-3-small",
) -> Optional[list[list[float]]]:
    """Embed a list of texts using the OpenAI embeddings API.

    Returns ``None`` if no API key is configured (caller should handle
    the fallback).  Raises on non-rate-limit API errors.

    Parameters
    ----------
    texts:
        Strings to embed.  Empty list returns ``[]``.
    model:
        OpenAI embedding model name.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log.warning("OPENAI_API_KEY not set — skipping embedding generation")
        return None

    if not texts:
        return []

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    all_embeddings: list[list[float]] = []

    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        payload = {"input": batch, "model": model}

        for attempt in range(_MAX_RETRIES):
            resp = requests.post(_API_URL, headers=headers, json=payload, timeout=60)

            if resp.status_code == 429:
                wait = _BACKOFF_BASE * (2**attempt)
                log.warning("Rate limited by OpenAI, retrying in %.1fs", wait)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()
            # Results may not be in order; sort by index
            sorted_data = sorted(data["data"], key=lambda d: d["index"])
            all_embeddings.extend(d["embedding"] for d in sorted_data)
            break
        else:
            raise RuntimeError(
                f"OpenAI embeddings API failed after {_MAX_RETRIES} retries (rate limit)"
            )

    return all_embeddings
