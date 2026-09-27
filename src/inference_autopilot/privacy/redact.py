from __future__ import annotations
import hashlib, re
from typing import Any

_SECRET_PATTERNS = [
    re.compile(r'(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+\-/=]+'),
    re.compile(r'(?i)(api[_-]?key\s*[:=]\s*)[A-Za-z0-9._~+\-/=]{12,}'),
    re.compile(r'(?i)(cookie\s*[:=]\s*)[^\s,;]+'),
    re.compile(r'\b(sk-[A-Za-z0-9_-]{12,})\b'),
]

def redact_text(value: str) -> str:
    out = value
    for pat in _SECRET_PATTERNS:
        out = pat.sub(lambda m: (m.group(1) if m.lastindex else "") + "[REDACTED]", out)
    return out

def redact_obj(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_obj(v) for v in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k.lower() in {"authorization","cookie","set-cookie","api_key","apikey","token","access_token","refresh_token"}:
                out[k] = "[REDACTED]"
            else:
                out[k] = redact_obj(v)
        return out
    return value

def stable_hash(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
