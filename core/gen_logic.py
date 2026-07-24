#!/usr/bin/env python3
"""Generate small, seeded logic suites with solver-verified unique answers."""

from __future__ import annotations

import argparse
import itertools
import json
import random
from collections.abc import Iterable
from pathlib import Path


FAMILIES = ("assignment", "schedule", "boolean", "code")
_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
_NAME_SETS = (
    ("Arin", "Bela", "Cato", "Dara", "Enzo"),
    ("Faye", "Galen", "Hana", "Ivo", "Jori"),
    ("Kira", "Lio", "Mara", "Niko", "Orla"),
    ("Paz", "Quin", "Rhea", "Sami", "Tova"),
    ("Uma", "Vero", "Wren", "Xavi", "Yara"),
    ("Asha", "Bram", "Cleo", "Dion", "Esme"),
)


def _permutation_candidates(names: list[str]) -> Iterable[dict[str, int]]:
    for positions in itertools.permutations(range(1, len(names) + 1)):
        yield dict(zip(names, positions))


def _assignment_match(solution: dict[str, int], clue: dict) -> bool:
    kind = clue["type"]
    if kind == "before":
        return solution[clue["a"]] < solution[clue["b"]]
    if kind == "adjacent":
        return abs(solution[clue["a"]] - solution[clue["b"]]) == 1
    if kind == "gap":
        return abs(solution[clue["a"]] - solution[clue["b"]]) == clue["n"]
    if kind == "not_slot":
        return solution[clue["a"]] != clue["slot"]
    if kind == "at":
        return solution[clue["a"]] == clue["slot"]
    raise ValueError(f"unknown assignment clue: {kind}")


def _schedule_match(solution: dict[str, int], clue: dict) -> bool:
    kind = clue["type"]
    if kind == "before":
        return solution[clue["a"]] < solution[clue["b"]]
    if kind == "immediately_before":
        return solution[clue["b"]] == solution[clue["a"]] + 1
    if kind == "days_between":
        return abs(solution[clue["a"]] - solution[clue["b"]]) - 1 == clue["n"]
    if kind == "not_day":
        return solution[clue["a"]] != clue["day"]
    if kind == "day":
        return solution[clue["a"]] == clue["day"]
    raise ValueError(f"unknown schedule clue: {kind}")


def _boolean_match(solution: dict[str, bool], clue: dict) -> bool:
    kind = clue["type"]
    if kind == "same":
        return solution[clue["a"]] == solution[clue["b"]]
    if kind == "different":
        return solution[clue["a"]] != solution[clue["b"]]
    if kind == "implies":
        return not solution[clue["a"]] or solution[clue["b"]]
    if kind == "exactly":
        return sum(solution[name] for name in clue["names"]) == clue["n"]
    if kind == "state":
        return solution[clue["a"]] is clue["value"]
    raise ValueError(f"unknown boolean clue: {kind}")


def _code_feedback(secret: tuple[int, ...], guess: tuple[int, ...]) -> tuple[int, int]:
    exact = sum(actual == proposed for actual, proposed in zip(secret, guess))
    common = len(set(secret) & set(guess))
    return exact, common - exact


def _solutions(item: dict) -> Iterable[dict | list[int]]:
    family = item["family"]
    clues = item["clues"]
    if family in ("assignment", "schedule"):
        names = item["domain"]["names"]
        matcher = _assignment_match if family == "assignment" else _schedule_match
        for candidate in _permutation_candidates(names):
            if all(matcher(candidate, clue) for clue in clues):
                if family == "schedule":
                    yield {name: _DAY_NAMES[candidate[name] - 1] for name in names}
                else:
                    yield candidate
        return
    if family == "boolean":
        names = item["domain"]["names"]
        for values in itertools.product((False, True), repeat=len(names)):
            candidate = dict(zip(names, values))
            if all(_boolean_match(candidate, clue) for clue in clues):
                yield candidate
        return
    if family == "code":
        digits = item["domain"]["digits"]
        length = item["domain"]["length"]
        for candidate in itertools.permutations(digits, length):
            if all(
                _code_feedback(candidate, tuple(clue["guess"]))
                == (clue["exact"], clue["misplaced"])
                for clue in clues
            ):
                yield {"code": list(candidate)}
        return
    raise ValueError(f"unknown logic family: {family}")


def solve_item(item: dict, limit: int | None = None) -> list[dict | list[int]]:
    """Return all satisfying answers, optionally stopping after ``limit``."""
    answers = []
    for answer in _solutions(item):
        answers.append(answer)
        if limit is not None and len(answers) >= limit:
            break
    return answers


def _minimize(item: dict, clues: list[dict], rng: random.Random) -> list[dict]:
    """Greedily produce an irreducible clue set while retaining uniqueness."""
    retained = clues[:]
    rng.shuffle(retained)
    item = {**item, "clues": retained}
    if len(solve_item(item, limit=2)) != 1:
        raise ValueError("candidate clues do not identify a unique solution")
    for clue in retained[:]:
        reduced = retained.copy()
        reduced.remove(clue)
        if len(solve_item({**item, "clues": reduced}, limit=2)) == 1:
            retained = reduced
    if len(retained) < 2:
        raise ValueError("degenerate logic item")
    return retained


def _assignment_clue_text(clue: dict) -> str:
    kind = clue["type"]
    if kind == "before":
        return f"{clue['a']} is somewhere before {clue['b']}."
    if kind == "adjacent":
        return f"{clue['a']} and {clue['b']} use adjacent stations."
    if kind == "gap":
        return f"{clue['a']} and {clue['b']} are {clue['n']} stations apart."
    if kind == "not_slot":
        return f"{clue['a']} is not at station {clue['slot']}."
    return f"{clue['a']} is at station {clue['slot']}."


def _schedule_clue_text(clue: dict) -> str:
    kind = clue["type"]
    if kind == "before":
        return f"{clue['a']} is scheduled before {clue['b']}."
    if kind == "immediately_before":
        return f"{clue['a']} is scheduled on the day immediately before {clue['b']}."
    if kind == "days_between":
        unit = "day" if clue["n"] == 1 else "days"
        return f"There are exactly {clue['n']} {unit} between {clue['a']} and {clue['b']}."
    if kind == "not_day":
        return f"{clue['a']} is not on {_DAY_NAMES[clue['day'] - 1]}."
    return f"{clue['a']} is on {_DAY_NAMES[clue['day'] - 1]}."


def _boolean_clue_text(clue: dict) -> str:
    kind = clue["type"]
    if kind == "same":
        return f"{clue['a']} and {clue['b']} have the same state."
    if kind == "different":
        return f"{clue['a']} and {clue['b']} have different states."
    if kind == "implies":
        return f"If {clue['a']} is active, then {clue['b']} is active."
    if kind == "exactly":
        return f"Exactly {clue['n']} of {', '.join(clue['names'])} are active."
    return f"{clue['a']} is {'active' if clue['value'] else 'inactive'}."


def _render_question(item: dict) -> str:
    family = item["family"]
    names = item["domain"].get("names", [])
    if family == "assignment":
        intro = (
            f"{', '.join(names)} each use one distinct station numbered 1-{len(names)}. "
            "Determine every person's station."
        )
        texts = [_assignment_clue_text(clue) for clue in item["clues"]]
        contract = "{" + ",".join(f'"{name}":<integer>' for name in names) + "}"
    elif family == "schedule":
        intro = (
            f"{', '.join(names)} are scheduled one per weekday from Monday through Friday. "
            "Determine the day for every task."
        )
        texts = [_schedule_clue_text(clue) for clue in item["clues"]]
        contract = "{" + ",".join(f'"{name}":"<weekday>"' for name in names) + "}"
    elif family == "boolean":
        intro = (
            f"The indicators {', '.join(names)} are each either active or inactive. "
            "Determine every indicator's state."
        )
        texts = [_boolean_clue_text(clue) for clue in item["clues"]]
        contract = "{" + ",".join(f'"{name}":<true|false>' for name in names) + "}"
    else:
        intro = (
            "A lock code has four distinct digits chosen from 0 through 5. "
            "For each guess, 'exact' means right digit and position; 'misplaced' means "
            "right digit but wrong position. Determine the code."
        )
        texts = [
            f"Guess {''.join(map(str, clue['guess']))}: {clue['exact']} exact, "
            f"{clue['misplaced']} misplaced."
            for clue in item["clues"]
        ]
        contract = '{"code":[<digit>,<digit>,<digit>,<digit>]}'
    numbered = " ".join(f"{index}) {text}" for index, text in enumerate(texts, 1))
    return f"{intro} Clues: {numbered} Answer format: {contract}."


def _assignment_item(rng: random.Random, index: int) -> dict:
    names = list(_NAME_SETS[index][:4])
    positions = list(range(1, 5))
    rng.shuffle(positions)
    secret = dict(zip(names, positions))
    clues = []
    for a, b in itertools.combinations(names, 2):
        before, after = (a, b) if secret[a] < secret[b] else (b, a)
        clues.append({"type": "before", "a": before, "b": after})
        if abs(secret[a] - secret[b]) == 1:
            clues.append({"type": "adjacent", "a": a, "b": b})
        if abs(secret[a] - secret[b]) == 2:
            clues.append({"type": "gap", "a": a, "b": b, "n": 2})
    for name in names:
        for slot in range(1, 5):
            if secret[name] != slot:
                clues.append({"type": "not_slot", "a": name, "slot": slot})
    base = {
        "id": f"logic-assignment-{index + 1:02d}",
        "family": "assignment",
        "domain": {"names": names},
        "answer": secret,
    }
    base["clues"] = _minimize(base, clues, rng)
    base["q"] = _render_question(base)
    return base


def _schedule_item(rng: random.Random, index: int) -> dict:
    names = [f"Task-{name}" for name in _NAME_SETS[index]]
    positions = list(range(1, 6))
    rng.shuffle(positions)
    secret = dict(zip(names, positions))
    clues = []
    for a, b in itertools.combinations(names, 2):
        before, after = (a, b) if secret[a] < secret[b] else (b, a)
        clues.append({"type": "before", "a": before, "b": after})
        difference = abs(secret[a] - secret[b])
        if difference == 1:
            earlier, later = (a, b) if secret[a] < secret[b] else (b, a)
            clues.append({"type": "immediately_before", "a": earlier, "b": later})
        elif difference in (2, 3):
            clues.append({"type": "days_between", "a": a, "b": b, "n": difference - 1})
    for name in names:
        for day in range(1, 6):
            if secret[name] != day:
                clues.append({"type": "not_day", "a": name, "day": day})
    answer = {name: _DAY_NAMES[secret[name] - 1] for name in names}
    base = {
        "id": f"logic-schedule-{index + 1:02d}",
        "family": "schedule",
        "domain": {"names": names},
        "answer": answer,
    }
    base["clues"] = _minimize(base, clues, rng)
    base["q"] = _render_question(base)
    return base


def _boolean_item(rng: random.Random, index: int) -> dict:
    names = [f"Signal-{name}" for name in _NAME_SETS[index][:4]]
    true_count = rng.choice((1, 3))
    active = set(rng.sample(names, true_count))
    secret = {name: name in active for name in names}
    clues = [{"type": "exactly", "names": names, "n": true_count}]
    for a, b in itertools.combinations(names, 2):
        clues.append({"type": "same" if secret[a] == secret[b] else "different", "a": a, "b": b})
        if not secret[a] or secret[b]:
            clues.append({"type": "implies", "a": a, "b": b})
        if not secret[b] or secret[a]:
            clues.append({"type": "implies", "a": b, "b": a})
    base = {
        "id": f"logic-boolean-{index + 1:02d}",
        "family": "boolean",
        "domain": {"names": names},
        "answer": secret,
    }
    base["clues"] = _minimize(base, clues, rng)
    base["q"] = _render_question(base)
    return base


def _code_item(rng: random.Random, index: int) -> dict:
    digits = list(range(6))
    secret = tuple(rng.sample(digits, 4))
    guesses = list(itertools.permutations(digits, 4))
    rng.shuffle(guesses)
    candidates = list(itertools.permutations(digits, 4))
    clues = []
    for guess in guesses:
        if guess == secret:
            continue
        exact, misplaced = _code_feedback(secret, guess)
        reduced = [candidate for candidate in candidates if _code_feedback(candidate, guess) == (exact, misplaced)]
        if len(reduced) < len(candidates):
            clues.append({"guess": list(guess), "exact": exact, "misplaced": misplaced})
            candidates = reduced
        if len(candidates) == 1:
            break
    base = {
        "id": f"logic-code-{index + 1:02d}",
        "family": "code",
        "domain": {"digits": digits, "length": 4},
        "answer": {"code": list(secret)},
    }
    # The generic code solver yields the bare digit list; wrap it for the contract.
    solver_base = {**base, "answer": list(secret)}
    minimized = _minimize(solver_base, clues, rng)
    base["clues"] = minimized
    base["q"] = _render_question(base)
    return base


def generate_pool(seed: int = 20260712) -> list[dict]:
    rng = random.Random(seed)
    makers = {
        "assignment": _assignment_item,
        "schedule": _schedule_item,
        "boolean": _boolean_item,
        "code": _code_item,
    }
    pool = [makers[family](rng, index) for family in FAMILIES for index in range(6)]
    if len({item["q"] for item in pool}) != len(pool):
        raise ValueError("duplicate generated logic question")
    for item in pool:
        if solve_item(item, limit=2) != [item["answer"]]:
            raise ValueError(f"logic item is not uniquely solved: {item['id']}")
    return pool


def sample_pool(pool: list[dict], seed: int, count_per_family: int = 2) -> list[dict]:
    rng = random.Random(seed)
    selected = []
    for family in FAMILIES:
        candidates = [item for item in pool if item["family"] == family]
        selected.extend(rng.sample(candidates, count_per_family))
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--out", type=Path, default=Path("logic_pool.json"))
    parser.add_argument("--sample-out", type=Path)
    args = parser.parse_args()
    pool = generate_pool(args.seed)
    args.out.write_text(json.dumps(pool, indent=2) + "\n")
    if args.sample_out:
        args.sample_out.write_text(json.dumps(sample_pool(pool, args.seed), indent=2) + "\n")


if __name__ == "__main__":
    main()
