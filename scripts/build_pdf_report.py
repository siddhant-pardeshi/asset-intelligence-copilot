"""
Generate a print-perfect 3-page PDF submission report.
Run: python scripts/build_pdf_report.py
Open the resulting HTML in Chrome, press Ctrl+P, set destination to
'Save as PDF', paper=A4, margins=None, background graphics=ON.
"""
import json, re
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[1]
results = json.loads((ROOT / "backend" / "final_results.json").read_text(encoding="utf-8"))

# ── helpers ────────────────────────────────────────────────────────────────
def md_to_html(txt: str) -> str:
    """Very small Markdown → HTML converter (bold, italic, newlines, lists)."""
    # escape
    txt = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # bold
    txt = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', txt)
    # italic
    txt = re.sub(r'\*(.+?)\*', r'<em>\1</em>', txt)
    # inline code
    txt = re.sub(r'`(.+?)`', r'<code>\1</code>', txt)
    # headings (### / ## / #)
    txt = re.sub(r'^### (.+)$', r'<h4>\1</h4>', txt, flags=re.M)
    txt = re.sub(r'^## (.+)$',  r'<h3>\1</h3>', txt, flags=re.M)
    txt = re.sub(r'^# (.+)$',   r'<h2>\1</h2>', txt, flags=re.M)
    # bullet lists
    lines = txt.split('\n')
    out, in_ul = [], False
    for line in lines:
        if re.match(r'^\s*[-*] ', line):
            if not in_ul:
                out.append('<ul>')
                in_ul = True
            out.append('<li>' + re.sub(r'^\s*[-*] ', '', line) + '</li>')
        else:
            if in_ul:
                out.append('</ul>')
                in_ul = False
            out.append(line)
    if in_ul:
        out.append('</ul>')
    txt = '\n'.join(out)
    # paragraphs (blank lines)
    paragraphs = re.split(r'\n{2,}', txt)
    result = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith('<h') or p.startswith('<ul') or p.startswith('<ol') or p.startswith('<table'):
            result.append(p)
        else:
            result.append('<p>' + p.replace('\n', '<br>') + '</p>')
    return '\n'.join(result)


def build_table(visual: dict) -> str:
    cols = visual.get("cols", visual.get("columns", []))
    rows = visual.get("rows", [])
    if not cols or not rows:
        return ""
    html = ['<div class="vtable"><table>',
            '<thead><tr>' + ''.join(f'<th>{c}</th>' for c in cols) + '</tr></thead>',
            '<tbody>']
    for row in rows[:30]:
        if isinstance(row, dict):
            html.append('<tr>' + ''.join(f'<td>{row.get(c,"")}</td>' for c in cols) + '</tr>')
        elif isinstance(row, list):
            html.append('<tr>' + ''.join(f'<td>{v}</td>' for v in row) + '</tr>')
    if len(rows) > 30:
        html.append(f'<tr><td colspan="{len(cols)}" class="more">…and {len(rows)-30} more rows</td></tr>')
    html.append('</tbody></table></div>')
    return '\n'.join(html)


# ── Page 1 content ──────────────────────────────────────────────────────────
PAGE1 = """
<div class="page page1">
  <div class="page-header">
    <div class="logo">🛢️</div>
    <div>
      <h1>Asset Intelligence Copilot</h1>
      <div class="subtitle">FlytBase Hackathon 2026 &nbsp;·&nbsp; Siddhant Pardeshi
        &nbsp;·&nbsp; <a href="https://github.com/siddhant-pardeshi/asset-intelligence-copilot">github.com/siddhant-pardeshi/asset-intelligence-copilot</a></div>
      <div class="subtitle">Dataset: 600 wells, 7 areas, 6 teams, 204,332 inspections, 28,745 maintenance records
        &nbsp;·&nbsp; Operating date: <strong>15 January 2027</strong></div>
    </div>
  </div>

  <h2>System Design &amp; Architecture</h2>

  <div class="arch-box">
<pre>
┌────────────────────────────────────────────────────────────────────────────────┐
│                     ASSET INTELLIGENCE COPILOT ARCHITECTURE                     │
├────────────────────────────────────────────────────────────────────────────────┤
│  [ Web Dashboard / Chat UI ]  ──  REST /api/chat, /api/memory, /api/conversations
│   • Reactive Zero-Build SPA  • Generative Visuals (Card|Table|Line|Bar|Map|Heatmap)
│   • Persona Selector (Supervisors, HSE, Technicians)  • Evidence Drawer           │
│                                   │                                               │
│                                   ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────────────┐ │
│  │ 1. DETERMINISTIC NLU SEMANTIC INTENT ROUTER                                  │ │
│  │    Regex &amp; Entity Matcher → Wells, Areas, Periods, Dates, Teams, SOPs         │ │
│  │    100% deterministic on regulatory compliance &amp; engineering metrics           │ │
│  ├──────────────────────────────────────────────────────────────────────────────┤ │
│  │ 2. DUAL-SCOPE MEMORY ENGINE                                                   │ │
│  │    Shared Knowledge: operator claims, pump swaps, field notes (all users)     │ │
│  │    Private Memory:   session context, personal display prefs (per user)       │ │
│  ├──────────────────────────────────────────────────────────────────────────────┤ │
│  │ 3. SOP COMPLIANCE AUDITING ENGINE (OPS Rev 2)                                 │ │
│  │    OPS-1 Gas Odor (12h/24h)  OPS-2 MOC Flowline Bypasses                     │ │
│  │    OPS-3 Status Precedence   OPS-4 Root Cause Classification                  │ │
│  │    OPS-5 Freeze Protection   OPS-6 Repeat Failure Tracking                    │ │
│  │    Well thresholds: T100 8°C | T200 12°C | T300 15°C | T500 25°C             │ │
│  └──────────────────────────────────────────────────────────────────────────────┘ │
│                                   │                                               │
│                                   ▼                                               │
│  [ SQLite WAL Knowledge Base ] 600 wells · 204k inspections · 28k maintenance    │
│   wells · inspections · maintenance · reports · context_notes · docs (SOPs/MOC)  │
└────────────────────────────────────────────────────────────────────────────────┘
</pre>
  </div>

  <div class="two-col">
    <div>
      <h3>🔧 Key Engineering Decisions</h3>
      <ul>
        <li><strong>Zero-Hallucination Pipeline:</strong> All safety-critical calculations
          (OPS deadlines, spill volumes, downtime days, cost aggregations) run through
          deterministic SQLite tools — never LLM text generation.</li>
        <li><strong>OPS SOP Rev 2 Native:</strong> OPS-1 switches gas response
          deadlines automatically (24h pre-2027 / 12h post-2027); OPS-2 validates
          every bypass against MOC memo expiry; OPS-5 enforces 7-day heat trace SLAs
          when ambient ≤ −5°C on producing wells.</li>
        <li><strong>Dual-Scope Memory:</strong> Pump swap reports (Nathan on WELL-0333,
          Olivia on WELL-0577) propagate to all users via shared memory; sort/format
          preferences stay private to each operator's session.</li>
        <li><strong>Generative UI Dispatch:</strong> NLU router selects the optimal
          visual type per question domain — status card, table, SVG line chart, bar,
          GIS map, or area×month heatmap.</li>
        <li><strong>Honest Data Gaps:</strong> Q1 (reservoir pressure) correctly reports
          zero pressure telemetry in the dataset rather than fabricating a map.</li>
      </ul>
    </div>
    <div>
      <h3>🗂 Tech Stack</h3>
      <table class="stack-table">
        <tr><th>Layer</th><th>Technology</th></tr>
        <tr><td>Backend API</td><td>Python 3.11 · FastAPI · Uvicorn</td></tr>
        <tr><td>Database</td><td>SQLite WAL · natural-key upsert ingest</td></tr>
        <tr><td>NLU Router</td><td>Deterministic regex + entity matching</td></tr>
        <tr><td>Frontend</td><td>Zero-build SPA · HTML5 · CSS3 · JS</td></tr>
        <tr><td>Charts</td><td>SVG (inline, no library)</td></tr>
        <tr><td>Maps</td><td>Leaflet.js · OpenStreetMap tiles</td></tr>
        <tr><td>Memory</td><td>SQLite-backed dual-scope store</td></tr>
        <tr><td>SOP Engine</td><td>Python rules (domain.py · tools.py)</td></tr>
        <tr><td>LLM (optional)</td><td>OpenAI-compatible via env var</td></tr>
      </table>

      <h3>📊 Dataset Scale</h3>
      <table class="stack-table">
        <tr><th>Entity</th><th>Count</th></tr>
        <tr><td>Wells</td><td>600</td></tr>
        <tr><td>Areas</td><td>7</td></tr>
        <tr><td>Teams</td><td>6</td></tr>
        <tr><td>Inspections</td><td>204,332</td></tr>
        <tr><td>Maintenance records</td><td>28,745</td></tr>
        <tr><td>Operating date</td><td>15 Jan 2027</td></tr>
      </table>
    </div>
  </div>
</div>
"""

# ── Build Pages 2 & 3 from results ─────────────────────────────────────────
q_sections = []

# Concise summaries + tables for each question
SUMMARIES = {
    "Q1": "The dataset does not contain reservoir pressure readings. Inspection records include wellhead and ambient temperatures but <strong>no direct pressure measurements</strong>. A pressure map cannot be produced without downhole gauge data or well test surveys. This was correctly identified — no hallucination.",
    "Q2": "<strong>WELL-0212</strong> had the most productive weeks in 2026: 53 continuous producing weeks with an average wellhead-to-air delta of <strong>36.6 °C</strong> (T500 well, Southeast Block 31). Note: volumetric production data is not in the dataset; uptime/thermal proxy was used.",
    "Q3": "26 operator notes mention gas/odour since 1 Nov 2026. <strong>17 met the OPS-1 deadline</strong>, <strong>9 missed it</strong>. Drone inspections were correctly rejected as field responses per SOP (drone carries thermal cameras, not gas detection equipment).",
    "Q4": "3 active bypasses found. <strong>WELL-0248</strong>: Allowed (MOC-2026-044, valid to 28 Feb 2027). <strong>WELL-0249</strong>: Expired (MOC-2026-036 expired 15 Dec 2026). <strong>WELL-0405</strong>: Not approved — no MOC memo on file. 5 total historical/current violations identified.",
    "Q5": "6 reportable spills (≥ 5 bbl) in NE Blocks 7 & 8 since 1 Jun 2026. <strong>4 non-compliant</strong> (clean-up reports lack required phrase \"Soil samples sent to the lab.\"). <strong>2 compliant</strong>: WELL-0277 and WELL-0119.",
    "Q6": "<strong>6 wells</strong> have conflicting status between latest inspection and operator notes. OPS-3 precedence applied: WELL-0032 & WELL-0033 → Producing oil (unconfirmed); WELL-0044, WELL-0323, WELL-0422, WELL-0481 → Not producing oil (shut in).",
    "Q7": "105 wells have unaddressed warning notes. Top 3 for immediate dispatch: <strong>WELL-0413, WELL-0211, WELL-0175</strong> — all flagged \"tagging bottom on downstroke\" (catastrophic sucker rod parting / pump damage risk).",
    "Q8": "Multi-user, multi-session recall tracking. Nathan reports WELL-0333 swapped → excluded field-wide. Olivia reports WELL-0577 swapped → excluded. Robert Hayes sees 4 active recalled pumps. Nathan Pierce (private pref: sort by area/ID, costs in $k) sees 3 in Northwest Block 12.",
    "Q9": "6-topic single session: (1) 4 recalled pumps in ground; (2) Nathan Pierce leads NW Production, 150 wells; (3) OPS-5 cold weather rule, WELL-0310 missed December check; (4) WELL-0332 gas odor on 3 Dec — no H2S ppm recorded (drone had no gas sensor); (5) WELL-0263 only recalled pump shut in; (6) <strong>WELL-0332 is #1 priority</strong> — active uninvestigated gas hazard.",
    "Q10": "2026 extended shut-ins: <strong>Weather 66.7%</strong> (26 jobs, typical 21 extra days), <strong>Parts 33.3%</strong> (13 jobs, 21–35 extra days). Northwest Block 12 stands out for weather (100% of delays, 24.5 days avg). Southeast Block 32 for parts delays (35 extra days).",
    "Q11": "<strong>Southeast Block 31</strong> consistently runs hottest: 31.4 °C thermal delta (wellhead 52.8 °C vs air 21.5 °C) across 9,433 inspection readings — highest of all 7 areas.",
}

for q in results:
    qid   = q["id"]
    title = q["title"]
    turns = q["turns"]

    turns_html = []
    for i, turn in enumerate(turns, 1):
        user   = turn.get("user", "")
        prompt = turn.get("prompt", "")
        visual = turn.get("visual")
        label  = f"Turn {i} — {user}" if len(turns) > 1 else user

        vhtml = ""
        if visual:
            vtbl = build_table(visual)
            if vtbl:
                vhtml = f'<div class="visual-label">📊 {visual.get("kind","").upper()} — {visual.get("title","")}</div>{vtbl}'

        turns_html.append(f"""
        <div class="turn">
          <div class="turn-header"><span class="turn-label">{label}</span>
            <span class="prompt-text">"{prompt}"</span></div>
          {vhtml}
        </div>""")

    summary_html = f'<div class="summary">{SUMMARIES.get(qid, "")}</div>'
    q_sections.append(f"""
    <div class="q-block">
      <div class="q-title"><span class="qid">{qid}</span> {title}</div>
      {summary_html}
      {''.join(turns_html)}
    </div>""")

PAGES23 = f"""
<div class="page page23">
  <div class="page-header tight">
    <h2>Results — All 11 Final Questions &nbsp;<span class="sub">600 wells · Today: 15 Jan 2027</span></h2>
  </div>
  {''.join(q_sections)}
</div>
"""

# ── Full HTML ───────────────────────────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Asset Intelligence Copilot — Submission Report</title>
<style>
  /* ── Reset & base ── */
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 9pt;
         color: #1a1a2e; background: #fff; }}
  a {{ color: #1565c0; text-decoration: none; }}

  /* ── Page breaks ── */
  .page {{ width: 100%; padding: 14mm 16mm; }}
  .page1 {{ page-break-after: always; }}
  .page23 {{ page-break-before: always; }}

  /* ── Headers ── */
  .page-header {{ display:flex; align-items:center; gap:12px;
                  border-bottom: 2.5px solid #1565c0; padding-bottom: 8px; margin-bottom: 12px; }}
  .page-header .logo {{ font-size: 28pt; }}
  h1 {{ font-size: 16pt; color: #1565c0; margin-bottom: 2px; }}
  h2 {{ font-size: 12pt; color: #1565c0; margin: 10px 0 5px; }}
  h3 {{ font-size: 10pt; color: #0d47a1; margin: 8px 0 4px; }}
  h4 {{ font-size: 9pt; color: #333; margin: 6px 0 3px; }}
  .subtitle {{ font-size: 8pt; color: #555; margin-top: 2px; }}
  .page-header.tight {{ padding-bottom: 4px; margin-bottom: 6px; }}
  .page-header.tight h2 {{ margin: 0; font-size: 11pt; }}
  .page-header.tight .sub {{ font-size: 8pt; font-weight: normal; color: #666; }}

  /* ── Architecture box ── */
  .arch-box {{ background: #0d1117; color: #c9d1d9; border-radius: 6px;
               padding: 8px 10px; margin: 8px 0; }}
  .arch-box pre {{ font-family: 'Consolas','Courier New',monospace;
                   font-size: 6.8pt; line-height: 1.35; white-space: pre-wrap; }}

  /* ── Two column ── */
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 8px; }}
  ul {{ padding-left: 14px; }}
  li {{ margin-bottom: 4px; line-height: 1.35; }}
  p {{ margin: 4px 0; line-height: 1.4; }}

  /* ── Stack table ── */
  .stack-table {{ width: 100%; border-collapse: collapse; font-size: 8pt; margin: 4px 0 8px; }}
  .stack-table th {{ background: #1565c0; color: #fff; padding: 3px 6px; text-align: left; }}
  .stack-table td {{ padding: 2px 6px; border-bottom: 1px solid #e0e0e0; }}
  .stack-table tr:nth-child(even) td {{ background: #f5f8ff; }}

  /* ── Q blocks ── */
  .q-block {{ margin-bottom: 10px; border-left: 3px solid #1565c0;
              padding-left: 8px; page-break-inside: avoid; }}
  .q-title {{ font-size: 10pt; font-weight: 700; color: #1565c0; margin-bottom: 3px; }}
  .qid {{ background: #1565c0; color: #fff; border-radius: 3px;
          padding: 1px 5px; font-size: 8.5pt; margin-right: 4px; }}
  .summary {{ font-size: 8.5pt; line-height: 1.4; margin-bottom: 4px;
              background: #f0f4ff; border-radius: 4px; padding: 5px 8px; }}
  .summary strong {{ color: #1565c0; }}

  /* ── Turns ── */
  .turn {{ margin-top: 4px; }}
  .turn-header {{ display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }}
  .turn-label {{ font-weight: 600; color: #333; font-size: 8pt; white-space: nowrap; }}
  .prompt-text {{ font-style: italic; color: #555; font-size: 8pt; line-height: 1.3; }}

  /* ── Visual tables ── */
  .visual-label {{ font-size: 7.5pt; font-weight: 600; color: #0d47a1;
                   margin: 4px 0 2px; }}
  .vtable {{ overflow-x: auto; margin: 2px 0 6px; }}
  .vtable table {{ width: 100%; border-collapse: collapse; font-size: 7.5pt; }}
  .vtable th {{ background: #1565c0; color: #fff; padding: 3px 5px;
                text-align: left; font-weight: 600; white-space: nowrap; }}
  .vtable td {{ padding: 2px 5px; border-bottom: 1px solid #e8eaf0;
                line-height: 1.25; }}
  .vtable tr:nth-child(even) td {{ background: #f5f8ff; }}
  .vtable .more {{ text-align: center; color: #888; font-style: italic; }}

  code {{ background: #f0f0f0; border-radius: 2px; padding: 0 3px; font-size: 8pt; }}

  /* ── Print ── */
  @media print {{
    body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .page {{ padding: 10mm 12mm; }}
    .arch-box {{ background: #0d1117 !important; color: #c9d1d9 !important; }}
    .vtable th {{ background: #1565c0 !important; color: #fff !important; }}
    .qid {{ background: #1565c0 !important; color: #fff !important; }}
    .stack-table th {{ background: #1565c0 !important; color: #fff !important; }}
  }}
</style>
</head>
<body>
{PAGE1}
{PAGES23}
</body>
</html>"""

out = ROOT / "SUBMISSION_REPORT_PRINT.html"
out.write_text(HTML, encoding="utf-8")
print(f"Written: {out}  ({out.stat().st_size:,} bytes)")
print("Open in Chrome → Ctrl+P → Save as PDF  (A4, No margins, Background graphics ON)")
