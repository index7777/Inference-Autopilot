# Inference Autopilot

**Find cheaper ways to run your LLM workload — without guessing.**

Inference Autopilot is a local-first, open-source CLI that analyzes LLM request logs and surfaces evidence-backed cost opportunities: duplicated context, caching candidates, constrained/simple-task traffic, and high-value cheaper-model replay candidates.

The v0.1 implementation is deliberately analysis-only. It does **not** route production traffic, upload prompts, mutate infrastructure, or require a SaaS account.

## Quick start

```bash
git clone https://github.com/index7777/Inference-Autopilot.git
cd Inference-Autopilot
python -m pip install -e .

inference-autopilot analyze examples/synthetic_logs.jsonl
inference-autopilot explain --top 10
inference-autopilot report --output report.html
```

The demo is deterministic and local. It includes repeated context, an exact repeated-request cluster, constrained classification traffic, and one malformed row so ingestion behavior is visible.

Expected detector classes:

```text
duplicate-context
cacheable
simple-task
downgrade-candidate
```

## CLI

```bash
# Analyze JSONL / JSON / CSV logs
inference-autopilot analyze ./logs.jsonl

# Force a provider adapter
inference-autopilot analyze ./logs.jsonl --provider openai
inference-autopilot analyze ./logs.jsonl --provider anthropic
inference-autopilot analyze ./logs.jsonl --provider openrouter

# Normalize into the v0.1 canonical JSONL schema
inference-autopilot normalize ./logs.jsonl --output normalized.jsonl

# Validate normalized data and pricing coverage
inference-autopilot validate normalized.jsonl

# Inspect findings and their evidence
inference-autopilot explain --top 20
inference-autopilot explain --detector duplicate-context
inference-autopilot explain --request-id req_123

# Build a self-contained local report
inference-autopilot report --output report.html

# Do not persist an analysis bundle
inference-autopilot analyze ./logs.jsonl --no-persist

# Avoid persisting response bodies
inference-autopilot analyze ./logs.jsonl --no-response-content

# Supply private/custom pricing
inference-autopilot analyze ./logs.jsonl --pricing pricing.json
```

## What v0.1 does

### Ingestion

- OpenAI-shaped logs
- Anthropic-shaped logs
- OpenRouter-shaped logs
- normalized-schema passthrough
- JSONL, JSON, and basic CSV ingestion
- invalid-row counting instead of silent dropping

### Cost baseline

- provider-observed cost wins when present
- otherwise versioned token pricing is used when known
- unknown models remain unknown; they are never treated as zero-cost
- custom pricing can be supplied with `--pricing`

The bundled pricing catalog is intentionally small and versioned. It currently includes selected OpenAI and Anthropic models used to make the MVP immediately testable. Pricing must be treated as data and updated independently of detector logic.

### Detectors

**`duplicate-context`** finds exact repeated system context at meaningful scale. It recommends caching/reuse; it does not claim duplicated content can simply be deleted.

**`cacheable`** finds exact repeated request clusters. Findings expose evidence and assumptions rather than hiding them behind a global score.

**`simple-task`** identifies structurally constrained traffic such as classification, routing, extraction, short JSON output, and low-temperature repeated tasks.

**`downgrade-candidate`** prioritizes traffic worth cheaper-model replay. It never claims a substitution is safe. Candidate confidence is explicitly different from quality confidence.

## Local analysis bundle

Unless `--no-persist` is used, the CLI writes:

```text
.inference-autopilot/
├── latest.json
├── profile.json
├── opportunities.json
└── normalized.jsonl
```

Raw source logs are not copied. Obvious credentials are redacted before persisted normalized output is written, and user/session identifiers are hashed when adapters can identify them.

## Static report

`inference-autopilot report --output report.html` generates a self-contained HTML file with no remote analytics or hosted backend. Every opportunity includes evidence, assumptions, impact context, confidence, and a recommended next step.

## Architecture

```text
Provider logs
    ↓
Adapters + local redaction
    ↓
Normalized request schema
    ↓
Versioned pricing + workload profiler
    ↓
Detectors
    ├── duplicate-context
    ├── cacheable
    ├── simple-task
    └── downgrade-candidate
    ↓
Evidence-backed opportunities
    ↓
CLI / explain / static HTML
```

See [`docs/MVP_SPEC.md`](docs/MVP_SPEC.md) and [`docs/normalized-request.schema.json`](docs/normalized-request.schema.json).

## Local tests

No CI or GitHub Actions workflow is used for this MVP.

Run smoke tests manually:

```bash
python -m unittest discover -s tests -v
```

## Design principles

1. **Local-first by default** — production prompts and responses stay on the user's machine.
2. **Evidence over magic scores** — every recommendation must expose why it exists.
3. **Deterministic first** — measurable signals before model-based judgment.
4. **Provider-neutral** — normalize logs once, analyze consistently.
5. **Conservative claims** — under-claim rather than manufacture savings precision.
6. **No silent automation** — v0.1 analyzes; it does not change production.

## Explicitly out of scope for v0.1

- production request routing
- automatic model switching
- automatic quantization or distillation
- GPU provisioning
- hosted SaaS / accounts / billing
- mandatory LLM-as-judge
- GitHub Actions
- CI automation
- PR QA workflows

## Open-source validation

Stars are useful, but they are not the primary validation signal. Stronger signals are:

- real workloads analyzed,
- high-quality issues about integrations and edge cases,
- external provider adapters and fixes,
- repeated usage on new data,
- users reporting verified savings opportunities.

The first meaningful target is **100 real workloads analyzed**. If users then ask for replay evaluation, additional providers, scheduled analysis, or self-hosted continuous monitoring, those requests decide what gets built next.

## Roadmap after v0.1

Only after real usage validates demand:

1. Replay representative requests against cheaper models.
2. Build a workload-specific quality/cost frontier.
3. Add continuous local/self-hosted analysis.
4. Consider policy-driven runtime routing.
5. Benchmark self-hosted quantized/distilled/runtime variants.

## Contributing

The most useful contributions now are anonymized log formats, provider adapters, detector test cases, pricing corrections, and false-positive/false-negative reports.

Please do **not** add CI, PR QA, or GitHub Actions workflows unless the project direction changes explicitly.

## Status

**v0.1 MVP implemented / experimental.** The command surface works end-to-end on the included synthetic workload; interfaces may still change as real workloads are tested.
