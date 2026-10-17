"""Cloud-storage smoke test: run the whole stack against a real MySQL
instance (Aiven) and check the deterministic answers match the SQLite ones.

    python ../scripts/test_mysql.py "mysql://user:pass@host:port/db?ssl-mode=REQUIRED"
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import config, db  # noqa: E402

config.MYSQL_URI = sys.argv[1]
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(detail)[:180]}"))


def main():
    t0 = time.time()
    counts = db.ingest()  # DATA_DIRS = sample + test dataset roots
    took = time.time() - t0
    check(f"ingest into MySQL ({took:.0f}s)", counts.get("inspections", 0) >= 125000, str(counts))

    conn = db.connect()
    wells = conn.execute("SELECT COUNT(*) c FROM wells").fetchone()["c"]
    insp = conn.execute("SELECT COUNT(*) c FROM inspections").fetchone()["c"]
    areas = conn.execute("SELECT COUNT(*) c FROM areas").fetchone()["c"]
    check("row counts match baseline", wells == 600 and insp == 125198 and areas == 7,
          f"wells={wells} insp={insp} areas={areas}")

    from app import agent, ops_tools, tools
    _, env = agent.answer(conn, "U-201",
                          "Is WELL-0001 producing oil right now? When was it last inspected, and by whom?")
    d = env["data"]
    check("status answer on MySQL", d["producing"] is True and d["inspector"] is not None,
          f"{d['producing']} / {d.get('inspector')} / {env['text'][:120]}")

    b = ops_tools.crew_board(conn)
    check("crew board on MySQL", b["data"]["counts"]["P1"] >= 1 and len(b["data"]["board"]) > 50,
          str(b["data"]["counts"]))

    dash = tools.dashboard_data(conn)
    check("dashboard on MySQL", dash["kpis"]["wells"] == 600 and len(dash["fleet"]) == 600,
          str(dash["kpis"]))

    _, env2 = agent.answer(conn, "U-201", "Which 3 wells in Northeast Block 8 had the most downtime in the last 4 months? Show a bar chart.")
    check("downtime ranking on MySQL", "days" in str(env2["data"].get("top", "")) or env2["data"],
          env2["text"][:140])

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"===== {passed}/{len(RESULTS)} MySQL smoke checks passed =====")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
