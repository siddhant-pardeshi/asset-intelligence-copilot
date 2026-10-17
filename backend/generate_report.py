"""Generate a comprehensive 3-page Submission Report in Markdown
with Page 1: System Design & Architecture, and Pages 2 & 3: Final 11 Questions Results.
"""
import json
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
results_file = backend_dir / "final_results.json"
results = json.loads(results_file.read_text(encoding="utf-8"))

report = []

report.append("""# Asset Intelligence Copilot — Final Submission Report
**FlytBase Hackathon 2026** · **Author:** Siddhant Pardeshi · **Repository:** [github.com/siddhant-pardeshi/asset-intelligence-copilot](https://github.com/siddhant-pardeshi/asset-intelligence-copilot)  
**Dataset Evaluation:** 600 wells, 7 areas, 6 teams, 204,332 inspections, 28,745 maintenance records · **Target Date (Today):** 15 January 2027  
**Live UI:** `http://127.0.0.1:8000` (FastAPI + Zero-build Reactive Dashboard)

---

## PAGE 1: System Design, Architecture & Methodology

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        ASSET INTELLIGENCE COPILOT ARCHITECTURE                         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  [ Web Dashboard / Chat UI ] ──(REST /api/chat, /api/memory, /api/conversations)──────┐│
│   • Reactive Zero-Build SPA  • Dynamic Generative Visuals (Tables, Cards, Maps, Bars)  ││
│   • Persona Selector (Supervisors, HSE, Technicians) • Interactive Evidence Drawer     ││
│                                                                                        │
│                                         │                                              │
│                                         ▼                                              │
│  [ Hybrid Agentic Reasoning Engine (FastAPI Backend) ]                                 │
│   ┌──────────────────────────────────────────────────────────────────────────────────┐ │
│   │ 1. Deterministic NLU Semantic Intent Router                                      │ │
│   │    - Exact Regex & Entity Matcher (Wells, Areas, Periods, Dates, Teams, SOPs)   │ │
│   │    - 100% Deterministic execution on domain rules (OPS-1 to OPS-6, SR, RC, WS)   │ │
│   │    - Zero hallucination guarantee on regulatory compliance & engineering metrics │ │
│   ├──────────────────────────────────────────────────────────────────────────────────┤ │
│   │ 2. Dual-Scope Memory & Knowledge State Engine                                    │ │
│   │    - Shared Knowledge: Operator claims, field swaps, shared notes across teams   │ │
│   │    - Private User Memory: Session entity tracking, personal formatting prefs     │ │
│   │    - Feedback & Corrections Store: Preserves raw records while updating view     │ │
│   ├──────────────────────────────────────────────────────────────────────────────────┤ │
│   │ 3. Domain Logic & SOP Compliance Auditing System                                 │ │
│   │    - OPS-1 Gas Odor Response (12h/24h)  - OPS-2 Temporary MOC Flowline Bypasses  │ │
│   │    - OPS-3 Status Evidence Precedence   - OPS-4 Root Cause Failure Classification │ │
│   │    - OPS-5 Winter Freeze Protection     - OPS-6 Repeat Failure Tracking          │ │
│   │    - Well Type Telemetry Thresholds: T100 (8°C), T200 (12°C), T300 (15°C), T500 (25°C)│
│   └──────────────────────────────────────────────────────────────────────────────────┘ │
│                                         │                                              │
│                                         ▼                                              │
│  [ Relational SQLite Knowledge Base (WAL Mode, Natural Key Upsert Ingest) ]            │
│   • wells (600 assets, coordinates, equipment, type history, decommission status)      │
│   • inspections (204k records, thermal telemetry, spill area %, volume bbl)           │
│   • maintenance (28k records, work orders, downtime hours, component costs)           │
│   • reports (unstructured maintenance reports, parts installed, root causes)          │
│   • context_notes (operator round logs, data corrections, planned work windows)       │
│   • docs (Markdown SOP manuals, MOC approval memos, supplier recall notices)          │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1. Architectural Highlights & Key Engineering Decisions
- **Zero-Hallucination Deterministic Grounding:** Routine operations and safety compliance demand mathematical correctness. While LLMs excel at language synthesis, mission-critical asset decisions (regulatory fines, gas leak deadlines, spill containment) require strict deterministic calculation. The Copilot uses a deterministic query pipeline with optional LLM reasoning fallback.
- **OPS SOP Revision 2 Implementation:** Full native support for the new test dataset operating procedures:
  - **OPS-1 (Gas Odor Response):** Automatic deadline switching (24 hours prior to 1 Jan 2027; 12 hours from 1 Jan 2027). Drone inspections are rejected as field responses per SOP.
  - **OPS-2 (Flowline Bypasses):** Cross-references active and past bypasses against Management of Change memos (`MOC-2026-031`, `MOC-2026-036`, and extension `MOC-2026-044`).
  - **OPS-3 (Status Evidence Precedence):** Resolves status conflicts between thermal inspection readings and operator round notes, correctly applying "Not producing (shut in)" or "Producing (unconfirmed)".
  - **OPS-5 (Winter Freeze Protection):** Enforces 7-day heat trace check SLAs on all producing wells with ambient telemetry $\le -5^\circ\text{C}$ between 1 Dec and 28 Feb.
- **Two-Level Memory Architecture:**
  - *Shared Memory:* User-reported field interventions (such as Nathan Pierce reporting the swap of recalled downhole pump on WELL-0333, or Olivia Grant confirming WELL-0577) persist in the database, updating recall tracking and asset status field-wide for all users.
  - *Private Per-User Memory:* Individual display rules (e.g., Nathan's preference for sorting wells by area/ID and rendering maintenance costs in thousands of dollars) apply exclusively to the user's active session without altering shared fleet state.
- **Audit Trails & Full Provenance:** Every response generates structured visual artifacts and an **Interactive Evidence Drawer** citing exact document IDs, inspection logs, and operator notes.

---

## PAGES 2 & 3: Comprehensive Final Questions Evaluation & Results

All 11 questions were executed sequentially against the 600-well test dataset (`test-data/dataset`, evaluated at current operating date **15 January 2027**). Below are the full recorded outputs, structured data tables, and reasoning:
""")

for q in results:
    qid = q["id"]
    qtitle = q["title"]
    report.append(f"\n### {qid}. {qtitle}\n")
    
    for turn_idx, t in enumerate(q["turns"], 1):
        u = t.get("user")
        prompt = t.get("prompt")
        ans = t.get("answer") or ""
        vis = t.get("visual")
        ev_list = t.get("evidence", [])
        
        if len(q["turns"]) > 1:
            report.append(f"**Turn {turn_idx} ({u}):** *\"{prompt}\"*  \n")
        else:
            report.append(f"**Asked by:** {u}  \n**Prompt:** *\"{prompt}\"*  \n")
            
        report.append(f"{ans}\n")
        
        if vis and vis.get("rows"):
            cols = vis.get("columns", [])
            header = "| " + " | ".join(cols) + " |"
            sep = "| " + " | ".join(["---"] * len(cols)) + " |"
            table_lines = [header, sep]
            for r in vis.get("rows", [])[:15]:  # show up to 15 rows cleanly
                row_str = "| " + " | ".join(str(cell).replace("\n", " ") for cell in r) + " |"
                table_lines.append(row_str)
            if len(vis.get("rows", [])) > 15:
                table_lines.append(f"| ... | *({len(vis['rows'])-15} additional rows in UI table)* | | | | | |"[:len(header)])
            report.append("\n" + "\n".join(table_lines) + "\n")
            
        if ev_list:
            cites = [f"`[{e.get('type')}] {e.get('id')}` ({e.get('label')})" for e in ev_list[:4]]
            report.append(f"*Evidence Cites:* {'; '.join(cites)}  \n")
            
        report.append("\n---\n")

report_text = "\n".join(report)
out_file = backend_dir.parent / "SUBMISSION_REPORT.md"
out_file.write_text(report_text, encoding="utf-8")
print(f"Generated complete submission report at: {out_file} ({len(report_text):,} bytes)")
