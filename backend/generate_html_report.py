import re
from pathlib import Path

md_path = Path(__file__).resolve().parent.parent / "SUBMISSION_REPORT.md"
html_path = Path(__file__).resolve().parent.parent / "SUBMISSION_REPORT.html"

md_text = md_path.read_text(encoding="utf-8")

lines = []
in_table = False
in_code = False

for line in md_text.splitlines():
    if line.startswith("```"):
        if not in_code:
            lines.append("<pre style=\"background:#0f172a;color:#f8fafc;padding:12px;border-radius:6px;overflow-x:auto;font-size:12px;font-family:monospace;\">")
            in_code = True
        else:
            lines.append("</pre>")
            in_code = False
        continue
    if in_code:
        lines.append(line)
        continue

    if line.startswith("|"):
        if not in_table:
            lines.append("<table border=\"1\" cellpadding=\"6\" cellspacing=\"0\" style=\"border-collapse:collapse;width:100%;margin:12px 0;font-size:13px;\">")
            in_table = True
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if all(set(c) <= {"-", ":", " "} for c in cells):
            continue
        row_html = "".join(f"<td style=\"padding:6px 8px;border:1px solid #cbd5e1;\">{c}</td>" for c in cells)
        lines.append(f"<tr>{row_html}</tr>")
    else:
        if in_table:
            lines.append("</table>")
            in_table = False
        if line.startswith("# "):
            lines.append(f"<h1 style=\"color:#0f172a;margin-bottom:4px;\">{line[2:]}</h1>")
        elif line.startswith("## "):
            lines.append(f"<h2 style=\"border-bottom:2px solid #2563eb;padding-bottom:4px;margin-top:28px;color:#1e3a8a;\">{line[3:]}</h2>")
        elif line.startswith("### "):
            lines.append(f"<h3 style=\"color:#1e40af;margin-top:20px;\">{line[4:]}</h3>")
        elif line.startswith("---"):
            lines.append("<hr style=\"border:0;border-top:1px solid #cbd5e1;margin:24px 0;\">")
        elif line.strip():
            l = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            l = re.sub(r"\*(.+?)\*", r"<em>\1</em>", l)
            lines.append(f"<p style=\"line-height:1.6;margin:6px 0;\">{l}</p>")

if in_table:
    lines.append("</table>")

body = "\n".join(lines)
html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Asset Intelligence Copilot — Final Submission Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; max-width: 980px; margin: 40px auto; padding: 0 24px; color: #1e293b; background: #ffffff; }}
h1 {{ color: #0f172a; }}
table {{ border: 1px solid #cbd5e1; border-collapse: collapse; margin: 12px 0; }}
th, td {{ border: 1px solid #cbd5e1; padding: 6px 10px; text-align: left; }}
tr:nth-child(even) {{ background: #f8fafc; }}
strong {{ color: #0f172a; }}
@media print {{
  body {{ margin: 12mm; max-width: 100%; }}
  h2 {{ page-break-before: always; }}
}}
</style>
</head>
<body>
{body}
</body>
</html>"""

html_path.write_text(html_content, encoding="utf-8")
print("HTML report successfully generated at:", html_path)
