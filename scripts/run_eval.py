"""Run the 18 example scenarios (03-evaluation-queries.md) end to end and check
the copilot's answers against the organizers' expected results.

Run from backend/:  python ../scripts/run_eval.py
"""
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import agent, config, db  # noqa: E402

# The 18 example scenarios are defined against the SAMPLE dataset with
# "today = 17 Oct 2026", so pin both regardless of what the live app is
# currently pointed at (the test dataset sets a different today).
SAMPLE_DIR = Path(__file__).resolve().parents[2] / "dataset" / "sample-data"
if not SAMPLE_DIR.exists():
    SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample-data"
config.DATA_DIRS = [SAMPLE_DIR]
config.FIXED_TODAY = date(2026, 10, 17)

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


def ask(conn, user_id, msg, cid=None):
    return agent.answer(conn, user_id, msg, cid)


def wells_of(env):
    out = []
    v = env.get("visual")
    if v and v.get("kind") == "table":
        out = [r[0] for r in v.get("rows", [])]
    elif v and v.get("kind") in ("bar", "map"):
        out = [p.get("asset_id") for p in v.get("points", [])]
    return out


def main():
    tmp = tempfile.mktemp(suffix=".db")
    print("ingesting sample data ...")
    db.ingest(db_path=tmp)
    conn = db.connect(tmp)

    # ---------------- Part A1 ----------------
    _, env = ask(conn, "U-201", "Is WELL-0001 producing oil right now? When was it last "
                               "inspected, and by whom?")
    d = env["data"]
    check("Q1 not producing", d["producing"] is False, env["text"][:120])
    check("Q1 latest inspection", d["last_inspected_at"].startswith("2026-10-15"), d["last_inspected_at"])
    check("Q1 inspector Ryan Brooks drone", d["inspector"] == "Ryan Brooks" and d["method"] == "drone",
          f"{d['inspector']}/{d['method']}")
    check("Q1 cites INS-0001-0203", "INS-0001-0203" in env["text"])

    _, env = ask(conn, "U-201", "Which wells in Northeast Block 8 are not producing oil right "
                                "now, and why? Show them in a table.")
    rows = wells_of(env)
    check("Q2 four wells", len(rows) == 4, str(rows))
    check("Q2 well ids", rows == ["WELL-0164", "WELL-0170", "WELL-0172", "WELL-0175"], str(rows))
    check("Q2 deltas", [r[1] for r in env["visual"]["rows"]] ==
          ["4.1 °C", "2.9 °C", "5.7 °C", "0.4 °C"], str([r[1] for r in env["visual"]["rows"]]))

    _, env = ask(conn, "U-201", "Show a line chart of WELL-0001's wellhead temperature against "
                                "air temperature for the last 13 weeks, and mark when it was "
                                "not producing oil.")
    d = env["data"]
    check("Q3 13 readings", len(d) == 13, str(len(d)))
    down = [p["date"] for p in d if not p["producing"]]
    check("Q3 not producing 8+15 Oct", down == ["2026-10-08", "2026-10-15"], str(down))
    check("Q3 line visual", env["visual"]["kind"] == "line")

    _, env = ask(conn, "U-201", "How many oil spills has WELL-0001 had in the last 4 years, and "
                                "how much oil in total? List them in a table.")
    d = env["data"]
    check("Q4 six spills", d["count"] == 6, str(d["count"]))
    check("Q4 15.1 bbl", abs(d["total_bbl"] - 15.1) < 0.05, str(d["total_bbl"]))

    _, env = ask(conn, "U-201", "How many days was WELL-0001 down in 2025?")
    check("Q5 21 days", env["data"]["days"] == 21, str(env["data"]["days"]))
    check("Q5 evidence", "MNT-0001-021" in env["text"] and "MNT-0001-023" in env["text"])

    _, env = ask(conn, "U-201", "Which 3 wells in Northeast Block 7 had the most downtime in the "
                                "last 4 months? Show a bar chart.")
    top = env["data"]["top"]
    check("Q6 top3", [(t["asset_id"], t["days"]) for t in top] ==
          [("WELL-0121", 49), ("WELL-0138", 42), ("WELL-0107", 42)], str(top))
    check("Q6 next 0119 28", env["data"]["next"] and env["data"]["next"][0]["asset_id"] ==
          "WELL-0119" and env["data"]["next"][0]["days"] == 28, str(env["data"]["next"]))
    check("Q6 bar visual", env["visual"]["kind"] == "bar")

    _, env = ask(conn, "U-201", "Show on a map every well in Northeast Block 8 with a real spill "
                                "in the last 90 days.")
    pins = {p["asset_id"]: (p["date"], round(p["volume_bbl"], 1)) for p in env["data"]}
    check("Q7 four pins", set(pins) == {"WELL-0151", "WELL-0165", "WELL-0175", "WELL-0186"},
          str(pins))
    check("Q7 0151 4.5", pins.get("WELL-0151", (None, None))[1] == 4.5, str(pins))
    check("Q7 map visual", env["visual"]["kind"] == "map")

    _, env = ask(conn, "U-201", "Show a heatmap of 2026 spills by geographic area and month.")
    grid = env["data"]
    totals = {k: sum(v) for k, v in grid.items()}
    check("Q8 totals", totals == {"Southwest Block 23": 35, "Southwest Block 24": 43,
                                  "Northeast Block 7": 37, "Northeast Block 8": 26}, str(totals))
    check("Q8 SW-23 Jan=4", grid["Southwest Block 23"][0] == 4)

    _, env = ask(conn, "U-201", "Which rules has WELL-0001 broken in the last 12 months, and "
                                "what is still open?")
    breaches = [b["rule"] for b in env["data"]["breaches"]]
    check("Q9 four breaches", len(breaches) == 4, str(breaches))
    check("Q9 rules", set(breaches) == {"SR-01", "SR-02", "SR-03", "RC-04"}, str(breaches))
    check("Q9 fine 5000 open", env["data"]["open_fines"] == 5000, str(env["data"]["open_fines"]))
    check("Q9 RCA pending", any("root-cause" in p["detail"] for p in env["data"]["pending"]))
    check("Q9 shut-in pending", any("shut-in" in p["detail"] for p in env["data"]["pending"]))
    check("Q9 RC-02 met", any(m["rule"] == "RC-02" for m in env["data"]["met"]))

    _, env = ask(conn, "U-201", "In Southwest Block 24, which spills in the last 90 days were "
                                "not contained within the SOP time limit?")
    rows = [r[0] for r in (env["visual"]["rows"] if env["visual"] else [])]
    check("Q10 two spills", rows == ["WELL-0082", "WELL-0100"], str(rows))

    # ---------------- Part A2 (one user, memory + feedback) ----------------
    _, env = ask(conn, "U-201", "Which 3 wells in Northeast Block 7 had the most downtime in the "
                                "last 4 months? Show a bar chart.")
    _, env = ask(conn, "U-201", "For the three wells we discussed yesterday, what have repairs "
                                "cost this year?")
    rows = {r[0]: r[1] for r in env["data"]} if env.get("data") else {}
    check("Q11 three wells", set(rows) == {"WELL-0121", "WELL-0138", "WELL-0107"}, str(rows))
    check("Q11 costs", rows.get("WELL-0121") == "USD 25,794" and
          rows.get("WELL-0138") == "USD 46,942" and rows.get("WELL-0107") == "USD 5,176",
          str(rows))

    _, env = ask(conn, "U-201", "The 15 Oct reading for WELL-0164 is wrong. The handheld thermal "
                                "gun used in that inspection was faulty; the field crew "
                                "re-measured the wellhead at 41.0 °C.")
    check("Q12 correction recorded", "INS-0164-0205" in env["text"], env["text"][:150])
    check("Q12 keeps original", "24.0" in env["text"])
    check("Q12 now producing", "producing oil**" in env["text"] or
          env["visual"]["payload"]["producing"] is True, env["text"][-200:])
    check("Q12 flags disagreeing note", "Pump jack not moving" in env["text"])
    _, env = ask(conn, "U-201", "Which wells in Northeast Block 8 are not producing oil right "
                                "now, and why? Show them in a table.")
    check("Q12 Q2 rerun three wells", wells_of(env) == ["WELL-0170", "WELL-0172", "WELL-0175"],
          str(wells_of(env)))
    check("Q12 explains 0164", "WELL-0164" in env["text"])

    _, env = ask(conn, "U-201", "The AI estimated the 24 Sep spill at WELL-0151 as 4.5 bbl. The "
                                "field crew measured 5.4 bbl.")
    t = env["text"]
    check("Q13 reportable + SR-01 flag", "reportable" in t and "SR-01" in t)
    check("Q13 no notice recorded", "none is recorded" in t)
    check("Q13 stale moderate class", "no longer holds" in t)
    check("Q13 SR-02 6.4h", "6.4" in t and "SR-02" in t)
    check("Q13 SR-03 due 23 Nov", "23 Nov 2026" in t)

    _, env = ask(conn, "U-201", "Which wells in Northeast Block 7 need a root-cause analysis on "
                                "their pump jack?")
    base = wells_of(env)
    check("Q14 base three", base == ["WELL-0108", "WELL-0121", "WELL-0138"], str(base))
    _, env = ask(conn, "U-201", "Note for all T350 wells: our team now wants a pump jack "
                                "root-cause analysis after 2 repairs, not 3.")
    _, env = ask(conn, "U-201", "Which wells in Northeast Block 7 need a root-cause analysis on "
                                "their pump jack?")
    after = wells_of(env)
    check("Q14 adds 0120", after == ["WELL-0108", "WELL-0120", "WELL-0121", "WELL-0138"],
          str(after))
    check("Q14 not 0102", "WELL-0102" not in after)
    check("Q14 cites rule not manual", "rule" in env["text"] and "manual" in env["text"])

    # ---------------- Part B (several users) ----------------
    _, env = ask(conn, "U-202", "Is WELL-0164 producing oil right now?")
    check("Q15 Jessica yes", env["data"]["producing"] is True)
    check("Q15 corrected by Michael", "Michael Turner" in env["text"])
    check("Q15 mentions disagreeing note", "Pump jack not moving" in env["text"])

    _, env = ask(conn, "U-401", "Which spills in Northeast Block 8 in the last 90 days needed a "
                                "report to the regulator?")
    rows = [r[0] for r in (env["visual"]["rows"] if env["visual"] else [])]
    check("Q15 Laura only 0151", rows == ["WELL-0151"], str(rows))
    check("Q15 overdue notice", "overdue" in env["text"].lower())

    _, env = ask(conn, "U-102", "FYI for everyone: WELL-0007 will be shut in from 17 Oct for a "
                                "10-day planned workover.")
    check("Q16 shared recorded", "WELL-0007" in env["text"])
    _, env = ask(conn, "U-201", "Is any downtime planned for WELL-0007?")
    check("Q16 Michael sees shared", "17 Oct" in env["text"] and "Jake Morales" in env["text"],
          env["text"][:200])
    _, env = ask(conn, "U-202", "For the three wells we discussed yesterday, what have repairs "
                                "cost this year?")
    check("Q16 Jessica no private memory", "earlier conversation" in env["text"] and
          "Michael" not in env["text"], env["text"][:200])

    _, env = ask(conn, "U-201", "WELL-0175 has been shut in for planned work since 14 Oct.")
    check("Q17 Michael claim ok", "Recorded" in env["text"], env["text"][:150])
    _, env = ask(conn, "U-204", "WELL-0175 is running fine.")
    check("Q17 Tyler conflict", "conflicts with the data" in env["text"] and
          "unconfirmed" in env["text"], env["text"][:300])
    check("Q17 cites inspection", "2026-10-15" in env["text"] or "INS-0175" in env["text"])
    check("Q17 mentions Michael note match", "matches" in env["text"] or "Michael" in env["text"],
          env["text"][:400])
    _, env = ask(conn, "U-102", "WELL-0001 is back online since 14 Oct.")
    check("Q17 Jake conflict", "conflicts with the data" in env["text"] and
          "unconfirmed" in env["text"], env["text"][:300])

    _, env = ask(conn, "U-201", "Was the 20 Aug spill at WELL-0101 real oil?")
    t = env["text"]
    check("Q18 yes + stands", "yes" in t.lower() and "stands" in t.lower(), t[:200])
    check("Q18 both notes", "CTX-0101-002" in t and "CTX-0101-003" in t)
    check("Q18 not formal corrections", "Neither note is a formal correction" in t)
    check("Q18 repair cited", "MNT-0101-029" in t)

    conn.close()
    os.remove(tmp)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n================ {passed}/{len(RESULTS)} checks passed ================")
    for name, ok, detail in RESULTS:
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {name}"
        if not ok:
            line += f"  -> {detail[:220]}"
        print(line)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
