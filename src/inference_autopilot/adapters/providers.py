from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from inference_autopilot.privacy.redact import stable_hash

def _ts(raw: dict[str, Any]) -> str:
    v = raw.get("timestamp") or raw.get("created_at") or raw.get("created")
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(v, str) and v:
        return v
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _usage(raw):
    u = raw.get("usage") or {}
    return {
        "input_tokens": u.get("input_tokens", u.get("prompt_tokens")),
        "output_tokens": u.get("output_tokens", u.get("completion_tokens")),
        "cached_input_tokens": u.get("cached_input_tokens", u.get("cache_read_input_tokens", 0)) or 0,
        "reasoning_tokens": u.get("reasoning_tokens"),
    }

def _base(raw, provider):
    messages = raw.get("messages") or (raw.get("request") or {}).get("messages") or raw.get("input") or []
    response_content = raw.get("response_content")
    if response_content is None and raw.get("choices"):
        choice = raw["choices"][0] if raw["choices"] else {}
        response_content = (choice.get("message") or {}).get("content") or choice.get("text")
    return {
        "schema_version":"0.1",
        "request_id":str(raw.get("request_id") or raw.get("id") or ""),
        "timestamp":_ts(raw), "provider":provider, "model":str(raw.get("model") or ""),
        "endpoint":raw.get("endpoint") or ("messages" if provider=="anthropic" else "chat.completions"),
        "request":{"messages":messages,"tools":raw.get("tools") or (raw.get("request") or {}).get("tools") or [],
                   "temperature":raw.get("temperature", (raw.get("request") or {}).get("temperature")),
                   "max_output_tokens":raw.get("max_output_tokens", raw.get("max_tokens"))},
        "response":{"content":response_content,"finish_reason":raw.get("finish_reason"),"tool_calls":raw.get("tool_calls") or []},
        "usage":_usage(raw), "latency_ms":raw.get("latency_ms"), "status":raw.get("status","success"), "error_type":raw.get("error_type"),
        "cost":{"observed_usd":raw.get("cost_usd"),"estimated_usd":None,"pricing_source":None,"pricing_version":None},
        "metadata":{"route":raw.get("route"),"user_id_hash":stable_hash(str(raw.get("user_id"))) if raw.get("user_id") else None,
                    "session_id_hash":stable_hash(str(raw.get("session_id"))) if raw.get("session_id") else None,"tags":raw.get("tags") or {}}
    }

class NormalizedAdapter:
    name="normalized"
    def can_parse(self,s): return 1.0 if s.get("schema_version")=="0.1" and "request_id" in s and "provider" in s else 0.0
    def normalize(self,raw): return dict(raw)

class OpenAIAdapter:
    name="openai"
    def can_parse(self,s):
        score=.4 if s.get("provider")=="openai" else 0
        if "choices" in s: score += .3
        if isinstance(s.get("usage"),dict) and any(k in s["usage"] for k in ("prompt_tokens","completion_tokens","input_tokens")): score += .3
        return min(score,1.0)
    def normalize(self,raw): return _base(raw,"openai")

class AnthropicAdapter:
    name="anthropic"
    def can_parse(self,s):
        score=.5 if s.get("provider")=="anthropic" else 0
        if "stop_reason" in s or (isinstance(s.get("usage"),dict) and "input_tokens" in s["usage"]): score += .4
        return min(score,1.0)
    def normalize(self,raw):
        r=_base(raw,"anthropic")
        if r["response"]["content"] is None and isinstance(raw.get("content"),list):
            r["response"]["content"]="".join(str(x.get("text","")) for x in raw["content"] if isinstance(x,dict))
        r["response"]["finish_reason"]=raw.get("stop_reason") or r["response"]["finish_reason"]
        return r

class OpenRouterAdapter(OpenAIAdapter):
    name="openrouter"
    def can_parse(self,s):
        score=.6 if s.get("provider")=="openrouter" or "openrouter" in str(s.get("base_url","")) else 0
        if isinstance(s.get("usage"),dict): score += .2
        if "cost" in s or "cost_usd" in s: score += .2
        return min(score,1.0)
    def normalize(self,raw):
        r=_base(raw,"openrouter")
        if r["cost"]["observed_usd"] is None: r["cost"]["observed_usd"]=raw.get("cost")
        return r

ADAPTERS=[NormalizedAdapter(), OpenRouterAdapter(), AnthropicAdapter(), OpenAIAdapter()]

def choose_adapter(sample, provider="auto"):
    if provider!="auto":
        for a in ADAPTERS:
            if a.name==provider: return a,1.0
        raise ValueError(f"Unsupported provider: {provider}")
    ranked=sorted(((a.can_parse(sample),a) for a in ADAPTERS), key=lambda x:x[0], reverse=True)
    if not ranked or ranked[0][0] < .4: raise ValueError("Could not detect provider format; pass --provider explicitly")
    if len(ranked)>1 and ranked[0][0]==ranked[1][0] and ranked[0][0] < .95: raise ValueError("Ambiguous provider format; pass --provider explicitly")
    return ranked[0][1],ranked[0][0]
