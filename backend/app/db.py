"""Storage layer: SQLite locally, MySQL (Aiven/any) in cloud deployments.

The whole query layer speaks a small, common SQL dialect with `?`
placeholders and `INSERT OR REPLACE`. Locally that runs on SQLite; when
MYSQL_URI is configured the same statements run on MySQL through a thin
translator, so the cloud keeps every answer identical while gaining real
24/7 persistence (uploads, memory and corrections survive restarts).

Ingestion is idempotent either way: every row is keyed by its natural id.
"""
import json
import re
import sqlite3
import threading
import time
from datetime import date, datetime
from pathlib import Path

from . import config

# Serialises access to the shared connection across request threads.
CONN_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs(
  doc_id TEXT PRIMARY KEY, path TEXT, title TEXT, kind TEXT, well_type TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS areas(
  area_id TEXT PRIMARY KEY, name TEXT, team_id TEXT, center_lat REAL, center_lon REAL, asset_ids_json TEXT);
CREATE TABLE IF NOT EXISTS teams(team_id TEXT PRIMARY KEY, name TEXT, lead_user_id TEXT);
CREATE TABLE IF NOT EXISTS users(user_id TEXT PRIMARY KEY, name TEXT, role TEXT, team_id TEXT);
CREATE TABLE IF NOT EXISTS wells(
  asset_id TEXT PRIMARY KEY, name TEXT, well_type TEXT, area_id TEXT, area_name TEXT, team_id TEXT,
  lat REAL, lon REAL, installed_on TEXT, recorded_status TEXT, in_charge_user_id TEXT, equipment_json TEXT,
  type_history_json TEXT, team_history_json TEXT, decommissioned_on TEXT);
CREATE TABLE IF NOT EXISTS inspections(
  inspection_id TEXT PRIMARY KEY, asset_id TEXT, inspected_at TEXT, insp_date TEXT,
  inspector_user_id TEXT, method TEXT, ambient_temp_c REAL, wellhead_temp_c REAL,
  spill_detected INTEGER, spill_area_pct REAL, spill_est_volume_bbl REAL, notes TEXT,
  recorded_at TEXT, pressure_psi REAL);
CREATE INDEX IF NOT EXISTS ix_insp_asset ON inspections(asset_id, insp_date);
CREATE TABLE IF NOT EXISTS maintenance(
  maintenance_id TEXT PRIMARY KEY, asset_id TEXT, started_at TEXT, start_date TEXT, completed_at TEXT,
  maintenance_type TEXT, equipment_kind TEXT, issue TEXT, action_taken TEXT, technician_user_id TEXT,
  downtime_hours REAL, cost_labor REAL, cost_parts REAL, cost_total REAL,
  triggered_by_inspection_id TEXT, report_file TEXT, recorded_at TEXT, cost_revision_json TEXT);
CREATE INDEX IF NOT EXISTS ix_mnt_asset ON maintenance(asset_id, start_date);
CREATE TABLE IF NOT EXISTS reg_events(
  event_id TEXT PRIMARY KEY, asset_id TEXT, date TEXT, agency TEXT, event_type TEXT,
  protocol_id TEXT, related_inspection_id TEXT, hours_to_report REAL, detail TEXT,
  fine_usd REAL, status TEXT);
CREATE TABLE IF NOT EXISTS context_notes(
  note_id TEXT PRIMARY KEY, asset_id TEXT, created_at TEXT, author_user_id TEXT,
  note_type TEXT, inspection_id TEXT, text TEXT, valid_from TEXT, valid_to TEXT,
  field TEXT, original_value TEXT, corrected_value TEXT);
CREATE TABLE IF NOT EXISTS reports(
  report_path TEXT PRIMARY KEY, asset_id TEXT, maintenance_id TEXT, text TEXT,
  containment_hours REAL, spill_class TEXT, rca_action_required INTEGER,
  parts_installed TEXT, follow_up TEXT);
CREATE TABLE IF NOT EXISTS conversations(
  conversation_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, title TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS messages(
  msg_id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER, user_id TEXT, role TEXT,
  content TEXT, envelope_json TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS corrections(
  correction_id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, inspection_id TEXT, asset_id TEXT,
  well_type TEXT, field TEXT, original_value TEXT, corrected_value TEXT, reason TEXT,
  author_user_id TEXT, created_at TEXT, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS shared_notes(
  shared_id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id TEXT, text TEXT, author_user_id TEXT,
  created_at TEXT, kind TEXT DEFAULT 'operator_note');
CREATE TABLE IF NOT EXISTS claims(
  claim_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, asset_id TEXT, text TEXT,
  status TEXT DEFAULT 'unconfirmed', conflict_json TEXT, conversation_id INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS user_rules(
  rule_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, rule_kind TEXT, scope TEXT,
  scope_value TEXT, value TEXT, text TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS entity_mentions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, conversation_id INTEGER, turn_id INTEGER,
  entity_id TEXT, entity_type TEXT, mentioned_at TEXT);
"""

# MySQL counterpart: id columns sized for keys/indexes, long free text as
# MEDIUMTEXT, dates kept as VARCHAR so string comparisons behave like SQLite.
SCHEMA_MYSQL = """
CREATE TABLE IF NOT EXISTS docs(
  doc_id VARCHAR(64) PRIMARY KEY, path VARCHAR(255), title VARCHAR(255), kind VARCHAR(32),
  well_type VARCHAR(32), text MEDIUMTEXT);
CREATE TABLE IF NOT EXISTS areas(
  area_id VARCHAR(64) PRIMARY KEY, name VARCHAR(255), team_id VARCHAR(64),
  center_lat DOUBLE, center_lon DOUBLE, asset_ids_json MEDIUMTEXT);
CREATE TABLE IF NOT EXISTS teams(
  team_id VARCHAR(64) PRIMARY KEY, name VARCHAR(255), lead_user_id VARCHAR(64));
CREATE TABLE IF NOT EXISTS users(
  user_id VARCHAR(64) PRIMARY KEY, name VARCHAR(255), role VARCHAR(64), team_id VARCHAR(64));
CREATE TABLE IF NOT EXISTS wells(
  asset_id VARCHAR(64) PRIMARY KEY, name VARCHAR(255), well_type VARCHAR(32), area_id VARCHAR(64),
  area_name VARCHAR(255), team_id VARCHAR(64), lat DOUBLE, lon DOUBLE, installed_on VARCHAR(32),
  recorded_status VARCHAR(32), in_charge_user_id VARCHAR(64), equipment_json MEDIUMTEXT,
  type_history_json MEDIUMTEXT, team_history_json MEDIUMTEXT, decommissioned_on VARCHAR(32));
CREATE TABLE IF NOT EXISTS inspections(
  inspection_id VARCHAR(64) PRIMARY KEY, asset_id VARCHAR(64), inspected_at VARCHAR(32),
  insp_date VARCHAR(32), inspector_user_id VARCHAR(64), method VARCHAR(32),
  ambient_temp_c DOUBLE, wellhead_temp_c DOUBLE, spill_detected INT, spill_area_pct DOUBLE,
  spill_est_volume_bbl DOUBLE, notes VARCHAR(512), recorded_at VARCHAR(32), pressure_psi DOUBLE);
CREATE TABLE IF NOT EXISTS maintenance(
  maintenance_id VARCHAR(64) PRIMARY KEY, asset_id VARCHAR(64), started_at VARCHAR(32),
  start_date VARCHAR(32), completed_at VARCHAR(32), maintenance_type VARCHAR(32),
  equipment_kind VARCHAR(64), issue VARCHAR(255), action_taken VARCHAR(255),
  technician_user_id VARCHAR(64), downtime_hours DOUBLE, cost_labor DOUBLE, cost_parts DOUBLE,
  cost_total DOUBLE, triggered_by_inspection_id VARCHAR(64), report_file VARCHAR(255),
  recorded_at VARCHAR(32), cost_revision_json MEDIUMTEXT);
CREATE TABLE IF NOT EXISTS reg_events(
  event_id VARCHAR(64) PRIMARY KEY, asset_id VARCHAR(64), date VARCHAR(32), agency VARCHAR(128),
  event_type VARCHAR(64), protocol_id VARCHAR(32), related_inspection_id VARCHAR(64),
  hours_to_report DOUBLE, detail VARCHAR(512), fine_usd DOUBLE, status VARCHAR(32));
CREATE TABLE IF NOT EXISTS context_notes(
  note_id VARCHAR(64) PRIMARY KEY, asset_id VARCHAR(64), created_at VARCHAR(32),
  author_user_id VARCHAR(64), note_type VARCHAR(32), inspection_id VARCHAR(64),
  text MEDIUMTEXT, valid_from VARCHAR(32), valid_to VARCHAR(32), field VARCHAR(64),
  original_value VARCHAR(255), corrected_value VARCHAR(255));
CREATE TABLE IF NOT EXISTS reports(
  report_path VARCHAR(255) PRIMARY KEY, asset_id VARCHAR(64), maintenance_id VARCHAR(64),
  text MEDIUMTEXT, containment_hours DOUBLE, spill_class VARCHAR(32),
  rca_action_required INT, parts_installed MEDIUMTEXT, follow_up MEDIUMTEXT);
CREATE TABLE IF NOT EXISTS conversations(
  conversation_id INT PRIMARY KEY AUTO_INCREMENT, user_id VARCHAR(64), title VARCHAR(255),
  created_at VARCHAR(32));
CREATE TABLE IF NOT EXISTS messages(
  msg_id INT PRIMARY KEY AUTO_INCREMENT, conversation_id INT, user_id VARCHAR(64),
  role VARCHAR(16), content MEDIUMTEXT, envelope_json MEDIUMTEXT, created_at VARCHAR(32));
CREATE TABLE IF NOT EXISTS corrections(
  correction_id INT PRIMARY KEY AUTO_INCREMENT, kind VARCHAR(32), inspection_id VARCHAR(64),
  asset_id VARCHAR(64), well_type VARCHAR(32), field VARCHAR(64), original_value VARCHAR(255),
  corrected_value VARCHAR(255), reason MEDIUMTEXT, author_user_id VARCHAR(64),
  created_at VARCHAR(32), active INT DEFAULT 1);
CREATE TABLE IF NOT EXISTS shared_notes(
  shared_id INT PRIMARY KEY AUTO_INCREMENT, asset_id VARCHAR(64), text MEDIUMTEXT,
  author_user_id VARCHAR(64), created_at VARCHAR(32), kind VARCHAR(32) DEFAULT 'operator_note');
CREATE TABLE IF NOT EXISTS claims(
  claim_id INT PRIMARY KEY AUTO_INCREMENT, user_id VARCHAR(64), asset_id VARCHAR(64),
  text MEDIUMTEXT, status VARCHAR(32) DEFAULT 'unconfirmed', conflict_json MEDIUMTEXT,
  conversation_id INT, created_at VARCHAR(32));
CREATE TABLE IF NOT EXISTS user_rules(
  rule_id INT PRIMARY KEY AUTO_INCREMENT, user_id VARCHAR(64), rule_kind VARCHAR(64),
  scope VARCHAR(32), scope_value VARCHAR(64), value VARCHAR(255), text MEDIUMTEXT,
  created_at VARCHAR(32));
CREATE TABLE IF NOT EXISTS entity_mentions(
  id INT PRIMARY KEY AUTO_INCREMENT, user_id VARCHAR(64), conversation_id INT, turn_id INT,
  entity_id VARCHAR(64), entity_type VARCHAR(32), mentioned_at VARCHAR(32));
"""


def _translate_sql(sql: str) -> str:
    """The few SQLite-isms the app uses, mapped to MySQL equivalents."""
    if "?" in sql:
        sql = sql.replace("?", "%s")
    if "INSERT OR REPLACE INTO" in sql:
        sql = sql.replace("INSERT OR REPLACE INTO", "REPLACE INTO")
    if "INSERT OR IGNORE INTO" in sql:
        sql = sql.replace("INSERT OR IGNORE INTO", "INSERT IGNORE INTO")
    if "PRAGMA journal_mode" in sql:
        sql = "SELECT 1"
    m = re.match(r"\s*PRAGMA table_info\((\w+)\)", sql)
    if m:
        sql = ("SELECT COLUMN_NAME AS name FROM information_schema.COLUMNS "
               "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='%s' ORDER BY ORDINAL_POSITION"
               % m.group(1))
    if "sqlite_master" in sql:
        sql = sql.replace("SELECT name FROM sqlite_master",
                          "SELECT TABLE_NAME AS name FROM information_schema.tables")
        sql = sql.replace("FROM sqlite_master", "FROM information_schema.tables")
    return sql


class _MyCursor:
    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur.fetchall())

    @property
    def lastrowid(self):
        return self._cur.lastrowid


class _MyConn:
    """The sqlite3.Connection surface the app relies on, backed by PyMySQL."""

    def __init__(self, uri: str):
        import pymysql
        self._uri = uri
        from urllib.parse import urlparse, unquote, parse_qs
        u = urlparse(uri)
        q = parse_qs(u.query)
        kwargs = dict(
            host=u.hostname, port=u.port or 3306, user=unquote(u.username or ""),
            password=unquote(u.password or ""), database=(u.path or "/").lstrip("/") or "defaultdb",
            charset="utf8mb4", autocommit=False, read_timeout=600, write_timeout=600,
            cursorclass=pymysql.cursors.DictCursor,
        )
        ssl_mode = (q.get("ssl-mode") or q.get("ssl_mode") or [None])[0]
        try:
            self._conn = pymysql.connect(ssl_mode=ssl_mode, **kwargs)
        except TypeError:  # older PyMySQL without ssl_mode
            self._conn = pymysql.connect(ssl={"ssl": ssl_mode is not None}, **kwargs)
        self._conn.ping(reconnect=True)
        # SQLite is permissive; match it so GROUP BY / loose typing behave the same
        c = self._conn.cursor()
        c.execute("SET SESSION sql_mode='NO_ENGINE_SUBSTITUTION'")
        c.close()
        self._conn.commit()

    def _hard_reconnect(self):
        import pymysql
        try:
            self._conn.close()
        except Exception:
            pass
        last = None
        for _ in range(6):
            try:
                self.__init__(self._uri)
                return
            except Exception as e:  # Aiven restarts / network blips happen
                last = e
                time.sleep(2)
        raise last

    def _is_conn_error(self, e):
        s = str(e)
        t = type(e).__name__
        return t in ("InterfaceError", "OperationalError") and any(
            k in s for k in ("(0, '')", "2006", "2013", "Lost connection",
                             "gone away", "Connection refused", "Connection reset"))

    def execute(self, sql, args=()):
        last = None
        for attempt in (1, 2):
            try:
                self._conn.ping(reconnect=True)
                cur = self._conn.cursor()
                cur.execute(_translate_sql(sql), args)
                return _MyCursor(cur)
            except Exception as e:
                last = e
                if attempt == 1 and self._is_conn_error(e):
                    self._hard_reconnect()
                    continue
                raise
        raise last

    def executemany(self, sql, seq):
        last = None
        for attempt in (1, 2):
            try:
                self._conn.ping(reconnect=True)
                cur = self._conn.cursor()
                cur.executemany(_translate_sql(sql), list(seq))
                return _MyCursor(cur)
            except Exception as e:
                last = e
                if attempt == 1 and self._is_conn_error(e):
                    self._hard_reconnect()
                    continue
                raise
        raise last

    def executescript(self, script):
        for stmt in [s.strip() for s in script.split(";") if s.strip()]:
            self.execute(stmt)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:
            pass

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def cursor(self):
        return self.execute("SELECT 1")


def connect(path=None):
    """SQLite by default; MySQL when MYSQL_URI is configured (db_path is a
    SQLite-only concept and is ignored there)."""
    if getattr(config, "MYSQL_URI", ""):
        return _MyConn(config.MYSQL_URI)
    conn = sqlite3.connect(path or config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_schema(conn) -> None:
    if isinstance(conn, _MyConn):
        conn.executescript(SCHEMA_MYSQL)
        # MySQL has no CREATE INDEX IF NOT EXISTS — tolerate duplicates
        for name, sql in [
            ("ix_insp_asset", "CREATE INDEX ix_insp_asset ON inspections(asset_id, insp_date)"),
            ("ix_mnt_asset", "CREATE INDEX ix_mnt_asset ON maintenance(asset_id, start_date)"),
        ]:
            try:
                conn.execute(sql)
                conn.commit()
            except Exception as e:
                if "1061" not in str(e) and "Duplicate key name" not in str(e):
                    raise
        conn.commit()
        return
    conn.executescript(SCHEMA)
    # lightweight migrations for DBs created before a column existed
    for table, col, coltype in [
        ("entity_mentions", "turn_id", "INTEGER"),
        ("wells", "type_history_json", "TEXT"),
        ("wells", "team_history_json", "TEXT"),
        ("wells", "decommissioned_on", "TEXT"),
        ("inspections", "recorded_at", "TEXT"),
        ("inspections", "pressure_psi", "REAL"),
        ("maintenance", "recorded_at", "TEXT"),
        ("maintenance", "cost_revision_json", "TEXT"),
        ("context_notes", "field", "TEXT"),
        ("context_notes", "original_value", "TEXT"),
        ("context_notes", "corrected_value", "TEXT"),
        ("reports", "parts_installed", "TEXT"),
        ("reports", "follow_up", "TEXT"),
    ]:
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
    conn.commit()


def _read_jsonl(path: Path):
    """One JSON object per line; a single JSON array also works, since users
    preparing their first export get this wrong constantly."""
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, list):
                yield from obj
            else:
                yield obj


class _Batch:
    """Buffers rows and flushes with executemany so a 125k-record ingest is a
    few hundred network round trips instead of 125k."""

    def __init__(self, conn, sql, size=2000):
        self.conn, self.sql, self.size, self.rows = conn, sql, size, []
        self.count = 0

    def add(self, row):
        self.rows.append(row)
        self.count += 1
        if len(self.rows) >= self.size:
            self.flush()

    def flush(self):
        if self.rows:
            self.conn.executemany(self.sql, self.rows)
            self.rows = []


def ingest(data_dirs=None, db_path=None) -> dict:
    """Load every data root into the store. Idempotent (INSERT OR REPLACE)."""
    dirs = data_dirs or config.DATA_DIRS
    mysql_mode = bool(getattr(config, "MYSQL_URI", ""))
    old = config.DB_PATH
    if db_path and not mysql_mode:
        config.DB_PATH = db_path
    try:
        conn = connect()
        init_schema(conn)
        counts = {}
        for root in dirs:
            root = Path(root)
            _ingest_fleet(conn, root, counts)
            _ingest_assets(conn, root, counts)
        conn.commit()

        # Auto-detect "today" from the latest inspection date
        row = conn.execute("SELECT MAX(insp_date) as latest FROM inspections").fetchone()
        if row and row["latest"]:
            latest = datetime.strptime(row["latest"][:10], "%Y-%m-%d").date()
            if latest > config.FIXED_TODAY:
                config.FIXED_TODAY = latest + __import__("datetime").timedelta(days=1)
            elif latest >= date(2027, 1, 1):
                config.FIXED_TODAY = date(2027, 1, 15)

        conn.close()
        return counts
    finally:
        config.DB_PATH = old


def _ingest_fleet(conn, root: Path, counts: dict) -> None:
    fleet = root / "fleet"
    if not fleet.exists():
        return
    areas_file = fleet / "areas.json"
    if not areas_file.exists():
        return
    areas = json.loads(areas_file.read_text(encoding="utf-8"))
    b_areas = _Batch(conn, "INSERT OR REPLACE INTO areas VALUES(?,?,?,?,?,?)")
    b_teams = _Batch(conn, "INSERT OR REPLACE INTO teams VALUES(?,?,?)")
    for a in areas["areas"]:
        b_areas.add((a["area_id"], a["name"], a["team_id"], a["center"]["lat"],
                     a["center"]["lon"], json.dumps(a["asset_ids"])))
    for t in areas.get("teams", []):
        b_teams.add((t["team_id"], t["name"], t.get("lead_user_id")))
    users_file = fleet / "users.json"
    n_users = 0
    if users_file.exists():
        b_users = _Batch(conn, "INSERT OR REPLACE INTO users VALUES(?,?,?,?)")
        for u in json.loads(users_file.read_text(encoding="utf-8"))["users"]:
            b_users.add((u["user_id"], u["name"], u["role"], u["team_id"]))
            n_users += 1
        b_users.flush()
    b_areas.flush()
    b_teams.flush()
    counts["users"] = counts.get("users", 0) + len(areas["areas"]) + n_users

    wt_dir = fleet / "well-types"
    if wt_dir.exists():
        for md in sorted(wt_dir.glob("*.md")):
            _store_doc(conn, md, kind="manual", well_type=md.stem)
    sops_dir = fleet / "sops"
    if sops_dir.exists():
        for md in sorted(sops_dir.glob("*.md")):
            _store_doc(conn, md, kind="sop", well_type=None)
    conn.commit()


def _store_doc(conn, md: Path, kind: str, well_type) -> None:
    text = md.read_text(encoding="utf-8")
    title = text.splitlines()[0].lstrip("# ").strip() if text else md.stem
    conn.execute("INSERT OR REPLACE INTO docs VALUES(?,?,?,?,?,?)",
                 (md.stem, str(md), title, kind, well_type, text))


def _ingest_assets(conn, root: Path, counts: dict) -> None:
    assets = root / "assets"
    if not assets.exists():
        return
    area_rows = {r["area_id"]: r["name"] for r in conn.execute("SELECT area_id, name FROM areas")}
    n_insp = n_mnt = 0
    b_wells = _Batch(conn, "INSERT OR REPLACE INTO wells VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
    b_insp = _Batch(conn, "INSERT OR REPLACE INTO inspections VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
    b_mnt = _Batch(conn, "INSERT OR REPLACE INTO maintenance VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
    b_reg = _Batch(conn, "INSERT OR REPLACE INTO reg_events VALUES(?,?,?,?,?,?,?,?,?,?,?)")
    b_ctx = _Batch(conn, "INSERT OR REPLACE INTO context_notes VALUES(?,?,?,?,?,?,?,?,?,?,?,?)")
    for wdir in sorted(assets.iterdir()):
        if not wdir.is_dir():
            continue
        meta_file = wdir / "metadata.json"
        if not meta_file.exists():
            continue
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        loc = meta.get("location") or {}
        b_wells.add(
            (meta["asset_id"], meta.get("name"), meta.get("well_type"), meta.get("area_id"),
             area_rows.get(meta.get("area_id")), meta.get("team_id"), loc.get("lat"), loc.get("lon"),
             meta.get("installed_on"), meta.get("recorded_status"), meta.get("in_charge_user_id"),
             json.dumps(meta.get("equipment", [])),
             json.dumps(meta.get("type_history")) if meta.get("type_history") else None,
             json.dumps(meta.get("team_history")) if meta.get("team_history") else None,
             meta.get("decommissioned_on")),
        )
        insp_file = wdir / "inspections.jsonl"
        if insp_file.exists():
            for insp in _read_jsonl(insp_file):
                b_insp.add(
                    (insp["inspection_id"], insp["asset_id"], insp["inspected_at"],
                     insp["inspected_at"][:10], insp.get("inspector_user_id"), insp.get("method"),
                     insp.get("ambient_temp_c"), insp.get("wellhead_temp_c"),
                     1 if insp.get("spill_detected") else 0, insp.get("spill_area_pct"),
                     insp.get("spill_est_volume_bbl"), insp.get("notes") or "",
                     insp.get("recorded_at"), insp.get("pressure_psi")),
                )
                n_insp += 1
        mnt_file = wdir / "maintenance.jsonl"
        if mnt_file.exists():
            for m in _read_jsonl(mnt_file):
                cost = m.get("cost_usd") or {}
                b_mnt.add(
                    (m["maintenance_id"], m["asset_id"], m.get("started_at"),
                     (m.get("started_at") or "")[:10] or None, m.get("completed_at"),
                     m.get("maintenance_type"), m.get("equipment_kind"), m.get("issue"),
                     m.get("action_taken"), m.get("technician_user_id"), m.get("downtime_hours"),
                     cost.get("labor"), cost.get("parts"), cost.get("total"),
                     m.get("triggered_by_inspection_id"), m.get("report_file"),
                     m.get("recorded_at"),
                     json.dumps(m.get("cost_revision")) if m.get("cost_revision") else None),
                )
                n_mnt += 1
        regf = wdir / "regulatory-events.jsonl"
        if regf.exists():
            for e in _read_jsonl(regf):
                b_reg.add(
                    (e["event_id"], e["asset_id"], e["date"], e.get("agency"), e.get("event_type"),
                     e.get("protocol_id"), e.get("related_inspection_id"), e.get("hours_to_report"),
                     e.get("detail"), e.get("fine_usd"), e.get("status")),
                )
        ctxf = wdir / "context.jsonl"
        if ctxf.exists():
            for c in _read_jsonl(ctxf):
                insp_id = c.get("inspection_id")
                if not insp_id and c.get("text"):
                    mt = re.search(r"INS-\d{4}-\d{3,4}", c["text"])
                    if mt and c.get("note_type") in ("correction", "data_correction"):
                        insp_id = mt.group(0)
                b_ctx.add(
                    (c["note_id"], c["asset_id"], c.get("created_at"), c.get("author_user_id"),
                     c.get("note_type"), insp_id, c.get("text"),
                     c.get("valid_from"), c.get("valid_to"),
                     c.get("field"), c.get("original_value"),
                     json.dumps(c["corrected_value"]) if "corrected_value" in c and not isinstance(c.get("corrected_value"), str) else c.get("corrected_value")),
                )
        repdir = wdir / "maintenance-reports"
        if repdir.exists():
            for rep in sorted(repdir.glob("*.md")):
                _store_report(conn, wdir.name, rep)
    b_wells.flush()
    b_insp.flush()
    b_mnt.flush()
    b_reg.flush()
    b_ctx.flush()
    counts.setdefault("inspections", 0)
    counts["inspections"] += n_insp
    counts["maintenance"] = counts.get("maintenance", 0) + n_mnt
    conn.commit()


def _store_report(conn, asset_id: str, rep: Path) -> None:
    from .domain import parse_report

    text = rep.read_text(encoding="utf-8")
    parsed = parse_report(text)
    rel = f"maintenance-reports/{rep.name}"
    conn.execute("INSERT OR REPLACE INTO reports VALUES(?,?,?,?,?,?,?,?,?)",
                 (rel, asset_id, parsed["maintenance_id"], text, parsed["containment_hours"],
                  parsed["spill_class"], parsed["rca_action_required"],
                  parsed.get("parts_installed"), parsed.get("follow_up")))
