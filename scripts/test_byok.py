"""End-to-end test for bring-your-own-key LLM connection:
status starts empty, a key can be saved (masked on read), a bad key fails the
test endpoint cleanly, disconnect clears everything, and the settings file is
persisted outside git.

Run from backend/:  python ../scripts/test_byok.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import config, db  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="byok-test-"))
config.DB_PATH = str(tmp / "test.db")
config.UPLOAD_DIR = tmp / "uploads"
config.MANIFEST_PATH = config.UPLOAD_DIR / "manifest.json"
config.LLM_SETTINGS_PATH = tmp / "llm_settings.json"
config.LLM_BASE_URL = config.LLM_MODEL = config.LLM_API_KEY = ""
config.LLM_SOURCE = "none"

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


def main():
    import warnings
    warnings.filterwarnings("ignore")
    from fastapi.testclient import TestClient
    from app.main import app

    db.ingest(db_path=config.DB_PATH)
    client = TestClient(app)

    st = client.get("/api/llm").json()
    check("starts unconfigured", st["configured"] is False and st["source"] == "none", str(st))

    # a bad key must fail the live test cleanly (provider error surfaced, no 500)
    bad = client.post("/api/llm/test", json={
        "provider": "custom", "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini", "api_key": "sk-definitely-not-real"}).json()
    check("bad key fails cleanly", bad["ok"] is False and len(bad["error"]) > 5, str(bad)[:150])

    # saving stores it, masks it on read, and persists outside git
    r = client.post("/api/llm", json={
        "provider": "openrouter", "base_url": "https://openrouter.ai/api/v1",
        "model": "google/gemma-4-31b-it:free", "api_key": "sk-or-v1-abcdef1234567890abcdef"})
    st = r.json()
    check("connect ok", r.status_code == 200 and st["configured"] is True, str(st)[:150])
    check("key masked, never echoed", st["key_masked"].endswith("cdef") and
          "abcdef1234567890" not in json.dumps(st), str(st["key_masked"]))
    saved = json.loads(config.LLM_SETTINGS_PATH.read_text())
    check("settings persisted for restarts", saved["model"] == "google/gemma-4-31b-it:free",
          str(saved)[:120])

    # a fresh startup picks the saved key back up (env has priority over it)
    client2 = TestClient(app)
    st2 = client2.get("/api/llm").json()
    check("startup reloads saved key", st2["configured"] is True and st2["source"] == "ui", str(st2))

    # disconnect wipes runtime + file
    d = client.delete("/api/llm").json()
    check("disconnect ok", d["configured"] is False and not config.LLM_SETTINGS_PATH.exists(),
          str(d)[:120])

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"===== {passed}/{len(RESULTS)} BYOK tests passed =====")
    for name, ok, detail in RESULTS:
        print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {detail[:200]}"))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
