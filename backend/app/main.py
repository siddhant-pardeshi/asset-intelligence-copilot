"""Asset Intelligence Copilot — API + static UI server."""
import io
import json
import os
import re
import shutil
import sqlite3
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agent, config, db, domain, memory, ops_tools, tools

app = FastAPI(title="Asset Intelligence Copilot", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

_conn: sqlite3.Connection = None


def get_conn():
    global _conn
    if _conn is None:
        _conn = db.connect()
        db.init_schema(_conn)
    return _conn


def guard_writes(request) -> JSONResponse | None:
    """Optional write protection for public deployments: set API_TOKEN and all
    mutating endpoints require the X-API-Token header. Read-only endpoints stay
    open so reviewers and stakeholders can browse without a key."""
    if not config.API_TOKEN:
        return None
    if request.headers.get("x-api-token") == config.API_TOKEN:
        return None
    return JSONResponse(status_code=401, content={"error": "missing or invalid X-API-Token"})


@app.get("/api/crew-board")
def crew_board(area: str | None = None):
    """Ranked open actions for the morning standup (deterministic)."""
    with db.CONN_LOCK:
        return _normalize(ops_tools.crew_board(get_conn(), area))


@app.get("/api/loss-estimate")
def loss_estimate(days: int = 30, area: str | None = None):
    """Downtime translated into barrels/USD under stated assumptions."""
    with db.CONN_LOCK:
        return _normalize(ops_tools.production_loss(get_conn(), days=max(1, min(days, 730)),
                                                    area_id=area))


def _normalize(res):
    return res if "text" in res else dict(res, text=res.pop("answer_md"))


@app.on_event("startup")
def startup():
    conn = get_conn()
    n_wells = conn.execute("SELECT COUNT(*) c FROM wells").fetchone()["c"]
    if n_wells == 0:
        db.ingest()
    # datasets visitors uploaded in earlier sessions stay merged
    for root in _manifest_load():
        if Path(root).exists():
            db.ingest(data_dirs=[Path(root)])
    _bump_today(conn)
    # a visitor-connected LLM key survives restarts, unless the deployment
    # owner set one in the environment (env wins)
    if config.LLM_SOURCE == "none" and config.LLM_SETTINGS_PATH.exists():
        try:
            saved = json.loads(config.LLM_SETTINGS_PATH.read_text(encoding="utf-8"))
            if saved.get("base_url") and saved.get("model"):
                config.LLM_BASE_URL = saved["base_url"]
                config.LLM_MODEL = saved["model"]
                config.LLM_API_KEY = saved.get("api_key", "")
                config.LLM_SOURCE = "ui"
        except (json.JSONDecodeError, OSError):
            pass


# --- bring-your-own-key LLM ----------------------------------------------------
def _mask(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 12:
        return "••••"
    return f"{key[:6]}…{key[-4:]}"


class LLMIn(BaseModel):
    provider: str = "custom"
    base_url: str
    model: str
    api_key: str = ""


def _llm_status():
    return {"configured": bool(config.LLM_BASE_URL and config.LLM_MODEL),
            "provider": getattr(config, "_llm_provider", "custom"),
            "base_url": config.LLM_BASE_URL, "model": config.LLM_MODEL,
            "key_masked": _mask(config.LLM_API_KEY), "source": config.LLM_SOURCE}


@app.get("/api/llm")
def llm_status():
    """Current AI-layer status. The key itself never leaves the server."""
    return _llm_status()


@app.post("/api/llm")
def llm_connect(request: Request, body: LLMIn):
    """Connect a visitor's own OpenAI-compatible key at runtime.

    Honest scope, stated in the UI too: the key enables the language layer
    (natural phrasing of answers). Every number, id and citation still comes
    from the deterministic engine — a weak or lying model cannot corrupt an
    answer, it can only make it read worse.
    """
    denied = guard_writes(request)
    if denied:
        return denied
    config.LLM_BASE_URL = body.base_url.strip().rstrip("/")
    config.LLM_MODEL = body.model.strip()
    config.LLM_API_KEY = body.api_key.strip()
    config._llm_provider = body.provider
    config.LLM_SOURCE = "ui"
    try:
        config.LLM_SETTINGS_PATH.write_text(json.dumps({
            "provider": body.provider, "base_url": config.LLM_BASE_URL,
            "model": config.LLM_MODEL, "api_key": config.LLM_API_KEY,
        }, indent=1), encoding="utf-8")
    except OSError:
        pass  # read-only deployment: key works for this session only
    return {"ok": True, **_llm_status()}


@app.delete("/api/llm")
def llm_disconnect(request: Request):
    denied = guard_writes(request)
    if denied:
        return denied
    if config.LLM_SOURCE == "env":
        return JSONResponse(status_code=400, content={
            "error": "this deployment provides its key via environment — contact the owner"})
    config.LLM_BASE_URL = config.LLM_MODEL = config.LLM_API_KEY = ""
    config.LLM_SOURCE = "none"
    try:
        config.LLM_SETTINGS_PATH.unlink(missing_ok=True)
    except OSError:
        pass
    return {"ok": True, **_llm_status()}


@app.post("/api/llm/test")
def llm_test(request: Request, body: LLMIn):
    """One tiny completion against the caller's settings, before saving."""
    denied = guard_writes(request)
    if denied:
        return denied
    try:
        from openai import OpenAI
        client = OpenAI(base_url=body.base_url.strip().rstrip("/"),
                        api_key=body.api_key.strip() or "x")
        t0 = time.time()
        resp = client.chat.completions.create(
            model=body.model.strip(),
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=8, timeout=20)
        text = (resp.choices[0].message.content or "").strip()
        return {"ok": True, "latency_ms": int((time.time() - t0) * 1000),
                "sample": text[:80]}
    except Exception as e:  # surface the provider's own error, never a 500
        return {"ok": False, "error": str(e)[:300]}


# --- user-supplied datasets ---------------------------------------------------
def _rm_tree_robust(path: Path) -> None:
    """shutil.rmtree with retries: on Windows, read-only bits and lingering
    file handles from a just-finished ingest otherwise leave folders behind."""
    import stat

    def _onerror(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass

    shutil.rmtree(path, onerror=_onerror)


def _manifest_load():
    if config.MANIFEST_PATH.exists():
        try:
            return json.loads(config.MANIFEST_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _manifest_save(roots):
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    config.MANIFEST_PATH.write_text(json.dumps(roots, indent=1), encoding="utf-8")


def _bump_today(conn):
    """'Today' tracks the newest data loaded, so a user's own dataset is asked
    about in its own present, not the demo dataset's."""
    row = conn.execute("SELECT MAX(insp_date) m FROM inspections").fetchone()
    if row and row["m"]:
        d = date.fromisoformat(row["m"]) + timedelta(days=1)
        if d > config.FIXED_TODAY:
            config.FIXED_TODAY = d


def _safe_extract(zip_bytes: bytes, dest: Path) -> None:
    """Extract member-by-member with a zip-slip guard (never trust archive paths)."""
    dest_res = dest.resolve()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for m in z.infolist():
            target = (dest / m.filename).resolve()
            try:
                target.relative_to(dest_res)
            except ValueError:
                raise ValueError(f"unsafe path in archive: {m.filename}")
            if m.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(m))


def _find_data_root(dest: Path) -> Path | None:
    """Accept a root containing fleet//assets directly, or one folder deeper."""
    if (dest / "fleet").exists() or (dest / "assets").exists():
        return dest
    for child in dest.iterdir():
        if child.is_dir() and ((child / "fleet").exists() or (child / "assets").exists()):
            return child
    return None


@app.post("/api/upload-dataset")
async def upload_dataset(request: Request, file: UploadFile = File(...),
                         name: str = Form("user-dataset")):
    """Add the uploader's own dataset (a zip of fleet/ + assets/) to the store.

    Ingestion is keyed by natural ids, so this MERGES: new wells appear next to
    the challenge data, re-uploads update what changed, nothing duplicates.
    The extracted folder is kept and re-ingested on startup, so user data
    survives restarts.
    """
    denied = guard_writes(request)
    if denied:
        return denied
    data = await file.read()
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        return JSONResponse(status_code=400, content={
            "error": f"file larger than {config.MAX_UPLOAD_MB} MB — for full-field "
                     f"exports use POST /api/ingest with a server-side directory"})
    if not zipfile.is_zipfile(io.BytesIO(data)):
        return JSONResponse(status_code=400, content={
            "error": "not a zip archive",
            "hint": "zip your dataset folder so it contains fleet/ and assets/"})
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name)[:40] or "dataset"
    dest = config.UPLOAD_DIR / f"{slug}-{int(time.time())}"
    try:
        config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        _safe_extract(data, dest)
    except ValueError as e:
        shutil.rmtree(dest, ignore_errors=True)
        return JSONResponse(status_code=400, content={"error": str(e)})
    root = _find_data_root(dest)
    if not root:
        shutil.rmtree(dest, ignore_errors=True)
        return JSONResponse(status_code=400, content={
            "error": "no fleet/ or assets/ folder found in the archive",
            "hint": "expected the challenge layout: fleet/ (areas, users, manuals, "
                    "sops) and assets/WELL-XXXX/ (metadata, inspections, ...)"})
    with db.CONN_LOCK:
        counts = db.ingest(data_dirs=[root])
        conn = get_conn()
        _bump_today(conn)
        wells = conn.execute("SELECT COUNT(*) c FROM wells").fetchone()["c"]
        areas = conn.execute("SELECT COUNT(*) c FROM areas").fetchone()["c"]
        manifest = [r for r in _manifest_load() if Path(r) != root]
        manifest.append(str(root))
        _manifest_save(manifest)
    return {"ok": True, "name": slug, "root": str(root), "counts": counts,
            "totals": {"wells": wells, "areas": areas, "today": config.today().isoformat()}}


@app.post("/api/reset-data")
def reset_data(request: Request):
    """Wipe everything (including uploaded datasets) and reload the challenge data."""
    denied = guard_writes(request)
    if denied:
        return denied
    with db.CONN_LOCK:
        conn = get_conn()
        for (tbl,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'").fetchall():
            conn.execute(f"DELETE FROM {tbl}")
        conn.commit()
        for root in _manifest_load():
            _rm_tree_robust(Path(root))
        _manifest_save([])
        config.FIXED_TODAY = config.FIXED_TODAY_ORIGINAL
        counts = db.ingest()
        _bump_today(conn)
    global _conn
    return {"ok": True, "counts": counts, "today": config.today().isoformat()}


class ChatIn(BaseModel):
    user_id: str | None = None
    user_name: str | None = None
    conversation_id: int | None = None
    message: str


@app.post("/api/chat")
def chat(body: ChatIn):
    conn = get_conn()
    user_id = body.user_id
    if not user_id and body.user_name:
        row = conn.execute("SELECT user_id FROM users WHERE name=?", (body.user_name,)).fetchone()
        user_id = row["user_id"] if row else None
    if not user_id:
        return JSONResponse(status_code=400, content={"error": "user_id or user_name required"})
    with db.CONN_LOCK:
        cid, envelope = agent.answer(conn, user_id, body.message, body.conversation_id)
    envelope = agent.llm_rephrase(envelope, body.message)
    return {"conversation_id": cid, "user_id": user_id, **envelope}


@app.get("/api/users")
def users():
    return [dict(r) for r in get_conn().execute(
        "SELECT user_id, name, role, team_id FROM users ORDER BY user_id")]


@app.get("/api/areas")
def areas():
    return [dict(r) for r in get_conn().execute("SELECT area_id, name FROM areas ORDER BY area_id")]


@app.get("/api/conversations")
def conversations(user_id: str):
    rows = get_conn().execute(
        "SELECT c.conversation_id, c.title, c.created_at, COUNT(m.msg_id) msgs "
        "FROM conversations c LEFT JOIN messages m ON m.conversation_id=c.conversation_id "
        "WHERE c.user_id=? GROUP BY c.conversation_id ORDER BY c.created_at DESC",
        (user_id,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int):
    rows = get_conn().execute(
        "SELECT role, content, envelope_json, created_at FROM messages "
        "WHERE conversation_id=? ORDER BY msg_id", (conversation_id,)).fetchall()
    out = []
    for r in rows:
        m = {"role": r["role"], "content": r["content"], "created_at": r["created_at"]}
        if r["envelope_json"]:
            m["envelope"] = json.loads(r["envelope_json"])
        out.append(m)
    return out


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
    conn.execute("DELETE FROM conversations WHERE conversation_id=?", (conversation_id,))
    conn.commit()
    return {"ok": True}


@app.post("/api/claims/{claim_id}/confirm")
def confirm_claim(claim_id: int):
    memory.confirm_claim(get_conn(), claim_id)
    return {"ok": True, "claim_id": claim_id, "status": "confirmed"}


@app.post("/api/ingest")
def ingest(request: Request, dirs: list[str] | None = None):
    """(Re)load data roots. Used in the final 2 hours to add the test dataset."""
    denied = guard_writes(request)
    if denied:
        return denied
    counts = db.ingest(data_dirs=[Path(d) for d in dirs] if dirs else None)
    global _conn
    _conn = None  # reopen against the refreshed DB
    return {"ok": True, "counts": counts, "data_dirs": [str(d) for d in config.DATA_DIRS]}


@app.get("/api/dashboard")
def dashboard():
    """Fleet-wide analytics for the dashboard view (all deterministic)."""
    with db.CONN_LOCK:
        return tools.dashboard_data(get_conn())


@app.get("/api/health")
def health():
    conn = get_conn()
    return {"ok": True, "wells": conn.execute("SELECT COUNT(*) c FROM wells").fetchone()["c"],
            "inspections": conn.execute("SELECT COUNT(*) c FROM inspections").fetchone()["c"],
            "today": config.today().isoformat()}

@app.get("/api/evidence/{item_id:path}")
def evidence_detail(item_id: str):
    conn = get_conn()
    clean_id = item_id.strip()
    # 1. Inspection
    r = conn.execute(
        "SELECT i.*, u.name as inspector_name, w.name as well_name, w.well_type "
        "FROM inspections i "
        "LEFT JOIN users u ON u.user_id = i.inspector_user_id "
        "LEFT JOIN wells w ON w.asset_id = i.asset_id "
        "WHERE i.inspection_id = ?", (clean_id,)).fetchone()
    if r:
        d = dict(r)
        corrs = [dict(c) for c in conn.execute(
            "SELECT * FROM corrections WHERE inspection_id=? AND active=1", (clean_id,)).fetchall()]
        notes = [dict(n) for n in conn.execute(
            "SELECT * FROM context_notes WHERE inspection_id=?", (clean_id,)).fetchall()]
        return {"found": True, "category": "inspection", "data": d, "corrections": corrs, "notes": notes}

    # 2. Context note
    r = conn.execute(
        "SELECT c.*, u.name as author_name FROM context_notes c "
        "LEFT JOIN users u ON u.user_id = c.author_user_id "
        "WHERE c.note_id = ?", (clean_id,)).fetchone()
    if r:
        return {"found": True, "category": "note", "data": dict(r)}

    # 3. Maintenance record
    r = conn.execute(
        "SELECT m.*, u.name as technician_name FROM maintenance m "
        "LEFT JOIN users u ON u.user_id = m.technician_user_id "
        "WHERE m.maintenance_id = ?", (clean_id,)).fetchone()
    if r:
        d = dict(r)
        rep = conn.execute("SELECT * FROM reports WHERE maintenance_id=?", (clean_id,)).fetchone()
        return {"found": True, "category": "maintenance", "data": d, "report": dict(rep) if rep else None}

    # 4. Regulator event
    r = conn.execute("SELECT * FROM reg_events WHERE event_id = ?", (clean_id,)).fetchone()
    if r:
        return {"found": True, "category": "regulatory_event", "data": dict(r)}

    # 5. SOP or Manual Doc
    r = conn.execute("SELECT doc_id, path, title, kind, well_type, text FROM docs WHERE doc_id = ?", (clean_id,)).fetchone()
    if r:
        return {"found": True, "category": "document", "data": dict(r)}

    # 6. Report path
    r = conn.execute("SELECT * FROM reports WHERE report_path = ?", (clean_id,)).fetchone()
    if r:
        return {"found": True, "category": "report", "data": dict(r)}

    return {"found": False, "item_id": item_id}


@app.get("/api/memory")
def get_memory():
    conn = get_conn()
    corrections = [dict(r) for r in conn.execute(
        "SELECT c.*, u.name as author_name FROM corrections c "
        "LEFT JOIN users u ON u.user_id = c.author_user_id "
        "ORDER BY c.correction_id DESC").fetchall()]
    shared_notes = [dict(r) for r in conn.execute(
        "SELECT s.*, u.name as author_name FROM shared_notes s "
        "LEFT JOIN users u ON u.user_id = s.author_user_id "
        "ORDER BY s.shared_id DESC").fetchall()]
    user_rules = [dict(r) for r in conn.execute(
        "SELECT ur.*, u.name as user_name FROM user_rules ur "
        "LEFT JOIN users u ON u.user_id = ur.user_id "
        "ORDER BY ur.rule_id DESC").fetchall()]
    claims = [dict(r) for r in conn.execute(
        "SELECT cl.*, u.name as user_name FROM claims cl "
        "LEFT JOIN users u ON u.user_id = cl.user_id "
        "ORDER BY cl.claim_id DESC").fetchall()]
    return {
        "corrections": corrections,
        "shared_notes": shared_notes,
        "user_rules": user_rules,
        "claims": claims
    }


# Static frontend (zero-build single-page app)
_ui = Path(__file__).resolve().parents[2] / "frontend"
if _ui.exists():
    app.mount("/", StaticFiles(directory=str(_ui), html=True), name="ui")
