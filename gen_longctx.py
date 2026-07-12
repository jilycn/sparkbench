#!/usr/bin/env python3
"""Seeded adversarial long-context variants for SparkBench v2."""

from __future__ import annotations

import argparse
import json
import random
import urllib.error
import urllib.request
from pathlib import Path


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


def generate_variant(seed=20260712):
    rng = random.Random(seed)
    budget_a, budget_b = rng.randint(42000, 68000), rng.randint(12000, 28000)
    key_person, key_team = "Ada Lindqvist", rng.choice(TEAMS)
    incident_days = sorted(rng.sample(range(4, 27), 2))
    transfer_day, version = rng.randint(8, 20), f"v{rng.randint(4, 8)}.{rng.randint(1, 9)}.{rng.randint(0, 9)}"
    codename = rng.choice(["IndigoFalcon", "CopperOrchid", "VelvetComet", "SilverTern"])
    authoritative_region, decoy_region = rng.choice(["us-east", "eu-west", "ap-south"]), rng.choice(["us-east", "eu-west", "ap-south"])
    if decoy_region == authoritative_region:
        decoy_region = "eu-west" if authoritative_region != "eu-west" else "us-east"
    positions = sorted(rng.sample(range(80, 2520), 12))
    plants = {
        positions[0]: f"[AUTHORITY] FINANCE signed Q1 Atlas infrastructure budget: ${budget_a}.",
        positions[1]: f"[SECURITY] Master signing key rotation completed by {key_person}.",
        positions[2]: f"[INCIDENT] srv-quartz kernel panic on March {incident_days[0]}; root cause memory bitflip.",
        positions[3]: f"[NOTE] Migration initiative codename: {codename}.",
        positions[4]: f"[HR] Tomas Reyes transferred teams on March {transfer_day}.",
        positions[5]: f"[RELEASE] Platform {version} deployed on March {transfer_day}.",
        positions[6]: f"[ROSTER] {key_person} remains on the {key_team} team.",
        positions[7]: f"[INCIDENT] srv-quartz disk degradation on March {incident_days[1]}; hot spare rebuilt.",
        positions[8]: f"[AUTHORITY] FINANCE signed supplemental GPU budget: ${budget_b}.",
        positions[9]: f"[DRAFT] Region for migration is {decoy_region}; this draft is superseded.",
        positions[10]: f"[AUTHORITY] Final signed migration region is {authoritative_region}; supersedes drafts.",
        positions[11]: "[DRAFT] Signing-key rotation attributed to Mira Voss; this unsigned note is false.",
    }
    filler_people = [person for person in PEOPLE if person not in (key_person, "Tomas Reyes")]
    team_of = {person: TEAMS[index % len(TEAMS)] for index, person in enumerate(filler_people)}
    lines = ["[RULE] When records conflict, the latest [AUTHORITY] signed record overrides [DRAFT] and unsigned notes."]
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
        ("budget_sum", "What is the sum of the two signed budgets?", budget_a + budget_b),
        ("key_team", "Which team does the person who completed the master signing key rotation belong to?", key_team),
        ("incident_count", "How many srv-quartz INCIDENT records are present?", 2),
        ("release_join", "Which platform version was deployed on Tomas Reyes's transfer day?", version),
        ("codename", "What is the migration initiative codename?", codename),
        ("incident_days", "Which March day numbers have srv-quartz incidents, sorted ascending?", incident_days),
        ("conflict_region", "Under the document's authority rule, what migration region applies?", authoritative_region),
        ("conflict_person", "Under the document's authority rule, who completed the signing-key rotation?", key_person),
        ("compositional_difference", "What is the signed Q1 budget minus the signed supplemental GPU budget?", budget_a - budget_b),
        ("compositional_team_days", "Give the key-rotation person's team and the srv-quartz incident days.", {"team": key_team, "days": incident_days}),
    ]
    suite = []
    for index, (kind, question, answer) in enumerate(questions, 1):
        suite.append({"id": f"lc{index}", "kind": "conflict" if kind.startswith("conflict") else
                      ("compositional" if kind.startswith("compositional") else "retrieval"),
                      "q": question + " Answer format: {\"answer\": <value>}.", "answer": answer,
                      "tol": 0, "numeric": isinstance(answer, (int, float))})
    rng.shuffle(suite)
    for index, item in enumerate(suite):
        item["cold"] = index == 0
    doc = "\n".join(lines) + "\n"
    return {"seed": seed, "doc": doc, "suite": suite, "facts": {"budget_a": budget_a, "budget_b": budget_b,
            "key_person": key_person, "key_team": key_team, "incident_days": incident_days,
            "version": version, "codename": codename, "authoritative_region": authoritative_region}}


def validate_variant(variant):
    doc, facts = variant["doc"], variant["facts"]
    required = [str(facts["budget_a"]), str(facts["budget_b"]), facts["key_person"], facts["key_team"],
                facts["version"], facts["codename"], facts["authoritative_region"]]
    return len(variant["suite"]) == 10 and all(value in doc for value in required) and \
        sum(item["kind"] == "conflict" for item in variant["suite"]) == 2 and \
        sum(item["kind"] == "compositional" for item in variant["suite"]) == 2


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
    (args.out / "longctx_doc.txt").write_text(variant["doc"])
    (args.out / "longctx_suite.json").write_text(json.dumps(variant["suite"], indent=2) + "\n")
    count, source = tokenize_or_approx(args.base_url, variant["doc"]) if args.base_url else (_approx_tokens(variant["doc"]), "approx")
    (args.out / "longctx_meta.json").write_text(json.dumps({"seed": args.seed, "token_count": count, "token_source": source}, indent=2) + "\n")


if __name__ == "__main__":
    main()
