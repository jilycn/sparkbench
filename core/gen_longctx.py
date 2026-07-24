#!/usr/bin/env python3
"""Seeded long-context variants with genuine authority arbitration."""

from __future__ import annotations

import argparse
import json
import random
import urllib.error
import urllib.request
from pathlib import Path

from sblib import write_json_atomic, write_text_atomic


PEOPLE = ["Mira Voss", "Kenji Park", "Lena Ortiz", "Tomas Reyes", "Ada Lindqvist", "Omar Haddad", "Priya Nair", "Jonas Weber"]
TEAMS = ["Atlas", "Borealis", "Cinder", "Dune", "Ember"]
SERVERS = ["srv-apollo", "srv-hydra", "srv-nimbus", "srv-quartz", "srv-vulcan"]
VERBS = ["patched", "rebooted", "monitored", "audited", "resized", "rotated certificates for"]


def _approx_tokens(text):
    return max(1, round(len(text.split()) * 1.4))


def tokenize_or_approx(base_url, text):
    body = json.dumps({"text": text}).encode()
    request = urllib.request.Request(base_url.rstrip("/") + "/tokenize", data=body,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read())
        count = payload.get("count", payload.get("token_count", len(payload.get("tokens", []))))
        if isinstance(count, int) and count >= 0:
            return count, "tokenize"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        pass
    return _approx_tokens(text), "approx"


def resolve_authority(case):
    """Apply the document rule: source rank first, then effective recency."""
    eligible = [record for record in case["records"] if record["signed"]]
    if not eligible:
        raise ValueError(f"authority case has no signed evidence: {case['id']}")
    return max(
        eligible,
        key=lambda record: (
            record["source_rank"],
            record["effective_day"],
            record["record_id"],
        ),
    )


def _other_values(selected, values):
    return [value for value in values if value != selected]


def _authority_cases(rng, authoritative_region, key_person):
    regions = ["us-east", "eu-west", "ap-south"]
    alternatives = _other_values(authoritative_region, regions)
    rng.shuffle(alternatives)
    older_region, later_lower_region = alternatives
    region_case = {
        "id": "migration_region",
        "policy_id": "GP-17",
        "policy": (
            "For migration-region decisions, signed Change Advisory Board resolutions rank "
            "above signed program memoranda, which rank above operations status records. "
            "Unsigned drafts are ineligible. Compare effective dates only within the highest "
            "eligible source class."
        ),
        "records": [
            {"record_id": "CAB-R1", "source_class": "cab_resolution", "source_rank": 3,
             "signed": True, "effective_day": 11, "value": older_region},
            {"record_id": "CAB-R2", "source_class": "cab_resolution", "source_rank": 3,
             "signed": True, "effective_day": 19, "value": authoritative_region},
            {"record_id": "PM-M4", "source_class": "program_memo", "source_rank": 2,
             "signed": True, "effective_day": 24, "value": later_lower_region},
            {"record_id": "CAB-D7", "source_class": "cab_resolution", "source_rank": 3,
             "signed": False, "effective_day": 26, "value": older_region},
        ],
    }
    older_person = rng.choice([person for person in PEOPLE if person != key_person])
    later_lower_person = rng.choice(
        [person for person in PEOPLE if person not in (key_person, older_person)]
    )
    key_case = {
        "id": "key_rotation_person",
        "policy_id": "SEC-9",
        "policy": (
            "For signing-key custody, signed Security Officer attestations rank above automated "
            "audit extracts, which rank above helpdesk notes. Unsigned records are ineligible. "
            "Compare effective dates only within the highest eligible source class."
        ),
        "records": [
            {"record_id": "SO-A1", "source_class": "security_officer", "source_rank": 3,
             "signed": True, "effective_day": 8, "value": older_person},
            {"record_id": "SO-A2", "source_class": "security_officer", "source_rank": 3,
             "signed": True, "effective_day": 17, "value": key_person},
            {"record_id": "AUD-X9", "source_class": "audit_extract", "source_rank": 2,
             "signed": True, "effective_day": 23, "value": later_lower_person},
            {"record_id": "HD-N6", "source_class": "helpdesk_note", "source_rank": 1,
             "signed": True, "effective_day": 25, "value": older_person},
        ],
    }
    return {case["id"]: case for case in (region_case, key_case)}


def _evidence_line(case, record):
    signature = "signed" if record["signed"] else "unsigned"
    subject = (
        f"migration region = {record['value']}"
        if case["id"] == "migration_region"
        else f"master signing-key rotation completed by {record['value']}"
    )
    return (
        f"[EVIDENCE {record['record_id']}] [class={record['source_class']}] "
        f"[{signature}] [effective=2026-03-{record['effective_day']:02d}] {subject}."
    )


def generate_variant(seed=20260712):
    rng = random.Random(seed)
    budget_a, budget_b = rng.randint(42000, 68000), rng.randint(12000, 28000)
    key_person = rng.choice([person for person in PEOPLE if person != "Tomas Reyes"])
    key_team = rng.choice(TEAMS)
    incident_days = sorted(rng.sample(range(4, 27), 2))
    transfer_day, version = rng.randint(8, 20), f"v{rng.randint(4, 8)}.{rng.randint(1, 9)}.{rng.randint(0, 9)}"
    codename = rng.choice(["IndigoFalcon", "CopperOrchid", "VelvetComet", "SilverTern"])
    authoritative_region = rng.choice(["us-east", "eu-west", "ap-south"])
    authority_cases = _authority_cases(rng, authoritative_region, key_person)
    planted_lines = [
        f"[AUTHORITY] FINANCE signed Q1 Atlas infrastructure budget: ${budget_a}.",
        f"[INCIDENT] srv-quartz kernel panic on March {incident_days[0]}; root cause memory bitflip.",
        f"[NOTE] Migration initiative codename: {codename}.",
        f"[HR] Tomas Reyes transferred teams on March {transfer_day}.",
        f"[RELEASE] Platform {version} deployed on March {transfer_day}.",
        f"[ROSTER] {key_person} remains on the {key_team} team.",
        f"[INCIDENT] srv-quartz disk degradation on March {incident_days[1]}; hot spare rebuilt.",
        f"[AUTHORITY] FINANCE signed supplemental GPU budget: ${budget_b}.",
    ]
    for case in authority_cases.values():
        planted_lines.append(f"[POLICY {case['policy_id']}] {case['policy']}")
        planted_lines.extend(_evidence_line(case, record) for record in case["records"])
    positions = sorted(rng.sample(range(80, 2520), len(planted_lines)))
    plants = dict(zip(positions, planted_lines))
    filler_people = [person for person in PEOPLE if person not in (key_person, "Tomas Reyes")]
    team_of = {person: TEAMS[index % len(TEAMS)] for index, person in enumerate(filler_people)}
    lines = [
        "[INDEX] Policies define evidence authority. Record order in this log does not itself "
        "determine which value governs."
    ]
    for index in range(2600):
        if index in plants:
            lines.append(plants[index])
            continue
        person = rng.choice(filler_people)
        server = rng.choice(SERVERS)
        day = 1 + index * 27 // 2600
        lines.append(f"[2026-03-{day:02d}] ticket#{rng.randint(1000,9999)} {person} ({team_of[person]} team) "
                     f"{rng.choice(VERBS)} {server}; duration {rng.randint(4,190)}m; status OK.")
    questions = [
        {"name": "budget_sum", "kind": "retrieval",
         "q": "What is the sum of the two signed budgets?", "answer": budget_a + budget_b},
        {"name": "key_team", "kind": "retrieval",
         "q": f"Which team is {key_person} rostered on?", "answer": key_team},
        {"name": "incident_count", "kind": "retrieval",
         "q": "How many srv-quartz INCIDENT records are present?", "answer": 2},
        {"name": "release_join", "kind": "retrieval",
         "q": "Which platform version was deployed on Tomas Reyes's transfer day?", "answer": version},
        {"name": "codename", "kind": "retrieval",
         "q": "What is the migration initiative codename?", "answer": codename},
        {"name": "incident_days", "kind": "retrieval",
         "q": "Which March day numbers have srv-quartz incidents, sorted ascending?", "answer": incident_days},
        {"name": "conflict_region", "kind": "conflict", "authority_case": "migration_region",
         "q": "Applying policy GP-17, what migration region governs?",
         "answer": resolve_authority(authority_cases["migration_region"])["value"]},
        {"name": "conflict_person", "kind": "conflict", "authority_case": "key_rotation_person",
         "q": "Applying policy SEC-9, who is the authoritative signing-key rotation person?",
         "answer": resolve_authority(authority_cases["key_rotation_person"])["value"]},
        {"name": "compositional_difference", "kind": "compositional",
         "q": "What is the signed Q1 budget minus the signed supplemental GPU budget?",
         "answer": budget_a - budget_b},
        {"name": "compositional_team_days", "kind": "compositional",
         "q": "Give the authoritative key-rotation person's team and the srv-quartz incident days.",
         "answer": {"team": key_team, "days": incident_days}},
    ]
    suite = []
    for index, question in enumerate(questions, 1):
        item = {
            "id": f"lc{index}",
            "kind": question["kind"],
            "q": question["q"] + ' Answer format: {"answer": <value>}.',
            "answer": question["answer"],
            "tol": 0,
            "numeric": isinstance(question["answer"], (int, float)),
        }
        if case_id := question.get("authority_case"):
            case = authority_cases[case_id]
            winner = resolve_authority(case)
            item["authority_case"] = case_id
            item["authority"] = {
                "policy_id": case["policy_id"],
                "winning_record": winner["record_id"],
                "losing_records": [
                    record["record_id"]
                    for record in case["records"]
                    if record["record_id"] != winner["record_id"]
                ],
            }
        suite.append(item)
    rng.shuffle(suite)
    for index, item in enumerate(suite):
        item["cold"] = index == 0
    doc = "\n".join(lines) + "\n"
    return {
        "seed": seed,
        "doc": doc,
        "suite": suite,
        "authority_cases": authority_cases,
        "facts": {
            "budget_a": budget_a,
            "budget_b": budget_b,
            "key_person": key_person,
            "key_team": key_team,
            "incident_days": incident_days,
            "version": version,
            "codename": codename,
            "authoritative_region": authoritative_region,
        },
    }


def validate_variant(variant):
    doc, facts = variant["doc"], variant["facts"]
    required = [str(facts["budget_a"]), str(facts["budget_b"]), facts["key_person"], facts["key_team"],
                facts["version"], facts["codename"], facts["authoritative_region"]]
    conflicts = [item for item in variant["suite"] if item["kind"] == "conflict"]
    authority_valid = all(
        (case := variant["authority_cases"].get(item.get("authority_case")))
        and resolve_authority(case)["value"] == item["answer"]
        and resolve_authority(case)["record_id"] == item["authority"]["winning_record"]
        and all(record["record_id"] in doc for record in case["records"])
        for item in conflicts
    )
    return (
        len(variant["suite"]) == 10
        and all(value in doc for value in required)
        and len(conflicts) == 2
        and sum(item["kind"] == "compositional" for item in variant["suite"]) == 2
        and authority_valid
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--out", type=Path, default=Path("."))
    parser.add_argument("--base-url", default=None)
    args = parser.parse_args()
    variant = generate_variant(args.seed)
    if not validate_variant(variant):
        raise SystemExit("generated context variant failed validation")
    args.out.mkdir(parents=True, exist_ok=True)
    write_text_atomic(args.out / "longctx_doc.txt", variant["doc"])
    write_json_atomic(args.out / "longctx_suite.json", variant["suite"])
    count, source = tokenize_or_approx(args.base_url, variant["doc"]) if args.base_url else (_approx_tokens(variant["doc"]), "approx")
    write_json_atomic(
        args.out / "longctx_meta.json",
        {"seed": args.seed, "token_count": count, "token_source": source},
    )


if __name__ == "__main__":
    main()
