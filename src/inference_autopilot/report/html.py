from __future__ import annotations
import html
from pathlib import Path

def write_html(bundle,path):
    p=bundle["profile"]; cards=[]
    for o in bundle["opportunities"]:
        ev="".join(f"<li>{html.escape(str(x))}</li>" for x in o["evidence"])
        asm="".join(f"<li>{html.escape(str(x))}</li>" for x in o["assumptions"])
        cards.append(f"<section><h3>{html.escape(o['title'])}</h3><p><b>{html.escape(o['detector'])}</b> · {html.escape(o['confidence'])} confidence</p><p>Affected requests: {o['affected_requests']}</p><h4>Evidence</h4><ul>{ev}</ul><h4>Assumptions</h4><ul>{asm}</ul><p><b>Next:</b> {html.escape(o['next_step'])}</p></section>")
    doc = """<!doctype html><html><head><meta charset='utf-8'><title>Inference Autopilot report</title><style>
body{font-family:system-ui;max-width:980px;margin:40px auto;padding:0 20px;color:#161616}section{border:1px solid #ddd;border-radius:12px;padding:18px;margin:16px 0}.metric{font-size:2rem;font-weight:700}</style></head><body>"""
    doc += f"<h1>Inference Autopilot</h1><p>Local evidence-backed inference cost analysis.</p><section><h2>Executive summary</h2><div class='metric'>${p['monthly_run_rate_usd']:,.2f}/mo</div><p>30-day run-rate estimate. Pricing coverage: {p['pricing_coverage_pct']:.1f}%.</p></section><h2>Opportunities</h2>"
    doc += "".join(cards) if cards else "<p>No evidence-backed opportunities found.</p>"
    doc += "<section><h2>Methodology & limitations</h2><p>Downgrade findings are candidates for replay evaluation, not claims that substitution is safe. Overlapping opportunities are not summed into a single savings promise.</p></section></body></html>"
    Path(path).write_text(doc,encoding="utf-8")
