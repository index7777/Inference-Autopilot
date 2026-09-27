import json
import tempfile
import unittest
from pathlib import Path

from inference_autopilot.adapters.providers import choose_adapter
from inference_autopilot.pricing.catalog import load_catalog, apply_cost
from inference_autopilot.engine import build_profile, run_detectors, public_profile
from inference_autopilot.privacy.redact import redact_obj
from inference_autopilot.report.html import write_html


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        source = Path(__file__).parents[1] / "examples" / "synthetic_logs.jsonl"
        for line in source.read_text(encoding="utf-8").splitlines():
            raw = json.loads(line)
            try:
                adapter, _ = choose_adapter(raw)
                row = redact_obj(adapter.normalize(raw))
                if not row.get("request_id") or not row.get("model"):
                    continue
                apply_cost(row, load_catalog())
                self.rows.append(row)
            except Exception:
                pass

    def test_demo_produces_findings_and_known_cost(self):
        self.assertEqual(len(self.rows), 5)
        profile = build_profile(self.rows)
        public = public_profile(profile)
        findings = run_detectors(self.rows, profile)
        names = {x["detector"] for x in findings}
        self.assertEqual(public["pricing_coverage_pct"], 100.0)
        self.assertGreater(public["known_cost_usd"], 0)
        self.assertIn("duplicate-context", names)
        self.assertIn("cacheable", names)
        self.assertIn("simple-task", names)
        self.assertIn("downgrade-candidate", names)

    def test_html_report_is_self_contained(self):
        profile = build_profile(self.rows)
        bundle = {"profile": public_profile(profile), "opportunities": run_detectors(self.rows, profile)}
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "report.html"
            write_html(bundle, str(out))
            text = out.read_text(encoding="utf-8")
            self.assertIn("Inference Autopilot", text)
            self.assertNotIn("<script src=", text)

    def test_redaction(self):
        value = redact_obj({"authorization":"Bearer abcdef1234567890","body":"api_key=abcdefghijklmnop"})
        self.assertEqual(value["authorization"], "[REDACTED]")
        self.assertNotIn("abcdefghijklmnop", value["body"])


if __name__ == "__main__":
    unittest.main()
