from __future__ import annotations
import hashlib
from collections import Counter, defaultdict
from inference_autopilot.pricing.catalog import effective_cost

def _norm(s): return " ".join((s or "").split())
def _fp(s): return hashlib.sha256(_norm(s).encode()).hexdigest()[:16]
def _messages_text(msgs): return "\n".join(str(m.get("content","")) for m in msgs if isinstance(m,dict))
def _sum_cost(rows): return sum(float(effective_cost(r) or 0) for r in rows)

def build_profile(records):
    providers=Counter(); models=Counter(); lat=[]; known=[]; success=0; systems=defaultdict(list); exact=defaultdict(list)
    for r in records:
        providers[r["provider"]]+=1; models[f'{r["provider"]}/{r["model"]}']+=1
        c=effective_cost(r)
        if c is not None: known.append(float(c))
        if r.get("latency_ms") is not None: lat.append(float(r["latency_ms"]))
        success += r.get("status")=="success"
        msgs=(r.get("request") or {}).get("messages") or []
        sys="\n".join(str(m.get("content","")) for m in msgs if isinstance(m,dict) and m.get("role")=="system")
        full=_messages_text(msgs)
        if sys: systems[_fp(sys)].append(r)
        if full: exact[_fp(full)].append(r)
    sl=sorted(lat)
    pct=lambda p: sl[min(len(sl)-1,int((len(sl)-1)*p))] if sl else None
    spend=sum(known)
    return {"request_count":len(records),"providers":dict(providers),"models":dict(models),"known_cost_usd":round(spend,6),
            "monthly_run_rate_usd":round(spend*30,2),"pricing_coverage_pct":round(len(known)/len(records)*100,1) if records else 0,
            "success_rate_pct":round(success/len(records)*100,1) if records else 0,"p50_latency_ms":pct(.5),"p95_latency_ms":pct(.95),
            "_system_groups":systems,"_request_groups":exact}

def _opp(id,detector,title,confidence,rows,evidence,assumptions,next_step,savings=None,factors=None):
    cost=_sum_cost(rows)
    return {"id":id,"detector":detector,"title":title,"confidence":confidence,"affected_requests":len(rows),
            "affected_cost_usd":round(cost,4) if cost else None,"estimated_savings_usd":round(savings,4) if savings else None,
            "estimated_savings_pct":round(savings/cost*100,1) if savings and cost else None,"evidence":evidence,"assumptions":assumptions,
            "next_step":next_step,"request_ids":[r["request_id"] for r in rows[:50]],"score_factors":factors}

def duplicate_context(profile):
    out=[]
    for i,rows in enumerate(profile["_system_groups"].values(),1):
        if len(rows)<3: continue
        text="\n".join(str(m.get("content","")) for m in rows[0]["request"].get("messages",[]) if m.get("role")=="system")
        if len(text)<120: continue
        cost=_sum_cost(rows)
        out.append(_opp(f"dup-{i}","duplicate-context","Repeated system context appears across many requests","high",rows,
            [f"Same system-message fingerprint appears in {len(rows)} requests",f"Repeated system content length is {len(text)} characters"],
            ["Savings estimate conservatively attributes 20% of affected request cost until token-level prefix attribution is available"],
            "Evaluate provider prompt caching or application-side context reuse",cost*.20 if cost else None))
    return out

def cacheable(profile):
    out=[]
    for i,rows in enumerate(profile["_request_groups"].values(),1):
        if len(rows)<3: continue
        cost=_sum_cost(rows)
        out.append(_opp(f"cache-{i}","cacheable","Exact repeated request cluster is a strong caching candidate","high",rows,
            [f"Exact normalized request fingerprint repeats {len(rows)} times"],["Savings estimate assumes repeated work can be reused or served from a cheaper cache path"],
            "Test provider prompt caching or an application response cache",cost*.50 if cost else None))
    return out

def _shape(r):
    req=r.get("request") or {}; resp=r.get("response") or {}; temp=req.get("temperature"); out=(r.get("usage") or {}).get("output_tokens") or 0
    user=" ".join(str(m.get("content","")) for m in req.get("messages") or [] if isinstance(m,dict) and m.get("role")=="user").lower()
    constrained=any(k in user for k in ("classify","category","return json","json object","yes or no","extract","route"))
    short=bool(out and out<=80); low=bool(temp is not None and float(temp)<=.3); content=resp.get("content"); structured=isinstance(content,str) and content.strip().startswith(("{","["))
    flags={"constrained_prompt":float(constrained),"short_output":float(short),"low_temperature":float(low),"structured_output":float(structured)}
    return sum(flags.values())/4,flags

def simple_and_downgrade(records):
    rows=[]
    for r in records:
        s,f=_shape(r)
        if s>=.5: rows.append((r,s,f))
    out=[]
    if rows:
        rs=[x[0] for x in rows]; avg=sum(x[1] for x in rows)/len(rows)
        out.append(_opp("simple-1","simple-task","Traffic structurally resembles constrained decision work","medium",rs,
            [f"{len(rs)} requests match at least two constrained-task signals",f"Average structural simplicity is {avg:.2f}"],
            ["This identifies replay candidates only; it does not prove a smaller model preserves quality"],
            "Replay a representative sample against a cheaper model or deterministic implementation",None,{"structural_simplicity":round(avg,3)}))
        priced=[x for x in rows if effective_cost(x[0]) is not None]
        if priced:
            prs=[x[0] for x in priced]; avgp=sum(x[1] for x in priced)/len(priced)
            out.append(_opp("down-1","downgrade-candidate","High-spend traffic worth cheaper-model replay evaluation","medium",prs,
                [f"{len(prs)} priced requests combine non-zero spend with structural simplicity",f"Average structural simplicity is {avgp:.2f}"],
                ["Candidate confidence is not quality confidence","No model substitution is considered safe until replay evaluation passes"],
                "Run offline replay against cheaper models and compare task-specific quality",None,{"structural_simplicity":round(avgp,3),"affected_cost":round(_sum_cost(prs),4)}))
    return out

def run_detectors(records,profile):
    return duplicate_context(profile)+cacheable(profile)+simple_and_downgrade(records)

def public_profile(profile): return {k:v for k,v in profile.items() if not k.startswith("_")}
