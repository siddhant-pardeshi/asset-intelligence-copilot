"""Field-operations decision-support tools.

These answer the two questions a production team actually opens the day with:
"what should the crew work on, in what order" and "what is this downtime
costing us". Both are computed from the same deterministic store as the
chat tools; nothing here calls a model.
"""
import sqlite3

from . import config, domain
from .tools import CITES, _thr_sql, ev, get_well, valid_spills


def crew_board(conn: sqlite3.Connection, area_id=None, window_days=90):
    """The morning-standup view: every open action the field team owns, ranked.

    Real fields run on a standup board, not on ad-hoc questions. This rolls up
    deadlines and orphans across the whole field into one ranked list, each row
    carrying the evidence behind it.
    """
    t = config.today()
    tiso = t.isoformat()
    board, evidence = [], []

    def add(prio, well, area, action, why, due, ev_item=None):
        board.append({"priority": prio, "asset_id": well, "area": area,
                      "action": action, "why": why, "due": due})
        if ev_item:
            evidence.append(ev_item)

    # P1: reportable spills (>=5 bbl, valid) with no written notice on record
    for s in valid_spills(conn, area_id=area_id, start=t - domain.timedelta(days=window_days), end=t):
        vol = s["spill_est_volume_bbl"]
        if vol < domain.SPILL_REPORTABLE_BBL:
            continue
        filed = conn.execute(
            "SELECT event_id FROM reg_events WHERE asset_id=? AND related_inspection_id=? "
            "AND event_type='spill_report_filed' LIMIT 1",
            (s["asset_id"], s["inspection_id"])).fetchone()
        if not filed:
            w = get_well(conn, s["asset_id"])
            add("P1", s["asset_id"], w["area_name"],
                "File the spill report with the State Oil & Gas Commission",
                f"{vol} bbl spill ({s['inspection_id']}, {s['insp_date']}) with no written "
                f"notice on record — SR-01 breach in progress",
                "overdue",
                ev("inspection", s["inspection_id"], f"{s['asset_id']} spill {s['insp_date']}"))

    # P1: NOVs whose 30-day response window (RC-04) has passed
    for n in conn.execute(
            "SELECT * FROM reg_events WHERE event_type='notice_of_violation' AND status='open'"):
        w = get_well(conn, n["asset_id"])
        if not w or (area_id and w["area_id"] != area_id):
            continue
        due = domain.iso_to_date(n["date"]) + domain.timedelta(days=domain.RC04_RESPONSE_DAYS)
        if due > t:
            continue
        resp = conn.execute(
            "SELECT COUNT(*) c FROM reg_events WHERE asset_id=? AND "
            "event_type='nov_response_filed' AND date>=?",
            (n["asset_id"], n["date"])).fetchone()["c"]
        if not resp:
            add("P1", n["asset_id"], w["area_name"],
                f"Answer notice of violation {n['event_id']}",
                f"open NOV since {n['date']}, response was due {due.isoformat()} "
                f"({CITES['rc04']})",
                f"overdue since {due.isoformat()}",
                ev("event", n["event_id"], n["detail"]))

    # P2: SR-03 remediation verifications past their 60-day deadline
    for s in valid_spills(conn, area_id=area_id, start=domain.months_ago(t, 12), end=t):
        vol = s["spill_est_volume_bbl"]
        if vol < domain.SPILL_REPORTABLE_BBL:
            continue
        disc = domain.iso_to_date(s["inspected_at"])
        due3 = disc + domain.timedelta(days=domain.SR03_VERIFY_DAYS)
        if due3 > t:
            continue
        closed = conn.execute(
            "SELECT COUNT(*) c FROM reg_events WHERE asset_id=? AND related_inspection_id=? "
            "AND event_type='site_inspection' AND status='closed'",
            (s["asset_id"], s["inspection_id"])).fetchone()["c"]
        if not closed:
            w = get_well(conn, s["asset_id"])
            add("P2", s["asset_id"], w["area_name"],
                "Close out SR-03 remediation verification with the agency",
                f"{vol} bbl spill {s['insp_date']}, verification due {due3.isoformat()} "
                f"({CITES['sr03']})",
                f"overdue since {due3.isoformat()}",
                ev("inspection", s["inspection_id"], "spill discovery"))

    # P2: root-cause analyses due (manual escalation counts; T500/ESP triggers at 2)
    start12 = str(domain.months_ago(t, 12))
    counts = conn.execute(
        """SELECT m.asset_id, m.equipment_kind, COUNT(*) c, w.well_type, w.area_name
           FROM maintenance m JOIN wells w ON w.asset_id=m.asset_id
           WHERE m.maintenance_type='corrective' AND m.started_at>=?
           GROUP BY m.asset_id, m.equipment_kind, w.well_type, w.area_name""",
        (start12,)).fetchall()
    for r in counts:
        thr = domain.RCA_COUNT_ESP if r["well_type"] == "T500" else domain.RCA_COUNT
        if r["c"] < thr:
            continue
        flagged = conn.execute(
            "SELECT COUNT(*) c FROM reports WHERE asset_id=? AND rca_action_required=1",
            (r["asset_id"],)).fetchone()["c"]
        if flagged:
            add("P2", r["asset_id"], r["area_name"],
                f"Run a root-cause analysis on the {r['equipment_kind'].replace('_', ' ')}",
                f"{r['c']} corrective repairs in 12 months vs {thr} allowed for "
                f"{r['well_type']} ({CITES['rca']})",
                "before the next repair closes")

    # P3: orphan down wells — two consecutive down weeks, no work order
    wells = conn.execute(
        "SELECT * FROM wells WHERE (? IS NULL OR area_id=?) ORDER BY asset_id",
        (area_id, area_id)).fetchall()
    for w in wells:
        if w["recorded_status"] == "plugged":
            continue
        last2 = conn.execute(
            "SELECT * FROM inspections WHERE asset_id=? ORDER BY inspected_at DESC LIMIT 2",
            (w["asset_id"],)).fetchall()
        if len(last2) < 2:
            continue
        thr = domain.producing_threshold(conn, w["well_type"])
        down2 = all(
            i["wellhead_temp_c"] is not None and i["ambient_temp_c"] is not None and
            (i["wellhead_temp_c"] - i["ambient_temp_c"]) < thr for i in last2)
        if not down2:
            continue
        open_m = conn.execute(
            "SELECT COUNT(*) c FROM maintenance WHERE asset_id=? AND "
            "maintenance_type='corrective' AND (completed_at IS NULL OR completed_at>?)",
            (w["asset_id"], f"{t}T23:59:59Z")).fetchone()["c"]
        if not open_m:
            add("P3", w["asset_id"], w["area_name"],
                "Assign a crew: two consecutive down weeks, no open work order",
                f"down since at least {last2[1]['insp_date']} with no corrective "
                f"maintenance on record",
                "this week",
                ev("inspection", last2[0]["inspection_id"], "latest down inspection"))

    # P3: planned shut-ins not recorded in the maintenance system (manual §4)
    for n in conn.execute(
            "SELECT * FROM context_notes WHERE note_type!='correction' AND "
            "(valid_from IS NULL OR valid_from<=?) AND (valid_to IS NULL OR valid_to>=?)",
            (tiso, tiso)):
        if "shut in" not in (n["text"] or "").lower():
            continue
        w = get_well(conn, n["asset_id"])
        if not w or (area_id and w["area_id"] != area_id):
            continue
        m = conn.execute(
            "SELECT COUNT(*) c FROM maintenance WHERE asset_id=? AND started_at>=?",
            (n["asset_id"], n["valid_from"] or "1990-01-01")).fetchone()["c"]
        if not m:
            add("P3", n["asset_id"], w["area_name"],
                "Record the planned shut-in in the maintenance system",
                f"note {n['note_id']}: \"{(n['text'] or '')[:70]}...\" — the manual "
                f"requires the work order before work starts",
                "today")

    order = {"P1": 0, "P2": 1, "P3": 2}
    board.sort(key=lambda x: (order[x["priority"]], x["asset_id"]))
    counts = {p: sum(1 for b in board if b["priority"] == p) for p in ("P1", "P2", "P3")}
    lines = [f"**{len(board)} open item(s)** on today's board — {counts['P1']} P1, "
             f"{counts['P2']} P2, {counts['P3']} P3."]
    for b in board[:15]:
        lines.append(f"- **{b['priority']} · {b['asset_id']}** ({b['area']}) — {b['action']}. "
                     f"{b['why']}. Due: {b['due']}.")
    if len(board) > 15:
        lines.append(f"...and {len(board) - 15} more on the dashboard board.")
    visual = {"kind": "table", "title": "Crew priority board",
              "columns": ["Priority", "Well", "Area", "Action", "Why", "Due"],
              "rows": [[b["priority"], b["asset_id"], b["area"], b["action"], b["why"],
                        b["due"]] for b in board]}
    return {"data": {"board": board, "counts": counts}, "visual": visual,
            "answer_md": "\n".join(lines), "evidence": evidence[:25]}


def production_loss(conn: sqlite3.Connection, days=30, area_id=None):
    """Downtime translated into barrels and dollars, under stated assumptions.

    The dataset never records production volumes, so this is explicitly an
    order-of-magnitude estimate for prioritisation: downtime weeks x an assumed
    rate per well type x an assumed price. Every answer repeats the assumptions
    so nobody mistakes it for a measurement, and both knobs are deployment
    settings, not hard-coded truths.
    """
    t = config.today()
    start = t - domain.timedelta(days=days)
    rates, price = config.LOSS_RATES_BBL_PER_DAY, config.OIL_PRICE_USD
    q = f"""SELECT i.asset_id, w.well_type, w.area_name, COUNT(*) n
            FROM inspections i JOIN wells w ON w.asset_id=i.asset_id
            WHERE i.insp_date>=? AND i.insp_date<=? AND i.wellhead_temp_c IS NOT NULL
              AND (i.wellhead_temp_c - i.ambient_temp_c) < {_thr_sql()}"""
    args = [str(start), str(t)]
    if area_id:
        q += " AND w.area_id=?"
        args.append(area_id)
    q += " GROUP BY i.asset_id, w.well_type, w.area_name"
    by_area, total_bbl, wells_hit = {}, 0.0, 0
    for r in conn.execute(q, args):
        rate = rates.get(r["well_type"], 60.0)
        bbl = r["n"] * 7 * rate
        total_bbl += bbl
        wells_hit += 1
        by_area.setdefault(r["area_name"], {"bbl": 0.0, "days": 0})
        by_area[r["area_name"]]["bbl"] += bbl
        by_area[r["area_name"]]["days"] += r["n"] * 7
    total_usd = total_bbl * price
    rows = sorted(by_area.items(), key=lambda kv: -kv[1]["bbl"])
    lines = [
        f"Wells down over the last {days} days cost an estimated "
        f"**{total_bbl:,.0f} barrels** (about **USD {total_usd:,.0f}** at the assumed "
        f"${price:.0f}/bbl).",
        f"Assumptions, stated openly: this dataset records downtime but never production "
        f"volumes, so the estimate uses {rates} bbl/day by well type and "
        f"${price:.0f}/bbl. It is a prioritisation aid, not a measurement — in a real "
        f"deployment both knobs come from the SCADA historian via LOSS_RATES_JSON and "
        f"OIL_PRICE_USD.",
    ]
    if rows:
        lines.append("By area:")
        for area, v in rows:
            lines.append(f"- {area}: {v['bbl']:,.0f} bbl ({v['days']} down-days)")
    visual = {"kind": "bar", "title": f"Estimated lost volume by area (last {days} days)",
              "x_key": "area", "y_key": "bbl",
              "points": [{"area": a, "bbl": round(v["bbl"])} for a, v in rows]}
    evidence = [ev("doc", "dataset-guide",
                   "downtime = 7 days per not-producing weekly inspection"),
                ev("doc", "deployment-config",
                   "rates and price are deployment settings, not recorded production")]
    return {"data": {"total_bbl": round(total_bbl), "total_usd": round(total_usd),
                     "by_area": dict(rows), "wells": wells_hit},
            "visual": visual, "answer_md": "\n".join(lines), "evidence": evidence}
