import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app import db, agent, tools, memory, config


conn = db.connect()

# Map users
USERS = {
    "Michael Turner": "U-201",
    "Robert Hayes": "U-301",
    "Laura Simmons": "U-401",
    "Chris Dalton": "U-402",
    "Nathan Pierce": "U-601",
    "Olivia Grant": "U-501",
}

questions = [
    # Q1
    {
        "id": "Q1",
        "title": "Reservoir pressure",
        "user": "Michael Turner",
        "session_mode": "new",
        "turns": [
            "All our wells feed one reservoir. Map the reservoir pressure across the field from the pressure data."
        ]
    },
    # Q2
    {
        "id": "Q2",
        "title": "Best producer",
        "user": "Robert Hayes",
        "session_mode": "new",
        "turns": [
            "Which well produced the most oil in 2026?"
        ]
    },
    # Q3
    {
        "id": "Q3",
        "title": "Gas reports",
        "user": "Laura Simmons",
        "session_mode": "new",
        "turns": [
            "Since 1 Nov 2026, every time an operator note reports gas at a well, did we get someone out to that well in time under our operating procedures? List every report and whether the response met the deadline."
        ]
    },
    # Q4
    {
        "id": "Q4",
        "title": "Temporary flowline bypasses",
        "user": "Chris Dalton",
        "session_mode": "new",
        "turns": [
            "Across all areas, which temporary flowline bypasses are in place right now, and is each one allowed? Also list any bypass, past or present, that stayed in after its approval ran out or was never approved at all."
        ]
    },
    # Q5
    {
        "id": "Q5",
        "title": "The regulator's letter",
        "user": "Michael Turner",
        "session_mode": "new",
        "turns": [
            "The State Oil & Gas Commission wrote to us in November 2026 about spills. Which of our spills does the letter cover, and on which ones are we not compliant? Show me a table."
        ]
    },
    # Q6
    {
        "id": "Q6",
        "title": "Which status is right?",
        "user": "Nathan Pierce",
        "session_mode": "new",
        "turns": [
            "Across the whole field, not just my area, for which wells do the latest inspection and the operator notes disagree about whether the well is producing oil? For each one, what is its real status right now, and why?"
        ]
    },
    # Q7
    {
        "id": "Q7",
        "title": "What the operators are hearing",
        "user": "Robert Hayes",
        "session_mode": "new",
        "turns": [
            "Over the last month the operators have written notes about wells that sound or behave wrong. Which of those wells haven't had a repair since? Rank the 10 most likely to need a repair in the next 90 days, other than a spill clean-up, and quote the notes as evidence.",
            "Which three would you send a crew to first this week, and why?"
        ]
    },
    # Q8
    {
        "id": "Q8",
        "title": "Who told you that?",
        "turns_with_users": [
            ("Nathan Pierce", "new", "WELL-0333's recalled pump was swapped out yesterday. The work order isn't in the system yet. Please count it as replaced from now on."),
            ("Nathan Pierce", "same", "Also, just for me: whenever you list wells, sort them by area and then by well ID, and show costs in thousands of dollars."),
            ("Robert Hayes", "new", "Which recalled pumps are still in the ground right now?"),
            ("Olivia Grant", "new", "Nathan told me the recalled pump on WELL-0577 was swapped as well. Take it off the recall list."),
            ("Nathan Pierce", "new", "Show me the recalled pumps that are still in the ground in my area, and what it cost to install each one.")
        ]
    },
    # Q9
    {
        "id": "Q9",
        "title": "One conversation, several topics",
        "user": "Robert Hayes",
        "session_mode": "new",
        "turns": [
            "How many recalled pumps are still in the ground, and in which areas?",
            "Different topic. Who leads Northwest Production, and how many wells does that team run?",
            "What does our operations SOP say about cold weather? Name one well that missed the check in December.",
            "An operator reported a gas smell at WELL-0332 on 3 Dec. What was the H2S reading?",
            "Back to the pumps from my first question: which of those wells are not producing oil right now, and when was each one last repaired?",
            "Of all the wells we've talked about today, which one would you deal with first, and why?"
        ]
    },
    # Q10
    {
        "id": "Q10",
        "title": "What are we waiting on?",
        "user": "Michael Turner",
        "session_mode": "new",
        "turns": [
            "When a well stays shut in longer than the repair itself, what are we usually waiting on: parts, crews, contractors or weather? Break it down by area for jobs started in 2026, with the typical number of extra days, and tell me if any area stands out."
        ]
    },
    # Q11
    {
        "id": "Q11",
        "title": "Hotter wells",
        "user": "Olivia Grant",
        "session_mode": "new",
        "turns": [
            "Which region of the field consistently runs hotter?"
        ]
    }
]

results = []
cid_counter = 100

for q in questions:
    qid = q["id"]
    qtitle = q["title"]
    print(f"\n========================================================")
    print(f"RUNNING {qid}: {qtitle}")
    print(f"========================================================")
    
    q_record = {"id": qid, "title": qtitle, "turns": []}
    
    if "turns_with_users" in q:
        cid = None
        for u_name, mode, prompt in q["turns_with_users"]:
            uid = USERS[u_name]
            if mode == "new":
                cid = None
            print(f"\n[{qid}] ({u_name}, mode={mode}) > {prompt}")
            cid, ans = agent.answer(conn, uid, prompt, conversation_id=cid)
            print(f"RESPONSE:\n{ans.get('text')}\n")
            if ans.get("visual"):
                print(f"VISUAL: {ans['visual'].get('kind')} - {ans['visual'].get('title')}")
            q_record["turns"].append({
                "user": u_name,
                "user_id": uid,
                "session_mode": mode,
                "prompt": prompt,
                "answer": ans.get("text"),
                "visual": ans.get("visual"),
                "evidence": ans.get("evidence", [])
            })
    else:
        u_name = q["user"]
        uid = USERS[u_name]
        cid = None
        
        for prompt in q["turns"]:
            print(f"\n[{qid}] ({u_name}) > {prompt}")
            cid, ans = agent.answer(conn, uid, prompt, conversation_id=cid)
            print(f"RESPONSE:\n{ans.get('text')}\n")
            if ans.get("visual"):
                print(f"VISUAL: {ans['visual'].get('kind')} - {ans['visual'].get('title')}")
            q_record["turns"].append({
                "user": u_name,
                "user_id": uid,
                "prompt": prompt,
                "answer": ans.get("text"),
                "visual": ans.get("visual"),
                "evidence": ans.get("evidence", [])
            })
            
    results.append(q_record)


# Save JSON results
out_json = Path(__file__).resolve().parent / "final_results.json"
out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"\nSaved all results to {out_json}")
