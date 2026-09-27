from __future__ import annotations

REQUIRED_TOP_LEVEL = ("schema_version","request_id","timestamp","provider","model","request","response","usage","cost","metadata")


def validate_normalized_record(record: dict) -> list[str]:
    errors=[]
    if record.get("schema_version") != "0.1":
        errors.append("schema_version must be 0.1")
    for key in REQUIRED_TOP_LEVEL:
        if key not in record:
            errors.append(f"missing field: {key}")
    for key in ("request_id","timestamp","provider","model"):
        if not record.get(key):
            errors.append(f"empty critical field: {key}")
    for key in ("request","response","usage","cost","metadata"):
        if key in record and not isinstance(record[key],dict):
            errors.append(f"{key} must be an object")
    usage=record.get("usage") if isinstance(record.get("usage"),dict) else {}
    if usage and all(usage.get(k) is None for k in ("input_tokens","output_tokens")):
        messages=(record.get("request") or {}).get("messages") if isinstance(record.get("request"),dict) else None
        response=(record.get("response") or {}).get("content") if isinstance(record.get("response"),dict) else None
        if not messages and response is None:
            errors.append("need token usage or enough request/response content to estimate usage")
    return errors
