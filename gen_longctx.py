#!/usr/bin/env python3
"""Generate ~45k-token synthetic ops log with planted facts + 6 cross-reference questions."""
import json, random

random.seed(77)
TEAMS = ["Atlas", "Borealis", "Cinder", "Dune", "Ember"]
PEOPLE = ["Mira Voss", "Kenji Park", "Lena Ortiz", "Tomas Reyes", "Ada Lindqvist", "Omar Haddad",
          "Priya Nair", "Jonas Weber", "Sofia Marino", "Derek Chu"]
SERVERS = ["srv-apollo", "srv-hydra", "srv-nimbus", "srv-quartz", "srv-vulcan"]
VERBS = ["patched", "rebooted", "monitored", "scanned", "audited", "resized", "migrated workloads on",
         "rotated certificates for", "updated firmware on", "ran diagnostics on"]

lines = []
# fillers use ONLY these people with FIXED teams, so planted facts are never contradicted
FILLER_PEOPLE = [p for p in PEOPLE if p not in ("Ada Lindqvist", "Tomas Reyes")]
TEAM_OF = {p: TEAMS[i % len(TEAMS)] for i, p in enumerate(FILLER_PEOPLE)}

def filler(day, i):
    p = random.choice(FILLER_PEOPLE); s = random.choice(SERVERS); v = random.choice(VERBS)
    dur = random.randint(4, 190); tick = random.randint(1000, 9999)
    return f"[2026-03-{day:02d} {random.randint(6,22):02d}:{random.randint(0,59):02d}] ticket#{tick} {p} ({TEAM_OF[p]} team) {v} {s}; duration {dur}m; status OK."

# ---- planted facts (unique tokens so grep can't be fooled, but answers need linking) ----
# F1 (early): budget figure A. F2 (very late): budget figure B. Q: sum.
BUDGET_A = 48250
BUDGET_B = 17390
# F3: person who rotated the master signing key + F4 (far away): that person's team -> Q: which TEAM rotated
KEY_PERSON = "Ada Lindqvist"
KEY_TEAM = "Cinder"
# F5/F6: srv-quartz incidents on exactly two days -> Q: how many + which days
INC_DAYS = [7, 23]
# F7: version deployed the same day Tomas Reyes transferred -> Q: version string
TRANSFER_DAY = 15
VERSION = "v4.7.2"
# F8: unique passphrase-like codename mentioned once mid-doc -> Q: recall
CODENAME = "IndigoFalcon"

random.shuffle(PEOPLE)
day = 1
entry = 0
TOTAL = 2600   # ~45k tokens
for i in range(TOTAL):
    if i == 60:
        lines.append(f"[2026-03-02 09:14] FINANCE: Q1 infrastructure budget for the Atlas team approved at ${BUDGET_A}.")
    elif i == 300:
        lines.append(f"[2026-03-05 11:02] SECURITY: master signing key rotation completed by {KEY_PERSON}.")
    elif i == 700:
        lines.append(f"[2026-03-{INC_DAYS[0]:02d} 03:41] INCIDENT: {SERVERS[3]} kernel panic, failover engaged, root cause memory bitflip.")
    elif i == 1200:
        lines.append(f"[2026-03-12 14:55] NOTE: project codename for the migration initiative is {CODENAME}. Do not reuse.")
    elif i == 1500:
        lines.append(f"[2026-03-{TRANSFER_DAY:02d} 10:12] HR: Tomas Reyes transferred from Dune team to Borealis team effective today.")
    elif i == 1502:
        lines.append(f"[2026-03-{TRANSFER_DAY:02d} 16:40] RELEASE: platform {VERSION} deployed to production cluster.")
    elif i == 1900:
        lines.append(f"[2026-03-19 08:30] STAFF: {KEY_PERSON} moved desk; she remains on the {KEY_TEAM} team roster this quarter.")
    elif i == 2100:
        lines.append(f"[2026-03-{INC_DAYS[1]:02d} 22:19] INCIDENT: {SERVERS[3]} disk array degraded, hot spare rebuilt overnight.")
    elif i == 2520:
        lines.append(f"[2026-03-28 17:45] FINANCE: supplemental hardware budget approved: ${BUDGET_B} for GPU expansion.")
    else:
        day = min(28, 1 + i * 28 // TOTAL)
        lines.append(filler(day, i))
    entry += 1

doc = "\n".join(lines)
open("longctx_doc.txt", "w").write(doc)

QUESTIONS = [
    {"id": "lc1", "q": "What is the SUM in dollars of the Q1 Atlas infrastructure budget and the supplemental GPU hardware budget? Answer format: {\"answer\": <int>}", "answer": BUDGET_A + BUDGET_B, "tol": 0},
    {"id": "lc2", "q": "Which TEAM does the person who completed the master signing key rotation belong to? Answer format: {\"answer\": \"<team name>\"}", "answer": KEY_TEAM, "tol": None},
    {"id": "lc3", "q": "How many INCIDENT entries does srv-quartz have in this log? Answer format: {\"answer\": <int>}", "answer": len(INC_DAYS), "tol": 0},
    {"id": "lc4", "q": "What platform version was deployed to production on the same day Tomas Reyes transferred teams? Answer format: {\"answer\": \"<version>\"}", "answer": VERSION, "tol": None},
    {"id": "lc5", "q": "What is the project codename for the migration initiative? Answer format: {\"answer\": \"<codename>\"}", "answer": CODENAME, "tol": None},
    {"id": "lc6", "q": "On which two March dates (day numbers) did srv-quartz have incidents? Answer format: {\"answer\": [<day>, <day>]} sorted ascending", "answer": INC_DAYS, "tol": None},
]
json.dump(QUESTIONS, open("longctx_suite.json", "w"), indent=2)
approx_tokens = len(doc.split()) * 1.4
print(f"doc: {len(doc)} chars, ~{int(approx_tokens)} tokens, {len(lines)} lines")
for q in QUESTIONS:
    print(q["id"], "=", q["answer"])
