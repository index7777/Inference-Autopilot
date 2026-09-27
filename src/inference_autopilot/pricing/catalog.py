from __future__ import annotations
import json
from pathlib import Path

VERSION="2026-09-27"
BUILTIN = {
    ("openai","gpt-6-astra"): {"input":10.0,"cached_input":1.0,"output":50.0},
    ("openai","gpt-6-sol"): {"input":2.0,"cached_input":0.20,"output":10.0},
    ("openai","gpt-6-luna"): {"input":0.10,"cached_input":0.01,"output":0.50},
    ("anthropic","claude-sonnet-5"): {"input":2.0,"cached_input":None,"output":10.0},
    ("anthropic","claude-opus-4-8"): {"input":5.0,"cached_input":0.50,"output":25.0},
}

def load_catalog(path=None):
    data=dict(BUILTIN)
    if path:
        raw=json.loads(Path(path).read_text())
        for e in raw if isinstance(raw,list) else raw.get("entries",[]):
            data[(e["provider"],e["model"])]= {"input":e["input_per_million_usd"],"cached_input":e.get("cached_input_per_million_usd"),"output":e["output_per_million_usd"]}
    return data

def apply_cost(r,catalog):
    if r.get("cost",{}).get("observed_usd") is not None:
        r["cost"].update(pricing_source="observed",pricing_version=VERSION); return True
    p=catalog.get((r.get("provider"),r.get("model")))
    if not p: return False
    u=r.get("usage") or {}; inp=u.get("input_tokens") or 0; out=u.get("output_tokens") or 0; cached=u.get("cached_input_tokens") or 0
    uncached=max(inp-cached,0); cr=p["cached_input"] if p["cached_input"] is not None else p["input"]
    r["cost"].update(estimated_usd=round((uncached*p["input"]+cached*cr+out*p["output"])/1_000_000,10),pricing_source="builtin",pricing_version=VERSION)
    return True

def effective_cost(r):
    c=r.get("cost") or {}
    return c.get("observed_usd") if c.get("observed_usd") is not None else c.get("estimated_usd")
