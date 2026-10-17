"""Build FINAL_RESULTS.md from final_results.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
results = json.loads((ROOT / "backend" / "final_results.json").read_text(encoding="utf-8"))

lines = []
lines.append("# Final Questions — Complete Results")
lines.append("**Dataset:** 600 wells, 7 areas, 6 teams | **Today:** 15 January 2027 | **System:** Asset Intelligence Copilot")
lines.append("")
lines.append("---")
lines.append("")

for q in results:
    qid = q["id"]
    qtitle = q["title"]
    lines.append(f"## {qid}. {qtitle}")
    lines.append("")

    for i, turn in enumerate(q["turns"], 1):
        user = turn.get("user", "")
        prompt = turn.get("prompt", "")
        answer = turn.get("answer", "")
        visual = turn.get("visual")
        evidence = turn.get("evidence", [])

        if len(q["turns"]) > 1:
            lines.append(f"### Turn {i} — {user}")
        else:
            lines.append(f"**Asked by:** {user}")
        lines.append("")
        lines.append(f"> {prompt}")
        lines.append("")
        lines.append(answer)
        lines.append("")

        if visual:
            kind = visual.get("kind", "")
            title = visual.get("title", "")
            lines.append(f"*Visual: {kind.upper()} — {title}*")
            rows = visual.get("rows", [])
            cols = visual.get("cols", visual.get("columns", []))
            if cols and rows:
                lines.append("")
                lines.append("| " + " | ".join(str(c) for c in cols) + " |")
                lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
                for row in rows[:25]:
                    if isinstance(row, dict):
                        lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
                    elif isinstance(row, list):
                        lines.append("| " + " | ".join(str(v) for v in row) + " |")
                if len(rows) > 25:
                    lines.append(f"| *...and {len(rows)-25} more rows* | |")
            lines.append("")

        if evidence:
            lines.append("<details><summary>Evidence Sources</summary>")
            lines.append("")
            for ev in evidence[:5]:
                src = ev if isinstance(ev, str) else str(ev)
                lines.append(f"- {src}")
            lines.append("")
            lines.append("</details>")
            lines.append("")

        lines.append("---")
        lines.append("")

out = ROOT / "FINAL_RESULTS.md"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Written {out} ({out.stat().st_size:,} bytes)")
