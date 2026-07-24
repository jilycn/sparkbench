#!/usr/bin/env python3
"""Generate three small, independent, reference-validated agent coding tasks."""

from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from sblib import write_json_atomic, write_text_atomic


FAMILIES = ("records", "dependencies", "ledger")
VARIANTS = {
    "records": ("latest_alpha", "highest_ranked", "first_by_name"),
    "dependencies": ("priority", "input_order", "lexical"),
    "ledger": ("skip_insufficient", "strict_insufficient", "credit_limit_10"),
}


def _records_config(variant):
    return {
        "latest_alpha": ("latest", "title", "id"),
        "highest_ranked": ("highest", "lower", "ranked"),
        "first_by_name": ("first", "preserve", "name"),
    }[variant]


def _records_oracle(records, variant):
    dedupe, case, order = _records_config(variant)
    if not isinstance(records, list):
        raise ValueError
    chosen = {}
    for record in records:
        if not isinstance(record, dict) or not {"id", "name", "score", "tags"} <= record.keys():
            raise ValueError
        identifier, name, score, tags = (
            record["id"],
            record["name"],
            record["score"],
            record["tags"],
        )
        if (
            not isinstance(identifier, str)
            or not identifier
            or not isinstance(name, str)
            or not isinstance(score, int)
            or isinstance(score, bool)
            or not isinstance(tags, list)
            or not all(isinstance(tag, str) for tag in tags)
        ):
            raise ValueError
        normalized_name = " ".join(name.split())
        if case == "title":
            normalized_name = normalized_name.title()
        elif case == "lower":
            normalized_name = normalized_name.casefold()
        normalized = {
            "id": identifier,
            "name": normalized_name,
            "score": score,
            "tags": sorted({tag.strip().casefold() for tag in tags if tag.strip()}),
        }
        if dedupe == "latest":
            chosen[identifier] = normalized
        elif dedupe == "first":
            chosen.setdefault(identifier, normalized)
        elif identifier not in chosen or score >= chosen[identifier]["score"]:
            chosen[identifier] = normalized
    result = list(chosen.values())
    keys = {
        "id": lambda item: item["id"],
        "ranked": lambda item: (-item["score"], item["id"]),
        "name": lambda item: (item["name"].casefold(), item["id"]),
    }
    return sorted(result, key=keys[order])


def _records_reference(variant):
    dedupe, case, order = _records_config(variant)
    return f'''class RecordError(Exception): pass

def normalize(records):
    if not isinstance(records, list):
        raise RecordError("records must be a list")
    chosen = {{}}
    for record in records:
        if not isinstance(record, dict) or not {{"id", "name", "score", "tags"}} <= record.keys():
            raise RecordError("invalid record")
        identifier, name, score, tags = record["id"], record["name"], record["score"], record["tags"]
        if (not isinstance(identifier, str) or not identifier or not isinstance(name, str)
                or not isinstance(score, int) or isinstance(score, bool)
                or not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags)):
            raise RecordError("invalid field")
        name = " ".join(name.split())
        if {case!r} == "title": name = name.title()
        elif {case!r} == "lower": name = name.casefold()
        value = {{"id": identifier, "name": name, "score": score,
                 "tags": sorted({{tag.strip().casefold() for tag in tags if tag.strip()}})}}
        if {dedupe!r} == "latest": chosen[identifier] = value
        elif {dedupe!r} == "first": chosen.setdefault(identifier, value)
        elif identifier not in chosen or score >= chosen[identifier]["score"]: chosen[identifier] = value
    keys = {{"id": lambda item: item["id"], "ranked": lambda item: (-item["score"], item["id"]),
            "name": lambda item: (item["name"].casefold(), item["id"])}}
    return sorted(chosen.values(), key=keys[{order!r}])
'''


def _records_cases(variant):
    basic = [
        {"id": "b", "name": "  BETA  team ", "score": 4, "tags": ["X", "x", " qa "]},
        {"id": "a", "name": "alpha", "score": 7, "tags": []},
    ]
    duplicate = [
        {"id": "x", "name": "first", "score": 5, "tags": ["A"]},
        {"id": "x", "name": "second", "score": 9, "tags": ["B"]},
        {"id": "x", "name": "third", "score": 9, "tags": ["C"]},
    ]
    ordering = [
        {"id": "z", "name": "Able", "score": 1, "tags": []},
        {"id": "a", "name": "Zulu", "score": 9, "tags": []},
        {"id": "m", "name": "Mike", "score": 5, "tags": []},
    ]
    return basic, duplicate, ordering


def _records_tests(module, variant):
    basic, duplicate, ordering = _records_cases(variant)
    expected_basic = _records_oracle(basic, variant)
    expected_duplicate = _records_oracle(duplicate, variant)
    expected_ordering = _records_oracle(ordering, variant)
    return f'''import copy
import pytest
from {module} import normalize, RecordError

def test_empty():
    assert normalize([]) == []

def test_basic_normalization():
    assert normalize({basic!r}) == {expected_basic!r}

def test_tags_are_trimmed_casefolded_unique_and_sorted():
    value = [{{"id":"x","name":" n ","score":1,"tags":[" QA ","qa","Ops",""]}}]
    assert normalize(value)[0]["tags"] == ["ops", "qa"]

def test_duplicate_policy():
    assert normalize({duplicate!r}) == {expected_duplicate!r}

def test_output_order():
    assert normalize({ordering!r}) == {expected_ordering!r}

def test_input_is_not_mutated():
    value = {basic!r}; before = copy.deepcopy(value); normalize(value); assert value == before

def test_missing_field_rejected():
    with pytest.raises(RecordError): normalize([{{"id":"x"}}])

def test_bad_scalar_type_rejected():
    with pytest.raises(RecordError):
        normalize([{{"id":"x","name":"x","score":True,"tags":[]}}])

def test_non_list_input_rejected():
    with pytest.raises(RecordError): normalize({{"id":"x"}})

def test_bad_tag_type_rejected():
    with pytest.raises(RecordError):
        normalize([{{"id":"x","name":"x","score":1,"tags":["ok",7]}}])

def test_extra_input_fields_are_not_leaked():
    result = normalize([{{"id":"x","name":" x ","score":1,"tags":[],"secret":"drop"}}])
    assert set(result[0]) == {{"id","name","score","tags"}}

def test_internal_name_whitespace_is_canonicalized():
    result = normalize([{{"id":"x","name":"  alpha\\t beta\\nteam ","score":1,"tags":[]}}])
    assert result[0]["name"].casefold() == "alpha beta team"
'''


def _records_probes(module, variant):
    basic, duplicate, ordering = _records_cases(variant)
    cases = [
        (basic + duplicate, _records_oracle(basic + duplicate, variant)),
        (list(reversed(ordering)), _records_oracle(list(reversed(ordering)), variant)),
    ]
    return f'''from {module} import normalize, RecordError
passed = 0
for value, expected in {cases!r}:
    try: passed += normalize(value) == expected
    except Exception: pass
try:
    normalize("not-a-list")
except RecordError: passed += 1
try:
    normalize([{{"id":"","name":"x","score":1,"tags":[]}}])
except RecordError: passed += 1
print(f"{{passed}}/4")
raise SystemExit(0 if passed == 4 else 1)
'''


def _dependency_key(variant, job, index):
    if variant == "priority":
        return (-job["priority"], job["id"])
    if variant == "input_order":
        return (index[job["id"]],)
    return (job["id"],)


def _dependency_oracle(jobs, variant):
    if not isinstance(jobs, list):
        raise ValueError
    by_id, index = {}, {}
    for position, job in enumerate(jobs):
        if (
            not isinstance(job, dict)
            or not {"id", "deps", "priority"} <= job.keys()
            or not isinstance(job["id"], str)
            or not job["id"]
            or not isinstance(job["deps"], list)
            or not all(isinstance(dep, str) for dep in job["deps"])
            or not isinstance(job["priority"], int)
            or isinstance(job["priority"], bool)
            or job["id"] in by_id
        ):
            raise ValueError
        by_id[job["id"]] = copy.deepcopy(job)
        index[job["id"]] = position
    if any(dep not in by_id for job in jobs for dep in job["deps"]):
        raise KeyError
    remaining, done, result = set(by_id), set(), []
    while remaining:
        ready = [by_id[name] for name in remaining if set(by_id[name]["deps"]) <= done]
        if not ready:
            raise RuntimeError
        selected = min(ready, key=lambda job: _dependency_key(variant, job, index))
        result.append(selected["id"])
        done.add(selected["id"])
        remaining.remove(selected["id"])
    return result


def _dependency_reference(variant):
    key = {
        "priority": "(-job['priority'], job['id'])",
        "input_order": "(index[job['id']],)",
        "lexical": "(job['id'],)",
    }[variant]
    return f'''class DependencyError(Exception): pass
class MissingDependencyError(DependencyError): pass
class CycleError(DependencyError): pass

def schedule(jobs):
    if not isinstance(jobs, list): raise DependencyError("jobs must be a list")
    by_id, index = {{}}, {{}}
    for position, job in enumerate(jobs):
        if (not isinstance(job, dict) or not {{"id","deps","priority"}} <= job.keys()
                or not isinstance(job["id"], str) or not job["id"]
                or not isinstance(job["deps"], list) or not all(isinstance(x, str) for x in job["deps"])
                or not isinstance(job["priority"], int) or isinstance(job["priority"], bool)
                or job["id"] in by_id):
            raise DependencyError("invalid or duplicate job")
        by_id[job["id"]] = {{"id":job["id"], "deps":list(job["deps"]), "priority":job["priority"]}}
        index[job["id"]] = position
    if any(dep not in by_id for job in by_id.values() for dep in job["deps"]):
        raise MissingDependencyError("missing dependency")
    remaining, done, result = set(by_id), set(), []
    while remaining:
        ready = [by_id[name] for name in remaining if set(by_id[name]["deps"]) <= done]
        if not ready: raise CycleError("cycle")
        job = min(ready, key=lambda job: {key})
        result.append(job["id"]); done.add(job["id"]); remaining.remove(job["id"])
    return result
'''


def _dependency_cases(variant):
    single = [{"id": "a", "deps": [], "priority": 1}]
    chain = [
        {"id": "c", "deps": ["b"], "priority": 9},
        {"id": "a", "deps": [], "priority": 1},
        {"id": "b", "deps": ["a"], "priority": 2},
    ]
    diamond = [
        {"id": "finish", "deps": ["left", "right"], "priority": 9},
        {"id": "root", "deps": [], "priority": 0},
        {"id": "right", "deps": ["root"], "priority": 3},
        {"id": "left", "deps": ["root"], "priority": 7},
    ]
    tie = [
        {"id": "z", "deps": [], "priority": 2},
        {"id": "a", "deps": [], "priority": 8},
        {"id": "m", "deps": [], "priority": 5},
    ]
    unlock = [
        {"id": "low", "deps": [], "priority": 1},
        {"id": "gate", "deps": [], "priority": 9},
        {"id": "new", "deps": ["gate"], "priority": 20},
    ]
    return single, chain, diamond, tie, unlock


def _dependency_tests(module, variant):
    single, chain, diamond, tie, unlock = _dependency_cases(variant)
    return f'''import copy
import pytest
from {module} import schedule, DependencyError, MissingDependencyError, CycleError

def test_single():
    assert schedule({single!r}) == {_dependency_oracle(single, variant)!r}

def test_chain():
    assert schedule({chain!r}) == {_dependency_oracle(chain, variant)!r}

def test_diamond():
    assert schedule({diamond!r}) == {_dependency_oracle(diamond, variant)!r}

def test_ready_tie_policy():
    assert schedule({tie!r}) == {_dependency_oracle(tie, variant)!r}

def test_newly_ready_jobs_join_selection():
    assert schedule({unlock!r}) == {_dependency_oracle(unlock, variant)!r}

def test_duplicate_rejected():
    with pytest.raises(DependencyError):
        schedule([{{"id":"a","deps":[],"priority":1}},{{"id":"a","deps":[],"priority":2}}])

def test_missing_dependency_rejected():
    with pytest.raises(MissingDependencyError):
        schedule([{{"id":"a","deps":["ghost"],"priority":1}}])

def test_cycle_rejected():
    with pytest.raises(CycleError):
        schedule([{{"id":"a","deps":["b"],"priority":1}},{{"id":"b","deps":["a"],"priority":1}}])

def test_empty_schedule():
    assert schedule([]) == []

def test_non_list_input_rejected():
    with pytest.raises(DependencyError): schedule({{"id":"a"}})

def test_bad_dependency_and_priority_types_rejected():
    with pytest.raises(DependencyError):
        schedule([{{"id":"a","deps":[1],"priority":1}}])
    with pytest.raises(DependencyError):
        schedule([{{"id":"a","deps":[],"priority":True}}])

def test_inputs_are_not_mutated():
    value = {diamond!r}; before = copy.deepcopy(value); schedule(value); assert value == before
'''


def _dependency_probes(module, variant):
    _, chain, diamond, tie, _ = _dependency_cases(variant)
    cases = [
        (list(reversed(chain)), _dependency_oracle(list(reversed(chain)), variant)),
        (diamond + [{"id": "solo", "deps": [], "priority": 4}],
         _dependency_oracle(diamond + [{"id": "solo", "deps": [], "priority": 4}], variant)),
    ]
    return f'''from {module} import schedule, DependencyError, CycleError
passed = 0
for value, expected in {cases!r}:
    try: passed += schedule(value) == expected
    except Exception: pass
try:
    schedule([{{"id":"a","deps":[],"priority":True}}])
except DependencyError: passed += 1
try:
    schedule([{{"id":"a","deps":["a"],"priority":1}}])
except CycleError: passed += 1
print(f"{{passed}}/4")
raise SystemExit(0 if passed == 4 else 1)
'''


def _ledger_oracle(opening, events, variant):
    if (
        not isinstance(opening, dict)
        or not all(
            isinstance(key, str)
            and key
            and isinstance(value, int)
            and not isinstance(value, bool)
            for key, value in opening.items()
        )
        or not isinstance(events, list)
    ):
        raise ValueError
    balances, seen = dict(opening), set()
    limit = -10 if variant == "credit_limit_10" else 0
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get("id"), str) or not event["id"]:
            raise ValueError
        if event["id"] in seen:
            continue
        seen.add(event["id"])
        kind, amount = event.get("type"), event.get("amount")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise ValueError
        if kind == "credit":
            account = event.get("account")
            if account not in balances:
                raise ValueError
            balances[account] += amount
            continue
        if kind == "debit":
            source, target = event.get("account"), None
        elif kind == "transfer":
            source, target = event.get("from"), event.get("to")
            if target not in balances:
                raise ValueError
        else:
            raise ValueError
        if source not in balances:
            raise ValueError
        if balances[source] - amount < limit:
            if variant == "strict_insufficient":
                raise RuntimeError
            continue
        balances[source] -= amount
        if target is not None:
            balances[target] += amount
    return balances


def _ledger_reference(variant):
    return f'''class LedgerError(Exception): pass

def apply_ledger(opening, events):
    if (not isinstance(opening, dict)
            or not all(isinstance(k, str) and k and isinstance(v, int) and not isinstance(v, bool)
                       for k, v in opening.items())
            or not isinstance(events, list)):
        raise LedgerError("invalid input")
    balances, seen = dict(opening), set()
    limit = {-10 if variant == "credit_limit_10" else 0}
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get("id"), str) or not event["id"]:
            raise LedgerError("invalid event")
        if event["id"] in seen: continue
        seen.add(event["id"])
        kind, amount = event.get("type"), event.get("amount")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise LedgerError("invalid amount")
        if kind == "credit":
            account = event.get("account")
            if account not in balances: raise LedgerError("unknown account")
            balances[account] += amount; continue
        if kind == "debit": source, target = event.get("account"), None
        elif kind == "transfer":
            source, target = event.get("from"), event.get("to")
            if target not in balances: raise LedgerError("unknown account")
        else: raise LedgerError("unknown type")
        if source not in balances: raise LedgerError("unknown account")
        if balances[source] - amount < limit:
            if {variant!r} == "strict_insufficient": raise LedgerError("insufficient funds")
            continue
        balances[source] -= amount
        if target is not None: balances[target] += amount
    return balances
'''


def _ledger_cases(variant):
    ordinary = [
        {"id": "1", "type": "credit", "account": "a", "amount": 5},
        {"id": "2", "type": "debit", "account": "b", "amount": 3},
    ]
    transfer = [{"id": "t", "type": "transfer", "from": "a", "to": "b", "amount": 4}]
    duplicate = ordinary + [
        {"id": "1", "type": "credit", "account": "a", "amount": 100}
    ]
    insufficient = [{"id": "x", "type": "debit", "account": "a", "amount": 15}]
    return ordinary, transfer, duplicate, insufficient


def _ledger_tests(module, variant):
    ordinary, transfer, duplicate, insufficient = _ledger_cases(variant)
    insufficient_test = (
        f'with pytest.raises(LedgerError): apply_ledger({{"a": 10}}, {insufficient!r})'
        if variant == "strict_insufficient"
        else f'assert apply_ledger({{"a": 10}}, {insufficient!r}) == '
        f'{_ledger_oracle({"a": 10}, insufficient, variant)!r}'
    )
    boundary = [{"id": "limit", "type": "debit", "account": "a", "amount": 20}]
    boundary_test = (
        f'with pytest.raises(LedgerError): apply_ledger({{"a": 10}}, {boundary!r})'
        if variant == "strict_insufficient"
        else f'assert apply_ledger({{"a": 10}}, {boundary!r}) == '
        f'{_ledger_oracle({"a": 10}, boundary, variant)!r}'
    )
    return f'''import copy
import pytest
from {module} import apply_ledger, LedgerError

def test_empty():
    assert apply_ledger({{"a":3}}, []) == {{"a":3}}

def test_credit_and_debit():
    assert apply_ledger({{"a":10,"b":8}}, {ordinary!r}) == {_ledger_oracle({"a":10,"b":8}, ordinary, variant)!r}

def test_transfer_is_atomic():
    assert apply_ledger({{"a":10,"b":8}}, {transfer!r}) == {_ledger_oracle({"a":10,"b":8}, transfer, variant)!r}

def test_duplicate_ids_are_ignored_after_first():
    assert apply_ledger({{"a":10,"b":8}}, {duplicate!r}) == {_ledger_oracle({"a":10,"b":8}, duplicate, variant)!r}

def test_inputs_are_not_mutated():
    opening={{"a":10,"b":8}}; events={ordinary!r}; before=(copy.deepcopy(opening),copy.deepcopy(events))
    apply_ledger(opening,events); assert (opening,events) == before

def test_insufficient_policy():
    {insufficient_test}

def test_unknown_account_rejected():
    with pytest.raises(LedgerError):
        apply_ledger({{"a":1}}, [{{"id":"x","type":"credit","account":"z","amount":1}}])

def test_invalid_amount_rejected():
    with pytest.raises(LedgerError):
        apply_ledger({{"a":1}}, [{{"id":"x","type":"debit","account":"a","amount":True}}])

def test_input_container_and_opening_types_rejected():
    with pytest.raises(LedgerError): apply_ledger({{"a":True}}, [])
    with pytest.raises(LedgerError): apply_ledger({{"a":1}}, {{"id":"x"}})

def test_unknown_transfer_endpoint_rejected():
    with pytest.raises(LedgerError):
        apply_ledger({{"a":2}}, [{{"id":"x","type":"transfer","from":"a","to":"ghost","amount":1}}])
    with pytest.raises(LedgerError):
        apply_ledger({{"a":2}}, [{{"id":"x","type":"transfer","from":"ghost","to":"a","amount":1}}])

def test_insufficient_boundary_is_exact():
    {boundary_test}

def test_duplicate_id_is_consumed_by_first_valid_event():
    events = [
        {{"id":"same","type":"credit","account":"a","amount":1}},
        {{"id":"same","type":"credit","account":"ghost","amount":True}},
    ]
    assert apply_ledger({{"a":1}}, events) == {{"a":2}}
'''


def _ledger_probes(module, variant):
    ordinary, transfer, duplicate, insufficient = _ledger_cases(variant)
    combined = ordinary + transfer + duplicate
    expected = _ledger_oracle({"a": 20, "b": 9}, combined, variant)
    insufficient_check = (
        "try:\n    apply_ledger({'a':0}, [{'id':'x','type':'debit','account':'a','amount':1}])\n"
        "except LedgerError: passed += 1"
        if variant == "strict_insufficient"
        else f"passed += apply_ledger({{'a':0}}, [{{'id':'x','type':'debit','account':'a','amount':1}}]) == "
        f"{_ledger_oracle({'a': 0}, [{'id':'x','type':'debit','account':'a','amount':1}], variant)!r}"
    )
    return f'''from {module} import apply_ledger, LedgerError
passed = 0
try: passed += apply_ledger({{"a":20,"b":9}}, {combined!r}) == {expected!r}
except Exception: pass
{insufficient_check}
try:
    apply_ledger({{"a":1}}, [{{"id":"x","type":"unknown","amount":1}}])
except LedgerError: passed += 1
try:
    apply_ledger({{"a":1}}, [{{"id":"","type":"credit","account":"a","amount":1}}])
except LedgerError: passed += 1
print(f"{{passed}}/4")
raise SystemExit(0 if passed == 4 else 1)
'''


def _contract(family, variant, filename):
    if family == "records":
        dedupe, case, order = _records_config(variant)
        return (
            f"Create `{filename}` implementing `normalize(records) -> list[dict]` and `RecordError`. "
            "Each input record requires id (nonempty str), name (str), score (non-bool int), and "
            "tags (list[str]); invalid input raises RecordError. Never mutate inputs. Collapse name "
            f"whitespace and apply name mode `{case}`. Tags are stripped, casefolded, deduplicated, "
            f"and sorted. Duplicate-id policy is `{dedupe}` (highest ties choose the later record). "
            f"Output order is `{order}` (ranked means score descending then id; name means normalized "
            "name then id). Return only id/name/score/tags keys."
        )
    if family == "dependencies":
        policy = {
            "priority": "highest numeric priority, then lexical id",
            "input_order": "earliest input position",
            "lexical": "lexical id",
        }[variant]
        return (
            f"Create `{filename}` implementing `schedule(jobs) -> list[str]`, DependencyError, "
            "MissingDependencyError, and CycleError. Each job requires a unique nonempty string id, "
            "deps list[str], and non-bool integer priority. Return a topological order. Whenever "
            f"multiple jobs are ready choose `{policy}`. Reject malformed/duplicate jobs, missing "
            "dependencies, and cycles with the corresponding exception; never mutate inputs."
        )
    return (
        f"Create `{filename}` implementing `apply_ledger(opening, events) -> dict[str,int]` and "
        "LedgerError. Do not mutate inputs. Process unique transaction ids once (first occurrence "
        "wins). Support positive-integer credit(account), debit(account), and transfer(from,to) "
        "events; reject malformed events and unknown accounts. "
        + {
            "skip_insufficient": "A debit/transfer that would make a balance negative is skipped.",
            "strict_insufficient": "A debit/transfer that would make a balance negative raises LedgerError.",
            "credit_limit_10": "Balances may reach -10; a debit/transfer below -10 is skipped.",
        }[variant]
    )


def _task_sources(family, variant, module):
    if family == "records":
        return (
            _records_reference(variant),
            _records_tests(module, variant),
            _records_probes(module, variant),
        )
    if family == "dependencies":
        return (
            _dependency_reference(variant),
            _dependency_tests(module, variant),
            _dependency_probes(module, variant),
        )
    return (
        _ledger_reference(variant),
        _ledger_tests(module, variant),
        _ledger_probes(module, variant),
    )


def _count_tests(source):
    return sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        for node in ast.parse(source).body
    )


def _validate_reference(task, reference_source, tests_source, probes_source):
    with tempfile.TemporaryDirectory(prefix="sparkbench-agent-reference-") as raw:
        work = Path(raw)
        (work / task["filename"]).write_text(reference_source)
        (work / task["tests_file"]).write_text(tests_source)
        (work / task["probes_file"]).write_text(probes_source)
        tests = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--no-header", task["tests_file"]],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=120,
        )
        probes = subprocess.run(
            [sys.executable, task["probes_file"]],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if tests.returncode or probes.returncode or f"{task['probe_count']}/{task['probe_count']}" not in probes.stdout:
            raise ValueError(
                f"reference validation failed for {task['id']}: "
                f"{tests.stdout[-500:]} {tests.stderr[-500:]} {probes.stdout[-500:]} {probes.stderr[-500:]}"
            )


def generate_agent_task(
    seed: int, source_root: Path, staging: Path, variant: str | None = None
):
    del source_root
    staging.mkdir(parents=True, exist_ok=True)
    families = ("records",) if variant == "smoke" else FAMILIES
    tasks, files = [], [Path("agent_tasks.json")]
    identities = []
    for family_index, family in enumerate(families):
        selected = (
            "latest_alpha"
            if variant == "smoke"
            else VARIANTS[family][(seed + family_index) % len(VARIANTS[family])]
        )
        module = f"{family}_solution"
        task = {
            "id": f"{family}-{selected}",
            "family": family,
            "variant": selected,
            "filename": f"{module}.py",
            "tests_file": f"agent_{family}_tests.py",
            "probes_file": f"agent_{family}_probes.py",
            "hidden_count": 12,
            "probe_count": 4,
            "max_turns": 6,
            "development_only": variant == "smoke",
        }
        task["contract"] = _contract(family, selected, task["filename"])
        reference, tests, probes = _task_sources(family, selected, module)
        if _count_tests(tests) != task["hidden_count"]:
            raise ValueError(f"wrong hidden-test count for {task['id']}")
        _validate_reference(task, reference, tests, probes)
        write_text_atomic(staging / task["tests_file"], tests)
        write_text_atomic(staging / task["probes_file"], probes)
        files.extend((Path(task["tests_file"]), Path(task["probes_file"])))
        tasks.append(task)
        identities.append(f"{family}:{selected}")
    write_json_atomic(staging / "agent_tasks.json", tasks)
    return {
        "variant": "smoke" if variant == "smoke" else "|".join(identities),
        "reference_validated": True,
        "files": files,
    }
