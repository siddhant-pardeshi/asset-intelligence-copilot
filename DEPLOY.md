# Deploying the Copilot

Two ways to run this publicly, both free. Pick based on how long you need it up.

## 1. Permanent: Hugging Face Space (Docker SDK)

The repo root already contains a working `Dockerfile`: it installs deps, clones
the public challenge dataset, bakes the merged SQLite store into the image and
serves API + UI on port 7860.

1. Create a Space at huggingface.co → **Docker** SDK → blank.
2. Push this repo to the Space (git remote add space ... && git push) or upload
   as files.
3. The Space builds (~3 min) and serves at `https://<your-name>-<space-name>.hf.space`.

Notes that matter outside a demo:

- The SQLite file lives inside the container. Memory (corrections, claims,
  notes) written at runtime resets on rebuild. For a real site, point
  `COPILOT_DB` at a mounted volume, or swap `db.connect()` for Postgres — the
  SQL is standard enough that it is an afternoon, not a rewrite.
- Set `API_TOKEN` in the Space secrets to lock the write endpoints (ingest,
  corrections, deletes) behind an `X-API-Token` header. Read-only browsing
  stays open, which is what you want for stakeholders.

## 2. Right now, from a laptop: Cloudflare quick tunnel

With the server running locally:

```
cloudflared tunnel --url http://localhost:8000
```

Prints a `*.trycloudflare.com` URL — no account, no config. It is live while
your machine is. Quick-tunnel URLs rotate on restart, so treat them as
disposable; use the Space for a link you can put on a slide.

## Pointing it at a real field

This is the part that makes the demo more than a demo:

- **Self-serve upload**: `POST /api/upload-dataset` takes a multipart zip of `fleet/` + `assets/`, extracts it with a zip-slip guard, merges it into the store and remembers it across restarts via a manifest. `POST /api/reset-data` restores the shipped datasets. The UI ships with both wired up (📥 Add Dataset in the top nav), so a leasing team can onboard their own field without touching the server.
- **Ingestion**: `POST /api/ingest` with a list of directories loads any folder
  of `fleet/` + `assets/` JSONL. A nightly SCADA export dropped into a watched
  folder is enough; the store is idempotent (every row keyed by its natural id),
  so re-running never duplicates.
- **Assumptions stay visible**: the production-loss estimator reads
  `LOSS_RATES_JSON` and `OIL_PRICE_USD`. Real deployments feed per-well rates
  from the historian instead of static numbers, and the copilot still says
  out loud that it is an estimate.
- **The rule layer is data**: well-type thresholds are parsed from the manuals
  at query time, not hard-coded. A new pump class means adding one markdown
  manual, not a code change.
- **Keys**: visitors can connect their own OpenAI-compatible key in the UI (🔑 Connect AI); it is stored in `llm_settings.json` (gitignored) and only ever rephrases deterministic output. As the owner, set `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` env vars instead — env keys take precedence over visitor keys, and visitors then see a read-only view they cannot disconnect.
- **Auth**: beyond the token guard, put the app behind your SSO proxy. The API
  is stateless per request, so that is a proxy concern, not an app rewrite.
