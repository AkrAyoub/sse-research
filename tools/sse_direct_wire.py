"""Minimal, dependency-free canonical JSON bytes for SSE direct-exchange storage.

This module deliberately does not import any signer, monitor adapter, RPC
client, provider service, or SLA code. It is the single byte encoding used by
both signed direct-delivery responses and the durable SQLite journal.
"""
from __future__ import annotations

import json

MAX_WIRE = 8192


class WireError(ValueError):
    pass


def wire_json_bytes(item) -> bytes:
    try:
        raw = json.dumps(item, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise WireError("invalid exchange JSON") from exc
    if not 1 <= len(raw) <= MAX_WIRE:
        raise WireError("exchange envelope too large")
    return raw
