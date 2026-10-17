"""Memory at two levels + learning from feedback.

- Shared knowledge about a well (shared_notes / claims): statements any user
  makes about a well are visible to everyone who later asks about that well.
- Private memory per user (conversations + entity_mentions): "the wells we
  discussed yesterday" resolves only against THAT user's history.
- Feedback (corrections): raw-data corrections and analysis corrections keep
  the original, record who corrected and why, and are applied in every later
  answer for every user, at the scope they were given (one well or a well type).
- Claims are checked against the data before being accepted; disagreements are
  surfaced, never silently resolved.
"""
import json
import sqlite3
from datetime import datetime, timedelta

from . import config, tools
from .domain import iso_to_date


def now_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def record_correction(conn, *, kind, inspection_id=None, asset_id=None, well_type=None,
                      field, original_value, corrected_value, reason, author_user_id):
    cur = conn.execute(
        "INSERT INTO corrections(kind, inspection_id, asset_id, well_type, field, "
        "original_value, corrected_value, reason, author_user_id, created_at, active) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,1)",
        (kind, inspection_id, asset_id, well_type, field, str(original_value),
         str(corrected_value), reason, author_user_id, now_iso()))
    conn.commit()
    return cur.lastrowid


def record_shared_note(conn, asset_id, text, author_user_id, kind="operator_note"):
    cur = conn.execute(
        "INSERT INTO shared_notes(asset_id, text, author_user_id, created_at, kind) "
        "VALUES(?,?,?,?,?)", (asset_id, text, author_user_id, now_iso(), kind))
    conn.commit()
    return cur.lastrowid


def record_user_rule(conn, user_id, rule_kind, scope, scope_value, value, text):
    cur = conn.execute(
        "INSERT INTO user_rules(user_id, rule_kind, scope, scope_value, value, text, created_at) "
        "VALUES(?,?,?,?,?,?,?)", (user_id, rule_kind, scope, scope_value, value, text, now_iso()))
    conn.commit()
    return cur.lastrowid


def record_entity_mentions(conn, user_id, conversation_id, entity_ids, entity_type="well",
                           turn_id=None):
    ts = now_iso()
    for e in dict.fromkeys(entity_ids):  # dedupe, keep order
        conn.execute(
            "INSERT INTO entity_mentions(user_id, conversation_id, turn_id, entity_id, "
            "entity_type, mentioned_at) VALUES(?,?,?,?,?,?)",
            (user_id, conversation_id, turn_id, e, entity_type, ts))
    conn.commit()


def discussed_entities(conn, user_id, n=3, days=7):
    """Private per-user memory: wells this user recently discussed.

    Resolution is turn-aware: if the user says "the three wells we discussed",
    prefer the most recent turn whose answer covered exactly n wells — that is
    almost always the conversation they mean — and fall back to the n most
    recently mentioned wells.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    turns = conn.execute(
        "SELECT turn_id, MAX(id) max_id, COUNT(DISTINCT entity_id) c FROM entity_mentions "
        "WHERE user_id=? AND entity_type='well' AND mentioned_at>=? AND turn_id IS NOT NULL "
        "GROUP BY turn_id ORDER BY max_id DESC", (user_id, cutoff)).fetchall()
    if n:
        for t in turns:
            if t["c"] == n:
                rows = conn.execute(
                    "SELECT DISTINCT entity_id FROM entity_mentions WHERE user_id=? AND "
                    "turn_id=? ORDER BY id", (user_id, t["turn_id"])).fetchall()
                return [r["entity_id"] for r in rows]
    rows = conn.execute(
        "SELECT DISTINCT entity_id FROM entity_mentions WHERE user_id=? AND entity_type='well' "
        "AND mentioned_at>=? ORDER BY id DESC LIMIT ?",
        (user_id, cutoff, n)).fetchall()
    return [r["entity_id"] for r in reversed(rows)]


def check_claim_against_data(conn, asset_id, text):
    """Returns (is_conflict, explanation, evidence) comparing a user statement
    with the latest inspection derived status."""
    insp = tools.latest_inspection(conn, asset_id)
    if not insp:
        return False, None, []
    well = tools.get_well(conn, asset_id)
    e = tools.eff(conn, insp)
    producing = tools.domain.is_producing(conn, e, well["well_type"])
    delta = e["wellhead_temp_c"] - e["ambient_temp_c"]
    inspector = tools.user_name(conn, insp["inspector_user_id"])
    t = text.lower()
    claims_running = any(k in t for k in ("running fine", "back online", "producing",
                                          "back up", "running again"))
    claims_down = any(k in t for k in ("shut in", "down", "stopped", "not running", "planned work"))
    if claims_running and not producing:
        expl = (f"the {insp['insp_date']} inspection ({insp['inspection_id']}, by {inspector}) "
                f"shows the wellhead only {delta:.1f} °C above the air, so the well is not "
                f"producing oil, which disagrees with that claim")
        return True, expl, [tools.ev("inspection", insp["inspection_id"], expl)]
    if claims_down and producing:
        expl = (f"the {insp['insp_date']} inspection ({insp['inspection_id']}, by {inspector}) "
                f"shows the wellhead {delta:.1f} °C above the air (above the {well['well_type']} "
                f"threshold), so the well is producing oil, which disagrees with that claim")
        return True, expl, [tools.ev("inspection", insp["inspection_id"], expl)]
    return False, None, []


def record_claim(conn, user_id, asset_id, text, conversation_id=None):
    """Record a user's statement about a well; surface conflicts honestly."""
    conflict, expl, evidence = check_claim_against_data(conn, asset_id, text)
    # A well-scoped statement is shared knowledge: everyone asking about the
    # well later sees it. Its confirmation status is kept on record.
    cur = conn.execute(
        "INSERT INTO claims(user_id, asset_id, text, status, conflict_json, conversation_id, "
        "created_at) VALUES(?,?,?,?,?,?,?)",
        (user_id, asset_id, text, "unconfirmed" if conflict else "on record",
         json.dumps({"explanation": expl}) if conflict else None, conversation_id, now_iso()))
    conn.commit()
    return cur.lastrowid, conflict, expl, evidence


def confirm_claim(conn, claim_id):
    conn.execute("UPDATE claims SET status='confirmed' WHERE claim_id=?", (claim_id,))
    conn.commit()


def pending_conflict_for(conn, asset_id, user_id=None):
    row = conn.execute(
        "SELECT * FROM claims WHERE asset_id=? AND status='unconfirmed' "
        "ORDER BY created_at DESC LIMIT 1", (asset_id,)).fetchone()
    return dict(row) if row else None


def get_planned_downtime(conn, asset_id):
    """Planned/known downtime for a well: context notes + shared notes."""
    out = []
    t = config.today().isoformat()
    for n in conn.execute(
            "SELECT * FROM context_notes WHERE asset_id=? AND note_type!='correction' "
            "AND (valid_from IS NULL OR valid_from<=?) AND (valid_to IS NULL OR valid_to>=?)",
            (asset_id, t, t)):
        if "shut in" in (n["text"] or "").lower() or "workover" in (n["text"] or "").lower():
            out.append({"source": "note", "id": n["note_id"], "text": n["text"],
                        "author": tools.user_name(conn, n["author_user_id"]),
                        "from": n["valid_from"], "to": n["valid_to"]})
    for n in conn.execute("SELECT * FROM shared_notes WHERE asset_id=?", (asset_id,)):
        if "shut in" in (n["text"] or "").lower() or "workover" in (n["text"] or "").lower():
            out.append({"source": "shared", "id": f"SHARED-{n['shared_id']}", "text": n["text"],
                        "author": tools.user_name(conn, n["author_user_id"]),
                        "from": None, "to": None})
    return out
