# Inference Autopilot v0.1 — MVP Specification

## 1. Goal

Build a local-first CLI that turns real LLM request logs into an evidence-backed cost optimization report.

The MVP is successful if a developer can point the CLI at a production log export and, without creating an account or sending data elsewhere, get a useful answer to:

> Where is inference spend being wasted, what could plausibly be cheaper, and what evidence supports that recommendation?

The MVP does **not** optimize production automatically. It discovers and explains optimization opportunities.

---

## 2. Non-goals

Do not build these in v0.1:

- live proxy / gateway,
- production request routing,
- automatic model switching,
- model quantization or distillation,
- GPU scheduling,
- hosted backend,
- authentication or billing,
- browser dashboard requiring a server,
- mandatory LLM-as-judge,
- GitHub Actions,
- CI automation,
- PR QA workflows.

These are explicitly deferred until open-source usage demonstrates demand.

---

## 3. Primary user

A developer, technical founder, ML engineer, or platform engineer who:

- already pays for OpenAI / Anthropic / OpenRouter or similar inference,
- has request-level logs or can export them,
- suspects some traffic is over-provisioned,
- wants a local analysis before changing production behavior.

Initial target workload sizes:

- 1,000 to 1,000,000 requests per analysis,
- one to seven days of logs,
- text/chat/tool-call traffic first.

---

## 4. User journey

### Happy path

```bash
pip install inference-autopilot
inference-autopilot analyze ./logs.jsonl
```

Expected flow:

1. Detect provider format or ask user to specify `--provider`.
2. Parse records.
3. Normalize records into the internal schema.
4. Redact obvious secrets in any persisted cache/output.
5. Calculate observed and estimated spend.
6. Profile traffic.
7. Run detectors.
8. Rank opportunities by estimated savings and confidence.
9. Print a terminal summary.
10. Persist a local analysis bundle so `explain` and `report` can reuse it.

### Follow-up

```bash
inference-autopilot explain --top 20
inference-autopilot report --output report.html
```

No cloud account should be required.

---

## 5. CLI contract

Binary name:

```text
inference-autopilot
```

### `analyze`

```bash
inference-autopilot analyze <path> [options]
```

Options:

```text
--provider <auto|openai|anthropic|openrouter>
--format <auto|jsonl|json|csv>
--pricing <pricing.json>
--sample <N|percentage>
--output-dir <path>
--no-response-content
--no-persist
--timezone <IANA timezone>
--currency <USD>
--verbose
```

Behavior:

- provider defaults to `auto`,
- unknown model pricing must be surfaced as unknown, never silently treated as zero,
- invalid rows are counted and reported,
- large files should be streamed when practical,
- detector failures should not abort unrelated detectors.

### `normalize`

```bash
inference-autopilot normalize <path> --output normalized.jsonl [--provider ...]
```

Produces only normalized records.

### `validate`

```bash
inference-autopilot validate <normalized.jsonl>
```

Outputs:

- valid row count,
- invalid row count,
- missing critical fields,
- unknown models,
- unknown providers,
- time range,
- token coverage percentage.

### `explain`

```bash
inference-autopilot explain [options]
```

Options:

```text
--top <N>
--detector <name>
--request-id <id>
--cluster <id>
--json
```

Every recommendation must expose:

- detector name,
- evidence,
- estimated savings method,
- confidence,
- assumptions,
- affected request count.

### `report`

```bash
inference-autopilot report --output report.html
```

Generates a static, self-contained HTML file from the latest local analysis bundle.

---

## 6. Normalized request schema

Canonical internal record:

```json
{
  "schema_version": "0.1",
  "request_id": "req_123",
  "timestamp": "2026-09-27T10:15:30Z",
  "provider": "openai",
  "model": "example-model",
  "endpoint": "chat.completions",
  "request": {
    "messages": [
      {"role": "system", "content": "..."},
      {"role": "user", "content": "..."}
    ],
    "tools": [],
    "temperature": 0.2,
    "max_output_tokens": 800
  },
  "response": {
    "content": "...",
    "finish_reason": "stop",
    "tool_calls": []
  },
  "usage": {
    "input_tokens": 1042,
    "output_tokens": 188,
    "cached_input_tokens": 0,
    "reasoning_tokens": null
  },
  "latency_ms": 842,
  "status": "success",
  "error_type": null,
  "cost": {
    "observed_usd": null,
    "estimated_usd": 0.00412,
    "pricing_source": "builtin",
    "pricing_version": "2026-09-27"
  },
  "metadata": {
    "route": null,
    "user_id_hash": null,
    "session_id_hash": null,
    "tags": {}
  }
}
```

### Required fields

At minimum, an analyzable record needs:

- `request_id`,
- `timestamp`,
- `provider`,
- `model`,
- token usage OR enough request/response text to estimate it.

### Privacy rules

- Never persist raw API keys, authorization headers, cookies, or obvious bearer tokens.
- Prefer hashes for user/session identifiers.
- `--no-response-content` drops response bodies after feature extraction.
- `--no-persist` keeps the analysis ephemeral.
- Reports should show excerpts only when the user explicitly allows content inclusion.

---

## 7. Provider adapters

Interface:

```python
class LogAdapter(Protocol):
    def can_parse(self, sample: dict) -> float: ...
    def normalize(self, raw: dict) -> NormalizedRequest: ...
```

### v0.1 adapters

1. OpenAI-shaped logs
2. Anthropic-shaped logs
3. OpenRouter-shaped logs
4. Generic normalized schema passthrough

Adapters should be independently testable fixtures, not coupled to detector code.

Auto-detection must return confidence and fail clearly when ambiguous.

---

## 8. Pricing model

Built-in pricing metadata should be versioned and replaceable.

Pricing entry:

```json
{
  "provider": "openai",
  "model": "example-model",
  "effective_from": "2026-09-01",
  "input_per_million_usd": 1.0,
  "cached_input_per_million_usd": 0.1,
  "output_per_million_usd": 4.0
}
```

Rules:

- prefer observed provider-reported cost if present,
- otherwise calculate from versioned pricing,
- never invent pricing for an unknown model,
- report unknown-cost request percentage,
- allow `--pricing` override for private/custom models.

The MVP should treat pricing as data, not hard-code it into detector logic.

---

## 9. Profiler

Before detectors run, generate workload-level features:

- request count,
- provider/model distribution,
- input/output token distribution,
- p50/p95 latency,
- success/error rate,
- estimated daily/monthly cost,
- repeated prompt/system-message fingerprints,
- repeated prefix fingerprints,
- request length buckets,
- response length buckets,
- likely task-shape features,
- time-of-day volume distribution.

The profiler creates reusable features so every detector does not repeatedly parse content.

---

## 10. Detector interface

Each detector returns one or more opportunities.

```python
class Detector(Protocol):
    name: str
    version: str

    def run(self, workload: WorkloadProfile) -> list[Opportunity]: ...
```

Opportunity shape:

```json
{
  "id": "opp_123",
  "detector": "duplicate-context",
  "title": "Repeated system prompt dominates input spend",
  "confidence": "high",
  "affected_requests": 4182,
  "affected_cost_usd": 312.44,
  "estimated_savings_usd": 187.12,
  "estimated_savings_pct": 59.9,
  "evidence": [
    "Same 5,214-token prefix appears in 4,182 requests",
    "Prefix accounts for 62% of input tokens in this cluster"
  ],
  "assumptions": [
    "Provider caching or application-level reuse is available"
  ],
  "next_step": "Evaluate provider prompt caching or application-side memoization"
}
```

Confidence is detector-specific. Do not collapse all findings into a fake global score.

---

## 11. v0.1 detectors

### A. `duplicate-context`

**Purpose:** Find repeated prompt/context material that is repeatedly paid for.

Signals:

- identical normalized system messages,
- identical long prefixes,
- high token-weight repeated blocks,
- repeated tool definitions / schema blocks.

Implementation approach:

1. Normalize whitespace and obviously volatile values.
2. Hash system messages and prefix chunks.
3. Count recurrence and token weight.
4. Estimate cost attributable to repeated material.
5. Report clusters where repetition exceeds configurable thresholds.

Confidence:

- HIGH when exact identical content repeats at meaningful scale,
- MEDIUM for normalized/fuzzy matches.

Do not claim all duplicated text is removable; recommend caching/reuse rather than deletion.

### B. `cacheable`

**Purpose:** Find request clusters likely to benefit from provider or application caching.

Signals:

- exact repeated requests,
- identical long prefixes with small suffix variation,
- low-temperature repeated tasks,
- repeated static tool/schema definitions.

Savings estimate:

- use known cached-token pricing where available,
- otherwise show token volume eligible for caching without converting it into dollars.

Confidence:

- HIGH for exact repeated requests,
- HIGH for exact repeated long prefixes,
- MEDIUM for semantic/fuzzy similarity.

### C. `simple-task`

**Purpose:** Identify traffic that resembles constrained decision work rather than open-ended generation.

Candidate shapes:

- classification,
- binary yes/no,
- routing,
- entity extraction,
- schema-constrained JSON,
- short normalization/transformation.

Signals should be primarily structural:

- very short outputs,
- low output entropy proxies,
- small finite label sets observed over time,
- strict JSON schemas,
- repeated prompt templates,
- tool-only responses,
- low temperature,
- stable response forms.

Output:

- mark candidate clusters,
- explain structural evidence,
- recommend replay evaluation against a smaller model or deterministic logic.

Important: v0.1 must **not** assert that a smaller model is safe without replay/evaluation.

Confidence:

- MEDIUM at best in v0.1 unless deterministic label-set evidence is strong.

### D. `downgrade-candidate`

**Purpose:** Prioritize request clusters for cheaper-model replay in the next product phase.

This detector does **not** claim a model substitution is valid. It ranks where evaluation is likely to have high expected value.

Signals:

- high spend,
- low output length,
- stable templates,
- low temperature,
- simple-task signal,
- low tool complexity,
- low reasoning-token dependence where observable,
- repeated deterministic response format.

Example ranking score:

```text
expected_value = affected_cost × structural_simplicity × repeatability
```

Display the factors, not just the score.

Confidence terminology should say `candidate confidence`, not `quality confidence`.

---

## 12. Savings calculations

Separate three concepts:

1. **Observed spend** — provider-reported, if present.
2. **Estimated spend** — reconstructed from token usage and pricing.
3. **Potential savings** — detector-specific opportunity estimate.

Never add overlapping opportunities naively.

Example:

A request may be both cacheable and a downgrade candidate. The headline report must avoid double counting.

For v0.1, use:

- `gross_opportunity_usd`: sum by detector independently,
- `conservative_combined_savings_usd`: only combine non-overlapping or clearly composable findings,
- show methodology in the report.

---

## 13. Local analysis bundle

Default directory:

```text
.inference-autopilot/
```

Suggested files:

```text
latest.json
profile.json
opportunities.json
normalized.jsonl   # optional depending on privacy flags
```

Do not persist raw original log files.

`latest.json` should include tool version, analysis timestamp, source path fingerprint, and detector versions.

---

## 14. HTML report

The report is static and self-contained.

Sections:

1. Executive summary
2. Current spend estimate
3. Spend by model/provider
4. Top opportunities
5. Duplicate context findings
6. Caching findings
7. Simple-task candidates
8. Downgrade evaluation candidates
9. Unknown / missing pricing
10. Methodology and limitations

Every opportunity card must contain:

- impact,
- confidence,
- evidence,
- assumptions,
- recommended next step.

No server-side analytics or tracking in v0.1.

---

## 15. Suggested repository layout

```text
inference-autopilot/
├── src/inference_autopilot/
│   ├── cli.py
│   ├── models.py
│   ├── adapters/
│   │   ├── base.py
│   │   ├── openai.py
│   │   ├── anthropic.py
│   │   ├── openrouter.py
│   │   └── normalized.py
│   ├── pricing/
│   │   ├── catalog.py
│   │   └── builtin.json
│   ├── profiler/
│   │   ├── workload.py
│   │   └── fingerprints.py
│   ├── detectors/
│   │   ├── base.py
│   │   ├── duplicate_context.py
│   │   ├── cacheable.py
│   │   ├── simple_task.py
│   │   └── downgrade_candidate.py
│   ├── privacy/
│   │   └── redact.py
│   └── report/
│       ├── terminal.py
│       └── html.py
├── tests/
│   ├── fixtures/
│   ├── test_adapters.py
│   ├── test_pricing.py
│   └── test_detectors.py
├── examples/
│   └── synthetic_logs.jsonl
├── docs/
│   └── MVP_SPEC.md
├── pyproject.toml
└── README.md
```

No `.github/workflows/` directory is required for the MVP.

---

## 16. Implementation order

### Milestone 1 — Trustworthy ingestion and cost baseline

Ship when:

- CLI installs,
- OpenAI/Anthropic/OpenRouter fixtures normalize,
- validation works,
- token/cost totals are reproducible,
- unknown pricing is explicit,
- obvious secrets are redacted from persisted output.

### Milestone 2 — Useful savings findings

Ship when:

- duplicate-context works on synthetic and real sanitized samples,
- cacheable works,
- simple-task produces evidence-backed candidates,
- downgrade-candidate ranking works,
- overlapping opportunities are not double-counted in headline savings.

### Milestone 3 — Shareable local report

Ship when:

- CLI summary is readable,
- `explain` traces a recommendation back to evidence,
- HTML report is self-contained,
- example dataset produces a compelling deterministic demo.

Launch publicly after Milestone 3. Do not wait for routing or SaaS.

---

## 17. MVP acceptance criteria

A fresh user should be able to:

```bash
pip install inference-autopilot
inference-autopilot analyze examples/synthetic_logs.jsonl
inference-autopilot explain --top 10
inference-autopilot report --output report.html
```

And get:

- zero network calls by default,
- a monthly cost estimate,
- at least two meaningful detector findings from the example dataset,
- evidence for every finding,
- a static HTML report,
- no GitHub Actions / CI / PR QA requirement.

Performance target for v0.1:

- analyze 100k ordinary JSONL records on a developer laptop without loading the entire raw file into memory where avoidable.

---

## 18. Validation metrics after launch

Do not optimize only for stars.

Track manually/community-side where possible:

- real workloads analyzed,
- external issue quality,
- external PRs,
- provider adapter requests,
- repeat users,
- reported savings,
- false-positive detector reports,
- requests for replay evaluation,
- requests for scheduled/self-hosted analysis.

Strong demand signal:

> Users ask the project to move from "show me where" to "prove the cheaper alternative still works."

That is the trigger to build replay evaluation.

---

## 19. Kill / continue criteria

After roughly 30 days of public exposure:

### Continue if

- users analyze real production-derived workloads,
- multiple users request additional providers,
- users report credible savings findings,
- contributors submit adapters or detector cases,
- teams ask for replay evaluation or continuous analysis.

### Reconsider or stop if

- stars rise but usage stays limited to the example dataset,
- issues are mainly feature curiosity with no real logs,
- recommendations are too noisy to trust,
- users cannot provide enough data to calculate cost reliably.

The project is an experiment in developer demand, not a commitment to build a company around the idea regardless of evidence.
