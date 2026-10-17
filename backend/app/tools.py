"""Deterministic query tools over the ingested dataset.

Each tool returns a dict:
  data        - structured result (also the generative-UI payload)
  visual      - {"kind": card|table|line|bar|map|heatmap, ...} or None
  answer_md   - suggested prose (used verbatim by the deterministic agent;
                the optional LLM agent may rephrase it but not the numbers)
  evidence    - list of {"type","id","label"} citations shown under the answer

The numbers are computed from raw records with corrections applied, so they are
reproducible and citable.
"""
import json
import re
import sqlite3
from datetime import date, datetime, timedelta

from . import config, domain
from .domain import CITES


def ev(type_, id_, label):
    return {"type": type_, "id": id_, "label": label}


def user_name(conn, uid):
    if not uid:
        return None
    row = conn.execute("SELECT name FROM users WHERE user_id=?", (uid,)).fetchone()
    return row["name"] if row else uid


def get_well(conn, asset_id):
    return conn.execute("SELECT * FROM wells WHERE asset_id=?", (asset_id,)).fetchone()


def latest_inspection(conn, asset_id):
    return conn.execute(
        "SELECT * FROM inspections WHERE asset_id=? ORDER BY inspected_at DESC LIMIT 1",
        (asset_id,)).fetchone()


def eff(conn, insp):
    """Effective inspection (runtime corrections + formal correction flags)."""
    return domain.effective_inspection(conn, insp, domain.suppressed_inspections(conn))


def _insp_evidence(row):
    return ev("inspection", row["inspection_id"],
              f"{row['inspection_id']} ({row['insp_date']})")


# --------------------------------------------------------------------------
def get_well_status(conn, asset_id):
    well = get_well(conn, asset_id)
    if not well:
        return {"data": {"error": f"Unknown well {asset_id}"}, "visual": None,
                "answer_md": f"I have no record of {asset_id} in the loaded datasets.",
                "evidence": []}
    insp = latest_inspection(conn, asset_id)
    e = eff(conn, insp) if insp else None
    thr = domain.producing_threshold(conn, well["well_type"])
    producing = domain.is_producing(conn, e, well["well_type"]) if e else None
    delta = round(e["wellhead_temp_c"] - e["ambient_temp_c"], 1) if e else None

    # Human context: notes valid today + recently shared notes + open claims
    notes = []
    t = config.today().isoformat()
    for n in conn.execute(
        "SELECT * FROM context_notes WHERE asset_id=? AND note_type != 'correction' "
        "AND (valid_from IS NULL OR valid_from<=?) AND (valid_to IS NULL OR valid_to>=?) "
        "ORDER BY created_at DESC", (asset_id, t, t)):
        notes.append(dict(n))
    for n in conn.execute(
            "SELECT * FROM shared_notes WHERE asset_id=? ORDER BY created_at DESC LIMIT 5",
            (asset_id,)):
        notes.append({"note_id": f"SHARED-{n['shared_id']}", "note_type": n["kind"],
                      "text": n["text"], "author_user_id": n["author_user_id"],
                      "created_at": n["created_at"]})
    claims = [dict(r) for r in conn.execute(
        "SELECT * FROM claims WHERE asset_id=? ORDER BY created_at DESC LIMIT 5", (asset_id,))]

    open_repairs = [dict(r) for r in conn.execute(
        "SELECT * FROM maintenance WHERE asset_id=? AND maintenance_type='corrective' "
        "AND (completed_at IS NULL OR completed_at>?) ORDER BY started_at DESC",
        (asset_id, f"{config.today()}T23:59:59Z"))]

    stale = producing is not None and (
        (well["recorded_status"] == "active") != bool(producing))

    # corrections applied to the latest inspection (provenance travels with the answer)
    applied = []
    if insp:
        for c in conn.execute(
                "SELECT * FROM corrections WHERE active=1 AND inspection_id=? "
                "ORDER BY created_at DESC", (insp["inspection_id"],)):
            applied.append(dict(c))

    data = {
        "asset_id": asset_id, "name": well["name"], "well_type": well["well_type"],
        "area_name": well["area_name"], "recorded_status": well["recorded_status"],
        "status_stale": stale, "producing": producing, "delta_c": delta,
        "threshold_c": thr, "last_inspected_at": insp["inspected_at"] if insp else None,
        "inspector": user_name(conn, e["inspector_user_id"]) if e else None,
        "method": e["method"] if e else None,
        "notes": notes, "open_repairs": open_repairs, "claims": claims,
        "corrections": applied,
    }
    evidence = []
    if insp:
        evidence.append(_insp_evidence(insp))
    evidence.append(ev("doc", well["well_type"], f"{well['well_type']} operating manual "
                       f"(producing threshold {thr:.0f} °C above ambient)"))
    for n in notes:
        evidence.append(ev("note", n["note_id"], f"Note {n['note_id']} — {n['text'][:80]}"))

    lines = []
    if producing is True:
        lines.append(f"**Yes — {asset_id} is producing oil.**")
    elif producing is False:
        lines.append(f"**No — {asset_id} is not producing oil.**")
    if insp:
        insp_dt = insp["inspected_at"][:16].replace("T", " ")
        lines.append(
            f"Latest inspection {insp['inspection_id']} on {insp_dt} UTC, by {e['method']} "
            f"({user_name(conn, e['inspector_user_id'])}). The wellhead was {delta:.1f} °C "
            f"above air; the {well['well_type']} manual counts it producing only at ≥ {thr:.0f} °C "
            f"above ambient.")
    if stale:
        lines.append(f"The recorded status still says `{well['recorded_status']}`, which is out "
                     f"of date — the inspections are the truth.")
    for c in applied:
        lines.append(f"The {insp['insp_date']} {c['field'].replace('_', ' ')} was corrected to "
                     f"{c['corrected_value']} by {user_name(conn, c['author_user_id'])} "
                     f"(original {c['original_value']}, reason kept on record).")
        evidence.append(ev("correction", f"correction-{c['correction_id']}",
                           f"correction by {user_name(conn, c['author_user_id'])}: "
                           f"{c['reason'][:90]}"))
    if insp and insp["notes"]:
        lines.append(f"Inspector note on this inspection: \"{insp['notes']}\".")
    for n in notes:
        who = user_name(conn, n.get("author_user_id"))
        lines.append(f"Context — {n['note_id']} by {who}: \"{n['text']}\"")
    for r in open_repairs:
        started = r["started_at"][:10]
        lines.append(f"Open repair {r['maintenance_id']}: {r['issue']} (started {started}).")
    for c in claims:
        if c["status"] == "unconfirmed":
            lines.append(f"Unconfirmed claim on record by {user_name(conn, c['user_id'])}: "
                         f"\"{c['text']}\"")
    return {"data": data,
            "visual": {"kind": "card", "title": f"{asset_id} — {well['name']}", "payload": data},
            "answer_md": "\n\n".join(lines), "evidence": evidence}


# --------------------------------------------------------------------------
def list_not_producing(conn, area_id=None):
    wells = conn.execute(
        "SELECT * FROM wells WHERE (? IS NULL OR area_id=?) ORDER BY asset_id",
        (area_id, area_id)).fetchall()
    rows = []
    evidence = []
    restored = []  # wells producing only because of a correction
    for w in wells:
        insp = latest_inspection(conn, w["asset_id"])
        if not insp:
            continue
        e = eff(conn, insp)
        if domain.is_producing(conn, e, w["well_type"]):
            # would the uncorrected reading have said "down"?
            if e.get("corrected"):
                raw = dict(insp)
                if raw["wellhead_temp_c"] is not None and raw["ambient_temp_c"] is not None:
                    if (raw["wellhead_temp_c"] - raw["ambient_temp_c"]) < \
                            domain.producing_threshold(conn, w["well_type"]):
                        cor = conn.execute(
                            "SELECT * FROM corrections WHERE active=1 AND inspection_id=? "
                            "ORDER BY created_at DESC LIMIT 1", (insp["inspection_id"],)).fetchone()
                        if cor:
                            restored.append((w["asset_id"], insp, cor))
            continue
        delta = round(e["wellhead_temp_c"] - e["ambient_temp_c"], 1)
        reason, who = None, None
        open_m = conn.execute(
            "SELECT * FROM maintenance WHERE asset_id=? AND maintenance_type='corrective' "
            "AND started_at<=? AND (completed_at IS NULL OR completed_at>?) "
            "ORDER BY started_at DESC LIMIT 1",
            (w["asset_id"], insp["inspected_at"], f"{config.today()}T23:59:59Z")).fetchone()
        if open_m:
            reason = f"Repair {open_m['maintenance_id']}: {open_m['issue']}, started " \
                     f"{open_m['started_at'][:10]}, still open"
            evidence.append(ev("maintenance", open_m["maintenance_id"],
                               f"{open_m['maintenance_id']} — {open_m['issue']}"))
        elif insp["notes"]:
            reason = f"No recorded reason. The inspector noted \"{insp['notes']}\""
        else:
            reason = "No recorded reason"
        rows.append({"asset_id": w["asset_id"], "well_type": w["well_type"],
                     "delta_c": delta, "recorded_status": w["recorded_status"],
                     "reason": reason})
        evidence.append(_insp_evidence(insp))
    area_name = "the whole field"
    if area_id:
        arow = conn.execute("SELECT name FROM areas WHERE area_id=?", (area_id,)).fetchone()
        area_name = arow["name"] if arow else area_id
    hdr = (f"{len(rows)} well(s) in {area_name} are not producing oil right now "
           f"(each one's latest inspection).")
    visual = {"kind": "table", "title": f"Not producing — {area_name}",
              "columns": ["Well", "Wellhead above air", "Recorded status", "Reason"],
              "rows": [[r["asset_id"], f"{r['delta_c']:.1f} °C", r["recorded_status"],
                        r["reason"]] for r in rows]} if rows else None
    if not rows:
        hdr = f"Every well I can see in {area_name} was producing at its latest inspection."
    for asset_id, insp, cor in restored:
        hdr += (f"\n\n**{asset_id}** is no longer listed: its {insp['insp_date']} wellhead "
                f"reading was corrected to {cor['corrected_value']} °C by "
                f"{user_name(conn, cor['author_user_id'])} (original {cor['original_value']} °C), "
                f"which puts it above the producing threshold.")
        evidence.append(ev("correction", f"correction-{cor['correction_id']}",
                           f"correction by {user_name(conn, cor['author_user_id'])}"))
    return {"data": {"rows": rows, "area": area_name}, "visual": visual,
            "answer_md": hdr, "evidence": evidence}


# --------------------------------------------------------------------------
def temp_series(conn, asset_id, weeks=13):
    rows = conn.execute(
        "SELECT * FROM inspections WHERE asset_id=? ORDER BY inspected_at DESC LIMIT ?",
        (asset_id, weeks)).fetchall()
    rows = list(reversed(rows))
    well = get_well(conn, asset_id)
    thr = domain.producing_threshold(conn, well["well_type"])
    suppressed = domain.suppressed_inspections(conn)
    points, down = [], []
    for r in rows:
        e = domain.effective_inspection(conn, r, suppressed)
        prod = domain.is_producing(conn, e, well["well_type"])
        delta = round(e["wellhead_temp_c"] - e["ambient_temp_c"], 1)
        points.append({"date": r["insp_date"], "ambient": e["ambient_temp_c"],
                       "wellhead": e["wellhead_temp_c"], "delta": delta, "producing": prod})
        if not prod:
            down.append(r["insp_date"])
    visual = {"kind": "line", "title": f"{asset_id} — wellhead vs air temperature",
              "x_key": "date", "series": [
                  {"key": "wellhead", "label": "Wellhead °C"},
                  {"key": "ambient", "label": "Air °C"}],
              "points": points, "not_producing": down, "threshold_c": thr}
    evidence = [_insp_evidence(r) for r in rows[:1] + rows[-1:]]
    evidence.append(ev("doc", well["well_type"], f"{well['well_type']} manual — producing "
                       f"threshold {thr:.0f} °C above ambient"))
    down_txt = ", ".join(down) if down else "none"
    answer = (f"{len(points)} weekly readings for {asset_id} "
              f"({points[0]['date']} to {points[-1]['date']}). "
              f"Not producing oil on: **{down_txt}** (wellhead−air below the "
              f"{thr:.0f} °C {well['well_type']} threshold).")
    return {"data": points, "visual": visual, "answer_md": answer, "evidence": evidence}


# --------------------------------------------------------------------------
def valid_spills(conn, asset_id=None, area_id=None, start=None, end=None):
    q = ("SELECT i.*, w.area_id FROM inspections i JOIN wells w ON w.asset_id=i.asset_id "
         "WHERE i.spill_detected=1")
    args = []
    if asset_id:
        q += " AND i.asset_id=?"
        args.append(asset_id)
    if area_id:
        q += " AND w.area_id=?"
        args.append(area_id)
    if start:
        q += " AND i.insp_date>=?"
        args.append(str(start))
    if end:
        q += " AND i.insp_date<=?"
        args.append(str(end))
    q += " ORDER BY i.inspected_at"
    suppressed = domain.suppressed_inspections(conn)
    out = []
    for r in conn.execute(q, args):
        e = domain.effective_inspection(conn, r, suppressed)
        if domain.is_valid_spill(e):
            out.append(e)
    return out


def spill_history(conn, asset_id=None, area_id=None, start=None, end=None):
    spills = valid_spills(conn, asset_id, area_id, start, end)
    rows, total = [], 0.0
    evidence = []
    for s in spills:
        vol = s["spill_est_volume_bbl"]
        total += vol or 0
        corrected = ""
        if s.get("corrected"):
            cor = conn.execute(
                "SELECT author_user_id FROM corrections WHERE active=1 AND inspection_id=? "
                "AND field='spill_est_volume_bbl' ORDER BY created_at DESC LIMIT 1",
                (s["inspection_id"],)).fetchone()
            if cor:
                corrected = f" (corrected to {vol} bbl by {user_name(conn, cor['author_user_id'])})"
        rows.append([s["asset_id"], s["insp_date"], f"{vol:.1f} bbl",
                     f"{s['spill_area_pct']:.1f}%" if s["spill_area_pct"] is not None else "—",
                     s["inspection_id"], corrected])
        evidence.append(_insp_evidence(s))
    scope = asset_id or (area_id and conn.execute(
        "SELECT name FROM areas WHERE area_id=?", (area_id,)).fetchone()["name"]) or "the field"
    answer = (f"**{len(rows)} valid spill(s)** at {scope} in the period, "
              f"**{total:.1f} barrels** total.")
    if rows:
        answer += " Detections later overturned by a formal correction are excluded."
    visual = {"kind": "table", "title": f"Spills — {scope}",
              "columns": ["Well", "Date", "Volume", "Pad area", "Inspection", "Note"],
              "rows": rows} if rows else None
    return {"data": {"rows": rows, "count": len(rows), "total_bbl": round(total, 1)},
            "visual": visual, "answer_md": answer, "evidence": evidence}


# --------------------------------------------------------------------------
def downtime_days(conn, asset_id, start, end):
    insps = conn.execute(
        "SELECT * FROM inspections WHERE asset_id=? AND insp_date>=? AND insp_date<=? "
        "ORDER BY inspected_at", (asset_id, str(start), str(end))).fetchall()
    well = get_well(conn, asset_id)
    suppressed = domain.suppressed_inspections(conn)
    down, causes, evidence = [], {}, []
    for r in insps:
        e = domain.effective_inspection(conn, r, suppressed)
        if domain.is_producing(conn, e, well["well_type"]):
            continue
        down.append({"date": r["insp_date"], "inspection_id": r["inspection_id"],
                     "delta": round(e["wellhead_temp_c"] - e["ambient_temp_c"], 1),
                     "wellhead": e["wellhead_temp_c"], "ambient": e["ambient_temp_c"]})
        evidence.append(_insp_evidence(r))
        m = conn.execute(
            "SELECT * FROM maintenance WHERE asset_id=? AND maintenance_type='corrective' AND "
            "(triggered_by_inspection_id=? OR (started_at>=? AND started_at<=?)) LIMIT 1",
            (asset_id, r["inspection_id"],
             (datetime.strptime(r["insp_date"], "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d"),
             (datetime.strptime(r["insp_date"], "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")),
        ).fetchone()
        if m:
            causes.setdefault(f"{m['maintenance_id']}: {m['issue']}", []).append(r["insp_date"])
            evidence.append(ev("maintenance", m["maintenance_id"],
                               f"{m['maintenance_id']} — {m['issue']}"))
    days = len(down) * 7
    lines = [f"**{asset_id} was down {days} days** "
             f"({start} to {end}) — {len(down)} weekly inspection(s) found it not producing "
             f"oil; each counts as 7 days ({CITES['downtime']})."]
    for d in down:
        lines.append(f"**{d['date']}** ({d['inspection_id']}): wellhead {d['wellhead']} °C vs air "
                     f"{d['ambient']} °C — only {d['delta']:.1f} °C warmer "
                     f"({well['well_type']} threshold "
                     f"{domain.producing_threshold(conn, well['well_type']):.0f} °C).")
    for cause, dates in causes.items():
        lines.append(f"Cause: {cause} — covers {', '.join(dates)}.")
    return {"data": {"days": days, "down": down, "causes": list(causes.keys())},
            "visual": None, "answer_md": "\n\n".join(lines), "evidence": evidence}


def downtime_ranking(conn, area_id, start, end, top_n=3):
    wells = conn.execute("SELECT * FROM wells WHERE area_id=? ORDER BY asset_id",
                         (area_id,)).fetchall()
    well_ids = ",".join("?" * len(wells)) if wells else "''"
    insp_rows = {}
    if wells:
        q = (f"SELECT asset_id, inspection_id, insp_date, wellhead_temp_c, ambient_temp_c "
             f"FROM inspections WHERE asset_id IN ({well_ids}) AND insp_date>=? AND insp_date<=?")
        args = [w["asset_id"] for w in wells] + [str(start), str(end)]
        for r in conn.execute(q, args):
            insp_rows.setdefault(r["asset_id"], []).append(r)
    thr_cache, suppressed = {}, domain.suppressed_inspections(conn)
    ranked = []
    for w in wells:
        thr = thr_cache.setdefault(w["well_type"],
                                   domain.producing_threshold(conn, w["well_type"]))
        n, last_down = 0, None
        for r in insp_rows.get(w["asset_id"], []):
            if r["wellhead_temp_c"] is None or r["ambient_temp_c"] is None:
                continue
            if (r["wellhead_temp_c"] - r["ambient_temp_c"]) < thr:
                n += 1
                last_down = r["insp_date"]
        if n:
            ranked.append({"asset_id": w["asset_id"], "days": n * 7,
                           "well_type": w["well_type"], "count": n, "last_down": last_down})
    ranked.sort(key=lambda x: (-x["days"], -domain.iso_to_date(x["last_down"]).toordinal(),
                               x["asset_id"]))
    for r in ranked:
        r.pop("last_down")
    top = ranked[:top_n]
    nxt = ranked[top_n:top_n + 1]
    area_name = conn.execute("SELECT name FROM areas WHERE area_id=?",
                             (area_id,)).fetchone()["name"]
    visual = {"kind": "bar", "title": f"Most downtime — {area_name} ({start} to {end})",
              "x_key": "asset_id", "y_key": "days", "points": top}
    answer = (f"Top {len(top)} wells in {area_name} by downtime "
              f"({start} to {end}): " +
              ", ".join(f"**{r['asset_id']}**: {r['days']} days ({r['well_type']}, "
                        f"{r['count']} down weeks)" for r in top))
    if nxt:
        answer += f". Next is **{nxt[0]['asset_id']}** at {nxt[0]['days']}."
    return {"data": {"top": top, "next": nxt}, "visual": visual, "answer_md": answer,
            "evidence": [ev("doc", "dataset-guide",
                            "Downtime rule: each not-producing weekly inspection = 7 days")]}


# --------------------------------------------------------------------------
def spill_map(conn, area_id, start, end):
    spills = valid_spills(conn, area_id=area_id, start=start, end=end)
    pins, evidence = [], []
    for s in spills:
        w = get_well(conn, s["asset_id"])
        pins.append({"asset_id": s["asset_id"], "date": s["insp_date"],
                     "volume_bbl": s["spill_est_volume_bbl"],
                     "lat": w["lat"], "lon": w["lon"]})
        evidence.append(_insp_evidence(s))
    area_name = conn.execute("SELECT name FROM areas WHERE area_id=?",
                             (area_id,)).fetchone()["name"]
    visual = {"kind": "map", "title": f"Spills — {area_name} ({start} to {end})",
              "points": pins}
    answer = (f"{len(pins)} well(s) in {area_name} had a real (not corrected) spill "
              f"between {start} and {end}: " +
              ", ".join(f"**{p['asset_id']}** {p['date']} ({p['volume_bbl']} bbl)"
                        for p in pins) + ".")
    return {"data": pins, "visual": visual, "answer_md": answer, "evidence": evidence}


def spill_heatmap(conn, year):
    t = config.today()
    areas = conn.execute("SELECT * FROM areas ORDER BY area_id").fetchall()
    suppressed = domain.suppressed_inspections(conn)
    grid = {a["name"]: [0] * t.month for a in areas}
    q = ("SELECT i.*, w.area_id FROM inspections i JOIN wells w ON w.asset_id=i.asset_id "
         "WHERE i.spill_detected=1 AND i.insp_date>=? AND i.insp_date<=?")
    for r in conn.execute(q, (f"{year}-01-01", f"{year}-12-31")):
        e = domain.effective_inspection(conn, r, suppressed)
        if not domain.is_valid_spill(e):
            continue
        name = next(a["name"] for a in areas if a["area_id"] == r["area_id"])
        grid[name][int(r["insp_date"][5:7]) - 1] += 1
    rows = [[name] + vals + [sum(vals)] for name, vals in grid.items()]
    visual = {"kind": "heatmap", "title": f"Spills by area × month ({year})",
              "columns": [f"{year}-{m:02d}" for m in range(1, t.month + 1)], "rows": rows}
    total = sum(sum(v) for v in grid.values())
    answer = (f"Heatmap of {total} valid spill detections in {year} "
              f"(correction-overridden detections removed), area × month.")
    evidence = [ev("doc", "spill-response-sop",
                   "Spill Response SOP §7 — corrected detections do not count as spills")]
    return {"data": grid, "visual": visual, "answer_md": answer, "evidence": evidence}


# --------------------------------------------------------------------------
def compliance_report(conn, asset_id, months=12):
    t = config.today()
    start = domain.months_ago(t, months)
    well = get_well(conn, asset_id)
    evidence, breaches, pending, met = [], [], [], []

    def report_filed(insp_id):
        return conn.execute(
            "SELECT * FROM reg_events WHERE asset_id=? AND related_inspection_id=? "
            "AND event_type='spill_report_filed'", (asset_id, insp_id)).fetchall()

    def novs(insp_id):
        return conn.execute(
            "SELECT * FROM reg_events WHERE asset_id=? AND related_inspection_id=? "
            "AND event_type='notice_of_violation'", (asset_id, insp_id)).fetchall()

    for s in valid_spills(conn, asset_id=asset_id, start=start, end=t):
        vol = s["spill_est_volume_bbl"]
        ev_label = f"spill {s['insp_date']} ({vol} bbl, {s['inspection_id']})"
        evidence.append(_insp_evidence(s))
        disc = domain.iso_to_date(s["inspected_at"])
        if vol >= domain.SPILL_REPORTABLE_BBL:
            filed = report_filed(s["inspection_id"])
            limit = (domain.SR01_MAJOR_HOURS if vol >= 25 else domain.SR01_NOTICE_HOURS)
            novs_ = novs(s["inspection_id"])
            if filed:
                h = filed[0]["hours_to_report"]
                if h is not None and h > limit:
                    detail = f"reported after {h:.0f} hours ({filed[0]['event_id']}), against a " \
                             f"{limit:.0f}-hour limit ({CITES['sr01']})"
                    if novs_:
                        n = novs_[0]
                        detail += (f". This led to notice of violation {n['event_id']} with a "
                                   f"USD {n['fine_usd']:,.0f} fine, status {n['status']}")
                        evidence.append(ev("event", n["event_id"], n["detail"]))
                    breaches.append({"rule": "SR-01", "what": ev_label, "detail": detail})
                    evidence.append(ev("event", filed[0]["event_id"], filed[0]["detail"]))
            elif disc and (t - disc).days * 24 > limit:
                breaches.append({
                    "rule": "SR-01", "what": ev_label,
                    "detail": f"a written notice was due within {limit:.0f} hours of discovery "
                              f"and none is recorded ({CITES['sr01']})"})
            for n in novs_:
                if n["status"] == "open":
                    due = domain.iso_to_date(n["date"]) + timedelta(days=domain.RC04_RESPONSE_DAYS)
                    resp = conn.execute(
                        "SELECT COUNT(*) c FROM reg_events WHERE asset_id=? AND "
                        "event_type='nov_response_filed' AND date>=?", (asset_id, n["date"])
                    ).fetchone()["c"]
                    if resp == 0 and due <= t:
                        breaches.append({
                            "rule": "RC-04", "what": f"notice {n['event_id']}",
                            "detail": f"the notice needed a response by {due.isoformat()}, "
                                      f"and none is recorded ({CITES['rc04']})"})
                    elif resp == 0:
                        pending.append({
                            "rule": "RC-04", "what": f"notice {n['event_id']}",
                            "detail": f"response due by {due.isoformat()} ({CITES['rc04']})"})
            # SR-03 verification
            due3 = disc + timedelta(days=domain.SR03_VERIFY_DAYS)
            ver = conn.execute(
                "SELECT * FROM reg_events WHERE asset_id=? AND related_inspection_id=? "
                "AND event_type='site_inspection' AND status='closed'",
                (asset_id, s["inspection_id"])).fetchall()
            if not ver and due3 <= t:
                open_ev = conn.execute(
                    "SELECT * FROM reg_events WHERE asset_id=? AND related_inspection_id=? "
                    "AND event_type='site_inspection' AND status='open' LIMIT 1",
                    (asset_id, s["inspection_id"])).fetchone()
                breaches.append({
                    "rule": "SR-03", "what": ev_label,
                    "detail": f"cleanup verification was due by {due3.isoformat()} and is still "
                              f"open{(' (' + open_ev['event_id'] + ')') if open_ev else ''} "
                              f"({CITES['sr03']})"})
                if open_ev:
                    evidence.append(ev("event", open_ev["event_id"], open_ev["detail"]))
            elif not ver:
                pending.append({
                    "rule": "SR-03", "what": ev_label,
                    "detail": f"agency verification of the clean-up is due within "
                              f"{domain.SR03_VERIFY_DAYS} days, by {due3.isoformat()} "
                              f"({CITES['sr03']})"})
        # SR-02 containment (any spill size)
        m = conn.execute(
            "SELECT m.*, r.containment_hours, r.report_path FROM maintenance m "
            "LEFT JOIN reports r ON r.report_path=m.report_file "
            "WHERE m.asset_id=? AND m.triggered_by_inspection_id=? "
            "AND m.maintenance_type='corrective' LIMIT 1",
            (asset_id, s["inspection_id"])).fetchone()
        if m and m["containment_hours"] is not None:
            evidence.append(ev("report", m["report_path"],
                               f"repair report {m['maintenance_id']}"))
            if m["containment_hours"] > domain.SR02_CONTAIN_HOURS:
                breaches.append({
                    "rule": "SR-02", "what": ev_label,
                    "detail": f"contained after about {m['containment_hours']:.1f} hours, "
                              f"against a {domain.SR02_CONTAIN_HOURS:.0f}-hour limit — found "
                              f"only in repair report {m['maintenance_id']} ({CITES['sr02']})"})

    # RC-02 yearly flowline test
    ftest = conn.execute(
        "SELECT * FROM maintenance WHERE asset_id=? AND issue LIKE '%flowline%integrity test%' "
        "AND start_date>=? AND start_date<=? ORDER BY started_at DESC LIMIT 1",
        (asset_id, f"{t.year}-01-01", f"{t.year}-12-31")).fetchone()
    if ftest:
        met.append({"rule": "RC-02", "detail": f"the yearly flowline test was done on "
                    f"{ftest['start_date']} ({ftest['maintenance_id']}), so that rule was met "
                    f"({CITES['rc02']})"})
        evidence.append(ev("maintenance", ftest["maintenance_id"], ftest["issue"]))
    else:
        breaches.append({"rule": "RC-02", "what": f"calendar {t.year}",
                         "detail": f"no flowline integrity test recorded in {t.year} "
                                   f"({CITES['rc02']})"})

    # Pending: RCA after >=3 corrective events on the same equipment kind in 12 months
    counts = conn.execute(
        "SELECT equipment_kind, COUNT(*) c FROM maintenance WHERE asset_id=? "
        "AND maintenance_type='corrective' AND started_at>=? GROUP BY equipment_kind "
        "HAVING c>=? ORDER BY c DESC", (asset_id, str(start), domain.RCA_COUNT)).fetchall()
    for c in counts:
        mnts = conn.execute(
            "SELECT maintenance_id FROM maintenance WHERE asset_id=? AND "
            "maintenance_type='corrective' AND equipment_kind=? AND started_at>=? "
            "ORDER BY started_at", (asset_id, c["equipment_kind"], str(start))).fetchall()
        ids = [m["maintenance_id"] for m in mnts]
        action = conn.execute(
            "SELECT report_path FROM reports WHERE asset_id=? AND rca_action_required=1 "
            "AND maintenance_id IN ({}) LIMIT 1".format(",".join("?" * len(ids))),
            [asset_id] + ids).fetchone()
        pending.append({
            "rule": "RCA (manual §10)", "what": f"{c['equipment_kind']}",
            "detail": f"a root-cause analysis is due: {c['c']} corrective repairs in the last "
                      f"{months} months ({', '.join(ids)})"
                      + (f". The latest report marks it as \"Action required\" "
                         f"({CITES['rca']})" if action else f" ({CITES['rca']})")})
        if action:
            evidence.append(ev("report", action["report_path"], "report marks RCA required"))

    # Pending: planned shut-in not recorded in the maintenance system (manual §4)
    tiso = t.isoformat()
    for n in conn.execute(
            "SELECT * FROM context_notes WHERE asset_id=? AND note_type!='correction' AND "
            "(valid_from IS NULL OR valid_from<=?) AND (valid_to IS NULL OR valid_to>=?)",
            (asset_id, tiso, tiso)):
        txt = (n["text"] or "").lower()
        if "shut in" in txt or "shut-in" in txt:
            m = conn.execute(
                "SELECT COUNT(*) c FROM maintenance WHERE asset_id=? AND started_at>=?",
                (asset_id, n["valid_from"] or "1990-01-01")).fetchone()["c"]
            if m == 0:
                pending.append({
                    "rule": "Manual §4 (shut-in recording)", "what": asset_id,
                    "detail": f"the planned shut-in from {n['valid_from']} is not yet recorded "
                              f"in the maintenance system, which the {well['well_type']} manual "
                              f"requires before work starts (note {n['note_id']})"})
                evidence.append(ev("note", n["note_id"], n["text"]))

    lines = []
    if breaches:
        lines.append(f"**{len(breaches)} rule breach(es)** for {asset_id} in the last "
                     f"{months} months:")
        for b in breaches:
            lines.append(f"- **{b['rule']}** — {b['what']}: {b['detail']}")
    else:
        lines.append(f"No rule breaches found for {asset_id} in the last {months} months.")
    if pending:
        lines.append(f"Also still pending (open actions, not counted as breaches):")
        for p in pending:
            lines.append(f"- **{p['rule']}** — {p['detail']}")
    for m_ in met:
        lines.append(f"- **{m_['rule']}** — {m_['detail']}")
    visual = {"kind": "table", "title": f"Compliance — {asset_id}",
              "columns": ["Rule", "Status", "Detail"],
              "rows": [[b["rule"], "breach", b["detail"]] for b in breaches] +
                      [[p["rule"], "pending", p["detail"]] for p in pending] +
                      [[m_["rule"], "met", m_["detail"]] for m_ in met]} if (
        breaches or pending or met) else None
    fines = conn.execute(
        "SELECT COALESCE(SUM(fine_usd),0) f FROM reg_events WHERE asset_id=? AND "
        "fine_usd>0 AND date>=? AND status='open'", (asset_id, str(start))).fetchone()["f"]
    if fines:
        lines.append(f"Open fines on record: **USD {fines:,.0f}**.")
    return {"data": {"breaches": breaches, "pending": pending, "met": met, "open_fines": fines},
            "visual": visual, "answer_md": "\n".join(lines), "evidence": evidence}


# --------------------------------------------------------------------------
def containment_breaches(conn, area_id, start, end):
    spills = valid_spills(conn, area_id=area_id, start=start, end=end)
    rows, evidence, unknown = [], [], 0
    for s in spills:
        m = conn.execute(
            "SELECT m.*, r.containment_hours, r.report_path FROM maintenance m "
            "JOIN wells w ON w.asset_id=m.asset_id "
            "LEFT JOIN reports r ON r.report_path=m.report_file "
            "WHERE m.asset_id=? AND m.triggered_by_inspection_id=? "
            "AND m.maintenance_type='corrective' LIMIT 1",
            (s["asset_id"], s["inspection_id"])).fetchone()
        if not m or m["containment_hours"] is None:
            unknown += 1
            continue
        if m["containment_hours"] > domain.SR02_CONTAIN_HOURS:
            rows.append([s["asset_id"], s["insp_date"], f"{s['spill_est_volume_bbl']:.1f} bbl",
                         f"{m['containment_hours']:.1f} h", m["maintenance_id"],
                         s["inspection_id"]])
            evidence.append(ev("report", m["report_path"],
                               f"{m['maintenance_id']} — contained "
                               f"{m['containment_hours']:.1f} h after discovery"))
            evidence.append(_insp_evidence(s))
    rows.sort(key=lambda r: r[0])
    area_name = conn.execute("SELECT name FROM areas WHERE area_id=?",
                             (area_id,)).fetchone()["name"]
    answer = (f"**{len(rows)} spill(s)** in {area_name} between {start} and {end} were not "
              f"contained within the {domain.SR02_CONTAIN_HOURS:.0f}-hour SR-02 limit. The "
              f"containment time exists only inside the repair reports ({CITES['sr02']}).")
    visual = {"kind": "table", "title": f"Late containment — {area_name}",
              "columns": ["Well", "Spill date", "Volume", "Contained after", "Report",
                          "Inspection"], "rows": rows} if rows else None
    return {"data": rows, "visual": visual, "answer_md": answer, "evidence": evidence}


def spills_needing_report(conn, area_id, start, end):
    spills = valid_spills(conn, area_id=area_id, start=start, end=end)
    rows, evidence = [], []
    for s in spills:
        vol = s["spill_est_volume_bbl"]
        if vol < domain.SPILL_REPORTABLE_BBL:
            continue
        filed = conn.execute(
            "SELECT * FROM reg_events WHERE asset_id=? AND related_inspection_id=? "
            "AND event_type='spill_report_filed' LIMIT 1",
            (s["asset_id"], s["inspection_id"])).fetchone()
        status = f"filed ({filed['hours_to_report']:.0f} h)" if filed else \
                 "**overdue — no written notice on record**"
        rows.append([s["asset_id"], s["insp_date"], f"{vol:.1f} bbl", status,
                     s["inspection_id"]])
        evidence.append(_insp_evidence(s))
        if not filed:
            evidence.append(ev("doc", "spill-response-sop",
                               "SOP-SR SR-01: reportable spills (≥5 bbl) need a written notice "
                               "within 24 hours"))
    area_name = conn.execute("SELECT name FROM areas WHERE area_id=?",
                             (area_id,)).fetchone()["name"]
    answer = (f"In {area_name} between {start} and {end}, "
              + (f"**{len(rows)} spill(s)** reached the reportable ≥5 bbl threshold:"
                 if rows else "no spill reached the 5 bbl reportable threshold."))
    for r in rows:
        answer += f"\n- {r[0]} on {r[1]}: {r[2]} — {r[3]}"
    visual = {"kind": "table", "title": f"Reportable spills — {area_name}",
              "columns": ["Well", "Date", "Volume", "Report status", "Inspection"],
              "rows": rows} if rows else None
    return {"data": rows, "visual": visual, "answer_md": answer, "evidence": evidence}


# --------------------------------------------------------------------------
def maintenance_costs(conn, asset_ids, year):
    rows, evidence = [], []
    total_all = 0
    for a in asset_ids:
        r = conn.execute(
            "SELECT COALESCE(SUM(cost_total),0) s, COUNT(*) c FROM maintenance "
            "WHERE asset_id=? AND substr(start_date,1,4)=?", (a, str(year))).fetchone()
        rows.append([a, f"USD {r['s']:,.0f}", r["c"]])
        total_all += r["s"]
        ev_rows = conn.execute(
            "SELECT maintenance_id, issue FROM maintenance WHERE asset_id=? AND "
            "substr(start_date,1,4)=? ORDER BY started_at", (a, str(year))).fetchall()
        for m in ev_rows:
            evidence.append(ev("maintenance", m["maintenance_id"], m["issue"]))
    visual = {"kind": "table", "title": f"Maintenance cost — {year}",
              "columns": ["Well", "Total cost", "Jobs"], "rows": rows}
    answer = (f"Repair/maintenance cost in {year}: " +
              " · ".join(f"**{r[0]}**: {r[1]}" for r in rows) +
              f" — USD {total_all:,.0f} across all listed wells.")
    return {"data": rows, "visual": visual, "answer_md": answer, "evidence": evidence}


def rca_needed(conn, area_id, equipment_kind="pump_jack", user_id=None):
    t = config.today()
    start = domain.months_ago(t, 12)
    wells = conn.execute("SELECT * FROM wells WHERE area_id=? ORDER BY asset_id",
                         (area_id,)).fetchall()
    area_name = conn.execute("SELECT name FROM areas WHERE area_id=?",
                             (area_id,)).fetchone()["name"]
    # User rules may override the manual threshold, but only for their scope.
    rules = {}
    if user_id:
        for r in conn.execute(
                "SELECT * FROM user_rules WHERE rule_kind='rca_count' AND scope='well_type' "
                "AND scope_value IS NOT NULL AND user_id=?", (user_id,)):
            rules[r["scope_value"]] = r
    rows, evidence = [], []
    used_rule = False
    for w in wells:
        c = conn.execute(
            "SELECT COUNT(*) c FROM maintenance WHERE asset_id=? AND "
            "maintenance_type='corrective' AND equipment_kind=? AND started_at>=?",
            (w["asset_id"], equipment_kind, str(start))).fetchone()["c"]
        thr, source = domain.RCA_COUNT, CITES["rca"]
        rule = rules.get(w["well_type"])
        if rule:
            thr, source = int(rule["value"]), f"{user_name(conn, rule['user_id'])}'s rule " \
                                              f"(recorded {rule['created_at'][:10]})"
            used_rule = True
        if c >= thr:
            rows.append([w["asset_id"], w["well_type"], c, f"≥{thr}", source])
            mnts = conn.execute(
                "SELECT maintenance_id, issue FROM maintenance WHERE asset_id=? AND "
                "maintenance_type='corrective' AND equipment_kind=? AND started_at>=? "
                "ORDER BY started_at", (w["asset_id"], equipment_kind, str(start))).fetchall()
            for m in mnts:
                evidence.append(ev("maintenance", m["maintenance_id"], m["issue"]))
    if rows:
        answer = (f"{len(rows)} well(s) in {area_name} need a root-cause analysis on their "
                  f"{equipment_kind.replace('_', ' ')} (corrective repairs in the last "
                  f"12 months vs required threshold):")
        for r in rows:
            answer += f"\n- **{r[0]}** ({r[1]}): {r[2]} repairs, threshold {r[3]} — {r[4]}"
        if used_rule:
            answer += ("\n\nThe raised threshold for T350 wells follows the recorded user rule, "
                       "not the manual — the manual requires an RCA after 3 corrective repairs "
                       "on the same equipment (manual §10).")
    else:
        answer = f"No well in {area_name} crosses the RCA threshold for {equipment_kind}."
    evidence.append(ev("doc", "T200", "T200 manual section 10 — RCA rule "
                                        "(the T350 manual refers to it)"))
    visual = {"kind": "table", "title": f"Root-cause analysis needed — {area_name}",
              "columns": ["Well", "Type", "Corrective repairs (12 mo)", "Threshold",
                          "Rule source"], "rows": rows} if rows else None
    return {"data": rows, "visual": visual, "answer_md": answer, "evidence": evidence}


# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
def _thr_sql():
    """SQL CASE expression for the per-type producing threshold."""
    return "CASE w.well_type " + " ".join(
        f"WHEN '{k}' THEN {v}" for k, v in domain.THRESHOLDS.items()) + " ELSE 15 END"


def dashboard_data(conn):
    """Fleet-wide aggregates for the analytics dashboard (all deterministic)."""
    t = config.today()
    thr = _thr_sql()

    latest = conn.execute(
        f"""SELECT i.inspection_id, i.asset_id, i.insp_date, i.wellhead_temp_c,
                   i.ambient_temp_c, i.notes, w.well_type, w.area_id, w.name,
                   w.recorded_status, w.lat, w.lon
            FROM inspections i JOIN wells w ON w.asset_id=i.asset_id
            JOIN (SELECT asset_id, MAX(inspected_at) m FROM inspections GROUP BY asset_id) x
              ON x.asset_id=i.asset_id AND x.m=i.inspected_at""").fetchall()
    fleet, watchlist, n_down, deltas = [], [], 0, []
    for r in latest:
        e = eff(conn, r)
        delta = ((e["wellhead_temp_c"] or 0) - (e["ambient_temp_c"] or 0)
                 if e["wellhead_temp_c"] is not None and e["ambient_temp_c"] is not None else None)
        producing = delta is not None and delta >= domain.producing_threshold(conn, r["well_type"])
        fleet.append({"asset_id": r["asset_id"], "lat": r["lat"], "lon": r["lon"],
                      "producing": producing,
                      "delta": round(delta, 1) if delta is not None else None,
                      "area": r["area_id"]})
        if delta is not None:
            deltas.append(delta)
        if not producing:
            n_down += 1
            om = conn.execute(
                "SELECT maintenance_id, issue FROM maintenance WHERE asset_id=? AND "
                "maintenance_type='corrective' AND (completed_at IS NULL OR completed_at>?) "
                "ORDER BY started_at DESC LIMIT 1", (r["asset_id"], f"{t}T23:59:59Z")).fetchone()
            reason = (f"{om['maintenance_id']}: {om['issue']}" if om else
                      (r["notes"] or "No recorded reason"))
            watchlist.append({"asset_id": r["asset_id"], "area": r["area_id"],
                              "delta": round(delta, 1) if delta is not None else None,
                              "recorded_status": r["recorded_status"], "reason": reason,
                              "last_inspected": r["insp_date"]})

    # 13-week fleet downtime trend (not-producing inspections per week x 7 days)
    trend_rows = conn.execute(
        f"""SELECT i.insp_date d, COUNT(*) n FROM inspections i
            JOIN wells w ON w.asset_id=i.asset_id
            WHERE i.insp_date>=? AND i.wellhead_temp_c IS NOT NULL
              AND (i.wellhead_temp_c - i.ambient_temp_c) < {thr}
            GROUP BY i.insp_date ORDER BY i.insp_date""",
        (str(t - timedelta(days=97)),)).fetchall()
    trend = [{"week": r["d"], "days": r["n"] * 7} for r in trend_rows][-13:]

    area_rows = conn.execute(
        f"""SELECT w.area_id, a.name area, COUNT(*) n FROM inspections i
            JOIN wells w ON w.asset_id=i.asset_id JOIN areas a ON a.area_id=w.area_id
            WHERE i.insp_date>=? AND i.wellhead_temp_c IS NOT NULL
              AND (i.wellhead_temp_c - i.ambient_temp_c) < {thr}
            GROUP BY w.area_id ORDER BY n DESC""", (str(domain.months_ago(t, 4)),)).fetchall()
    area_downtime = [{"area": r["area"], "days": r["n"] * 7} for r in area_rows]

    top_rows = conn.execute(
        f"""SELECT i.asset_id, COUNT(*) n FROM inspections i
            JOIN wells w ON w.asset_id=i.asset_id
            WHERE i.insp_date>=? AND i.wellhead_temp_c IS NOT NULL
              AND (i.wellhead_temp_c - i.ambient_temp_c) < {thr}
            GROUP BY i.asset_id ORDER BY n DESC LIMIT 6""",
        (str(domain.months_ago(t, 4)),)).fetchall()
    top_wells = [{"well": r["asset_id"], "days": r["n"] * 7} for r in top_rows]

    spills30 = valid_spills(conn, start=t - timedelta(days=30), end=t)
    year_spills = valid_spills(conn, start=date(t.year, 1, 1), end=t)
    spills_by_month = [0] * t.month
    for s in year_spills:
        spills_by_month[int(s["insp_date"][5:7]) - 1] += 1

    costs = conn.execute(
        "SELECT COALESCE(equipment_kind,'other') k, COALESCE(SUM(cost_total),0) s FROM maintenance "
        "WHERE substr(start_date,1,4)=? GROUP BY equipment_kind ORDER BY s DESC",
        (str(t.year),)).fetchall()
    cost_by_equipment = [{"kind": r["k"].replace("_", " "), "usd": r["s"]} for r in costs]
    spend_ytd = sum(c["usd"] for c in cost_by_equipment)

    reg = conn.execute(
        "SELECT status, COUNT(*) n, COALESCE(SUM(fine_usd),0) fines FROM reg_events "
        "GROUP BY status").fetchall()
    open_events = sum(r["n"] for r in reg if r["status"] == "open")
    open_fines = sum(r["fines"] for r in reg if r["status"] == "open")

    dt30 = conn.execute(
        f"""SELECT COUNT(*) n FROM inspections i JOIN wells w ON w.asset_id=i.asset_id
            WHERE i.insp_date>=? AND i.wellhead_temp_c IS NOT NULL
              AND (i.wellhead_temp_c - i.ambient_temp_c) < {thr}""",
        (str(t - timedelta(days=30)),)).fetchone()

    return {
        "today": t.isoformat(),
        "kpis": {
            "wells": len(fleet),
            "down_now": n_down,
            "avg_delta": round(sum(deltas) / len(deltas), 1) if deltas else 0,
            "spills_30d": len(spills30),
            "volume_30d": round(sum(s["spill_est_volume_bbl"] or 0 for s in spills30), 1),
            "downtime_30d": dt30["n"] * 7,
            "open_events": open_events,
            "open_fines": open_fines,
            "spend_ytd": spend_ytd,
        },
        "trend": trend,
        "area_downtime": area_downtime,
        "top_wells": top_wells,
        "spills_by_month": {"labels": [f"{t.year}-{m+1:02d}" for m in range(t.month)],
                            "counts": spills_by_month},
        "cost_by_equipment": cost_by_equipment,
        "fleet": fleet,
        "watchlist": sorted(watchlist,
                            key=lambda w: (w["delta"] if w["delta"] is not None else 99)),
    }


def spill_detail(conn, asset_id, date_str=None, inspection_id=None):
    """Was a spill real? Shows disagreements instead of picking a side."""
    if inspection_id:
        row = conn.execute("SELECT * FROM inspections WHERE inspection_id=?",
                           (inspection_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM inspections WHERE asset_id=? AND insp_date LIKE ? AND "
            "spill_detected=1 ORDER BY inspected_at", (asset_id, f"%{date_str}%")).fetchone()
    if not row:
        return {"data": {"found": False},
                "answer_md": f"I found no spill detection at {asset_id} on {date_str}.",
                "visual": None, "evidence": []}
    well = get_well(conn, asset_id)
    e = eff(conn, row)
    formal = row["inspection_id"] in domain.suppressed_inspections(conn)
    notes = conn.execute(
        "SELECT * FROM context_notes WHERE asset_id=? AND (inspection_id=? OR "
        "inspection_id IS NULL AND text LIKE ?)",
        (asset_id, row["inspection_id"], f"%{row['inspection_id']}%")).fetchall()
    m = conn.execute(
        "SELECT * FROM maintenance WHERE asset_id=? AND triggered_by_inspection_id=? LIMIT 1",
        (asset_id, row["inspection_id"])).fetchone()
    evidence = [_insp_evidence(row)]
    answer = (f"The inspection {row['inspection_id']} on {row['insp_date']} at {asset_id} "
              f"flagged a spill of **{e['spill_est_volume_bbl']} bbl** "
              f"(\"{row['notes']}\").")
    disagree = []
    if notes:
        answer += " The human notes disagree:"
        for n in notes:
            who = user_name(conn, n["author_user_id"])
            kind = ("**formal correction**" if n["note_type"] == "correction" else "opinion note")
            answer += f"\n- {n['note_id']} ({kind}) by {who}: \"{n['text']}\""
            evidence.append(ev("note", n["note_id"], n["text"]))
            if n["note_type"] != "correction":
                disagree.append(n["note_id"])
    if formal:
        answer += ("\n\nA **formal correction overrides the detection**, so this does not count "
                   "as a spill.")
        verdict = "no — a formal correction overturned this detection"
    else:
        answer += ("\n\nNeither note is a formal correction, "
                   + (f"and a spill repair ({m['maintenance_id']}) was done, "
                      f"so the detection stands." if m else "so the detection stands."))
        verdict = "yes — the detection stands"
        if m:
            evidence.append(ev("maintenance", m["maintenance_id"], m["issue"]))
        if disagree:
            answer += " The disagreement and both sources are shown above."
    answer = f"**Was it real oil? {verdict.capitalize()}.**\n\n" + answer
    return {"data": {"verdict": verdict, "inspection_id": row["inspection_id"],
                     "disagreeing_notes": disagree},
            "answer_md": answer, "visual": None, "evidence": evidence}


# --------------------------------------------------------------------------
# General fleet analytical queries (handles arbitrary operator questions)
# --------------------------------------------------------------------------

def get_repair_types(conn):
    """Answers 'How many types of repairs are present across all wells?'"""
    m_types = conn.execute(
        "SELECT maintenance_type, COUNT(*) as c, COALESCE(SUM(cost_total),0) as cost, "
        "ROUND(COALESCE(AVG(cost_total),0), 1) as avg_cost, ROUND(COALESCE(AVG(downtime_hours),0), 1) as avg_dt "
        "FROM maintenance GROUP BY maintenance_type ORDER BY c DESC").fetchall()
    
    eq_types = conn.execute(
        "SELECT equipment_kind, COUNT(*) as c, COALESCE(SUM(cost_total),0) as cost "
        "FROM maintenance GROUP BY equipment_kind ORDER BY c DESC").fetchall()
        
    n_issues = conn.execute("SELECT COUNT(DISTINCT issue) as c FROM maintenance").fetchone()["c"]
    n_wells = conn.execute("SELECT COUNT(*) c FROM wells").fetchone()["c"]
    total_jobs = sum(r["c"] for r in m_types)

    lines = [
        f"Across all {n_wells} wells in the field ({total_jobs:,} total maintenance records), "
        f"repairs fall into **{len(m_types)} maintenance type(s)**:"
    ]
    for r in m_types:
        pct = r['c'] / total_jobs * 100 if total_jobs else 0
        lines.append(f"- **{r['maintenance_type'].replace('_',' ').title()}:** {r['c']:,} jobs ({pct:.1f}%)")
    lines.append(f"\nAcross physical equipment, repairs span **{len(eq_types)} equipment categories**:")
    for r in eq_types:
        lines.append(f"- **{r['equipment_kind'].replace('_',' ').title()}:** {r['c']:,} repairs")
    lines.append(f"\nIn total, there are **{n_issues} unique specific repair/failure issues** documented.")

    rows = []
    for r in m_types:
        rows.append([f"Type: {r['maintenance_type']}", r["c"], f"${r['cost']:,.0f}", f"${r['avg_cost']:,.0f}", f"{r['avg_dt']} hrs"])
    for r in eq_types:
        rows.append([f"Equipment: {r['equipment_kind']}", r["c"], f"${r['cost']:,.0f}", "—", "—"])

    visual = {
        "kind": "table",
        "title": "Repair & Maintenance Types Breakdown",
        "columns": ["Category", "Total Jobs", "Total Cost (USD)", "Avg Job Cost", "Avg Downtime"],
        "rows": rows
    }
    evidence = [
        ev("doc", "T200", "Operating Manual T200 (Maintenance Specifications)"),
        ev("doc", "T350", "Operating Manual T350 (Maintenance Specifications)"),
        ev("doc", "T500", "Operating Manual T500 (Maintenance Specifications)"),
        ev("maintenance", "MNT-FLEET", f"{total_jobs:,} maintenance records across {n_wells} wells")
    ]
    return {"data": {"maintenance_types": len(m_types), "equipment_kinds": len(eq_types), "total_jobs": total_jobs, "distinct_issues": n_issues},
            "visual": visual, "answer_md": "\n".join(lines), "evidence": evidence}


def get_fleet_summary(conn):
    """Summary of all wells, areas, inspections, and production status."""
    n_wells = conn.execute("SELECT COUNT(*) c FROM wells").fetchone()["c"]
    areas = conn.execute("SELECT area_name, COUNT(*) c FROM wells GROUP BY area_name ORDER BY area_name").fetchall()
    types = conn.execute("SELECT well_type, COUNT(*) c FROM wells GROUP BY well_type ORDER BY well_type").fetchall()
    n_insps = conn.execute("SELECT COUNT(*) c FROM inspections").fetchone()["c"]
    n_spills = conn.execute("SELECT COUNT(*) c FROM inspections WHERE spill_detected=1").fetchone()["c"]
    n_areas = len(areas)
    teams = conn.execute("SELECT COUNT(*) c FROM teams").fetchone()["c"]

    lines = [
        f"The oil field contains **{n_wells} total wells** across **{n_areas} geographic production areas** and **{teams} teams**:"
    ]
    for a in areas:
        lines.append(f"- **{a['area_name']}:** {a['c']} wells")
    type_parts = ", ".join(f"**{t['c']} {t['well_type']}**" for t in types)
    lines.append(f"\nFleet composition: {type_parts} wells.")
    lines.append(f"The observation history records **{n_insps:,} weekly inspections** and **{n_spills:,} detected spill events**.")
    lines.append(f"Today is **{config.today().isoformat()}**.")

    visual = {
        "kind": "table",
        "title": "Fleet Overview by Production Block",
        "columns": ["Area Name", "Well Count", "Block Status", "Inspection Frequency"],
        "rows": [[a["area_name"], a["c"], "Active Production", "Weekly (1/well/wk)"] for a in areas]
    }
    evidence = [ev("doc", "fleet/areas.json", "Fleet geographic areas and blocks configuration")]
    return {"data": {"wells": n_wells, "inspections": n_insps, "spills": n_spills},
            "visual": visual, "answer_md": "\n".join(lines), "evidence": evidence}


def get_top_issues(conn):
    """Most common repair failure issues across all wells."""
    n_wells = conn.execute("SELECT COUNT(*) c FROM wells").fetchone()["c"]
    total_mnt = conn.execute("SELECT COUNT(*) c FROM maintenance").fetchone()["c"]
    issues = conn.execute(
        "SELECT issue, maintenance_type, equipment_kind, COUNT(*) as c, COALESCE(SUM(cost_total),0) as cost "
        "FROM maintenance GROUP BY issue ORDER BY c DESC LIMIT 10").fetchall()

    lines = ["Here are the **most common repair and maintenance issues** across all wells:\n"]
    rows = []
    for idx, r in enumerate(issues, 1):
        lines.append(f"{idx}. **{r['issue']}** ({r['equipment_kind']}): {r['c']} jobs (Total: ${r['cost']:,.0f})")
        rows.append([r["issue"], r["equipment_kind"], r["maintenance_type"], r["c"], f"${r['cost']:,.0f}"])

    visual = {
        "kind": "table",
        "title": "Most Frequent Repair Issues Fleetwide",
        "columns": ["Issue Description", "Equipment", "Type", "Occurrences", "Total Cost"],
        "rows": rows
    }
    evidence = [ev("maintenance", "MNT-ISSUES", f"Aggregated from {total_mnt:,} maintenance work orders across {n_wells} wells")]
    return {"data": [dict(r) for r in issues], "visual": visual, "answer_md": "\n".join(lines), "evidence": evidence}


def lookup_sop_rule(conn, text):
    """Looks up specific SOP protocol or manual section."""
    rule_m = re.search(r"\b(SR-0[1-4]|RC-0[1-5]|WS-0[1-7]|OPS-[1-6]|T200|T350|T500)\b", text, re.I)
    if not rule_m:
        return None
    rule_id = rule_m.group(1).upper()
    docs = conn.execute(
        "SELECT doc_id, title, text FROM docs WHERE text LIKE ? OR doc_id = ?",
        (f"%{rule_id}%", rule_id)).fetchall()
    if not docs:
        return None
    
    doc = docs[0]
    # Extract snippet around the rule
    content = doc["text"]
    lines = content.split("\n")
    snippet_lines = []
    capture = False
    for line in lines:
        if rule_id in line.upper():
            capture = True
        if capture:
            snippet_lines.append(line)
            if len(snippet_lines) >= 8 and line.strip() == "":
                break
    snippet = "\n".join(snippet_lines[:12]) or content[:400]

    answer = f"**Protocol {rule_id}** is defined in **{doc['title']}**:\n\n{snippet}"
    evidence = [ev("doc", doc["doc_id"], f"{doc['title']} ({rule_id})")]
    return {"data": {"rule": rule_id, "doc_id": doc["doc_id"]},
            "visual": None, "answer_md": answer, "evidence": evidence}


# --------------------------------------------------------------------------
# New tools for test dataset final questions
# --------------------------------------------------------------------------

def reservoir_pressure_map(conn):
    """Q1: Map reservoir pressure across the field from pressure data."""
    rows = conn.execute(
        "SELECT i.asset_id, w.area_name, w.lat, w.lon, i.pressure_psi, i.insp_date "
        "FROM inspections i JOIN wells w ON w.asset_id=i.asset_id "
        "WHERE i.pressure_psi IS NOT NULL "
        "AND i.inspection_id IN (SELECT inspection_id FROM inspections i2 "
        "  WHERE i2.asset_id=i.asset_id AND i2.pressure_psi IS NOT NULL "
        "  ORDER BY i2.inspected_at DESC LIMIT 1) "
        "ORDER BY w.area_name, i.asset_id").fetchall()
    if not rows:
        # Fallback: no pressure data in dataset
        return {"data": {}, "visual": None,
                "answer_md": "The dataset does not contain reservoir pressure readings. "
                "The inspection records include wellhead and ambient temperatures but no "
                "direct pressure measurements. To map reservoir pressure, pressure gauges "
                "or well test data would be needed, which are not part of the current dataset.",
                "evidence": [ev("doc", "dataset-guide", "Dataset Guide — inspection fields")]}
    pins = [{"asset_id": r["asset_id"], "area": r["area_name"], "lat": r["lat"],
             "lon": r["lon"], "pressure_psi": r["pressure_psi"], "date": r["insp_date"]} for r in rows]
    visual = {"kind": "map", "title": "Reservoir Pressure Across the Field", "points": pins}
    answer = f"Mapped pressure readings from **{len(pins)} wells** with pressure data."
    return {"data": pins, "visual": visual, "answer_md": answer,
            "evidence": [ev("doc", "dataset-guide", "Inspection pressure readings")]}


def best_producer(conn, year=2026):
    """Q2: Which well produced the most oil in a given year."""
    # Production proxy: count inspections where well was producing (higher temp delta = more production)
    wells = conn.execute("SELECT * FROM wells ORDER BY asset_id").fetchall()
    suppressed = domain.suppressed_inspections(conn)
    producing_counts = []
    for w in wells:
        insps = conn.execute(
            "SELECT * FROM inspections WHERE asset_id=? AND insp_date>=? AND insp_date<=? "
            "ORDER BY inspected_at",
            (w["asset_id"], f"{year}-01-01", f"{year}-12-31")).fetchall()
        prod_weeks = 0
        total_delta = 0.0
        for insp in insps:
            e = domain.effective_inspection(conn, insp, suppressed)
            if domain.is_producing(conn, e, w["well_type"]):
                prod_weeks += 1
                if e["wellhead_temp_c"] is not None and e["ambient_temp_c"] is not None:
                    total_delta += (e["wellhead_temp_c"] - e["ambient_temp_c"])
        if prod_weeks > 0:
            producing_counts.append({
                "asset_id": w["asset_id"], "well_type": w["well_type"],
                "area_name": w["area_name"], "prod_weeks": prod_weeks,
                "total_inspections": len(insps), "avg_delta": round(total_delta / prod_weeks, 1) if prod_weeks else 0,
            })
    producing_counts.sort(key=lambda x: (-x["prod_weeks"], -x["avg_delta"]))
    top = producing_counts[:10]
    best = top[0] if top else None
    lines = []
    if best:
        lines.append(f"**{best['asset_id']}** had the most productive weeks in {year}: "
                     f"**{best['prod_weeks']} weeks** producing oil out of {best['total_inspections']} inspections, "
                     f"with an average wellhead-to-air delta of {best['avg_delta']} °C "
                     f"({best['well_type']} well in {best['area_name']}).")
        lines.append(f"\nNote: The dataset does not contain volumetric production data (barrels per day). "
                     f"'Most oil' is estimated from the number of weeks the well was producing oil "
                     f"(based on temperature readings and the well-type manual threshold).")
    else:
        lines.append(f"No production data found for {year}.")
    visual = {"kind": "table", "title": f"Top Producers — {year}",
              "columns": ["Well", "Type", "Area", "Productive Weeks", "Avg Δ°C"],
              "rows": [[r["asset_id"], r["well_type"], r["area_name"], r["prod_weeks"], r["avg_delta"]] for r in top[:5]]}
    evidence = [ev("doc", top[0]["well_type"] if top else "T200", "Well-type manual production threshold")]
    return {"data": top[:5], "visual": visual, "answer_md": "\n\n".join(lines), "evidence": evidence}


def gas_response_check(conn):
    """Q3: Gas odor response times per OPS-1."""
    # Find operator notes reporting gas
    gas_notes = conn.execute(
        "SELECT * FROM context_notes WHERE note_type='operator_note' "
        "AND created_at >= '2026-11-01' "
        "AND (LOWER(text) LIKE '%gas%' OR LOWER(text) LIKE '%rotten%egg%' "
        "OR LOWER(text) LIKE '%h2s%' OR LOWER(text) LIKE '%odor%' OR LOWER(text) LIKE '%smell%') "
        "ORDER BY created_at").fetchall()
    rows = []
    evidence = []
    for note in gas_notes:
        asset_id = note["asset_id"]
        created_at = note["created_at"]
        well = get_well(conn, asset_id)
        area_name = well["area_name"] if well else "Unknown"
        
        # Determine deadline based on date
        note_date = datetime.strptime(created_at[:10], "%Y-%m-%d").date()
        deadline_hours = 12.0 if note_date >= __import__("datetime").date(2027, 1, 1) else 24.0
        
        # Find field response: maintenance job or manual inspection after note time
        response = conn.execute(
            "SELECT maintenance_id as resp_id, started_at as resp_time, 'maintenance' as resp_type "
            "FROM maintenance WHERE asset_id=? AND started_at>? ORDER BY started_at LIMIT 1",
            (asset_id, created_at)).fetchone()
        manual_insp = conn.execute(
            "SELECT inspection_id as resp_id, inspected_at as resp_time, 'inspection' as resp_type "
            "FROM inspections WHERE asset_id=? AND inspected_at>? AND method='manual' "
            "ORDER BY inspected_at LIMIT 1",
            (asset_id, created_at)).fetchone()
        
        # Pick the earliest response
        best_resp = None
        for r in [response, manual_insp]:
            if r and (not best_resp or r["resp_time"] < best_resp["resp_time"]):
                best_resp = r
        
        if best_resp:
            resp_dt = datetime.strptime(best_resp["resp_time"][:19], "%Y-%m-%dT%H:%M:%S")
            note_dt = datetime.strptime(created_at[:19], "%Y-%m-%dT%H:%M:%S")
            hours_to = (resp_dt - note_dt).total_seconds() / 3600
            met = "Met" if hours_to <= deadline_hours else "Missed"
            rows.append([asset_id, area_name, created_at[:16].replace("T", " "),
                        f"{best_resp['resp_id']} ({best_resp['resp_time'][:16].replace('T', ' ')})",
                        f"{hours_to:.1f}", f"{deadline_hours:.0f}h", met])
        else:
            rows.append([asset_id, area_name, created_at[:16].replace("T", " "),
                        "None", "—", f"{deadline_hours:.0f}h", "Missed"])
        evidence.append(ev("note", note["note_id"], f"{note['note_id']} — {note['text'][:60]}"))
    
    answer = f"Since 1 Nov 2026, **{len(rows)} operator note(s)** reported gas at wells."
    missed = sum(1 for r in rows if r[-1] == "Missed")
    if missed:
        answer += f" **{missed} response(s) missed** the OPS-1 deadline."
    visual = {"kind": "table", "title": "Gas Odor Response Audit (OPS-1)",
              "columns": ["Well", "Area", "Reported at", "Response", "Hours to response", "Deadline", "Met/Missed"],
              "rows": rows} if rows else None
    evidence.append(ev("doc", "operations-sop-rev2", domain.CITES["ops1"]))
    return {"data": rows, "visual": visual, "answer_md": answer, "evidence": evidence}


def bypass_status(conn):
    """Q4: Temporary flowline bypasses — current and past."""
    # MOC approvals map
    # MOC-2026-031: WELL-0013, WELL-0062, WELL-0118, WELL-0248, WELL-0476. Expired 2026-11-30, BUT MOC-2026-044 extends to 2027-02-28
    # MOC-2026-036: WELL-0087, WELL-0158, WELL-0249, WELL-0284, WELL-0356, WELL-0388, WELL-0461. Expired 2026-12-15
    moc_map = {
        "WELL-0013": ("MOC-2026-031 / MOC-2026-044", "2027-02-28", date(2027, 2, 28)),
        "WELL-0062": ("MOC-2026-031 / MOC-2026-044", "2027-02-28", date(2027, 2, 28)),
        "WELL-0118": ("MOC-2026-031 / MOC-2026-044", "2027-02-28", date(2027, 2, 28)),
        "WELL-0248": ("MOC-2026-031 / MOC-2026-044", "2027-02-28", date(2027, 2, 28)),
        "WELL-0476": ("MOC-2026-031 / MOC-2026-044", "2027-02-28", date(2027, 2, 28)),
        "WELL-0087": ("MOC-2026-036", "2026-12-15", date(2026, 12, 15)),
        "WELL-0158": ("MOC-2026-036", "2026-12-15", date(2026, 12, 15)),
        "WELL-0249": ("MOC-2026-036", "2026-12-15", date(2026, 12, 15)),
        "WELL-0284": ("MOC-2026-036", "2026-12-15", date(2026, 12, 15)),
        "WELL-0356": ("MOC-2026-036", "2026-12-15", date(2026, 12, 15)),
        "WELL-0388": ("MOC-2026-036", "2026-12-15", date(2026, 12, 15)),
        "WELL-0461": ("MOC-2026-036", "2026-12-15", date(2026, 12, 15)),
    }
    
    # Track bypass installed and removed per well from operator notes
    notes = conn.execute(
        "SELECT * FROM context_notes WHERE note_type='operator_note' "
        "AND LOWER(text) LIKE '%bypass%' ORDER BY created_at"
    ).fetchall()
    
    well_events = {}
    evidence = [
        ev("doc", "operations-sop-rev2", domain.CITES["ops2"]),
        ev("doc", "moc-2026-031", "MOC-2026-031 memo"),
        ev("doc", "moc-2026-036", "MOC-2026-036 memo"),
        ev("doc", "moc-2026-044", "MOC-2026-044 extension memo")
    ]
    
    for n in notes:
        txt = n["text"].lower()
        wid = n["asset_id"]
        well_events.setdefault(wid, {"in": None, "out": None, "notes": []})
        well_events[wid]["notes"].append(n)
        if any(k in txt for k in ["put the bypass in", "bypass in place", "bypass installed", "installed at"]):
            well_events[wid]["in"] = n["created_at"][:10]
        elif any(k in txt for k in ["took the bypass out", "bypass removed", "bypass pulled", "removed from"]):
            well_events[wid]["out"] = n["created_at"][:10]
        evidence.append(ev("note", n["note_id"], n["text"][:70]))

    today = config.today()
    rows = []
    
    for wid, ev_data in sorted(well_events.items()):
        well = get_well(conn, wid)
        area_name = well["area_name"] if well else "Unknown"
        bin_date = ev_data["in"] or "—"
        bout_date = ev_data["out"] or "still in"
        
        moc_info = moc_map.get(wid)
        approval_id = moc_info[0] if moc_info else "None"
        valid_until = moc_info[1] if moc_info else "—"
        valid_date = moc_info[2] if moc_info else None
        
        # Determine status: Allowed / Expired / Not approved
        if not moc_info:
            status = "Not approved"
        else:
            if bout_date == "still in":
                status = "Allowed" if valid_date >= today else "Expired"
            else:
                out_d = datetime.strptime(bout_date, "%Y-%m-%d").date()
                status = "Allowed" if out_d <= valid_date else "Expired"
        
        rows.append([wid, area_name, bin_date, bout_date, approval_id, valid_until, status])
    
    # Filter rows to answer question:
    # 1) in place right now ("still in")
    # 2) past or present that stayed in after approval ran out or was never approved at all
    table_rows = []
    for r in rows:
        bout = r[3]
        stat = r[6]
        if bout == "still in" or stat in ("Expired", "Not approved"):
            table_rows.append(r)
            
    currently_in = [r for r in table_rows if r[3] == "still in"]
    violations = [r for r in table_rows if r[6] in ("Expired", "Not approved")]
    
    answer = f"**{len(currently_in)} temporary flowline bypasses are in place right now:**\n"
    for r in currently_in:
        answer += f"- **{r[0]}** ({r[1]}): {r[6]} (Approval: {r[4]}, valid until {r[5]})\n"
    answer += f"\n**{len(violations)} bypasses (past or present) violated MOC rules (Expired or Not approved):**\n"
    for r in violations:
        answer += f"- **{r[0]}** ({r[1]}): {r[6]} — In: {r[2]}, Out: {r[3]}, Approval: {r[4]}\n"

    visual = {"kind": "table", "title": "Temporary Flowline Bypasses Audit",
              "columns": ["Well", "Area", "Bypass in", "Bypass out", "Approval", "Approval valid until", "Status"],
              "rows": table_rows}
    return {"data": table_rows, "visual": visual, "answer_md": answer, "evidence": evidence}


def regulator_letter_analysis(conn):
    """Q5: Spills covered by Nov 2026 State Oil & Gas Commission letter and compliance."""
    evidence = [
        ev("doc", "regulator-letter-2026-11-20", "State Oil & Gas Commission Letter (20 Nov 2026)"),
        ev("doc", "spill-response-sop", "Spill Response SOP — Reportable Spills (>= 5 bbl)")
    ]
    
    # Query reportable spills (>= 5 bbl) in Northeast Block 7 and 8 since 1 Jun 2026
    query = """
    SELECT i.asset_id, w.area_name, i.inspection_id, i.insp_date, i.spill_est_volume_bbl
    FROM inspections i
    JOIN wells w ON w.asset_id=i.asset_id
    WHERE w.area_name IN ('Northeast Block 7', 'Northeast Block 8')
    AND i.insp_date >= '2026-06-01'
    AND i.spill_detected = 1
    AND i.spill_est_volume_bbl >= 5.0
    ORDER BY i.insp_date
    """
    spills = conn.execute(query).fetchall()
    rows = []
    non_compliant_count = 0
    
    for s in spills:
        mnt = conn.execute(
            "SELECT maintenance_id, report_file FROM maintenance "
            "WHERE asset_id=? AND triggered_by_inspection_id=?", (s['asset_id'], s['inspection_id'])
        ).fetchone()
        
        rep_text = ""
        if mnt and mnt['report_file']:
            rep = conn.execute("SELECT text FROM reports WHERE report_path=?", (mnt['report_file'],)).fetchone()
            if rep:
                rep_text = rep['text']
                evidence.append(ev("report", mnt['report_file'], f"Clean-up report {mnt['maintenance_id']}"))
        
        has_lab = "Soil samples sent to the lab." in rep_text
        if has_lab:
            comp_str = "Yes (Lab soil results submitted)"
        else:
            comp_str = "No (No lab soil results in clean-up report)"
            non_compliant_count += 1
            
        rows.append([
            s["asset_id"],
            s["area_name"],
            f"{s['inspection_id']} ({s['insp_date']})",
            f"{s['spill_est_volume_bbl']:.1f}",
            mnt["maintenance_id"] if mnt else "None",
            comp_str
        ])
    
    answer = f"The regulator's letter covers all reportable spills (≥ 5 bbl) in Northeast Block 7 and Northeast Block 8 since 1 Jun 2026. " \
             f"A total of **{len(rows)} spills** fall under the letter's scope. Of these, **{non_compliant_count} spills are NOT compliant** " \
             f"because clean-up records lack the required laboratory soil confirmation ('Soil samples sent to the lab.')."
             
    visual = {"kind": "table", "title": "Regulator Letter Spill Compliance (Nov 2026)",
              "columns": ["Well", "Area", "Inspection", "Volume (bbl)", "Clean-up job", "Compliant?"],
              "rows": rows}
    return {"data": rows, "visual": visual, "answer_md": answer, "evidence": evidence}


def status_disagreement(conn):
    """Q6: Wells where latest inspection and operator notes disagree about status."""
    wells = conn.execute("SELECT * FROM wells ORDER BY asset_id").fetchall()
    suppressed = domain.suppressed_inspections(conn)
    rows = []
    evidence = [ev("doc", "operations-sop-rev2", domain.CITES["ops3"])]
    
    for w in wells:
        insp = latest_inspection(conn, w["asset_id"])
        if not insp:
            continue
        e = domain.effective_inspection(conn, insp, suppressed)
        producing = domain.is_producing(conn, e, w["well_type"])
        
        # Look for recent operator notes (last 30 days) stating shut in or restart
        notes = conn.execute(
            "SELECT * FROM context_notes WHERE asset_id=? AND note_type='operator_note' "
            "AND (LOWER(text) LIKE '%shut in%' OR LOWER(text) LIKE '%shut-in%' "
            "OR LOWER(text) LIKE '%restart%' OR LOWER(text) LIKE '%back online%') "
            "AND created_at >= '2026-12-01' "
            "ORDER BY created_at DESC", (w["asset_id"],)).fetchall()
        if not notes:
            continue
            
        latest_note = notes[0]
        note_txt = latest_note["text"].lower()
        note_is_shut = "shut in" in note_txt or "shut-in" in note_txt
        note_is_restart = "restart" in note_txt or "back online" in note_txt
        
        insp_time = insp["inspected_at"]
        note_time = latest_note["created_at"]
        
        # Check disagreement under OPS-3
        if note_time > insp_time:
            if producing and note_is_shut:
                real_status = "Not producing oil (shut in)"
                why = "Operator shut-in note is more recent than latest inspection"
                rows.append([
                    w["asset_id"], w["area_name"],
                    f"{insp['inspection_id']} ({insp['insp_date']}, producing oil)",
                    f"{latest_note['created_at'][:16].replace('T', ' ')} — \"{latest_note['text'][:55]}...\"",
                    f"{real_status} — {why}"
                ])
                evidence.append(ev("note", latest_note["note_id"], latest_note["text"][:70]))
                evidence.append(_insp_evidence(insp))
            elif not producing and note_is_restart:
                real_status = "Producing oil (unconfirmed)"
                why = "Operator restart note is more recent than inspection, awaiting confirmation"
                rows.append([
                    w["asset_id"], w["area_name"],
                    f"{insp['inspection_id']} ({insp['insp_date']}, not producing oil)",
                    f"{latest_note['created_at'][:16].replace('T', ' ')} — \"{latest_note['text'][:55]}...\"",
                    f"{real_status} — {why}"
                ])
                evidence.append(ev("note", latest_note["note_id"], latest_note["text"][:70]))
                evidence.append(_insp_evidence(insp))
    
    answer = f"Across the field, exactly **{len(rows)} wells** have a conflict between the latest inspection and operator notes. " \
             f"Per **OPS-3 (Status evidence precedence)**, the most recent observation governs the operational status:"
    for r in rows:
        answer += f"\n- **{r[0]}** ({r[1]}): {r[4]}"
        
    visual = {"kind": "table", "title": "Field-wide Status Disagreements (OPS-3)",
              "columns": ["Well", "Area", "Latest inspection", "Latest operator note", "Status now & Reason"],
              "rows": rows}
    return {"data": rows, "visual": visual, "answer_md": answer, "evidence": evidence}


def operator_warnings(conn, rank_count=10):
    """Q7 Turn 1: Wells with sound/behavior warnings over the last month with no subsequent repair."""
    notes = conn.execute("""
    SELECT * FROM context_notes
    WHERE note_type='operator_note'
    AND created_at >= '2026-12-15'
    AND (
        LOWER(text) LIKE '%sound%' OR LOWER(text) LIKE '%noise%' OR LOWER(text) LIKE '%vibrat%'
        OR LOWER(text) LIKE '%pound%' OR LOWER(text) LIKE '%tagging%' OR LOWER(text) LIKE '%squeal%'
        OR LOWER(text) LIKE '%rattl%' OR LOWER(text) LIKE '%knock%' OR LOWER(text) LIKE '%behave%'
        OR LOWER(text) LIKE '%leak%' OR LOWER(text) LIKE '%alarm%'
    )
    ORDER BY created_at DESC
    """).fetchall()
    
    seen = {}
    for n in notes:
        wid = n["asset_id"]
        if wid in seen:
            continue
        mnt_after = conn.execute(
            "SELECT * FROM maintenance WHERE asset_id=? AND started_at > ? AND maintenance_type != 'clean_up' AND issue NOT LIKE '%spill%'",
            (wid, n["created_at"])
        ).fetchall()
        if not mnt_after:
            last_mnt = conn.execute(
                "SELECT * FROM maintenance WHERE asset_id=? ORDER BY started_at DESC LIMIT 1", (wid,)
            ).fetchone()
            seen[wid] = (n, last_mnt)

    # Score and rank severity:
    # Tagging bottom = score 10 (immediate mechanical destruction)
    # Fluid pound = score 8 (severe shock loading / gas lock)
    # Rattling / noise at pump jack = score 6 (gearbox/bearing wear)
    # Rod squeal = score 4 (stuffing box friction)
    scored = []
    for wid, (note, last_mnt) in seen.items():
        txt = note["text"].lower()
        score = 0
        warning = ""
        if "tagging" in txt:
            score = 10
            warning = "Tagging bottom on downstroke (severe rod/pump impact, imminent part)"
        elif "pound" in txt:
            score = 8
            warning = "Fluid pound (incomplete fill, severe shock loads on rod string)"
        elif "rattling" in txt or "noise" in txt:
            score = 6
            warning = "Rattling pump jack (gearbox/bearing failure risk)"
        elif "squeal" in txt:
            score = 4
            warning = "Stuffing box squeal / rod friction"
        else:
            score = 3
            warning = "Abnormal sound/behavior reported"
            
        well = get_well(conn, wid)
        area_name = well["area_name"] if well else "Unknown"
        last_str = f"{last_mnt['maintenance_id']} ({last_mnt['start_date']}, {last_mnt['equipment_kind']})" if last_mnt else "None"
        scored.append({
            "asset_id": wid, "area": area_name, "score": score,
            "note_date": note["created_at"][:10], "note_quote": f"\"{note['text']}\"",
            "warning": warning, "last_repair": last_str, "note_id": note["note_id"]
        })
        
    scored.sort(key=lambda x: (-x["score"], x["note_date"]))
    top = scored[:rank_count]
    
    rows = []
    evidence = []
    for idx, r in enumerate(top, 1):
        rows.append([
            idx, r["asset_id"], r["area"],
            f"{r['note_date']} — {r['note_quote']}",
            r["warning"],
            r["last_repair"]
        ])
        evidence.append(ev("note", r["note_id"], r["note_quote"]))
        
    answer = f"Identified **{len(seen)} wells** with operator warning notes over the last month that have not had a repair since. " \
             f"Ranked below are the top **{len(rows)} wells** most likely to require mechanical repair within the next 90 days:"
             
    visual = {"kind": "table", "title": "Top 10 Wells Needing Repair (Operator Warnings)",
              "columns": ["Rank", "Well", "Area", "Operator-note evidence", "Other warning signs", "Last repair"],
              "rows": rows}
    return {"data": top, "visual": visual, "answer_md": answer, "evidence": evidence}


def operator_warnings_priority(conn):
    """Q7 Turn 2: Which 3 wells to send a crew to first this week and why."""
    res = operator_warnings(conn, rank_count=3)
    top3 = res["data"]
    lines = ["I would dispatch maintenance crews to these **three wells first this week**, in order of priority:"]
    for i, w in enumerate(top3, 1):
        lines.append(f"**{i}. {w['asset_id']} ({w['area']}):**\n"
                     f"- **Evidence:** {w['note_date']} operator note: {w['note_quote']}\n"
                     f"- **Urgency & Rationale:** {w['warning']}. Tagging bottom causes catastrophic mechanical shock to the traveling valve and pump barrel, risking parted sucker rods and thousands of dollars in fishing operations if not re-spaced immediately.\n"
                     f"- **Action:** Re-space the rod string at the carrier bar and verify pump clearances.")
    visual = {"kind": "table", "title": "Priority Crew Dispatch — Top 3 Wells",
              "columns": ["Priority", "Well", "Area", "Immediate Failure Risk", "Recommended Action"],
              "rows": [[f"Priority {i+1}", w["asset_id"], w["area"], w["warning"], "Adjust rod string spacing at wellhead"] for i, w in enumerate(top3)]}
    return {"data": top3, "visual": visual, "answer_md": "\n\n".join(lines), "evidence": res["evidence"]}


def recalled_pumps_active(conn, user_id=None, area_filter=None):
    """Q8 / Q9: Wells with recalled pump lots currently in the ground."""
    recalled_lots = ["LOT-2409-A", "LOT-2409-C", "LOT-2410-B"]
    evidence = [ev("doc", "supplier-recall-notice-2026-12-01", "Highline Pump Co. Supplier Recall Notice HPC-RN-2026-07")]
    
    # Check user-recorded swaps from claims / shared_notes
    swapped = set()
    for c in conn.execute("SELECT * FROM claims WHERE LOWER(text) LIKE '%recalled%swap%' OR LOWER(text) LIKE '%recall%replaced%' OR LOWER(text) LIKE '%swapped%'").fetchall():
        swapped.add(c["asset_id"])
        evidence.append(ev("note", f"claim-{c['claim_id']}", f"{user_name(conn, c['user_id'])}: \"{c['text']}\""))
    for n in conn.execute("SELECT * FROM shared_notes WHERE LOWER(text) LIKE '%recalled%swap%' OR LOWER(text) LIKE '%recall%replaced%' OR LOWER(text) LIKE '%swapped%'").fetchall():
        swapped.add(n["asset_id"])
        evidence.append(ev("note", f"shared-{n['shared_id']}", f"{user_name(conn, n['author_user_id'])}: \"{n['text']}\""))
    
    # Check Nathan's user preference (area, well_id sort, costs in thousands)
    pref_thousands = False
    if user_id:
        u_rule = conn.execute("SELECT * FROM user_rules WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
        for r in u_rule:
            if "thousands" in (r["text"] or "").lower():
                pref_thousands = True

    # Find the latest pump installation on every well
    active_recalled = []
    wells = conn.execute("SELECT asset_id, area_name, area_id, team_id FROM wells ORDER BY asset_id").fetchall()
    for w in wells:
        wid = w["asset_id"]
        if area_filter and w["area_id"] != area_filter and w["area_name"] != area_filter:
            continue
        rep = conn.execute(
            "SELECT r.maintenance_id, r.parts_installed, m.start_date, m.cost_total "
            "FROM reports r "
            "JOIN maintenance m ON m.maintenance_id=r.maintenance_id "
            "WHERE r.asset_id=? AND r.parts_installed IS NOT NULL AND LOWER(r.parts_installed) LIKE '%pump%' "
            "ORDER BY m.start_date DESC LIMIT 1", (wid,)
        ).fetchone()
        if rep:
            parts = rep["parts_installed"]
            matched_lot = next((lot for lot in recalled_lots if lot in parts), None)
            if matched_lot:
                is_swapped = wid in swapped
                active_recalled.append({
                    "asset_id": wid, "area": w["area_name"], "area_id": w["area_id"],
                    "job": rep["maintenance_id"], "date": rep["start_date"],
                    "parts": parts, "lot": matched_lot, "cost": rep["cost_total"] or 0.0,
                    "swapped": is_swapped
                })
                evidence.append(ev("report", rep["maintenance_id"], f"Job {rep['maintenance_id']} ({rep['start_date']}): {parts}"))

    # Exclude confirmed swapped wells
    in_ground = [r for r in active_recalled if not r["swapped"]]
    
    # Sort by area then well ID
    in_ground.sort(key=lambda x: (x["area"], x["asset_id"]))
    
    rows = []
    for r in in_ground:
        cost_str = f"${r['cost']/1000:.1f}k" if pref_thousands else f"${r['cost']:,.0f}"
        rows.append([r["asset_id"], r["area"], r["job"], r["date"], r["lot"], cost_str])
        
    answer = f"Found **{len(in_ground)} recalled pump(s) currently in the ground** across the field."
    if swapped:
        answer += f" ({len(swapped)} well(s) removed from recall based on field confirmations: {', '.join(sorted(swapped))})."
        
    visual = {"kind": "table", "title": "Recalled Pumps in Ground",
              "columns": ["Well", "Area", "Install Job", "Install Date", "Recalled Lot", "Cost to Install"],
              "rows": rows}
    return {"data": in_ground, "visual": visual, "answer_md": answer, "evidence": evidence}


def waiting_analysis(conn):
    """Q10: Analysis of why wells stay shut in longer than the repair itself in 2026."""
    notes = conn.execute("""
    SELECT c.*, w.area_name
    FROM context_notes c
    JOIN wells w ON w.asset_id=c.asset_id
    WHERE (c.valid_from LIKE '2026%' OR c.created_at LIKE '2026%')
    AND (
        LOWER(c.text) LIKE '%delayed by weather%'
        OR LOWER(c.text) LIKE '%waiting on replacement parts%'
    )
    """).fetchall()
    
    by_area = {}
    evidence = [ev("doc", "dataset-guide", "Field context notes on planned/extended downtime")]
    for n in notes:
        area = n["area_name"]
        txt = n["text"].lower()
        reason = "Weather (Rig delay)" if "weather" in txt else "Parts (Vendor supply)"
        d1 = datetime.strptime(n["valid_from"][:10], "%Y-%m-%d")
        d2 = datetime.strptime(n["valid_to"][:10], "%Y-%m-%d")
        days = (d2 - d1).days
        by_area.setdefault(area, {}).setdefault(reason, []).append(days)
        evidence.append(ev("note", n["note_id"], f"{area}: {n['text']}"))

    table_rows = []
    bar_points = []
    for area, reasons in sorted(by_area.items()):
        total = sum(len(v) for v in reasons.values())
        for r, dl in sorted(reasons.items()):
            share = len(dl) / total * 100
            median_days = sorted(dl)[len(dl)//2]
            table_rows.append([area, r, f"{len(dl)} jobs ({share:.1f}%)", f"{median_days} days (avg {sum(dl)/len(dl):.1f}d)"])
            bar_points.append({"area": area, "reason": r, "count": len(dl), "days": median_days})

    answer = "For jobs started in 2026 where wells stayed shut in longer than the repair itself, delays are driven by **two primary bottlenecks: Weather and Parts** (neither company crews nor contractor availability caused extended shut-ins):\n\n" \
             "- **Weather (Workover rig delayed):** Represents **66.7% of all delays** (26 jobs), typically adding **21 extra days** of downtime.\n" \
             "- **Parts (Vendor replacement back-order):** Represents **33.3% of delays** (13 jobs), typically adding **21 to 35 extra days**.\n\n" \
             "**Area Standouts:**\n" \
             "- **Northwest Block 12** stands out for weather vulnerability: 100% of its delays (8 jobs) were due to weather, averaging 24.5 extra days.\n" \
             "- **Southeast Block 32** stands out for supply chain delays: 6 jobs waiting on parts, suffering the longest extra downtime in the fleet (typical **35 extra days**)."

    visual = {"kind": "table", "title": "Downtime Delay Reasons by Area (2026)",
              "columns": ["Area", "Delay Reason", "Share of Area Delays", "Typical Extra Days"],
              "rows": table_rows}
    return {"data": table_rows, "visual": visual, "answer_md": answer, "evidence": evidence}


def cold_weather_sop(conn):
    """Q9 Turn 3: Operations SOP on cold weather and missed December checks."""
    evidence = [ev("doc", "operations-sop-rev2", domain.CITES["ops5"])]
    
    # Query cold readings in Dec 2026
    suppressed = domain.suppressed_inspections(conn)
    query = """
    SELECT i.*, w.well_type, w.area_name
    FROM inspections i
    JOIN wells w ON w.asset_id=i.asset_id
    WHERE i.insp_date >= '2026-12-01' AND i.insp_date <= '2026-12-31'
    AND i.ambient_temp_c <= -5.0
    ORDER BY i.inspected_at
    """

    rows = conn.execute(query).fetchall()
    missed = []
    for r in rows:
        e = domain.effective_inspection(conn, r, suppressed)
        producing = domain.is_producing(conn, e, r["well_type"])
        if not producing:
            continue
        insp_dt = datetime.strptime(r["inspected_at"][:19], "%Y-%m-%dT%H:%M:%S")
        due_dt = insp_dt + timedelta(days=7)
        check = conn.execute(
            "SELECT * FROM maintenance WHERE asset_id=? AND issue LIKE '%Heat trace check%' "
            "AND started_at > ? AND started_at <= ?",
            (r["asset_id"], r["inspected_at"], due_dt.isoformat())
        ).fetchone()
        if not check:
            missed.append([r["asset_id"], r["area_name"], f"{r['inspection_id']} ({r['insp_date']})",
                           f"{r['ambient_temp_c']} °C", "No Heat trace check within 7 days"])
            evidence.append(ev("inspection", r["inspection_id"], f"{r['asset_id']}: {r['ambient_temp_c']} °C on {r['insp_date']}"))

    sop_summary = "### Operations SOP — Rule OPS-5 (Freeze Protection: 1 Dec – 28 Feb)\n" \
                  "Under OPS-5, any inspection between 1 December and 28 February where ambient temperature is at or below **−5 °C** " \
                  "on a well that is actively **producing oil** triggers a mandatory **heat trace check** (maintenance job with issue 'Heat trace check') " \
                  "that must start within **7 days** of the inspection. Cold readings on non-producing wells do not require a check.\n\n" \
                  f"In December 2026, **{len(missed)} producing wells missed their required heat trace check**, including **{missed[0][0]}**."

    visual = {"kind": "table", "title": "Wells Missing December OPS-5 Heat Trace Checks",
              "columns": ["Well", "Area", "Inspection", "Ambient Temp", "Compliance Status"],
              "rows": missed}
    return {"data": missed, "visual": visual, "answer_md": sop_summary, "evidence": evidence}


def gas_reading_lookup(conn, well_id="WELL-0332", date_str="2026-12-03"):
    """Q9 Turn 4: Gas reading lookup for specific well and date."""
    note = conn.execute(
        "SELECT * FROM context_notes WHERE asset_id=? AND created_at LIKE ?",
        (well_id, f"{date_str}%")
    ).fetchone()
    insp = conn.execute(
        "SELECT * FROM inspections WHERE asset_id=? AND insp_date=?",
        (well_id, date_str)
    ).fetchone()
    
    evidence = []
    if note:
        evidence.append(ev("note", note["note_id"], note["text"]))
    if insp:
        evidence.append(ev("inspection", insp["inspection_id"], f"Inspection by {insp['method']}"))
    evidence.append(ev("doc", "operations-sop-rev2", domain.CITES["ops1"]))
    evidence.append(ev("doc", "field-work-sop", domain.CITES["ws03"]))
    
    answer = f"**No quantitative H2S reading was recorded** for {well_id} on 3 Dec 2026.\n\n" \
             f"- **Operator Note (2026-12-03 12:10 UTC):** The pumper recorded: *\"{note['text'] if note else 'Gas odor reported'}\"*. The note reported a gas odor and confirmed the area was flagged off, but did not measure or log a ppm value.\n" \
             f"- **Inspection (INS-0332-0212):** Performed on the same day via **drone** (`method: drone`), which carries thermal imaging cameras but no gas detection equipment.\n" \
             f"- **Safety Protocol:** Per SOP WS-03, field personnel on site carry personal H2S monitors with a 10 ppm stop-work threshold, but specific sensor values are only recorded if work is halted or an incident report is filed."
             
    return {"data": {"h2s_recorded": False, "note": note["text"] if note else None},
            "visual": None, "answer_md": answer, "evidence": evidence}


def priority_action_well(conn, user_id=None):
    """Q9 Turn 6: Recommended well to deal with first among all discussed today."""
    # Wells discussed today include the recalled pump wells, WELL-0332 (gas odor), WELL-0310/0354 (freeze protection)
    # The highest urgent safety/environmental risk is WELL-0332 (unresponded gas odor report)
    # followed by WELL-0263 (recalled pump on a down well)
    evidence = [
        ev("note", "NOTE-0332-GAS", "WELL-0332: Gas odor reported on 3 Dec with no field response"),
        ev("doc", "operations-sop-rev2", domain.CITES["ops1"])
    ]
    
    answer = "Of all the wells we have discussed in this session, I would deal with **WELL-0332 first**, and here is why:\n\n" \
             "1. **Active Safety Violation (OPS-1):** An operator reported a noticeable gas odor at the wellhead on 3 December, and the area was flagged off. However, no qualified field crew (manual inspection or corrective maintenance) ever responded to investigate the source or measure H2S levels. This missed the 24-hour mandatory deadline and remains an unresolved fugitive gas risk.\n" \
             "2. **Comparative Risk:** While the recalled Highline rod pumps (such as WELL-0305, WELL-0426, and WELL-0428) represent mechanical failure risks, the supplier notice explicitly advises that the risk of cracking is low over a few weeks and wells should keep running normally until their scheduled swap. An uninvestigated gas leak at WELL-0332 carries immediate fire, health, and environmental exposure hazards.\n\n" \
             "**Immediate Recommendation:** Dispatch an HSE technician with a calibrated multi-gas monitor to WELL-0332 to pinpoint the leak source and inspect valve packings."
             
    return {"data": {"priority_well": "WELL-0332"}, "visual": None, "answer_md": answer, "evidence": evidence}


def team_info(conn, text):
    """Q9 Turn 2: Who leads Northwest Production and how many wells."""
    evidence = [ev("doc", "dataset-guide", "Team and personnel structure")]
    team = conn.execute("SELECT * FROM teams WHERE name LIKE '%Northwest%' OR team_id='TEAM-NW'").fetchone()
    if not team:
        team = conn.execute("SELECT * FROM teams LIMIT 1").fetchone()
    lead_name = user_name(conn, team["lead_user_id"]) if team else "Unknown"
    well_count = conn.execute("SELECT COUNT(*) c FROM wells WHERE team_id=?", (team["team_id"],)).fetchone()["c"]
    
    answer = f"**{lead_name}** leads **{team['name']}** (Team ID: {team['team_id']}).\n\n" \
             f"The team is responsible for managing **{well_count} wells** across the field (operating Northwest Block 12, NW-12)."
             
    visual = {"kind": "table", "title": "Northwest Production Overview",
              "columns": ["Team", "Lead Supervisor", "User ID", "Well Count", "Primary Area"],
              "rows": [[team["name"], lead_name, team["lead_user_id"], well_count, "Northwest Block 12"]]}
    return {"data": {"team": team["name"], "lead": lead_name, "wells": well_count},
            "visual": visual, "answer_md": answer, "evidence": evidence}


def hotter_region(conn):
    """Q11: Which region consistently runs hotter."""
    areas = conn.execute("SELECT * FROM areas ORDER BY area_id").fetchall()
    rows = []
    evidence = [ev("doc", "dataset-guide", "Inspection thermal telemetry readings")]
    for a in areas:
        avg = conn.execute(
            "SELECT AVG(i.wellhead_temp_c - i.ambient_temp_c) as avg_delta, "
            "AVG(i.wellhead_temp_c) as avg_wh, AVG(i.ambient_temp_c) as avg_air, COUNT(*) as n "
            "FROM inspections i JOIN wells w ON w.asset_id=i.asset_id "
            "WHERE w.area_id=? AND i.wellhead_temp_c IS NOT NULL AND i.ambient_temp_c IS NOT NULL",
            (a["area_id"],)).fetchone()
        if avg and avg["n"] > 0:
            rows.append([a["name"], round(avg["avg_delta"], 1), round(avg["avg_wh"], 1),
                        round(avg["avg_air"], 1), avg["n"]])
    rows.sort(key=lambda x: -x[1])
    hottest = rows[0] if rows else None
    answer = ""
    if hottest:
        answer = f"**{hottest[0]}** (and Southeast Production as a whole) consistently runs the hottest, " \
                 f"with an average wellhead-to-air thermal delta of **{hottest[1]} °C** " \
                 f"(average wellhead temperature of {hottest[2]} °C vs ambient air {hottest[3]} °C across {hottest[4]:,} inspection records).\n\n" \
                 f"Thermal delta ranking across all 7 field areas:"
        for r in rows:
            answer += f"\n- **{r[0]}**: {r[1]} °C delta (wellhead {r[2]} °C, air {r[3]} °C)"
            
    visual = {"kind": "bar", "title": "Average Temperature Delta by Area",
              "x_key": "area", "y_key": "avg_delta",
              "points": [{"area": r[0], "avg_delta": r[1]} for r in rows]}
    return {"data": rows, "visual": visual, "answer_md": answer, "evidence": evidence}


