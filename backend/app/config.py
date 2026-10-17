"""Central configuration for the Asset Intelligence Copilot."""
import os
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Data roots (folders containing fleet/ and assets/). The final-2-hours test
# dataset can be added by appending another root - ingest merges them.
# Cloud deployments pass extra roots via DATA_DIRS (semicolon-separated).
DATA_DIRS = [
    p
    for p in [
        # Test dataset (600 wells, today = 15 Jan 2027)
        PROJECT_ROOT.parent / "dataset" / "test-data" / "dataset",
        PROJECT_ROOT / "test-data" / "dataset",
        PROJECT_ROOT.parent / "test-data" / "dataset",
        PROJECT_ROOT / "dataset" / "test-data" / "dataset",
        Path(os.environ.get("EXTRA_DATA_DIR", "")) if os.environ.get("EXTRA_DATA_DIR") else None,
    ]
    + [Path(d) for d in os.environ.get("DATA_DIRS", "").split(";") if d.strip()]
    if p and Path(str(p)).exists()
]

# Remote store for 24/7 deployments (mysql://user:pass@host:port/db).
# Unset => local SQLite at DB_PATH.
MYSQL_URI = os.environ.get("MYSQL_URI", "")


DB_PATH = os.environ.get("COPILOT_DB", str(PROJECT_ROOT / "backend" / "copilot.db"))

# "Today" for the test dataset is 15 Jan 2027.
# For the sample dataset it was 16 Oct 2026.
# Auto-detected from the latest inspection date during ingest.
FIXED_TODAY = date(2027, 1, 15)

# Optional LLM (OpenAI-compatible: OpenAI, OpenRouter, Ollama, Gemini-compat...).
# When unset, the copilot runs fully deterministically on the built-in router.
# Users can connect their own key at runtime (POST /api/llm); it is stored in
# LLM_SETTINGS_PATH, which is gitignored. LLM_SOURCE tracks where the active
# settings came from: "env" (deployment owner) | "ui" (visitor) | "none".
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_SOURCE = "env" if (LLM_BASE_URL and LLM_MODEL) else "none"
LLM_SETTINGS_PATH = Path(
    os.environ.get("LLM_SETTINGS_PATH", str(PROJECT_ROOT / "backend" / "llm_settings.json")))


def today() -> date:
    """The copilot's notion of 'now', derived from config + loaded data."""
    return FIXED_TODAY


# --- Production-loss estimator assumptions -----------------------------------
# The dataset records downtime, never production volumes. These rates turn
# downtime into an ORDER-OF-MAGNITUDE estimate for prioritisation. They are
# assumptions, not measurements, and every answer says so. Override per
# deployment via LOSS_RATES_JSON='{"T200":60,...}' and OIL_PRICE_USD.
LOSS_RATES_BBL_PER_DAY = {"T200": 60.0, "T350": 120.0, "T500": 200.0}
if os.environ.get("LOSS_RATES_JSON"):
    import json as _json
    LOSS_RATES_BBL_PER_DAY.update(_json.loads(os.environ["LOSS_RATES_JSON"]))
OIL_PRICE_USD = float(os.environ.get("OIL_PRICE_USD", "70"))

# When set, write endpoints (ingest, claims, conversation deletes) require
# the X-API-Token header. Read-only endpoints stay open so judges and
# stakeholders can browse without a key.
API_TOKEN = os.environ.get("API_TOKEN", "")

# --- User-supplied datasets ---------------------------------------------------
# Uploaded zips are extracted here and re-ingested on every startup, so a
# visitor's data survives server restarts. Reset restores the challenge data.
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(PROJECT_ROOT / "backend" / "uploads")))
MANIFEST_PATH = UPLOAD_DIR / "manifest.json"
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "300"))
FIXED_TODAY_ORIGINAL = FIXED_TODAY
