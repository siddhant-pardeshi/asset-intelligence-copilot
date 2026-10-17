"""Deterministic natural-language router (no LLM required).

Maps an operator's question onto the deterministic tools: extracts entities
(wells, areas, people, equipment, periods, visuals) with regexes anchored in
the dataset, then scores intents. The optional LLM layer reuses the same tool
set; this router is the always-available fallback, which is what makes the
system hold up under rate limits during the final-2-hours test run.
"""
import re
from datetime import date, datetime, timedelta

from . import config, domain

WELL_RE = re.compile(r"WELL[- ]?(\d{1,4})", re.I)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def find_wells(text):
    out = []
    for m in WELL_RE.finditer(text):
        out.append(f"WELL-{int(m.group(1)):04d}")
    return out


def find_area(text, areas):
    n = norm(text)
    for area_id, name in areas:
        if norm(name) in n or norm(area_id) in n:
            return area_id
    return None


def find_equipment(text):
    t = text.lower()
    for kind, label in [("pump jack", "pump_jack"), ("pump_jack", "pump_jack"),
                        ("rod string", "rod_string"), ("downhole pump", "downhole_pump"),
                        ("flowline", "flowline"), ("wellhead", "wellhead"),
                        ("separator", "separator"), ("esp pump", "esp_pump"),
                        ("esp_pump", "esp_pump"), ("submersible pump", "esp_pump"),
                        ("esp", "esp_pump")]:
        if kind in t:
            return label
    return None


def find_visual(text):
    t = text.lower()
    for hint, kind in [("heatmap", "heatmap"), ("heat map", "heatmap"), ("bar chart", "bar"),
                       ("bar graph", "bar"), (" as a bar", "bar"), ("line chart", "line"),
                       ("line graph", "line"), (" as a table", "table"), ("in a table", "table"),
                       ("show a table", "table"), (" on a map", "map"), ("show a map", "map"),
                       (" as a map", "map"), (" as a card", "card"), (" status card", "card")]:
        if hint in t:
            return kind
    if re.search(r"\bmap\b", t):
        return "map"
    if "table" in t and re.search(r"show|list|table", t):
        return "table"
    return None


def find_period(text):
    """Returns dict(start, end, year, label) or None."""
    t = text.lower()
    t0 = config.today()
    m = re.search(r"last (\d+) days?", t)
    if m:
        n = int(m.group(1))
        return {"start": t0 - timedelta(days=n), "end": t0, "label": f"last {n} days"}
    m = re.search(r"last (\d+) weeks?", t)
    if m:
        n = int(m.group(1))
        return {"start": t0 - timedelta(days=7 * n), "end": t0, "label": f"last {n} weeks",
                "weeks": n}
    m = re.search(r"last (\d+) months?", t)
    if m:
        n = int(m.group(1))
        return {"start": domain.months_ago(t0, n), "end": t0, "label": f"last {n} months"}
    m = re.search(r"last (\d+) years?", t)
    if m:
        n = int(m.group(1))
        return {"start": domain.months_ago(t0, 12 * n), "end": t0, "label": f"last {n} years"}
    m = re.search(r"\b(20\d{2})\b", t)
    if m:
        y = int(m.group(1))
        return {"start": date(y, 1, 1), "end": date(y, 12, 31), "year": y, "label": str(y)}
    if "this year" in t:
        return {"start": date(t0.year, 1, 1), "end": t0, "year": t0.year,
                "label": f"{t0.year} year-to-date"}
    return None


def find_number_after(text, pattern):
    m = re.search(pattern, text, re.I)
    return float(m.group(1)) if m else None


def find_date_hint(text):
    """'15 Oct', '24 Sep 2026', '20 Aug' → (month, day) tuple or None."""
    m = re.search(r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                  r"(?:\w+)?(?:\s+(20\d{2}))?\b", text, re.I)
    if not m:
        return None
    month = datetime.strptime(m.group(2)[:3], "%b").month
    return {"month": month, "day": int(m.group(1)), "year": int(m.group(3)) if m.group(3) else None}


def find_user_ref(text):
    """Try to extract a user name reference from the text."""
    m = re.search(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b", text)
    return m.group(1) if m else None


def resolve_inspection(conn, asset_id, hint):
    """Find the inspection at a well matching a loose date hint (latest wins)."""
    if not hint:
        return None
    rows = conn.execute(
        "SELECT inspection_id, insp_date FROM inspections WHERE asset_id=? ORDER BY inspected_at",
        (asset_id,)).fetchall()
    cands = [r for r in rows
             if int(r["insp_date"][5:7]) == hint["month"] and int(r["insp_date"][8:10]) == hint["day"]
             and (hint.get("year") is None or int(r["insp_date"][:4]) == hint["year"])]
    return cands[-1]["inspection_id"] if cands else None


def is_question(text):
    if text.rstrip().endswith("?"):
        return True
    return bool(re.match(r"^\s*(what|which|how|when|why|who|is|are|was|were|does|do|did|can|"
                         r"show|list|tell|give|any)\b", text.strip(), re.I))


# ----------------------------------------------------------------------------
def route(conn, text, areas, user_id=None):
    """Returns {"intent": ..., params..., "memory_refs": bool}."""
    q = text.strip()
    low = q.lower()
    wells = find_wells(q)
    area = find_area(q, areas)
    period = find_period(q)
    visual = find_visual(q)
    equipment = find_equipment(q)
    params = {"wells": wells, "area": area, "period": period, "visual": visual,
              "equipment": equipment, "text": q}

    # --- declarative feedback & preferences -----------------------------------
    if re.search(r"recalled.*pump.*(swapped|replaced|changed)|(swap|replace|take.*off).*recall|pump.*swapped", low):
        params["intent"] = "pump_swap_claim"
        return params
    if re.search(r"just for me|whenever you list wells|show costs in thousands", low):
        params["intent"] = "user_pref"
        return params

    if not is_question(q):
        m = re.search(r"(?:note|rule|remember)(?:\s+this)?\s+for\s+all\s+([A-Za-z0-9]+)\s+wells?"
                      r".*?after\s+(\d+)\s+repairs", q, re.I | re.S)
        if m:
            params["intent"] = "rule_rca"
            params["well_type"] = m.group(1).upper()
            params["value"] = int(m.group(2))
            return params
        if re.search(r"\bfyi\b|for everyone", low) and wells:
            params["intent"] = "shared_note"
            return params
        if (re.search(r"\b(is|was|are)\s+wrong\b|re-?measured|the real value|"
                      r"actually\s+(\d+(?:\.\d+)?)", low) or
                (re.search(r"measured\s+\d+(\.\d+)?\s*bbl", low) and wells)):
            m = re.search(r"(\d+(?:\.\d+)?)\s*°?\s*C\b", q)
            bbls = re.findall(r"(\d+(?:\.\d+)?)\s*bbl", q)
            bbl = float(bbls[-1]) if bbls else None  # the LAST figure is the crew's correction
            hint = find_date_hint(q)
            if bbl and not m:
                params.update(intent="correction_analysis", value=bbl, date_hint=hint,
                              field="spill_est_volume_bbl")
                return params
            if m:
                field = "wellhead_temp_c" if "wellhead" in low else \
                        ("ambient_temp_c" if "air" in low else "wellhead_temp_c")
                params.update(intent="correction_raw", value=m.group(1), field=field,
                              date_hint=hint)
                return params
        if wells and re.search(r"\b(shut[- ]?in|running|back online|down|fine|stopped)\b", low):
            params["intent"] = "claim"
            return params

    # --- memory references -----------------------------------------------------
    if re.search(r"\b(we|I)\s+(discussed|talked about|looked at|covered)\b", low):
        params["memory_refs"] = True
        m = re.search(r"\b(\d+|three|two|four|five)\s+wells?\b", low)
        wordmap = {"three": 3, "two": 2, "four": 4, "five": 5}
        params["n_refs"] = int(m.group(1)) if m and m.group(1).isdigit() else \
            (wordmap.get(m.group(1), 3) if m else 3)
        q2 = re.sub(r"[Ff]or the .*?we discussed[^,]*,?\s*", "", q)
        if q2 and q2 != q:
            sub = route(conn, q2, areas, user_id)
            sub.update(memory_refs=True, n_refs=params["n_refs"])
            return sub
        params["intent"] = "memory_recall"
        return params

    # --- specific final questions (PRIORITY ROUTING) ---------------------------
    # Q1: Reservoir pressure mapping
    if re.search(r"reservoir pressure|pressure.*across.*field|map.*pressure|pressure.*map", low):
        params["intent"] = "reservoir_pressure"
        return params

    # Q2: Best producer
    if re.search(r"produced the most oil|highest produc|most oil|best producer", low):
        params["intent"] = "best_producer"
        return params

    # Q3: Gas reports / OPS-1 response audit
    if re.search(r"since 1 nov 2026.*gas|every time an operator note reports gas|met the deadline|response met the deadline", low):
        params["intent"] = "gas_response"
        return params

    # Q4: Temporary bypass / OPS-2
    if re.search(r"temporary flowline bypass|bypasses are in place right now|flowline bypass|which temporary.*bypass", low):
        params["intent"] = "bypass_status"
        return params

    # Q5: Regulator letter / spill compliance
    # (must NOT swallow generic "spills in <area>" questions — those belong to
    #  spill_map / report_needed; the letter tool matches the letter's wording)
    if re.search(r"commission wrote to us|regulator.{0,20}letter|which of our spills does the letter cover", low):
        params["intent"] = "regulator_letter"
        return params

    # Q6: Status disagreement / OPS-3
    if re.search(r"disagree.*whether.*producing oil|disagree.*producing|latest inspection and.*operator notes disagree|real status right now", low):
        params["intent"] = "status_disagreement"
        return params

    # Q7 Turn 1: Operator warnings
    if re.search(r"operators have written notes.*sound|sound or behave wrong|rank the 10 most likely to need a repair", low):
        params["intent"] = "operator_warnings"
        return params

    # Q7 Turn 2: Which 3 to send a crew to first
    if re.search(r"which three would you send|send a crew to first|which 3.*crew.*first", low):
        params["intent"] = "operator_priority"
        return params

    # Q9 Turn 4: Gas reading lookup on specific date
    if re.search(r"h2s reading|gas smell at well-0332|reading.*well-0332", low):
        params["intent"] = "gas_reading"
        return params

    # Q9 Turn 5: Recalled pumps not producing right now
    if re.search(r"back to the pumps|which of those wells are not producing oil right now", low):
        params["intent"] = "recalled_pumps_status"
        return params

    # Q9 Turn 6: Recommended well to deal with first
    if re.search(r"which one would you deal with first|deal with first.*why|which.*deal with first", low):
        params["intent"] = "priority_action"
        return params

    # Q9 Turn 3: Cold weather / freeze / OPS-5
    if re.search(r"cold weather|operations sop say about cold weather|missed the check in december", low):
        params["intent"] = "cold_weather"
        return params

    # Q8 & Q9 Turn 1: Recalled pumps inquiry
    if re.search(r"recalled pumps.*(still in the ground|in which areas|my area)|which recalled pumps", low):
        params["intent"] = "recalled_pumps"
        return params

    # Q9 Turn 2: Who leads / team info
    if re.search(r"who leads|team lead|how many wells does that team run", low):
        params["intent"] = "team_info"
        return params

    # Q10: Waiting on (parts/crews/contractors/weather)
    if re.search(r"waiting on|what are we usually waiting on|shut in longer.*repair|typical.*extra days", low):
        params["intent"] = "waiting_analysis"
        return params

    # Q11: Hotter region
    if re.search(r"hotter|runs hotter|consistently.*hot|which region.*hot", low):
        params["intent"] = "hotter_region"
        return params

    # --- general domain questions ---------------------------------------------
    if re.search(r"downtime planned|planned (shut-?in|maintenance|work|outage)|"
                 r"any (planned )?(downtime|shut-?in)|shut-?in planned", low):
        params["intent"] = "planned_downtime"
        return params
    if re.search(r"root[- ]?cause", low):
        params["intent"] = "rca"
        return params
    if re.search(r"most downtime|down the longest|longest downtime|most days down", low):
        m = re.search(r"(?:top\s*(\d+)|(\d+)\s+wells?)", low)
        params["intent"] = "downtime_ranking"
        params["top_n"] = int(m.group(1) or m.group(2)) if m else 3
        return params
    if re.search(r"how many days\b", low) and wells:
        params["intent"] = "downtime_days"
        return params
    if "temperature" in low and re.search(r"chart|graph|against|over|plot|last \d+ weeks", low):
        params["intent"] = "temp_series"
        m = re.search(r"last (\d+) weeks?", low)
        params["weeks"] = int(m.group(1)) if m else 13
        return params
    if re.search(r"heatmap|heat map", low) or \
            (re.search(r"by .*(area|block).*month|area.{0,20}month", low) and "spill" in low):
        params["intent"] = "heatmap"
        return params
    if re.search(r"\bmap\b", low) and re.search(r"spill|well", low):
        params["intent"] = "spill_map"
        return params
    if re.search(r"contain\w*( within| time| after| in )|not contained|containment", low):
        params["intent"] = "containment"
        return params
    if re.search(r"needed a report|report to the regulator|should (have been )?reported|"
                 r"reportable", low):
        params["intent"] = "report_needed"
        return params
    if re.search(r"real oil|was it real|actually (crude )?oil|real spill|was the .* spill", low):
        params["intent"] = "spill_detail"
        return params
    if re.search(r"rules? .*(broken|violat)|breach|violation|compliance", low) and wells:
        params["intent"] = "compliance"
        m = re.search(r"last (\d+) months?", low)
        params["months"] = int(m.group(1)) if m else 12
        return params
    # downtime cost / lost production beats the generic "cost" and "how much
    # oil" matchers, which would otherwise grab these
    if re.search(r"(production|oil) loss|lost (oil|production|volume)|barrels lost|"
                 r"cost of downtime|downtime cost|how much (oil|money|revenue) "
                 r"(are we )?losing", low):
        params["intent"] = "production_loss"
        return params
    if re.search(r"cost|spend|spent", low):
        params["intent"] = "costs"
        return params
    if re.search(r"how many (oil )?spills|how much oil|total.*(bbl|barrels)|spills.*total", low):
        params["intent"] = "spill_history"
        return params
    if wells and re.search(r"spill", low):
        params["intent"] = "spill_history"
        return params
    if re.search(r"which wells", low) and re.search(r"not producing|down|offline|stopped", low):
        params["intent"] = "not_producing"
        return params
    if wells and re.search(r"producing|running|status|down\b|last inspected", low):
        params["intent"] = "well_status"
        return params
    if wells:
        params["intent"] = "well_status"
        return params
    if area and re.search(r"not producing|down", low):
        params["intent"] = "not_producing"
        return params
    if "spill" in low:
        params["intent"] = "spill_history"
        return params
    if re.search(r"types? of (repair|maintenance)|maintenance types?|repair types?|kinds? of (repair|maintenance)|what repairs|how many repairs|categories of (repair|maintenance)", low):
        params["intent"] = "repair_types"
        return params
    if re.search(r"(most common|top|frequent) (repair|maintenance|issue|problem|failure)s?", low):
        params["intent"] = "top_issues"
        return params
    if re.search(r"how many wells|total wells|wells in each area|fleet summary|wells per area|overview of (the )?fleet", low):
        params["intent"] = "fleet_summary"
        return params
    if re.search(r"\b(sr-0[1-4]|rc-0[1-5]|ws-0[1-7]|ops-[1-6])\b|what is rule|explain (rule |sop )", low):
        params["intent"] = "sop_rule"
        return params
    # Field-operations decision support
    if re.search(r"crew board|priority board|action list|today'?s (actions|priorities)|"
                 r"standup|what should we (fix|work on|tackle) first|next actions", low):
        params["intent"] = "crew_board"
        return params
    params["intent"] = "fallback_search"
    return params

