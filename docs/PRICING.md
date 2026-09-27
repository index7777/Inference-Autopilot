# Pricing data provenance

The built-in pricing catalog is intentionally small and versioned. Unknown models are reported as unknown rather than assigned invented prices.

Catalog version: `2026-09-27`

## OpenAI

Source: https://developers.openai.com/api/docs/pricing

The bundled catalog currently includes short-context standard pricing for:

- `gpt-6-astra`
- `gpt-6-sol`
- `gpt-6-luna`

The implementation records cached-input pricing separately where available.

## Anthropic

Sources:

- https://www.anthropic.com/news/claude-sonnet-5
- https://platform.claude.com/docs/en/about-claude/pricing

The bundled catalog currently includes:

- `claude-sonnet-5`
- `claude-opus-4-8`

## Policy

Pricing is data, not detector logic. When a model/provider is missing or a private negotiated price applies, supply a JSON pricing override:

```json
{
  "entries": [
    {
      "provider": "my-provider",
      "model": "my-model",
      "input_per_million_usd": 1.0,
      "cached_input_per_million_usd": 0.1,
      "output_per_million_usd": 4.0
    }
  ]
}
```

Run:

```bash
inference-autopilot analyze logs.jsonl --pricing pricing.json
```

Pricing can change. Do not treat the built-in catalog as a billing authority; it is an analysis baseline and should be refreshed or overridden when precision matters.
