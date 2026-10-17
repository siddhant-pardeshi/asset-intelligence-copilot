"""End-to-end test for user dataset upload: build a tiny synthetic dataset
zip, upload it, query the new well through the agent, then reset and confirm
the store is back to the challenge data only.

Run from backend/:  python ../scripts/test_upload.py
"""
import io
import json
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import config, db  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="upload-test-"))
config.DB_PATH = str(tmp / "test.db")
config.UPLOAD_DIR = tmp / "uploads"
config.MANIFEST_PATH = config.UPLOAD_DIR / "manifest.json"

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


def tiny_dataset_zip() -> bytes:
    """One area, one user, one well with three weekly inspections (last one
    down) and one corrective repair — enough for every tool to light up."""
    fleet = {
        "areas": {"areas": [{"area_id": "TE-99", "name": "Test Block 99", "team_id": "TEAM-T",
                             "center": {"lat": 30.0, "lon": -100.0},
                             "asset_ids": ["WELL-9001"]}],
                  "teams": [{"team_id": "TEAM-T", "name": "Test Team", "lead_user_id": "U-901"}]},
        "users": {"users": [{"user_id": "U-901", "name": "Test Owner", "role": "field_operator",
                             "team_id": "TEAM-T"}]},
    }
    meta = {"asset_id": "WELL-9001", "name": "Test Well 001", "asset_category": "oil_well",
            "well_type": "T200", "area_id": "TE-99", "team_id": "TEAM-T",
            "in_charge_user_id": "U-901", "location": {"lat": 30.0, "lon": -100.0},
            "installed_on": "2024-01-15", "equipment": [], "recorded_status": "active"}
    insp = [
        {"inspection_id": "INS-9001-0001", "asset_id": "WELL-9001",
         "inspected_at": "2028-02-17T09:00:00Z", "inspector_user_id": "U-901", "method": "drone",
         "ambient_temp_c": 15.0, "wellhead_temp_c": 45.0, "spill_detected": False,
         "spill_area_pct": None, "spill_est_volume_bbl": None, "evidence_images": [], "notes": ""},
        {"inspection_id": "INS-9001-0002", "asset_id": "WELL-9001",
         "inspected_at": "2028-02-24T09:00:00Z", "inspector_user_id": "U-901", "method": "drone",
         "ambient_temp_c": 14.0, "wellhead_temp_c": 44.0, "spill_detected": False,
         "spill_area_pct": None, "spill_est_volume_bbl": None, "evidence_images": [], "notes": ""},
        {"inspection_id": "INS-9001-0003", "asset_id": "WELL-9001",
         "inspected_at": "2028-03-01T09:00:00Z", "inspector_user_id": "U-901", "method": "manual",
         "ambient_temp_c": 13.0, "wellhead_temp_c": 15.0, "spill_detected": False,
         "spill_area_pct": None, "spill_est_volume_bbl": None, "evidence_images": [],
         "notes": "Pump jack not moving."},
    ]
    mnt = [{"maintenance_id": "MNT-9001-001", "asset_id": "WELL-9001",
            "started_at": "2028-03-01T10:00:00Z", "completed_at": None,
            "maintenance_type": "corrective", "equipment_kind": "pump_jack",
            "issue": "Prime mover trip", "action_taken": "Investigating",
            "technician_user_id": "U-901", "downtime_hours": 24,
            "cost_usd": {"labor": 100, "parts": 200, "total": 300},
            "triggered_by_inspection_id": None, "report_file": None}]
    ctx = [{"asset_id": "WELL-9001", "created_at": "2028-02-28T08:00:00Z",
            "author_user_id": "U-901", "note_type": "operator_feedback",
            "inspection_id": None,
            "text": "Hearing a knock from the gearbox, watching it closely.",
            "valid_from": "2028-02-28", "valid_to": None, "note_id": "CTX-9001-001"}]

    def jsonl(rows):
        return "\n".join(json.dumps(r) for r in rows).encode()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("my-field/fleet/areas.json", json.dumps(fleet["areas"]))
        z.writestr("my-field/fleet/users.json", json.dumps(fleet["users"]))
        z.writestr("my-field/assets/WELL-9001/metadata.json", json.dumps(meta))
        z.writestr("my-field/assets/WELL-9001/inspections.jsonl", jsonl(insp))
        z.writestr("my-field/assets/WELL-9001/maintenance.jsonl", jsonl(mnt))
        z.writestr("my-field/assets/WELL-9001/context.jsonl", jsonl(ctx))
    return buf.getvalue()


def main():
    import warnings
    warnings.filterwarnings("ignore")
    from fastapi.testclient import TestClient
    from app.main import app

    db.ingest(db_path=config.DB_PATH)
    client = TestClient(app)

    base = client.get("/api/health").json()
    check("baseline loaded", base["wells"] == 600, str(base))

    # a bad upload is rejected with guidance, not a 500
    r = client.post("/api/upload-dataset", files={"file": ("junk.zip", b"not a zip")})
    check("bad upload rejected", r.status_code == 400 and "zip" in r.json()["error"],
          f"{r.status_code} {r.json()}")

    # the real thing
    r = client.post("/api/upload-dataset",
                    files={"file": ("my-field.zip", tiny_dataset_zip())},
                    data={"name": "my field!"})
    up = r.json()
    check("upload accepted", r.status_code == 200 and up.get("ok"), str(up)[:200])
    totals = up.get("totals", {})
    check("merged, not replaced", totals.get("wells") == 601, str(totals))
    check("today follows user data", totals.get("today") == "2028-03-02", str(totals))

    # the new well answers through the full agent, with its own facts
    d = client.post("/api/chat", json={"user_id": "U-201",
                                       "message": "Is WELL-9001 producing oil right now?"}).json()
    check("chat knows the uploaded well", "WELL-9001" in d["text"] and "not producing" in d["text"],
          d["text"][:160])
    check("chat cites open repair", "MNT-9001-001" in d["text"], d["text"][:300])

    d = client.post("/api/chat", json={"user_id": "U-201",
                                       "message": "Which wells in Test Block 99 are not producing oil right now?"}).json()
    check("uploaded area queryable", any("WELL-9001" in str(r) for r in
                                         (d.get("visual") or {}).get("rows", [])), d["text"][:160])

    # manifest persisted for restart survival
    manifest = json.loads(config.MANIFEST_PATH.read_text()) if config.MANIFEST_PATH.exists() else []
    check("manifest records upload", len(manifest) == 1 and Path(manifest[0]).exists(), str(manifest))

    # reset returns the store to the challenge data
    r = client.post("/api/reset-data")
    rs = r.json()
    check("reset ok", r.status_code == 200 and rs.get("ok"), str(rs)[:150])
    after = client.get("/api/health").json()
    check("reset restores 600 wells", after["wells"] == 600, str(after))
    gone = client.post("/api/chat", json={"user_id": "U-201",
                                          "message": "Is WELL-9001 producing oil right now?"}).json()
    check("uploaded well gone after reset", "no record" in gone["text"].lower()
          or "Unknown well" in gone["text"], gone["text"][:140])

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"===== {passed}/{len(RESULTS)} upload tests passed =====")
    for name, ok, detail in RESULTS:
        print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {detail[:200]}"))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
