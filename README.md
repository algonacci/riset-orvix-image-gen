# riset-orvix-image-gen

Probe Orvix `POST /v1/images/generations` (ship-5) via prepaid Image Credits.

Checkout storefront stays HOLD. Debit = `orvix-image-credits-100` only.

## Setup

```bash
uv sync
cp .env.example .env
```

Paste a live `ai:invoke` key into `ORV_KEY`. Do not invent one.

## Run

One model (default `ORV_MODEL`, usually flux-2-pro):

```bash
uv run python generate.py
```

Override model / prompt:

```bash
uv run python generate.py --model qwen-image-3.0 --prompt "a red circle on white"
```

All five:

```bash
uv run python generate.py --model all
```

Images land in `outputs/`. Catalogue debit per image: flux 7, qwen 8, seedream/gpt 11, gemini 30.
