"""Domain rules, derived values and corrections.

Every rule here carries a citation to the document it comes from. Thresholds are
parsed from the well-type manuals at query time so the system still works on
unseen data (e.g. a new well type in the test dataset) instead of relying on
hard-coded numbers alone.
"""
import re
import sqlite3
from datetime import date, datetime, timedelta

from . import config

# --- Fallback constants (each cites its source document) -------------------
THRESHOLDS = {"T200": 15.0, "T350": 20.0, "T500": 25.0}  # manuals: OM-T200 9.3, OM-T350 3, OM-T500 3
SPILL_REPORTABLE_BBL = 5.0                          # SOP-SR 3/4 (SR-01)
SR01_NOTICE_HOURS = 24.0                            # SOP-SR SR-01
SR01_MAJOR_HOURS = 2.0                              # SOP-SR SR-01 (major >= 25 bbl)
SR02_CONTAIN_HOURS = 4.0                            # SOP-SR SR-02
SR03_VERIFY_DAYS = 60                               # SOP-SR SR-03
RC04_RESPONSE_DAYS = 30                             # SOP-RC RC-04
RCA_COUNT = 3                                       # OM-T200 10
RCA_COUNT_ESP = 2                                   # OM-T500 7 (ESP: 2 events trigger RCA)
RCA_WINDOW_DAYS = 365
HSE_NOTICE_MODERATE_HOURS = 72.0                    # SOP-SR 3
TEMP_ALARM = {"T200": 85.0, "T350": 95.0, "T500": 95.0}  # OM-T200 9.4, OM-T350 4, OM-T500 4
SHUTIN_SPILL_AREA_PCT = 5.0                         # OM-T200 9.5
OPS1_GAS_RESPONSE_HOURS_BEFORE_2027 = 24.0          # SOP-OPS OPS-1
OPS1_GAS_RESPONSE_HOURS_FROM_2027 = 12.0            # SOP-OPS OPS-1 (from 1 Jan 2027)
OPS5_FREEZE_TEMP_C = -5.0                           # SOP-OPS OPS-5
OPS5_HEAT_TRACE_DAYS = 7                            # SOP-OPS OPS-5

CITES = {
    "threshold": "Well-type manual (OM-T200 9.3 / OM-T350 3 / OM-T500 3)",
    "sr01": "Spill Response SOP, SR-01",
    "sr02": "Spill Response SOP, SR-02",
    "sr03": "Spill Response SOP, SR-03",
    "rc02": "Regulatory Compliance SOP, RC-02",
    "rc04": "Regulatory Compliance SOP, RC-04",
    "rca": "Well-type manual section 10 / OM-T500 section 7",
    "downtime": "Dataset Guide (one inspection = 7 days of downtime)",
    "ops1": "Operations SOP Rev 2, OPS-1",
    "ops2": "Operations SOP Rev 2, OPS-2",
    "ops3": "Operations SOP Rev 2, OPS-3",
    "ops4": "Operations SOP Rev 2, OPS-4",
    "ops5": "Operations SOP Rev 2, OPS-5",
    "ws03": "Field Work SOP, WS-03 (H2S Safety)",
}



def doc_cite(conn: sqlite3.Connection, doc_id: str) -> str:
    row = conn.execute("SELECT title FROM docs WHERE doc_id=?", (doc_id,)).fetchone()
    return f"{doc_id} — {row['title']}" if row else doc_id


def producing_threshold(conn: sqlite3.Connection, well_type: str) -> float:
    """Parse the threshold from the manual; fall back to known values."""
    row = conn.execute("SELECT text FROM docs WHERE doc_id=?", (well_type,)).fetchone()
    if row:
        m = re.search(r"at least \*\*?(\d+(?:\.\d+)?)\s*°?C above ambient", row["text"])
        if m:
            return float(m.group(1))
    return THRESHOLDS.get(well_type, 15.0)


# --- Corrections ------------------------------------------------------------
def applied_corrections(conn: sqlite3.Connection, inspection_id: str) -> dict:
    """Active runtime corrections for one inspection: {field: corrected_value}.
    
    Includes both user-entered corrections (corrections table) and
    data_correction notes from context.jsonl.
    """
    out = {}
    # User-entered corrections
    for r in conn.execute(
        "SELECT field, corrected_value FROM corrections WHERE active=1 AND inspection_id=?",
        (inspection_id,),
    ):
        try:
            out[r["field"]] = float(r["corrected_value"])
        except (TypeError, ValueError):
            out[r["field"]] = r["corrected_value"]
    # data_correction notes from context.jsonl
    for r in conn.execute(
        "SELECT field, corrected_value FROM context_notes "
        "WHERE note_type='data_correction' AND inspection_id=? AND field IS NOT NULL",
        (inspection_id,),
    ):
        if r["field"] and r["corrected_value"] is not None:
            try:
                out[r["field"]] = float(r["corrected_value"])
            except (TypeError, ValueError):
                out[r["field"]] = r["corrected_value"]
    return out


def suppressed_inspections(conn: sqlite3.Connection) -> set:
    """Inspections whose spill detection was overridden by a formal correction
    note (context.jsonl note_type='correction' naming the inspection)."""
    return {r["inspection_id"] for r in conn.execute(
        "SELECT DISTINCT inspection_id FROM context_notes "
        "WHERE note_type IN ('correction', 'data_correction') AND inspection_id IS NOT NULL")}


def effective_inspection(conn: sqlite3.Connection, insp: sqlite3.Row, suppressed: set) -> dict:
    """Inspection with runtime corrections applied and formal corrections marked."""
    d = dict(insp)
    d["spill_suppressed"] = insp["inspection_id"] in suppressed
    for field, value in applied_corrections(conn, insp["inspection_id"]).items():
        if field in d:
            d[f"original_{field}"] = insp[field]
            d[field] = value
            d["corrected"] = True
    return d


def is_producing(conn: sqlite3.Connection, eff: dict, well_type: str) -> bool:
    thr = producing_threshold(conn, well_type)
    if eff["wellhead_temp_c"] is None or eff["ambient_temp_c"] is None:
        return True
    return (eff["wellhead_temp_c"] - eff["ambient_temp_c"]) >= thr


def is_valid_spill(eff: dict) -> bool:
    """A spill that counts: detected, not overridden by a formal correction."""
    return bool(eff["spill_detected"]) and not eff["spill_suppressed"] and (
        eff["spill_est_volume_bbl"] is not None)


# --- Maintenance report parsing ---------------------------------------------
def parse_report(text: str) -> dict:
    """Extract the few structured facts the copilot needs from a free-text report."""
    mid = None
    m = re.search(r"MNT-\d{4}-\d{3}", text)
    if m:
        mid = m.group(0)

    hours = None
    m = re.search(r"contain\w*\s+(?:about\s+)?(?:in\s+)?(?:roughly\s+)?~?(\d+(?:\.\d+)?)\s*hours", text, re.I)
    if m:
        hours = float(m.group(1))

    cls = None
    m = re.search(r"\b(minor|moderate|reportable|major)\b(?:\s+class)?", text, re.I)
    if m:
        cls = m.group(1).lower()

    rca = 1 if re.search(r"Action required", text, re.I) else 0

    # New fields in test data reports
    parts = None
    m = re.search(r"\*\*Parts installed:\*\*\s*(.+?)(?:\n\n|\n\*\*)", text, re.S)
    if m:
        parts = m.group(1).strip()

    follow = None
    m = re.search(r"\*\*Follow-up:\*\*\s*(.+?)(?:\n\n|\n\*\*)", text, re.S)
    if m:
        follow = m.group(1).strip()

    return {"maintenance_id": mid, "containment_hours": hours, "spill_class": cls,
            "rca_action_required": rca, "parts_installed": parts, "follow_up": follow}


# --- Time helpers -------------------------------------------------------------
def iso_to_date(s):
    return datetime.strptime(s[:10], "%Y-%m-%d").date() if s else None


def months_ago(d: date, n: int) -> date:
    m = d.month - n
    y = d.year
    while m <= 0:
        m += 12
        y -= 1
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28,
                      31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return date(y, m, day)


def window_last_months(n_months: int):
    t = config.today()
    return {"start": months_ago(t, n_months), "end": t}


def window_last_days(n_days: int):
    t = config.today()
    return {"start": t - timedelta(days=n_days), "end": t}

