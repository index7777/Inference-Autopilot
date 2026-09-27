# Inference Autopilot

**Find cheaper ways to run your LLM workload — without guessing.**

Inference Autopilot is a local-first, open-source CLI that analyzes real LLM request logs and identifies cost-saving opportunities such as model downgrades, prompt/context duplication, caching candidates, and requests that may not need a large generative model at all.

The first release is intentionally offline and analysis-only. It does **not** route production traffic, upload prompts, mutate infrastructure, or require a SaaS account.

## What it should answer

Given a few days of OpenAI / Anthropic / OpenRouter logs, answer:

- What is this workload costing today?
- Which requests are expensive because of duplicated context?
- Which requests are likely cacheable?
- Which traffic looks like classification / extraction / routing rather than open-ended generation?
- Which request clusters are candidates for a cheaper model?
- What is the estimated savings opportunity, and how confident are we?

The long-term metric is **cost per successful outcome**, not just cost per token.

## MVP demo

```bash
pip install inference-autopilot

inference-autopilot analyze ./logs.jsonl
```

Example output:

```text
Analyzed 12,481 requests
Period: 7 days

Current monthly estimate      $14,220
Potential optimized spend      $8,940
Potential savings               37.1%

Opportunities
✓ 21% requests likely cacheable
✓ 14% duplicate system/context tokens
✓ 18% simple classification/extraction traffic
✓ 11% candidates for cheaper-model evaluation

Confidence
HIGH    duplicated context
HIGH    exact/prefix cache candidates
MEDIUM  simple task detection
LOW     model downgrade until replay evaluation is run

Next:
  inference-autopilot explain --top 20
  inference-autopilot report --output report.html
```

## MVP scope

### In scope

- Local JSONL / JSON / CSV ingestion
- Adapters for OpenAI, Anthropic, and OpenRouter-shaped logs
- One normalized request schema
- Token and spend estimation
- Traffic clustering / profiling
- Deterministic savings detectors
- Heuristic downgrade-candidate detection
- CLI summary and explain views
- Static HTML report
- Redaction of obvious secrets before any local persistence

### Explicitly out of scope for v0.1

- Production request routing
- Automatic model switching
- Automatic quantization / distillation
- GPU provisioning
- Hosted SaaS
- Accounts / billing
- Uploading prompts or responses to a remote service
- LLM-as-judge as a required dependency
- GitHub Actions / CI / PR QA workflows

## Design principles

1. **Local-first by default** — production prompts and responses stay on the user's machine.
2. **Evidence over magic scores** — every recommendation must show why it was produced.
3. **Deterministic first** — use measurable signals before model-based judgment.
4. **Provider-neutral** — normalize logs once, run the same analysis across providers.
5. **Conservative estimates** — prefer under-claiming savings over fabricated precision.
6. **No silent automation** — v0.1 analyzes; it does not modify production behavior.

## Proposed CLI

```bash
# Analyze a workload
inference-autopilot analyze ./logs.jsonl

# Force/declare an adapter
inference-autopilot analyze ./logs.jsonl --provider openai
inference-autopilot analyze ./logs.jsonl --provider anthropic
inference-autopilot analyze ./logs.jsonl --provider openrouter

# Inspect the biggest opportunities and evidence
inference-autopilot explain --top 20
inference-autopilot explain --detector duplicate-context

# Generate a local HTML report
inference-autopilot report --output report.html

# Validate / inspect normalized data
inference-autopilot normalize ./logs.jsonl --output normalized.jsonl
inference-autopilot validate normalized.jsonl

# Override pricing when a provider/model is missing or private
inference-autopilot analyze ./logs.jsonl --pricing pricing.json
```

## Architecture

```text
Provider logs
    ↓
Adapters
    ↓
Normalized request schema
    ↓
Profiler + cost calculator
    ↓
Detectors
    ├── duplicate-context
    ├── cacheable
    ├── simple-task
    └── downgrade-candidate
    ↓
Evidence + savings estimate
    ↓
CLI / local HTML report
```

See [`docs/MVP_SPEC.md`](docs/MVP_SPEC.md) for the implementation-ready v0.1 specification.

## What success looks like

This project is an experiment. Stars are useful, but they are not the primary validation signal.

The strongest signals are:

- real workloads analyzed,
- high-quality issues about integrations and real edge cases,
- external provider adapters / PRs,
- users returning to analyze new data,
- users reporting verified savings opportunities.

A healthy first milestone is **100 real workloads analyzed** and evidence that teams want additional providers, replay evaluation, or scheduled analysis.

## Roadmap after v0.1

Only if v0.1 gets real usage:

1. **Replay evaluation** — run representative requests against cheaper models.
2. **Quality / cost frontier** — compare success metrics, latency, and spend.
3. **Continuous analysis** — scheduled local or self-hosted reports.
4. **Runtime routing** — optional policy-driven routing after sufficient evidence.
5. **Self-hosted model optimization** — benchmark quantized / distilled / runtime variants.

## Contributing

The most useful contributions during v0.1 are:

- anonymized sample log formats,
- provider adapters,
- detector test cases,
- pricing metadata corrections,
- real-world false positive / false negative reports.

Please avoid adding CI, PR QA, or GitHub Actions workflows unless the project direction changes explicitly.

## Status

**MVP specification / pre-alpha.** Interfaces may change quickly while the first real workloads are tested.
