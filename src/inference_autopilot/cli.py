from __future__ import annotations
import argparse, csv, json, sys
from pathlib import Path
from datetime import datetime, timezone
from inference_autopilot import __version__
from inference_autopilot.adapters.providers import choose_adapter
from inference_autopilot.privacy.redact import redact_obj
from inference_autopilot.pricing.catalog import load_catalog,apply_cost
from inference_autopilot.engine import build_profile,run_detectors,public_profile
from inference_autopilot.report.html import write_html

DEFAULT_DIR=Path(".inference-autopilot")

def _coerce_csv_row(row):
    out=dict(row)
    for key in ("usage","messages","request","choices","content","tools","tags"):
        if isinstance(out.get(key),str) and out[key].strip().startswith(("{","[")):
            try: out[key]=json.loads(out[key])
            except json.JSONDecodeError: pass
    for key in ("latency_ms","cost_usd","cost","temperature","max_tokens","max_output_tokens"):
        if isinstance(out.get(key),str) and out[key] != "":
            try: out[key]=float(out[key])
            except ValueError: pass
    return out

def _read(path, fmt="auto"):
    p=Path(path)
    actual=fmt
    if actual=="auto":
        actual={".jsonl":"jsonl",".ndjson":"jsonl",".csv":"csv"}.get(p.suffix.lower(),"json")
    if actual=="jsonl":
        for line in p.open(encoding="utf-8"):
            if line.strip(): yield json.loads(line)
    elif actual=="csv":
        with p.open(encoding="utf-8",newline="") as f:
            for row in csv.DictReader(f): yield _coerce_csv_row(row)
    elif actual=="json":
        data=json.loads(p.read_text())
        for x in data if isinstance(data,list) else [data]: yield x
    else:
        raise ValueError(f"Unsupported format: {fmt}")

def _normalize(path,provider,no_response=False,pricing=None,fmt="auto",sample=None):
    good=[]; invalid=0; adapter=None; confidence=None; catalog=load_catalog(pricing)
    limit=None
    if sample:
        try:
            if str(sample).endswith("%"): limit=None
            else: limit=max(1,int(sample))
        except ValueError: raise ValueError("--sample must be an integer row count or percentage")
    for raw in _read(path,fmt):
        if limit is not None and len(good)>=limit: break
        try:
            if adapter is None: adapter,confidence=choose_adapter(raw,provider)
            r=redact_obj(adapter.normalize(raw))
            if not r.get("request_id") or not r.get("model") or not r.get("provider"): raise ValueError("missing critical fields")
            if no_response: r["response"]["content"]=None
            apply_cost(r,catalog); good.append(r)
        except Exception:
            invalid += 1
    return good,invalid,(adapter.name if adapter else None),confidence

def cmd_analyze(a):
    records,invalid,adapter,confidence=_normalize(a.path,a.provider,a.no_response_content,a.pricing,a.format,a.sample)
    if not records:
        print("No valid rows found",file=sys.stderr); return 2
    profile=build_profile(records); opps=run_detectors(records,profile); pub=public_profile(profile)
    bundle={"tool_version":__version__,"analysis_timestamp":datetime.now(timezone.utc).isoformat(),"source":str(Path(a.path)),"adapter":adapter,"adapter_confidence":confidence,"invalid_rows":invalid,"profile":pub,"opportunities":opps}
    print(f"Analyzed {pub['request_count']:,} requests ({invalid} invalid rows)")
    print(f"Known spend in sample       ${pub['known_cost_usd']:,.2f}")
    print(f"30-day run-rate estimate    ${pub['monthly_run_rate_usd']:,.2f}")
    print(f"Pricing coverage             {pub['pricing_coverage_pct']:.1f}%\n")
    print("Opportunities")
    if not opps: print("  No evidence-backed opportunities found.")
    for o in opps[:10]: print(f"  [{o['confidence'].upper():6}] {o['detector']}: {o['title']}")
    if not a.no_persist:
        out=Path(a.output_dir or DEFAULT_DIR); out.mkdir(parents=True,exist_ok=True)
        (out/"latest.json").write_text(json.dumps(bundle,indent=2),encoding="utf-8")
        (out/"profile.json").write_text(json.dumps(pub,indent=2),encoding="utf-8")
        (out/"opportunities.json").write_text(json.dumps(opps,indent=2),encoding="utf-8")
        with (out/"normalized.jsonl").open("w",encoding="utf-8") as f:
            for r in records: f.write(json.dumps(r,ensure_ascii=False)+"\n")
    return 0

def cmd_normalize(a):
    records,invalid,_,_=_normalize(a.path,a.provider,a.no_response_content,a.pricing,a.format,None)
    with Path(a.output).open("w",encoding="utf-8") as f:
        for r in records: f.write(json.dumps(r,ensure_ascii=False)+"\n")
    print(f"Wrote {len(records)} normalized rows; {invalid} invalid rows")
    return 0 if records else 2

def cmd_validate(a):
    valid=invalid=0; providers=set(); models=set(); unknown=set(); timestamps=[]; token_rows=0; catalog=load_catalog(a.pricing)
    for raw in _read(a.path,"auto"):
        try:
            if raw.get("schema_version")!="0.1" or not all(raw.get(k) for k in ("request_id","timestamp","provider","model")): raise ValueError
            valid+=1; providers.add(raw["provider"]); models.add(raw["model"]); timestamps.append(raw["timestamp"])
            u=raw.get("usage") or {}; token_rows += bool(u.get("input_tokens") is not None or u.get("output_tokens") is not None)
            if (raw["provider"],raw["model"]) not in catalog and (raw.get("cost") or {}).get("observed_usd") is None: unknown.add(f'{raw["provider"]}/{raw["model"]}')
        except Exception: invalid+=1
    out={"valid_rows":valid,"invalid_rows":invalid,"providers":sorted(providers),"models":sorted(models),"unknown_models":sorted(unknown),"time_range":[min(timestamps),max(timestamps)] if timestamps else None,"token_coverage_pct":round(token_rows/valid*100,1) if valid else 0}
    print(json.dumps(out,indent=2)); return 0 if valid else 2

def _load_bundle(path=None):
    p=Path(path) if path else DEFAULT_DIR/"latest.json"
    return json.loads(p.read_text())

def cmd_explain(a):
    b=_load_bundle(a.bundle); ops=b["opportunities"]
    if a.detector: ops=[o for o in ops if o["detector"]==a.detector]
    if a.request_id: ops=[o for o in ops if a.request_id in (o.get("request_ids") or [])]
    ops=ops[:a.top]
    if a.json: print(json.dumps(ops,indent=2)); return 0
    for o in ops:
        print(f"\n{o['title']} [{o['confidence']}]\nDetector: {o['detector']}\nAffected: {o['affected_requests']}")
        print("Evidence:"); [print(f"  - {x}") for x in o["evidence"]]
        print("Assumptions:"); [print(f"  - {x}") for x in o["assumptions"]]
        print(f"Next: {o['next_step']}")
    return 0

def cmd_report(a):
    b=_load_bundle(a.bundle); write_html(b,a.output); print(f"Wrote {a.output}"); return 0

def build_parser():
    p=argparse.ArgumentParser(prog="inference-autopilot"); p.add_argument("--version",action="version",version=__version__)
    sp=p.add_subparsers(dest="cmd",required=True)
    def common(s):
        s.add_argument("path"); s.add_argument("--provider",default="auto",choices=["auto","openai","anthropic","openrouter"]); s.add_argument("--pricing"); s.add_argument("--no-response-content",action="store_true"); s.add_argument("--format",default="auto",choices=["auto","jsonl","json","csv"])
    s=sp.add_parser("analyze"); common(s); s.add_argument("--output-dir"); s.add_argument("--no-persist",action="store_true"); s.add_argument("--sample"); s.add_argument("--timezone",default="UTC"); s.add_argument("--currency",default="USD"); s.add_argument("--verbose",action="store_true"); s.set_defaults(func=cmd_analyze)
    s=sp.add_parser("normalize"); common(s); s.add_argument("--output",required=True); s.set_defaults(func=cmd_normalize)
    s=sp.add_parser("validate"); s.add_argument("path"); s.add_argument("--pricing"); s.set_defaults(func=cmd_validate)
    s=sp.add_parser("explain"); s.add_argument("--top",type=int,default=20); s.add_argument("--detector"); s.add_argument("--request-id"); s.add_argument("--cluster"); s.add_argument("--json",action="store_true"); s.add_argument("--bundle"); s.set_defaults(func=cmd_explain)
    s=sp.add_parser("report"); s.add_argument("--output",required=True); s.add_argument("--bundle"); s.set_defaults(func=cmd_report)
    return p

def main():
    a=build_parser().parse_args(); raise SystemExit(a.func(a))
if __name__=="__main__": main()
