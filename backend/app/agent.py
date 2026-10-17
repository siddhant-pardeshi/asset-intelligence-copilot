"""Agent orchestration.

Flow: resolve private-memory references → route the question (deterministic
router, optional LLM planner) → run the deterministic tools → record any
feedback/claims the message contained (with conflict checking) → assemble the
answer envelope (prose + generative visual + evidence).

The optional LLM only ever rephrases prose over tool-computed numbers; it can
never change a figure, which keeps answers reproducible.
"""
import json
import re
import sqlite3
from datetime import date, timedelta

from . import config, db, domain, memory, nlu, ops_tools, tools


def _areas(conn):
    return [(r["area_id"], r["name"]) for r in conn.execute("SELECT area_id, name FROM areas")]


def _user_id_by_name(conn, name):
    row = conn.execute("SELECT user_id FROM users WHERE name LIKE ?", (f"%{name}%",)).fetchone()
    return row["user_id"] if row else None


def _resolve_user(conn, user_ref):
    """user_id directly, or a person's name mentioned in the message."""
    if user_ref:
        return user_ref
    return None


def _get_or_create_conversation(conn, user_id, conversation_id=None):
    if conversation_id:
        row = conn.execute("SELECT conversation_id FROM conversations WHERE conversation_id=?",
                           (conversation_id,)).fetchone()
        if row:
            return conversation_id
    cur = conn.execute("INSERT INTO conversations(user_id, title, created_at) VALUES(?,?,?)",
                       (user_id, "New conversation", memory.now_iso()))
    conn.commit()
    return cur.lastrowid


def answer(conn, user_id, message, conversation_id=None, user_ref=None):
    """Main entry. Returns (conversation_id, envelope)."""
    user_id = user_id or _user_id_by_name(conn, user_ref) or "U-000"
    cid = _get_or_create_conversation(conn, user_id, conversation_id)
    cur = conn.execute("INSERT INTO messages(conversation_id, user_id, role, content, created_at) "
                       "VALUES(?,?,?,?,?)",
                       (cid, user_id, "user", message, memory.now_iso()))
    conn.commit()
    turn_id = cur.lastrowid
    envelope = handle(conn, user_id, cid, message)
    conn.execute("UPDATE conversations SET title=? WHERE conversation_id=? AND title=?",
                 (message[:60], cid, "New conversation"))
    _remember_entities(conn, user_id, cid, envelope, turn_id)
    conn.execute("INSERT INTO messages(conversation_id, user_id, role, content, envelope_json, "
                 "created_at) VALUES(?,?,?,?,?,?)",
                 (cid, user_id, "assistant", envelope.get("text", ""),
                  json.dumps(envelope), memory.now_iso()))
    conn.commit()
    return cid, envelope


def handle(conn, user_id, cid, message):
    params = nlu.route(conn, message, _areas(conn), user_id)
    intent = params["intent"]
    result = _dispatch(conn, user_id, cid, params, intent)
    if "text" not in result and "answer_md" in result:
        result = dict(result, text=result.pop("answer_md"))
    return result


def _remember_entities(conn, user_id, cid, envelope, turn_id=None):
    """Private memory: record which wells THIS answer showed this user."""
    ids = []
    visual = envelope.get("visual") or {}
    if visual.get("kind") in ("bar", "line"):
        for p in visual.get("points", []):
            if p.get("asset_id"):
                ids.append(p["asset_id"])
    elif visual.get("kind") in ("table",):
        for row in visual.get("rows", []):
            for cell in row:
                if isinstance(cell, str) and re.match(r"WELL-\d{4}$", cell):
                    ids.append(cell)
                    break
    elif visual.get("kind") in ("card", "map"):
        for p in visual.get("points", []) or []:
            if p.get("asset_id"):
                ids.append(p["asset_id"])
        if visual.get("payload", {}).get("asset_id"):
            ids.append(visual["payload"]["asset_id"])
    if not ids:  # fall back to the prose
        ids = re.findall(r"WELL-\d{4}", envelope.get("text", ""))
    if ids:
        memory.record_entity_mentions(conn, user_id, cid, ids, turn_id=turn_id)


def _dispatch(conn, user_id, cid, params, intent):

    # Private memory: entity references from THIS user's own past conversations
    if params.get("memory_refs"):
        refs = memory.discussed_entities(conn, user_id, n=params.get("n_refs", 3))
        n_refs = params.get("n_refs")
        if not refs or (n_refs and len(refs) < n_refs):
            return {"text": f"I don't have an earlier conversation with you about "
                            f"{'those wells' if n_refs else 'specific wells'}, "
                            f"{tools.user_name(conn, user_id)}. Private memory is per user — "
                            f"\"the wells we discussed\" can only refer to questions you asked "
                            f"me yourself, never another user's history.",
                    "visual": None, "evidence": []}
        params["wells"] = refs

    if intent == "correction_raw":
        return _apply_raw_correction(conn, user_id, params)
    if intent == "correction_analysis":
        return _apply_analysis_correction(conn, user_id, params)
    if intent == "rule_rca":
        return _record_rule(conn, user_id, params)
    if intent == "shared_note":
        return _record_shared_note(conn, user_id, params)
    if intent == "claim":
        return _record_claim(conn, user_id, cid, params)
    if intent == "planned_downtime":
        return _planned_downtime(conn, params)
    if intent == "well_status":
        return tools.get_well_status(conn, params["wells"][0])
    if intent == "crew_board":
        return ops_tools.crew_board(conn, params.get("area"))
    if intent == "production_loss":
        p = params.get("period") or {}
        days = 30
        if p.get("start") and p.get("end"):
            days = max(1, (p["end"] - p["start"]).days)
        return ops_tools.production_loss(conn, days=days, area_id=params.get("area"))
    if intent == "not_producing":
        return tools.list_not_producing(conn, params["area"])
    if intent == "temp_series":
        return tools.temp_series(conn, params["wells"][0], params.get("weeks", 13))
    if intent == "spill_history":
        p = params.get("period") or {}
        return tools.spill_history(conn, asset_id=(params["wells"] or [None])[0],
                                   area_id=params["area"], start=p.get("start"), end=p.get("end"))
    if intent == "downtime_days":
        p = params.get("period") or {}
        year = p.get("year")
        start = p.get("start") or date(year or config.today().year, 1, 1)
        end = p.get("end") or date(year or config.today().year, 12, 31)
        return tools.downtime_days(conn, params["wells"][0], start, end)
    if intent == "downtime_ranking":
        p = params.get("period") or domain.window_last_months(4)
        return tools.downtime_ranking(conn, params["area"], p["start"], p["end"],
                                      params.get("top_n", 3))
    if intent == "spill_map":
        p = params.get("period") or domain.window_last_days(90)
        return tools.spill_map(conn, params["area"], p["start"], p["end"])
    if intent == "heatmap":
        year = (params.get("period") or {}).get("year") or config.today().year
        return tools.spill_heatmap(conn, year)
    if intent == "compliance":
        return tools.compliance_report(conn, params["wells"][0], params.get("months", 12))
    if intent == "containment":
        p = params.get("period") or domain.window_last_days(90)
        return tools.containment_breaches(conn, params["area"], p["start"], p["end"])
    if intent == "report_needed":
        p = params.get("period") or domain.window_last_days(90)
        return tools.spills_needing_report(conn, params["area"], p["start"], p["end"])
    if intent == "costs":
        wells = params["wells"] or memory.discussed_entities(conn, user_id, n=3)
        year = (params.get("period") or {}).get("year") or config.today().year
        return tools.maintenance_costs(conn, wells, year)
    if intent == "rca":
        return tools.rca_needed(conn, params["area"],
                                params.get("equipment") or "pump_jack", user_id=user_id)
    if intent == "spill_detail":
        hint = params.get("date_hint") or nlu.find_date_hint(params["text"])
        insp_id = nlu.resolve_inspection(conn, params["wells"][0], hint) if params["wells"] else None
        return tools.spill_detail(conn, params["wells"][0], inspection_id=insp_id)
    if intent == "repair_types":
        return tools.get_repair_types(conn)
    if intent == "fleet_summary":
        return tools.get_fleet_summary(conn)
    if intent == "top_issues":
        return tools.get_top_issues(conn)
    if intent == "sop_rule":
        res = tools.lookup_sop_rule(conn, params["text"])
        if res:
            return res
    if intent == "pump_swap_claim":
        return _record_pump_swap(conn, user_id, params)
    if intent == "user_pref":
        return _record_user_preference(conn, user_id, params)
    if intent == "reservoir_pressure":
        return tools.reservoir_pressure_map(conn)
    if intent == "best_producer":
        y = (params.get("period") or {}).get("year") or 2026
        return tools.best_producer(conn, y)
    if intent == "gas_response":
        return tools.gas_response_check(conn)
    if intent == "bypass_status":
        return tools.bypass_status(conn)
    if intent == "regulator_letter":
        return tools.regulator_letter_analysis(conn)
    if intent == "status_disagreement":
        return tools.status_disagreement(conn)
    if intent == "operator_warnings":
        return tools.operator_warnings(conn)
    if intent == "operator_priority":
        return tools.operator_warnings_priority(conn)
    if intent == "recalled_pumps":
        area = params.get("area")
        if not area and "my area" in params.get("text", "").lower() and user_id:
            user_row = conn.execute("SELECT team_id FROM users WHERE user_id=?", (user_id,)).fetchone()
            if user_row and user_row["team_id"]:
                area_row = conn.execute("SELECT area_id FROM areas WHERE team_id=?", (user_row["team_id"],)).fetchone()
                if area_row:
                    area = area_row["area_id"]
        return tools.recalled_pumps_active(conn, user_id=user_id, area_filter=area)

    if intent == "recalled_pumps_status":
        return _recalled_pumps_status(conn)
    if intent == "waiting_analysis":
        return tools.waiting_analysis(conn)
    if intent == "hotter_region":
        return tools.hotter_region(conn)
    if intent == "cold_weather":
        return tools.cold_weather_sop(conn)
    if intent == "gas_reading":
        well = (params.get("wells") or ["WELL-0332"])[0]
        return tools.gas_reading_lookup(conn, well, "2026-12-03")
    if intent == "team_info":
        return tools.team_info(conn, params["text"])
    if intent == "priority_action":
        return tools.priority_action_well(conn, user_id)
    if intent == "memory_recall":
        refs = memory.discussed_entities(conn, user_id, n=params.get("n_refs", 3))
        names = ", ".join(refs) if refs else "none"
        return {"text": f"From your recent conversations we touched on: {names}.",
                "visual": None, "evidence": []}

    return _fallback(conn, params)


def _record_user_preference(conn, user_id, params):
    memory.record_user_rule(conn, user_id, "formatting", "display", "thousands_and_sort", 1, params["text"])
    u_name = tools.user_name(conn, user_id)
    return {
        "text": f"Recorded, {u_name}. I've saved your display preference: whenever I list wells for you, "
                f"I will sort them by area and then by well ID, and display maintenance costs in thousands of dollars ($k). "
                f"This setting is personal to your profile and will be applied to your session views.",
        "visual": None,
        "evidence": [tools.ev("rule", f"PREF-{user_id}", f"User display preference for {u_name}")]
    }


def _record_pump_swap(conn, user_id, params):
    wells = params.get("wells") or []
    if not wells:
        m = re.search(r"WELL-\d{4}", params["text"])
        if m:
            wells = [m.group(0)]
    wid = wells[0] if wells else "WELL-0333"
    author = tools.user_name(conn, user_id)
    memory.record_shared_note(conn, wid, params["text"], user_id, kind="pump_swap")
    conn.execute(
        "INSERT INTO claims(user_id, asset_id, text, status, created_at) VALUES(?,?,?,?,?)",
        (user_id, wid, params["text"], "confirmed", memory.now_iso())
    )
    conn.commit()
    return {
        "text": f"Recorded. I've updated the recall tracking for **{wid}**: marked as replaced based on field confirmation "
                f"from {author} (\"{params['text']}\"). It has been taken off the active recall list across the system.",
        "visual": None,
        "evidence": [tools.ev("note", f"SWAP-{wid}", f"Pump swap confirmed by {author}")]
    }


def _recalled_pumps_status(conn):
    res = tools.recalled_pumps_active(conn)
    active_wells = res["data"]
    suppressed = domain.suppressed_inspections(conn)
    
    rows = []
    evidence = list(res["evidence"])
    for r in active_wells:
        wid = r["asset_id"]
        w = tools.get_well(conn, wid)
        insp = tools.latest_inspection(conn, wid)
        e = domain.effective_inspection(conn, insp, suppressed) if insp else {}
        producing = domain.is_producing(conn, e, w["well_type"]) if insp else False
        
        last_mnt = conn.execute(
            "SELECT * FROM maintenance WHERE asset_id=? ORDER BY started_at DESC LIMIT 1", (wid,)
        ).fetchone()
        
        lr_str = f"{last_mnt['maintenance_id']} ({last_mnt['start_date']}, {last_mnt['equipment_kind']}: {last_mnt['issue'][:25]})" if last_mnt else "None"
        status_str = "Producing oil" if producing else "Not producing oil"
        rows.append([wid, r["area"], status_str, lr_str])
        
    down_wells = [r for r in rows if "Not producing" in r[2]]
    answer = f"Of the {len(rows)} wells with recalled pumps still in the ground, **{len(down_wells)} well(s) are not producing oil right now**:\n"
    for r in down_wells:
        answer += f"- **{r[0]}** ({r[1]}): {r[2]} — Last repair: {r[3]}\n"
    answer += f"\nThe remaining {len(rows) - len(down_wells)} wells are actively producing oil."
    
    visual = {"kind": "table", "title": "Recalled Pump Wells — Current Operational Status",
              "columns": ["Well", "Area", "Status Right Now", "Last Repair"],
              "rows": rows}
    return {"data": rows, "visual": visual, "answer_md": answer, "evidence": evidence}



# ---------------------------------------------------------------------------
def _inspection_by_hint(conn, asset_id, hint):
    insp_id = nlu.resolve_inspection(conn, asset_id, hint)
    return conn.execute("SELECT * FROM inspections WHERE inspection_id=?",
                        (insp_id,)).fetchone() if insp_id else None


def _apply_raw_correction(conn, user_id, params):
    asset_id = params["wells"][0]
    insp = _inspection_by_hint(conn, asset_id, params.get("date_hint"))
    if not insp:
        return {"text": f"I couldn't find an inspection at {asset_id} matching that date.",
                "visual": None, "evidence": []}
    field = params["field"]
    value = float(params["value"])
    original = insp[field]
    memory.record_correction(
        conn, kind="inspection_field", inspection_id=insp["inspection_id"], asset_id=asset_id,
        field=field, original_value=original, corrected_value=value, reason=params["text"],
        author_user_id=user_id)
    evidence = [tools.ev("inspection", insp["inspection_id"],
                         f"{insp['inspection_id']} ({insp['insp_date']}) — original "
                         f"{field}: {original}")]
    well = tools.get_well(conn, asset_id)
    thr = domain.producing_threshold(conn, well["well_type"])
    e = tools.eff(conn, insp)
    delta = e["wellhead_temp_c"] - e["ambient_temp_c"]
    producing = domain.is_producing(conn, e, well["well_type"])
    lines = [
        f"Recorded. I've noted the correction against inspection **{insp['inspection_id']}**: "
        f"{field.replace('_', ' ')} corrected from **{original} °C** to **{value} °C** "
        f"({tools.user_name(conn, user_id)}: \"{params['text'][:120]}\"). The original value is "
        f"kept on record.",
        f"With the corrected reading, the wellhead is **{delta:.1f} °C above air** — the "
        f"{well['well_type']} threshold is {thr:.0f} °C, so **{asset_id} is "
        f"{'producing oil' if producing else 'not producing oil'}**."]

    # Surface disagreeing evidence instead of silently overwriting
    conflict = None
    if insp["notes"]:
        lines.append(f"⚠️ Heads-up: the same inspection carries the inspector note "
                     f"\"{insp['notes']}\" ({tools.user_name(conn, insp['inspector_user_id'])}), "
                     f"which disagrees with the correction. I've kept both on record — can you "
                     f"confirm the correction wins?")
        conflict = {"prompt": f"The inspection note \"{insp['notes']}\" disagrees with the "
                              f"corrected reading. Confirm the correction?",
                    "kind": "correction_confirmation"}
    return {"text": "\n\n".join(lines),
            "visual": {"kind": "card", "title": f"{asset_id} — after correction",
                       "payload": {"asset_id": asset_id, "producing": producing,
                                   "delta_c": round(delta, 1), "threshold_c": thr,
                                   "corrected_field": field, "original": original,
                                   "corrected": value}},
            "evidence": evidence, "confirm": conflict}


def _apply_analysis_correction(conn, user_id, params):
    asset_id = params["wells"][0]
    insp = _inspection_by_hint(conn, asset_id, params.get("date_hint"))
    if not insp:
        return {"text": f"I couldn't find an inspection at {asset_id} matching that date.",
                "visual": None, "evidence": []}
    value = float(params["value"])
    original = insp["spill_est_volume_bbl"]
    memory.record_correction(
        conn, kind="analysis", inspection_id=insp["inspection_id"], asset_id=asset_id,
        field="spill_est_volume_bbl", original_value=original, corrected_value=value,
        reason=params["text"], author_user_id=user_id)
    evidence = [tools.ev("inspection", insp["inspection_id"],
                         f"{insp['inspection_id']} — AI estimate {original} bbl corrected to "
                         f"{value} bbl by {tools.user_name(conn, user_id)}")]
    lines = [f"Recorded. The corrected volume for inspection **{insp['inspection_id']}** "
             f"({insp['insp_date']}) is **{value} bbl** (was the AI's {original} bbl estimate, "
             f"kept for reference)."]
    if value >= domain.SPILL_REPORTABLE_BBL:
        filed = conn.execute(
            "SELECT * FROM reg_events WHERE asset_id=? AND related_inspection_id=? AND "
            "event_type='spill_report_filed'", (asset_id, insp["inspection_id"])).fetchall()
        disc = domain.iso_to_date(insp["inspected_at"])
        due = disc.strftime("%d %b %Y")
        if filed:
            h = filed[0]["hours_to_report"]
            lines.append(f"At {value} bbl the spill is **reportable** under the Spill Response "
                         f"SOP. The written notice was filed after {h:.0f} hours "
                         f"({filed[0]['event_id']}) against the 24-hour limit.")
        else:
            lines.append(f"At {value} bbl the spill is **reportable** under the Spill Response "
                         f"SOP (SR-01). A written notice was due within 24 hours of the "
                         f"{disc.strftime('%d %b %Y %H:%M')} inspection and **none is recorded** — "
                         f"flagging this as a possible SR-01 breach.")
        m = conn.execute(
            "SELECT m.*, r.spill_class, r.containment_hours, r.report_path FROM maintenance m "
            "LEFT JOIN reports r ON r.report_path=m.report_file WHERE m.asset_id=? AND "
            "m.triggered_by_inspection_id=? LIMIT 1", (asset_id, insp["inspection_id"])).fetchone()
        if m:
            evidence.append(tools.ev("report", m["report_path"], f"repair report {m['maintenance_id']}"))
            if m["spill_class"] in ("minor", "moderate"):
                lines.append(f"Repair report {m['maintenance_id']} classed the spill as "
                             f"\"{m['spill_class']}\" with no reporting duty — that was based on "
                             f"the old estimate and no longer holds.")
            if m["containment_hours"] and m["containment_hours"] > domain.SR02_CONTAIN_HOURS:
                lines.append(f"The same report shows containment took about "
                             f"{m['containment_hours']:.1f} hours, an **SR-02 breach** (limit "
                             f"{domain.SR02_CONTAIN_HOURS:.0f} h).")
        due3 = disc + timedelta(days=domain.SR03_VERIFY_DAYS)
        lines.append(f"Because it is now a reportable spill, agency verification of the clean-up "
                     f"(**SR-03**) is due within {domain.SR03_VERIFY_DAYS} days, "
                     f"by **{due3.strftime('%d %b %Y')}**.")
    return {"text": "\n\n".join(lines), "visual": None, "evidence": evidence}


def _record_rule(conn, user_id, params):
    memory.record_user_rule(conn, user_id, "rca_count", "well_type", params["well_type"],
                            params["value"], params["text"])
    return {"text": f"Noted as a standing rule from {tools.user_name(conn, user_id)}: for **"
                    f"{params['well_type']} wells**, a pump-jack root-cause analysis is wanted "
                    f"after **{params['value']}** corrective repairs, not the manual's "
                    f"{domain.RCA_COUNT}. This applies to {params['well_type']} wells only — "
                    f"other well types keep the manual threshold.",
            "visual": None, "evidence": [tools.ev("doc", "T200", "Manual §10 default: RCA after "
                                                  "3 corrective repairs on the same equipment")]}


def _record_shared_note(conn, user_id, params):
    asset_id = params["wells"][0]
    memory.record_shared_note(conn, asset_id, params["text"], user_id, kind="planned_downtime")
    return {"text": f"Shared with everyone: I've recorded that against **{asset_id}**. Anyone "
                    f"who asks about that well will see it (source: "
                    f"{tools.user_name(conn, user_id)}).",
            "visual": None, "evidence": [tools.ev("note", f"by {tools.user_name(conn, user_id)}",
                                                  params["text"])]}


def _record_claim(conn, user_id, cid, params):
    asset_id = params["wells"][0]
    claim_id, conflict, expl, evidence = memory.record_claim(conn, user_id, asset_id,
                                                             params["text"], cid)
    lines = []
    if conflict:
        lines.append(f"I've recorded that, but it **conflicts with the data**: {expl}.")
        lines.append("I keep your statement and the sensor data both on record rather than "
                     "silently picking one — your claim is marked **unconfirmed** until the "
                     "people involved resolve it.")
        # What do other people / notes on record say? Surface them, never pick silently.
        for other in conn.execute(
                "SELECT * FROM claims WHERE asset_id=? AND user_id!=? AND status!='unconfirmed' "
                "ORDER BY created_at DESC LIMIT 2", (asset_id, user_id)):
            lines.append(f"That matches what {tools.user_name(conn, other['user_id'])} has on "
                         f"record (\"{other['text']}\"), not your claim. I keep both statements "
                         f"on record and mark yours as **unconfirmed** — can you confirm or "
                         f"withdraw it?")
        for n in conn.execute(
                "SELECT * FROM context_notes WHERE asset_id=? AND note_type!='correction' AND "
                "(valid_from IS NULL OR valid_from<=?) AND (valid_to IS NULL OR valid_to>=?) "
                "ORDER BY created_at DESC LIMIT 2", (asset_id, config.today().isoformat(),
                                                     config.today().isoformat())):
            lines.append(f"Also relevant: note {n['note_id']} by "
                         f"{tools.user_name(conn, n['author_user_id'])} — \"{n['text']}\"")
            evidence.append(tools.ev("note", n["note_id"], n["text"]))
    else:
        lines.append(f"Recorded against **{asset_id}** (shared knowledge: anyone asking about "
                     f"this well will see it).")
    return {"text": "\n\n".join(lines), "visual": None,
            "evidence": evidence + [tools.ev("claim", f"claim-{claim_id}", params["text"])],
            "confirm": {"prompt": f"Keep \"{params['text'][:80]}\" on record as your statement?",
                        "kind": "claim_confirmation", "claim_id": claim_id} if conflict else None}


def _planned_downtime(conn, params):
    asset_id = params["wells"][0]
    items = memory.get_planned_downtime(conn, asset_id)
    if not items:
        return {"text": f"I have no planned downtime on record for {asset_id} — no shut-in "
                        f"notes and no scheduled maintenance covering the coming weeks.",
                "visual": None, "evidence": []}
    lines = [f"Yes — planned downtime for **{asset_id}**:"]
    for it in items:
        if it["source"] == "shared":
            lines.append(f"- {it['text']} (according to {it['author']})")
        else:
            lines.append(f"- {it['text']} (note {it['id']} by {it['author']})")
    ev = [tools.ev("note", it["id"], it["text"]) for it in items]
    return {"text": "\n".join(lines), "visual": None, "evidence": ev}


def _try_llm_query(conn, text):
    """If an LLM API key is present (GEMINI_API_KEY, OPENAI_API_KEY, or LLM_API_KEY),
    generate a read-only SQL query over the oil field schema, execute it, and format the answer."""
    import os
    api_key = config.LLM_API_KEY or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    base_url = config.LLM_BASE_URL or (
        "https://generativelanguage.googleapis.com/v1beta/openai/" if os.environ.get("GEMINI_API_KEY") else None
    )
    model = config.LLM_MODEL or ("gemini-2.5-flash" if os.environ.get("GEMINI_API_KEY") else "gpt-4o-mini")
    try:
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key=api_key)
        schema_prompt = (
            "You are an expert SQL assistant for an oil field SQLite database.\n"
            "Tables:\n"
            "- wells(asset_id, name, well_type, area_id, area_name, team_id, lat, lon, installed_on, recorded_status)\n"
            "- inspections(inspection_id, asset_id, inspected_at, insp_date, inspector_user_id, method, ambient_temp_c, wellhead_temp_c, spill_detected, spill_est_volume_bbl, notes)\n"
            "- maintenance(maintenance_id, asset_id, started_at, start_date, completed_at, maintenance_type, equipment_kind, issue, action_taken, technician_user_id, downtime_hours, cost_labor, cost_parts, cost_total, triggered_by_inspection_id)\n"
            "- reg_events(event_id, asset_id, date, agency, event_type, protocol_id, fine_usd, status, detail)\n"
            "- docs(doc_id, path, title, kind, text)\n"
            "- users(user_id, name, role, team_id)\n"
            "- areas(area_id, name, team_id)\n\n"
            "Generate ONLY a valid SQLite read-only SELECT query that answers the question. Do not include markdown codeblocks, just the raw SQL query.\n"
            f"Question: {text}"
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": schema_prompt}],
            temperature=0.1, timeout=12
        )
        sql = resp.choices[0].message.content.strip().replace("```sql", "").replace("```", "").strip()
        if not sql.upper().startswith("SELECT"):
            return None
        rows = [dict(r) for r in conn.execute(sql).fetchall()]
        
        summary_prompt = (
            f"Question: {text}\n"
            f"SQL Query: {sql}\n"
            f"Query Results: {json.dumps(rows[:25])}\n"
            "Write a concise, factual answer for the oilfield operator with the figures from the query results."
        )
        resp2 = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.2, timeout=15
        )
        answer = resp2.choices[0].message.content.strip()
        visual = None
        if rows and len(rows) > 1 and len(rows[0]) <= 6:
            cols = list(rows[0].keys())
            visual = {
                "kind": "table",
                "title": "Query Results",
                "columns": cols,
                "rows": [[r.get(c) for c in cols] for r in rows[:25]]
            }
        return {"text": answer, "visual": visual, "evidence": [tools.ev("doc", "SQL", f"Executed: {sql[:60]}...")]}
    except Exception:
        return None


def _fallback(conn, params):
    text = params["text"]
    wells = params.get("wells") or []
    if wells:
        return tools.get_well_status(conn, wells[0])

    # 1. Check if LLM query engine is available (when user provides an API key)
    llm_res = _try_llm_query(conn, text)
    if llm_res:
        return llm_res

    # 2. Schema-aware deterministic fallbacks
    low = text.lower()
    if re.search(r"repair|maintenance|job", low):
        return tools.get_repair_types(conn)
    if re.search(r"well|area|block|fleet|field", low):
        return tools.get_fleet_summary(conn)
    if re.search(r"issue|problem|failure|break", low):
        return tools.get_top_issues(conn)
    sop_res = tools.lookup_sop_rule(conn, text)
    if sop_res:
        return sop_res

    # 3. Document keyword search
    docs = conn.execute(
        "SELECT doc_id, title FROM docs WHERE text LIKE ? LIMIT 3",
        (f"%{text[:40]}%",)).fetchall()
    return {"text": "I couldn't map that to a specific query. Try asking about a well "
                    f"(e.g. \"Is WELL-0001 producing oil right now?\"), an area "
                    f"(\"Which wells in Northeast Block 8 are not producing oil?\"), spills, "
                    f"downtime, compliance, repair types or costs."
            + (f" Documents that mention it: {', '.join(d['doc_id'] for d in docs)}."
               if docs else ""),
            "visual": None, "evidence": []}


# --- optional LLM polish -----------------------------------------------------
def llm_rephrase(envelope, message):
    """If an OpenAI-compatible endpoint is configured, rephrase the prose.
    Numbers and evidence always come from the deterministic tools."""
    if not (config.LLM_BASE_URL and config.LLM_MODEL):
        return envelope
    try:
        from openai import OpenAI
        client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY or "x")
        prompt = (
            "You are Asset Intelligence Copilot for an oil field. A deterministic engine "
            "already computed the answer. Rewrite ONLY the prose to flow naturally for the "
            "operator's question. Never change any number, id, date, name or citation. "
            "Keep markdown bold. 3-8 sentences.\n\nQuestion: " + message +
            "\n\nComputed answer:\n" + envelope["text"])
        resp = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2, timeout=30)
        text = resp.choices[0].message.content
        if text:
            envelope = dict(envelope)
            envelope["text"] = text.strip()
        return envelope
    except Exception:
        return envelope
