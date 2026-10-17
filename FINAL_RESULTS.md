# Final Questions — Complete Results
**Dataset:** 600 wells, 7 areas, 6 teams | **Today:** 15 January 2027 | **System:** Asset Intelligence Copilot

---

## Q1. Reservoir pressure

**Asked by:** Michael Turner

> All our wells feed one reservoir. Map the reservoir pressure across the field from the pressure data.

The dataset does not contain reservoir pressure readings. The inspection records include wellhead and ambient temperatures but no direct pressure measurements. To map reservoir pressure, pressure gauges or well test data would be needed, which are not part of the current dataset.

<details><summary>Evidence Sources</summary>

- {'type': 'doc', 'id': 'dataset-guide', 'label': 'Dataset Guide — inspection fields'}

</details>

---

## Q2. Best producer

**Asked by:** Robert Hayes

> Which well produced the most oil in 2026?

**WELL-0212** had the most productive weeks in 2026: **53 weeks** producing oil out of 53 inspections, with an average wellhead-to-air delta of 36.6 °C (T500 well in Southeast Block 31).


Note: The dataset does not contain volumetric production data (barrels per day). 'Most oil' is estimated from the number of weeks the well was producing oil (based on temperature readings and the well-type manual threshold).

*Visual: TABLE — Top Producers — 2026*

| Well | Type | Area | Productive Weeks | Avg Δ°C |
| --- | --- | --- | --- | --- |
| WELL-0212 | T500 | Southeast Block 31 | 53 | 36.6 |
| WELL-0242 | T500 | Southeast Block 31 | 53 | 36.6 |
| WELL-0228 | T500 | Southeast Block 31 | 53 | 36.5 |
| WELL-0287 | T500 | Southwest Block 23 | 53 | 36.5 |
| WELL-0550 | T500 | Southeast Block 32 | 53 | 36.5 |

<details><summary>Evidence Sources</summary>

- {'type': 'doc', 'id': 'T500', 'label': 'Well-type manual production threshold'}

</details>

---

## Q3. Gas reports

**Asked by:** Laura Simmons

> Since 1 Nov 2026, every time an operator note reports gas at a well, did we get someone out to that well in time under our operating procedures? List every report and whether the response met the deadline.

Since 1 Nov 2026, **26 operator note(s)** reported gas at wells. **9 response(s) missed** the OPS-1 deadline.

*Visual: TABLE — Gas Odor Response Audit (OPS-1)*

| Well | Area | Reported at | Response | Hours to response | Deadline | Met/Missed |
| --- | --- | --- | --- | --- | --- | --- |
| WELL-0163 | Northeast Block 8 | 2026-11-03 20:55 | MNT-0163-019 (2026-11-14 08:00) | 251.1 | 24h | Missed |
| WELL-0149 | Northeast Block 7 | 2026-11-06 18:20 | MNT-0149-029 (2026-11-07 08:00) | 13.7 | 24h | Met |
| WELL-0165 | Northeast Block 8 | 2026-11-13 20:35 | MNT-0165-031 (2026-11-14 08:00) | 11.4 | 24h | Met |
| WELL-0341 | Northwest Block 12 | 2026-11-19 07:40 | INS-0341-0109 (2026-12-17 13:30) | 677.8 | 24h | Missed |
| WELL-0091 | Southwest Block 24 | 2026-11-27 22:25 | MNT-0091-019 (2026-11-28 08:00) | 9.6 | 24h | Met |
| WELL-0423 | Northwest Block 12 | 2026-12-03 05:25 | INS-0423-0213 (2026-12-03 09:15) | 3.8 | 24h | Met |
| WELL-0059 | Southwest Block 24 | 2026-12-03 06:10 | INS-0059-0213 (2026-12-03 12:15) | 6.1 | 24h | Met |
| WELL-0332 | Northwest Block 12 | 2026-12-03 12:10 | None | — | 24h | Missed |
| WELL-0401 | Northwest Block 12 | 2026-12-05 13:50 | MNT-0401-033 (2026-12-11 08:00) | 138.2 | 24h | Missed |
| WELL-0189 | Northeast Block 8 | 2026-12-10 12:35 | MNT-0189-037 (2026-12-11 08:00) | 19.4 | 24h | Met |
| WELL-0403 | Northwest Block 12 | 2026-12-10 21:15 | MNT-0403-024 (2026-12-11 08:00) | 10.8 | 24h | Met |
| WELL-0244 | Southeast Block 31 | 2026-12-11 05:25 | MNT-0244-026 (2026-12-11 08:00) | 2.6 | 24h | Met |
| WELL-0040 | Southwest Block 23 | 2026-12-12 01:55 | MNT-0040-029 (2026-12-12 08:00) | 6.1 | 24h | Met |
| WELL-0228 | Southeast Block 31 | 2026-12-16 19:50 | INS-0228-0144 (2026-12-17 12:45) | 16.9 | 24h | Met |
| WELL-0052 | Southwest Block 24 | 2026-12-18 06:45 | None | — | 24h | Missed |
| WELL-0370 | Northwest Block 12 | 2026-12-21 12:45 | MNT-0370-028 (2026-12-22 08:00) | 19.2 | 24h | Met |
| WELL-0362 | Northwest Block 12 | 2026-12-24 00:15 | MNT-0362-030 (2026-12-25 08:00) | 31.8 | 24h | Missed |
| WELL-0161 | Northeast Block 8 | 2026-12-25 15:45 | INS-0161-0168 (2027-01-14 11:00) | 475.2 | 24h | Missed |
| WELL-0135 | Northeast Block 7 | 2026-12-27 03:50 | MNT-0135-034 (2026-12-27 08:00) | 4.2 | 24h | Met |
| WELL-0324 | Northwest Block 12 | 2027-01-01 22:40 | MNT-0324-036 (2027-01-02 08:00) | 9.3 | 12h | Met |
| WELL-0330 | Northwest Block 12 | 2027-01-02 21:40 | MNT-0330-030 (2027-01-03 08:00) | 10.3 | 12h | Met |
| WELL-0599 | Southeast Block 32 | 2027-01-06 17:20 | INS-0599-0196 (2027-01-07 09:45) | 16.4 | 12h | Missed |
| WELL-0516 | Southeast Block 32 | 2027-01-06 21:15 | INS-0516-0215 (2027-01-07 12:15) | 15.0 | 12h | Missed |
| WELL-0425 | Northwest Block 12 | 2027-01-07 05:20 | INS-0425-0218 (2027-01-07 09:00) | 3.7 | 12h | Met |
| WELL-0465 | Southeast Block 32 | 2027-01-08 23:35 | MNT-0465-031 (2027-01-09 08:00) | 8.4 | 12h | Met |
| *...and 1 more rows* | |

<details><summary>Evidence Sources</summary>

- {'type': 'note', 'id': 'CTX-0163-002', 'label': 'CTX-0163-002 — H2S monitor alarmed at WELL-0163, crew moved upwind and repo'}
- {'type': 'note', 'id': 'CTX-0149-004', 'label': 'CTX-0149-004 — Strong gas odor around the WELL-0149 cellar, called it in to'}
- {'type': 'note', 'id': 'CTX-0165-001', 'label': 'CTX-0165-001 — Rotten-egg smell at the WELL-0165 pad on arrival, called the'}
- {'type': 'note', 'id': 'CTX-0341-002', 'label': 'CTX-0341-002 — H2S monitor alarmed at WELL-0341, crew moved upwind and repo'}
- {'type': 'note', 'id': 'CTX-0091-001', 'label': 'CTX-0091-001 — H2S monitor alarmed at WELL-0091, crew moved upwind and repo'}

</details>

---

## Q4. Temporary flowline bypasses

**Asked by:** Chris Dalton

> Across all areas, which temporary flowline bypasses are in place right now, and is each one allowed? Also list any bypass, past or present, that stayed in after its approval ran out or was never approved at all.

**3 temporary flowline bypasses are in place right now:**
- **WELL-0248** (Southeast Block 31): Allowed (Approval: MOC-2026-031 / MOC-2026-044, valid until 2027-02-28)
- **WELL-0249** (Southeast Block 31): Expired (Approval: MOC-2026-036, valid until 2026-12-15)
- **WELL-0405** (Northwest Block 12): Not approved (Approval: None, valid until —)

**5 bypasses (past or present) violated MOC rules (Expired or Not approved):**
- **WELL-0087** (Southwest Block 24): Expired — In: 2026-12-02, Out: 2027-01-06, Approval: MOC-2026-036
- **WELL-0158** (Northeast Block 8): Expired — In: 2026-11-20, Out: 2026-12-28, Approval: MOC-2026-036
- **WELL-0249** (Southeast Block 31): Expired — In: 2026-11-25, Out: still in, Approval: MOC-2026-036
- **WELL-0405** (Northwest Block 12): Not approved — In: 2026-12-20, Out: still in, Approval: None
- **WELL-0561** (Southeast Block 32): Not approved — In: 2026-12-08, Out: 2026-12-19, Approval: None


*Visual: TABLE — Temporary Flowline Bypasses Audit*

| Well | Area | Bypass in | Bypass out | Approval | Approval valid until | Status |
| --- | --- | --- | --- | --- | --- | --- |
| WELL-0087 | Southwest Block 24 | 2026-12-02 | 2027-01-06 | MOC-2026-036 | 2026-12-15 | Expired |
| WELL-0158 | Northeast Block 8 | 2026-11-20 | 2026-12-28 | MOC-2026-036 | 2026-12-15 | Expired |
| WELL-0248 | Southeast Block 31 | 2026-11-05 | still in | MOC-2026-031 / MOC-2026-044 | 2027-02-28 | Allowed |
| WELL-0249 | Southeast Block 31 | 2026-11-25 | still in | MOC-2026-036 | 2026-12-15 | Expired |
| WELL-0405 | Northwest Block 12 | 2026-12-20 | still in | None | — | Not approved |
| WELL-0561 | Southeast Block 32 | 2026-12-08 | 2026-12-19 | None | — | Not approved |

<details><summary>Evidence Sources</summary>

- {'type': 'doc', 'id': 'operations-sop-rev2', 'label': 'Operations SOP Rev 2, OPS-2'}
- {'type': 'doc', 'id': 'moc-2026-031', 'label': 'MOC-2026-031 memo'}
- {'type': 'doc', 'id': 'moc-2026-036', 'label': 'MOC-2026-036 memo'}
- {'type': 'doc', 'id': 'moc-2026-044', 'label': 'MOC-2026-044 extension memo'}
- {'type': 'note', 'id': 'CTX-0476-002', 'label': 'Temporary bypass in place on WELL-0476 until the new valve arrives.'}

</details>

---

## Q5. The regulator's letter

**Asked by:** Michael Turner

> The State Oil & Gas Commission wrote to us in November 2026 about spills. Which of our spills does the letter cover, and on which ones are we not compliant? Show me a table.

The regulator's letter covers all reportable spills (≥ 5 bbl) in Northeast Block 7 and Northeast Block 8 since 1 Jun 2026. A total of **6 spills** fall under the letter's scope. Of these, **4 spills are NOT compliant** because clean-up records lack the required laboratory soil confirmation ('Soil samples sent to the lab.').

*Visual: TABLE — Regulator Letter Spill Compliance (Nov 2026)*

| Well | Area | Inspection | Volume (bbl) | Clean-up job | Compliant? |
| --- | --- | --- | --- | --- | --- |
| WELL-0168 | Northeast Block 8 | INS-0168-0190 (2026-06-11) | 5.6 | MNT-0168-024 | No (No lab soil results in clean-up report) |
| WELL-0123 | Northeast Block 7 | INS-0123-0093 (2026-09-24) | 6.0 | MNT-0123-014 | No (No lab soil results in clean-up report) |
| WELL-0277 | Northeast Block 7 | INS-0277-0205 (2026-10-01) | 6.2 | MNT-0277-031 | Yes (Lab soil results submitted) |
| WELL-0119 | Northeast Block 7 | INS-0119-0209 (2026-11-05) | 6.0 | MNT-0119-029 | Yes (Lab soil results submitted) |
| WELL-0182 | Northeast Block 8 | INS-0182-0208 (2026-12-03) | 5.2 | MNT-0182-028 | No (No lab soil results in clean-up report) |
| WELL-0262 | Northeast Block 8 | INS-0262-0218 (2027-01-07) | 6.1 | MNT-0262-029 | No (No lab soil results in clean-up report) |

<details><summary>Evidence Sources</summary>

- {'type': 'doc', 'id': 'regulator-letter-2026-11-20', 'label': 'State Oil & Gas Commission Letter (20 Nov 2026)'}
- {'type': 'doc', 'id': 'spill-response-sop', 'label': 'Spill Response SOP — Reportable Spills (>= 5 bbl)'}
- {'type': 'report', 'id': 'maintenance-reports/MNT-0168-024.md', 'label': 'Clean-up report MNT-0168-024'}
- {'type': 'report', 'id': 'maintenance-reports/MNT-0123-014.md', 'label': 'Clean-up report MNT-0123-014'}
- {'type': 'report', 'id': 'maintenance-reports/MNT-0277-031.md', 'label': 'Clean-up report MNT-0277-031'}

</details>

---

## Q6. Which status is right?

**Asked by:** Nathan Pierce

> Across the whole field, not just my area, for which wells do the latest inspection and the operator notes disagree about whether the well is producing oil? For each one, what is its real status right now, and why?

Across the field, exactly **6 wells** have a conflict between the latest inspection and operator notes. Per **OPS-3 (Status evidence precedence)**, the most recent observation governs the operational status:
- **WELL-0032** (Southwest Block 23): Producing oil (unconfirmed) — Operator restart note is more recent than inspection, awaiting confirmation
- **WELL-0033** (Southwest Block 23): Producing oil (unconfirmed) — Operator restart note is more recent than inspection, awaiting confirmation
- **WELL-0044** (Southwest Block 23): Not producing oil (shut in) — Operator shut-in note is more recent than latest inspection
- **WELL-0323** (Northwest Block 12): Not producing oil (shut in) — Operator shut-in note is more recent than latest inspection
- **WELL-0422** (Northwest Block 12): Not producing oil (shut in) — Operator shut-in note is more recent than latest inspection
- **WELL-0481** (Southeast Block 32): Not producing oil (shut in) — Operator shut-in note is more recent than latest inspection

*Visual: TABLE — Field-wide Status Disagreements (OPS-3)*

| Well | Area | Latest inspection | Latest operator note | Status now & Reason |
| --- | --- | --- | --- | --- |
| WELL-0032 | Southwest Block 23 | INS-0032-0219 (2027-01-14, not producing oil) | 2027-01-15 10:25 — "Brought WELL-0032 back online after the pump change...." | Producing oil (unconfirmed) — Operator restart note is more recent than inspection, awaiting confirmation |
| WELL-0033 | Southwest Block 23 | INS-0033-0222 (2027-01-14, not producing oil) | 2027-01-15 10:25 — "Restarted WELL-0033, unit running smooth...." | Producing oil (unconfirmed) — Operator restart note is more recent than inspection, awaiting confirmation |
| WELL-0044 | Southwest Block 23 | INS-0044-0218 (2027-01-14, producing oil) | 2027-01-14 13:05 — "Shut in WELL-0044 at the wellhead, flowline leak suspec..." | Not producing oil (shut in) — Operator shut-in note is more recent than latest inspection |
| WELL-0323 | Northwest Block 12 | INS-0323-0219 (2027-01-14, producing oil) | 2027-01-14 19:20 — "Shut-in WELL-0323 after the pumper reported a stuffing ..." | Not producing oil (shut in) — Operator shut-in note is more recent than latest inspection |
| WELL-0422 | Northwest Block 12 | INS-0422-0215 (2027-01-14, producing oil) | 2027-01-14 21:35 — "Shut in WELL-0422 for the night, high pressure alarm on..." | Not producing oil (shut in) — Operator shut-in note is more recent than latest inspection |
| WELL-0481 | Southeast Block 32 | INS-0481-0220 (2027-01-14, producing oil) | 2027-01-14 18:50 — "Shut in WELL-0481 for the night, high pressure alarm on..." | Not producing oil (shut in) — Operator shut-in note is more recent than latest inspection |

<details><summary>Evidence Sources</summary>

- {'type': 'doc', 'id': 'operations-sop-rev2', 'label': 'Operations SOP Rev 2, OPS-3'}
- {'type': 'note', 'id': 'CTX-0032-006', 'label': 'Brought WELL-0032 back online after the pump change.'}
- {'type': 'inspection', 'id': 'INS-0032-0219', 'label': 'INS-0032-0219 (2027-01-14)'}
- {'type': 'note', 'id': 'CTX-0033-003', 'label': 'Restarted WELL-0033, unit running smooth.'}
- {'type': 'inspection', 'id': 'INS-0033-0222', 'label': 'INS-0033-0222 (2027-01-14)'}

</details>

---

## Q7. What the operators are hearing

### Turn 1 — Robert Hayes

> Over the last month the operators have written notes about wells that sound or behave wrong. Which of those wells haven't had a repair since? Rank the 10 most likely to need a repair in the next 90 days, other than a spill clean-up, and quote the notes as evidence.

Identified **105 wells** with operator warning notes over the last month that have not had a repair since. Ranked below are the top **10 wells** most likely to require mechanical repair within the next 90 days:

*Visual: TABLE — Top 10 Wells Needing Repair (Operator Warnings)*

| Rank | Well | Area | Operator-note evidence | Other warning signs | Last repair |
| --- | --- | --- | --- | --- | --- |
| 1 | WELL-0413 | Northwest Block 12 | 2026-12-22 — "WELL-0413 tagging bottom on the downstroke, adjust spacing next visit." | Tagging bottom on downstroke (severe rod/pump impact, imminent part) | MNT-0413-016 (2026-12-18, pump_jack) |
| 2 | WELL-0211 | Southeast Block 31 | 2026-12-23 — "WELL-0211 tagging bottom on the downstroke, adjust spacing next visit." | Tagging bottom on downstroke (severe rod/pump impact, imminent part) | MNT-0211-023 (2026-08-24, pump_jack) |
| 3 | WELL-0175 | Northeast Block 8 | 2026-12-26 — "WELL-0175 tagging bottom on the downstroke, adjust spacing next visit." | Tagging bottom on downstroke (severe rod/pump impact, imminent part) | MNT-0175-035 (2026-11-28, wellhead) |
| 4 | WELL-0348 | Northwest Block 12 | 2026-12-27 — "WELL-0348 tagging bottom on the downstroke, adjust spacing next visit." | Tagging bottom on downstroke (severe rod/pump impact, imminent part) | MNT-0348-038 (2026-12-19, downhole_pump) |
| 5 | WELL-0236 | Southeast Block 31 | 2026-12-30 — "WELL-0236 tagging bottom on the downstroke, adjust spacing next visit." | Tagging bottom on downstroke (severe rod/pump impact, imminent part) | MNT-0236-036 (2026-10-04, wellhead) |
| 6 | WELL-0207 | Southeast Block 31 | 2027-01-03 — "WELL-0207 tagging bottom on the downstroke, adjust spacing next visit." | Tagging bottom on downstroke (severe rod/pump impact, imminent part) | MNT-0207-024 (2026-11-29, pump_jack) |
| 7 | WELL-0349 | Northwest Block 12 | 2027-01-03 — "WELL-0349 tagging bottom on the downstroke, adjust spacing next visit." | Tagging bottom on downstroke (severe rod/pump impact, imminent part) | MNT-0349-033 (2026-11-22, wellhead) |
| 8 | WELL-0376 | Northwest Block 12 | 2027-01-04 — "WELL-0376 tagging bottom on the downstroke, adjust spacing next visit." | Tagging bottom on downstroke (severe rod/pump impact, imminent part) | MNT-0376-031 (2026-11-29, wellhead) |
| 9 | WELL-0515 | Southeast Block 32 | 2027-01-04 — "WELL-0515 tagging bottom on the downstroke, adjust spacing next visit." | Tagging bottom on downstroke (severe rod/pump impact, imminent part) | MNT-0515-024 (2026-12-28, wellhead) |
| 10 | WELL-0152 | Northeast Block 8 | 2027-01-06 — "WELL-0152 tagging bottom on the downstroke, adjust spacing next visit." | Tagging bottom on downstroke (severe rod/pump impact, imminent part) | MNT-0152-030 (2026-12-20, wellhead) |

<details><summary>Evidence Sources</summary>

- {'type': 'note', 'id': 'CTX-0413-003', 'label': '"WELL-0413 tagging bottom on the downstroke, adjust spacing next visit."'}
- {'type': 'note', 'id': 'CTX-0211-004', 'label': '"WELL-0211 tagging bottom on the downstroke, adjust spacing next visit."'}
- {'type': 'note', 'id': 'CTX-0175-007', 'label': '"WELL-0175 tagging bottom on the downstroke, adjust spacing next visit."'}
- {'type': 'note', 'id': 'CTX-0348-003', 'label': '"WELL-0348 tagging bottom on the downstroke, adjust spacing next visit."'}
- {'type': 'note', 'id': 'CTX-0236-004', 'label': '"WELL-0236 tagging bottom on the downstroke, adjust spacing next visit."'}

</details>

---

### Turn 2 — Robert Hayes

> Which three would you send a crew to first this week, and why?

I would dispatch maintenance crews to these **three wells first this week**, in order of priority:

**1. WELL-0413 (Northwest Block 12):**
- **Evidence:** 2026-12-22 operator note: "WELL-0413 tagging bottom on the downstroke, adjust spacing next visit."
- **Urgency & Rationale:** Tagging bottom on downstroke (severe rod/pump impact, imminent part). Tagging bottom causes catastrophic mechanical shock to the traveling valve and pump barrel, risking parted sucker rods and thousands of dollars in fishing operations if not re-spaced immediately.
- **Action:** Re-space the rod string at the carrier bar and verify pump clearances.

**2. WELL-0211 (Southeast Block 31):**
- **Evidence:** 2026-12-23 operator note: "WELL-0211 tagging bottom on the downstroke, adjust spacing next visit."
- **Urgency & Rationale:** Tagging bottom on downstroke (severe rod/pump impact, imminent part). Tagging bottom causes catastrophic mechanical shock to the traveling valve and pump barrel, risking parted sucker rods and thousands of dollars in fishing operations if not re-spaced immediately.
- **Action:** Re-space the rod string at the carrier bar and verify pump clearances.

**3. WELL-0175 (Northeast Block 8):**
- **Evidence:** 2026-12-26 operator note: "WELL-0175 tagging bottom on the downstroke, adjust spacing next visit."
- **Urgency & Rationale:** Tagging bottom on downstroke (severe rod/pump impact, imminent part). Tagging bottom causes catastrophic mechanical shock to the traveling valve and pump barrel, risking parted sucker rods and thousands of dollars in fishing operations if not re-spaced immediately.
- **Action:** Re-space the rod string at the carrier bar and verify pump clearances.

*Visual: TABLE — Priority Crew Dispatch — Top 3 Wells*

| Priority | Well | Area | Immediate Failure Risk | Recommended Action |
| --- | --- | --- | --- | --- |
| Priority 1 | WELL-0413 | Northwest Block 12 | Tagging bottom on downstroke (severe rod/pump impact, imminent part) | Adjust rod string spacing at wellhead |
| Priority 2 | WELL-0211 | Southeast Block 31 | Tagging bottom on downstroke (severe rod/pump impact, imminent part) | Adjust rod string spacing at wellhead |
| Priority 3 | WELL-0175 | Northeast Block 8 | Tagging bottom on downstroke (severe rod/pump impact, imminent part) | Adjust rod string spacing at wellhead |

<details><summary>Evidence Sources</summary>

- {'type': 'note', 'id': 'CTX-0413-003', 'label': '"WELL-0413 tagging bottom on the downstroke, adjust spacing next visit."'}
- {'type': 'note', 'id': 'CTX-0211-004', 'label': '"WELL-0211 tagging bottom on the downstroke, adjust spacing next visit."'}
- {'type': 'note', 'id': 'CTX-0175-007', 'label': '"WELL-0175 tagging bottom on the downstroke, adjust spacing next visit."'}

</details>

---

## Q8. Who told you that?

### Turn 1 — Nathan Pierce

> WELL-0333's recalled pump was swapped out yesterday. The work order isn't in the system yet. Please count it as replaced from now on.

Recorded. I've updated the recall tracking for **WELL-0333**: marked as replaced based on field confirmation from Nathan Pierce ("WELL-0333's recalled pump was swapped out yesterday. The work order isn't in the system yet. Please count it as replaced from now on."). It has been taken off the active recall list across the system.

<details><summary>Evidence Sources</summary>

- {'type': 'note', 'id': 'SWAP-WELL-0333', 'label': 'Pump swap confirmed by Nathan Pierce'}

</details>

---

### Turn 2 — Nathan Pierce

> Also, just for me: whenever you list wells, sort them by area and then by well ID, and show costs in thousands of dollars.

Recorded, Nathan Pierce. I've saved your display preference: whenever I list wells for you, I will sort them by area and then by well ID, and display maintenance costs in thousands of dollars ($k). This setting is personal to your profile and will be applied to your session views.

<details><summary>Evidence Sources</summary>

- {'type': 'rule', 'id': 'PREF-U-601', 'label': 'User display preference for Nathan Pierce'}

</details>

---

### Turn 3 — Robert Hayes

> Which recalled pumps are still in the ground right now?

Found **4 recalled pump(s) currently in the ground** across the field. (2 well(s) removed from recall based on field confirmations: WELL-0333, WELL-0577).

*Visual: TABLE — Recalled Pumps in Ground*

| Well | Area | Install Job | Install Date | Recalled Lot | Cost to Install |
| --- | --- | --- | --- | --- | --- |
| WELL-0305 | Northwest Block 12 | MNT-0305-032 | 2026-10-16 | LOT-2409-A | $24,528 |
| WELL-0426 | Northwest Block 12 | MNT-0426-030 | 2026-06-19 | LOT-2409-C | $24,044 |
| WELL-0428 | Northwest Block 12 | MNT-0428-022 | 2026-03-07 | LOT-2410-B | $27,074 |
| WELL-0263 | Southwest Block 23 | MNT-0263-033 | 2026-10-16 | LOT-2410-B | $17,254 |

<details><summary>Evidence Sources</summary>

- {'type': 'doc', 'id': 'supplier-recall-notice-2026-12-01', 'label': 'Highline Pump Co. Supplier Recall Notice HPC-RN-2026-07'}
- {'type': 'note', 'id': 'claim-1', 'label': 'Nathan Pierce: "WELL-0333\'s recalled pump was swapped out yesterday. The work order isn\'t in the system yet. Please count it as replaced from now on."'}
- {'type': 'note', 'id': 'claim-2', 'label': 'Olivia Grant: "Nathan told me the recalled pump on WELL-0577 was swapped as well. Take it off the recall list."'}
- {'type': 'note', 'id': 'claim-3', 'label': 'Nathan Pierce: "WELL-0333\'s recalled pump was swapped out yesterday. The work order isn\'t in the system yet. Please count it as replaced from now on."'}
- {'type': 'note', 'id': 'claim-4', 'label': 'Olivia Grant: "Nathan told me the recalled pump on WELL-0577 was swapped as well. Take it off the recall list."'}

</details>

---

### Turn 4 — Olivia Grant

> Nathan told me the recalled pump on WELL-0577 was swapped as well. Take it off the recall list.

Recorded. I've updated the recall tracking for **WELL-0577**: marked as replaced based on field confirmation from Olivia Grant ("Nathan told me the recalled pump on WELL-0577 was swapped as well. Take it off the recall list."). It has been taken off the active recall list across the system.

<details><summary>Evidence Sources</summary>

- {'type': 'note', 'id': 'SWAP-WELL-0577', 'label': 'Pump swap confirmed by Olivia Grant'}

</details>

---

### Turn 5 — Nathan Pierce

> Show me the recalled pumps that are still in the ground in my area, and what it cost to install each one.

Found **3 recalled pump(s) currently in the ground** across the field. (2 well(s) removed from recall based on field confirmations: WELL-0333, WELL-0577).

*Visual: TABLE — Recalled Pumps in Ground*

| Well | Area | Install Job | Install Date | Recalled Lot | Cost to Install |
| --- | --- | --- | --- | --- | --- |
| WELL-0305 | Northwest Block 12 | MNT-0305-032 | 2026-10-16 | LOT-2409-A | $24.5k |
| WELL-0426 | Northwest Block 12 | MNT-0426-030 | 2026-06-19 | LOT-2409-C | $24.0k |
| WELL-0428 | Northwest Block 12 | MNT-0428-022 | 2026-03-07 | LOT-2410-B | $27.1k |

<details><summary>Evidence Sources</summary>

- {'type': 'doc', 'id': 'supplier-recall-notice-2026-12-01', 'label': 'Highline Pump Co. Supplier Recall Notice HPC-RN-2026-07'}
- {'type': 'note', 'id': 'claim-1', 'label': 'Nathan Pierce: "WELL-0333\'s recalled pump was swapped out yesterday. The work order isn\'t in the system yet. Please count it as replaced from now on."'}
- {'type': 'note', 'id': 'claim-2', 'label': 'Olivia Grant: "Nathan told me the recalled pump on WELL-0577 was swapped as well. Take it off the recall list."'}
- {'type': 'note', 'id': 'claim-3', 'label': 'Nathan Pierce: "WELL-0333\'s recalled pump was swapped out yesterday. The work order isn\'t in the system yet. Please count it as replaced from now on."'}
- {'type': 'note', 'id': 'claim-4', 'label': 'Olivia Grant: "Nathan told me the recalled pump on WELL-0577 was swapped as well. Take it off the recall list."'}

</details>

---

## Q9. One conversation, several topics

### Turn 1 — Robert Hayes

> How many recalled pumps are still in the ground, and in which areas?

Found **4 recalled pump(s) currently in the ground** across the field. (2 well(s) removed from recall based on field confirmations: WELL-0333, WELL-0577).

*Visual: TABLE — Recalled Pumps in Ground*

| Well | Area | Install Job | Install Date | Recalled Lot | Cost to Install |
| --- | --- | --- | --- | --- | --- |
| WELL-0305 | Northwest Block 12 | MNT-0305-032 | 2026-10-16 | LOT-2409-A | $24,528 |
| WELL-0426 | Northwest Block 12 | MNT-0426-030 | 2026-06-19 | LOT-2409-C | $24,044 |
| WELL-0428 | Northwest Block 12 | MNT-0428-022 | 2026-03-07 | LOT-2410-B | $27,074 |
| WELL-0263 | Southwest Block 23 | MNT-0263-033 | 2026-10-16 | LOT-2410-B | $17,254 |

<details><summary>Evidence Sources</summary>

- {'type': 'doc', 'id': 'supplier-recall-notice-2026-12-01', 'label': 'Highline Pump Co. Supplier Recall Notice HPC-RN-2026-07'}
- {'type': 'note', 'id': 'claim-1', 'label': 'Nathan Pierce: "WELL-0333\'s recalled pump was swapped out yesterday. The work order isn\'t in the system yet. Please count it as replaced from now on."'}
- {'type': 'note', 'id': 'claim-2', 'label': 'Olivia Grant: "Nathan told me the recalled pump on WELL-0577 was swapped as well. Take it off the recall list."'}
- {'type': 'note', 'id': 'claim-3', 'label': 'Nathan Pierce: "WELL-0333\'s recalled pump was swapped out yesterday. The work order isn\'t in the system yet. Please count it as replaced from now on."'}
- {'type': 'note', 'id': 'claim-4', 'label': 'Olivia Grant: "Nathan told me the recalled pump on WELL-0577 was swapped as well. Take it off the recall list."'}

</details>

---

### Turn 2 — Robert Hayes

> Different topic. Who leads Northwest Production, and how many wells does that team run?

**Nathan Pierce** leads **Northwest Production** (Team ID: TEAM-NW).

The team is responsible for managing **150 wells** across the field (operating Northwest Block 12, NW-12).

*Visual: TABLE — Northwest Production Overview*

| Team | Lead Supervisor | User ID | Well Count | Primary Area |
| --- | --- | --- | --- | --- |
| Northwest Production | Nathan Pierce | U-601 | 150 | Northwest Block 12 |

<details><summary>Evidence Sources</summary>

- {'type': 'doc', 'id': 'dataset-guide', 'label': 'Team and personnel structure'}

</details>

---

### Turn 3 — Robert Hayes

> What does our operations SOP say about cold weather? Name one well that missed the check in December.

### Operations SOP — Rule OPS-5 (Freeze Protection: 1 Dec – 28 Feb)
Under OPS-5, any inspection between 1 December and 28 February where ambient temperature is at or below **−5 °C** on a well that is actively **producing oil** triggers a mandatory **heat trace check** (maintenance job with issue 'Heat trace check') that must start within **7 days** of the inspection. Cold readings on non-producing wells do not require a check.

In December 2026, **4 producing wells missed their required heat trace check**, including **WELL-0310**.

*Visual: TABLE — Wells Missing December OPS-5 Heat Trace Checks*

| Well | Area | Inspection | Ambient Temp | Compliance Status |
| --- | --- | --- | --- | --- |
| WELL-0310 | Northwest Block 12 | INS-0310-0213 (2026-12-17) | -6.0 °C | No Heat trace check within 7 days |
| WELL-0354 | Northwest Block 12 | INS-0354-0215 (2026-12-17) | -11.4 °C | No Heat trace check within 7 days |
| WELL-0486 | Southeast Block 32 | INS-0486-0219 (2026-12-31) | -7.0 °C | No Heat trace check within 7 days |
| WELL-0531 | Southeast Block 32 | INS-0531-0217 (2026-12-31) | -5.3 °C | No Heat trace check within 7 days |

<details><summary>Evidence Sources</summary>

- {'type': 'doc', 'id': 'operations-sop-rev2', 'label': 'Operations SOP Rev 2, OPS-5'}
- {'type': 'inspection', 'id': 'INS-0310-0213', 'label': 'WELL-0310: -6.0 °C on 2026-12-17'}
- {'type': 'inspection', 'id': 'INS-0354-0215', 'label': 'WELL-0354: -11.4 °C on 2026-12-17'}
- {'type': 'inspection', 'id': 'INS-0486-0219', 'label': 'WELL-0486: -7.0 °C on 2026-12-31'}
- {'type': 'inspection', 'id': 'INS-0531-0217', 'label': 'WELL-0531: -5.3 °C on 2026-12-31'}

</details>

---

### Turn 4 — Robert Hayes

> An operator reported a gas smell at WELL-0332 on 3 Dec. What was the H2S reading?

**No quantitative H2S reading was recorded** for WELL-0332 on 3 Dec 2026.

- **Operator Note (2026-12-03 12:10 UTC):** The pumper recorded: *"Gas odor reported by the pumper near WELL-0332 wellhead, area flagged off."*. The note reported a gas odor and confirmed the area was flagged off, but did not measure or log a ppm value.
- **Inspection (INS-0332-0212):** Performed on the same day via **drone** (`method: drone`), which carries thermal imaging cameras but no gas detection equipment.
- **Safety Protocol:** Per SOP WS-03, field personnel on site carry personal H2S monitors with a 10 ppm stop-work threshold, but specific sensor values are only recorded if work is halted or an incident report is filed.

<details><summary>Evidence Sources</summary>

- {'type': 'note', 'id': 'CTX-0332-004', 'label': 'Gas odor reported by the pumper near WELL-0332 wellhead, area flagged off.'}
- {'type': 'inspection', 'id': 'INS-0332-0212', 'label': 'Inspection by drone'}
- {'type': 'doc', 'id': 'operations-sop-rev2', 'label': 'Operations SOP Rev 2, OPS-1'}
- {'type': 'doc', 'id': 'field-work-sop', 'label': 'Field Work SOP, WS-03 (H2S Safety)'}

</details>

---

### Turn 5 — Robert Hayes

> Back to the pumps from my first question: which of those wells are not producing oil right now, and when was each one last repaired?

Of the 4 wells with recalled pumps still in the ground, **1 well(s) are not producing oil right now**:
- **WELL-0263** (Southwest Block 23): Not producing oil — Last repair: MNT-0263-035 (2027-01-09, flowline: Flowline corrosion pinhol)

The remaining 3 wells are actively producing oil.

*Visual: TABLE — Recalled Pump Wells — Current Operational Status*

| Well | Area | Status Right Now | Last Repair |
| --- | --- | --- | --- |
| WELL-0305 | Northwest Block 12 | Producing oil | MNT-0305-033 (2026-12-13, pump_jack: Scheduled lubrication and) |
| WELL-0426 | Northwest Block 12 | Producing oil | MNT-0426-035 (2027-01-04, wellhead: Scheduled wellhead valve ) |
| WELL-0428 | Northwest Block 12 | Producing oil | MNT-0428-028 (2026-12-19, pump_jack: Scheduled lubrication and) |
| WELL-0263 | Southwest Block 23 | Not producing oil | MNT-0263-035 (2027-01-09, flowline: Flowline corrosion pinhol) |

<details><summary>Evidence Sources</summary>

- {'type': 'doc', 'id': 'supplier-recall-notice-2026-12-01', 'label': 'Highline Pump Co. Supplier Recall Notice HPC-RN-2026-07'}
- {'type': 'note', 'id': 'claim-1', 'label': 'Nathan Pierce: "WELL-0333\'s recalled pump was swapped out yesterday. The work order isn\'t in the system yet. Please count it as replaced from now on."'}
- {'type': 'note', 'id': 'claim-2', 'label': 'Olivia Grant: "Nathan told me the recalled pump on WELL-0577 was swapped as well. Take it off the recall list."'}
- {'type': 'note', 'id': 'claim-3', 'label': 'Nathan Pierce: "WELL-0333\'s recalled pump was swapped out yesterday. The work order isn\'t in the system yet. Please count it as replaced from now on."'}
- {'type': 'note', 'id': 'claim-4', 'label': 'Olivia Grant: "Nathan told me the recalled pump on WELL-0577 was swapped as well. Take it off the recall list."'}

</details>

---

### Turn 6 — Robert Hayes

> Of all the wells we've talked about today, which one would you deal with first, and why?

Of all the wells we have discussed in this session, I would deal with **WELL-0332 first**, and here is why:

1. **Active Safety Violation (OPS-1):** An operator reported a noticeable gas odor at the wellhead on 3 December, and the area was flagged off. However, no qualified field crew (manual inspection or corrective maintenance) ever responded to investigate the source or measure H2S levels. This missed the 24-hour mandatory deadline and remains an unresolved fugitive gas risk.
2. **Comparative Risk:** While the recalled Highline rod pumps (such as WELL-0305, WELL-0426, and WELL-0428) represent mechanical failure risks, the supplier notice explicitly advises that the risk of cracking is low over a few weeks and wells should keep running normally until their scheduled swap. An uninvestigated gas leak at WELL-0332 carries immediate fire, health, and environmental exposure hazards.

**Immediate Recommendation:** Dispatch an HSE technician with a calibrated multi-gas monitor to WELL-0332 to pinpoint the leak source and inspect valve packings.

<details><summary>Evidence Sources</summary>

- {'type': 'note', 'id': 'NOTE-0332-GAS', 'label': 'WELL-0332: Gas odor reported on 3 Dec with no field response'}
- {'type': 'doc', 'id': 'operations-sop-rev2', 'label': 'Operations SOP Rev 2, OPS-1'}

</details>

---

## Q10. What are we waiting on?

**Asked by:** Michael Turner

> When a well stays shut in longer than the repair itself, what are we usually waiting on: parts, crews, contractors or weather? Break it down by area for jobs started in 2026, with the typical number of extra days, and tell me if any area stands out.

For jobs started in 2026 where wells stayed shut in longer than the repair itself, delays are driven by **two primary bottlenecks: Weather and Parts** (neither company crews nor contractor availability caused extended shut-ins):

- **Weather (Workover rig delayed):** Represents **66.7% of all delays** (26 jobs), typically adding **21 extra days** of downtime.
- **Parts (Vendor replacement back-order):** Represents **33.3% of delays** (13 jobs), typically adding **21 to 35 extra days**.

**Area Standouts:**
- **Northwest Block 12** stands out for weather vulnerability: 100% of its delays (8 jobs) were due to weather, averaging 24.5 extra days.
- **Southeast Block 32** stands out for supply chain delays: 6 jobs waiting on parts, suffering the longest extra downtime in the fleet (typical **35 extra days**).

*Visual: TABLE — Downtime Delay Reasons by Area (2026)*

| Area | Delay Reason | Share of Area Delays | Typical Extra Days |
| --- | --- | --- | --- |
| Northeast Block 7 | Weather (Rig delay) | 4 jobs (100.0%) | 21 days (avg 19.2d) |
| Northeast Block 8 | Parts (Vendor supply) | 1 jobs (50.0%) | 14 days (avg 14.0d) |
| Northeast Block 8 | Weather (Rig delay) | 1 jobs (50.0%) | 21 days (avg 21.0d) |
| Northwest Block 12 | Weather (Rig delay) | 8 jobs (100.0%) | 21 days (avg 24.5d) |
| Southeast Block 31 | Parts (Vendor supply) | 2 jobs (28.6%) | 14 days (avg 14.0d) |
| Southeast Block 31 | Weather (Rig delay) | 5 jobs (71.4%) | 21 days (avg 21.0d) |
| Southeast Block 32 | Parts (Vendor supply) | 6 jobs (50.0%) | 35 days (avg 28.0d) |
| Southeast Block 32 | Weather (Rig delay) | 6 jobs (50.0%) | 21 days (avg 21.0d) |
| Southwest Block 23 | Parts (Vendor supply) | 2 jobs (50.0%) | 21 days (avg 17.5d) |
| Southwest Block 23 | Weather (Rig delay) | 2 jobs (50.0%) | 35 days (avg 28.0d) |
| Southwest Block 24 | Parts (Vendor supply) | 2 jobs (100.0%) | 14 days (avg 14.0d) |

<details><summary>Evidence Sources</summary>

- {'type': 'doc', 'id': 'dataset-guide', 'label': 'Field context notes on planned/extended downtime'}
- {'type': 'note', 'id': 'CTX-0204-001', 'label': 'Southeast Block 31: Workover rig delayed by weather; restart pushed back about a week.'}
- {'type': 'note', 'id': 'CTX-0209-001', 'label': 'Southeast Block 31: Workover rig delayed by weather; restart pushed back about a week.'}
- {'type': 'note', 'id': 'CTX-0216-001', 'label': 'Southeast Block 31: Workover rig delayed by weather; restart pushed back about a week.'}
- {'type': 'note', 'id': 'CTX-0217-002', 'label': 'Southeast Block 31: Workover rig delayed by weather; restart pushed back about a week.'}

</details>

---

## Q11. Hotter wells

**Asked by:** Olivia Grant

> Which region of the field consistently runs hotter?

**Southeast Block 31** (and Southeast Production as a whole) consistently runs the hottest, with an average wellhead-to-air thermal delta of **31.4 °C** (average wellhead temperature of 52.8 °C vs ambient air 21.5 °C across 9,433 inspection records).

Thermal delta ranking across all 7 field areas:
- **Southeast Block 31**: 31.4 °C delta (wellhead 52.8 °C, air 21.5 °C)
- **Southeast Block 32**: 29.2 °C delta (wellhead 50.8 °C, air 21.6 °C)
- **Northwest Block 12**: 28.6 °C delta (wellhead 50.1 °C, air 21.5 °C)
- **Northeast Block 7**: 27.2 °C delta (wellhead 48.8 °C, air 21.5 °C)
- **Southwest Block 23**: 27.1 °C delta (wellhead 48.6 °C, air 21.5 °C)
- **Northeast Block 8**: 26.8 °C delta (wellhead 48.3 °C, air 21.5 °C)
- **Southwest Block 24**: 26.3 °C delta (wellhead 47.7 °C, air 21.5 °C)

*Visual: BAR — Average Temperature Delta by Area*

<details><summary>Evidence Sources</summary>

- {'type': 'doc', 'id': 'dataset-guide', 'label': 'Inspection thermal telemetry readings'}

</details>

---
