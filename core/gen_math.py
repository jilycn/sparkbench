#!/usr/bin/env python3
"""Generate the seeded SparkBench 2.2 math pool and balanced sample."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
from decimal import Decimal
from functools import lru_cache
from pathlib import Path


TEMPLATES = {
    "easy": (
        "percent_chain",
        "average_update",
        "linear_equation",
        "ratio_conversion",
        "quadratic_sequence",
    ),
    "med": (
        "combined_rates",
        "system_2x2",
        "conditional_sampling",
        "committee_constraints",
        "modular_exponentiation",
    ),
    "hard": (
        "crt",
        "bounded_diophantine",
        "inclusion_exclusion3",
        "parameterized_recurrence",
        "constrained_arrangements",
    ),
}


def _decimal2(value):
    return float(Decimal(value).quantize(Decimal("0.01")))


def _item(identifier, difficulty, kind, params, question, answer, tol=0.0):
    return {
        "id": identifier,
        "difficulty": difficulty,
        "kind": kind,
        "params": list(params),
        "q": question + ' Answer format: {"answer": <number>}.',
        "answer": answer,
        "tol": tol,
        "numeric": True,
    }


def _percent_chain(rng, identifier, difficulty):
    base = rng.randrange(120, 1201, 10)
    increase = rng.choice((5, 8, 10, 12, 15, 20, 25))
    decrease = rng.choice((4, 6, 10, 12, 15, 20))
    answer = _decimal2(
        Decimal(base) * Decimal(100 + increase) * Decimal(100 - decrease) / Decimal(10000)
    )
    return _item(
        identifier,
        difficulty,
        "percent_chain",
        (base, increase, decrease),
        f"A price of ${base} rises by {increase}% and then falls by {decrease}%. What is the final price?",
        answer,
        0.01,
    )


def _average_update(rng, identifier, difficulty):
    count = rng.randint(6, 18)
    average = rng.randint(24, 95)
    added = rng.randint(10, 120)
    total = count * average
    answer = round((total + added) / (count + 1), 2)
    return _item(
        identifier,
        difficulty,
        "average_update",
        (total, count, added),
        f"{count} measurements have average {average}. After adding {added}, what is the new average?",
        answer,
        0.01,
    )


def _linear_equation(rng, identifier, difficulty):
    coefficient = rng.randint(3, 19)
    offset = rng.randint(-40, 55)
    solution = rng.randint(-18, 35)
    right = coefficient * solution + offset
    return _item(
        identifier,
        difficulty,
        "linear_equation",
        (coefficient, offset, right),
        f"Solve for x: {coefficient}x + ({offset}) = {right}.",
        solution,
    )


def _ratio_conversion(rng, identifier, difficulty):
    first = rng.randint(2, 9)
    second = rng.randint(2, 9)
    scale = rng.randint(8, 40)
    total = (first + second) * scale
    answer = first * scale
    return _item(
        identifier,
        difficulty,
        "ratio_conversion",
        (first, second, total),
        f"A mixture has concentrate-to-water ratio {first}:{second} and total volume {total} mL. "
        "How many mL are concentrate?",
        answer,
    )


def _quadratic_sequence(rng, identifier, difficulty):
    a = rng.randint(1, 5)
    b = rng.randint(-5, 8)
    c = rng.randint(-10, 20)
    shown = [a * n * n + b * n + c for n in range(1, 6)]
    answer = a * 36 + b * 6 + c
    return _item(
        identifier,
        difficulty,
        "quadratic_sequence",
        (a, b, c, 6),
        f"The sequence begins {', '.join(map(str, shown))}. It follows a quadratic pattern. What is the next term?",
        answer,
    )


def _combined_rates(rng, identifier, difficulty):
    times = rng.sample(range(6, 25), 3)
    answer = round(1 / sum(1 / value for value in times), 2)
    return _item(
        identifier,
        difficulty,
        "combined_rates",
        times,
        f"Three pumps can fill a tank alone in {times[0]}, {times[1]}, and {times[2]} hours. "
        "How many hours do they need working together?",
        answer,
        0.01,
    )


def _system_2x2(rng, identifier, difficulty):
    while True:
        a, b, c, d = (rng.randint(-8, 9) for _ in range(4))
        if a * d - b * c and all(value != 0 for value in (a, b, c, d)):
            break
    x, y = rng.randint(-12, 20), rng.randint(-12, 20)
    e, f = a * x + b * y, c * x + d * y
    return _item(
        identifier,
        difficulty,
        "system_2x2",
        (a, b, c, d, e, f),
        f"Solve the system {a}x + {b}y = {e} and {c}x + {d}y = {f}. What is x?",
        x,
    )


def _conditional_sampling(rng, identifier, difficulty):
    red, blue = rng.randint(3, 14), rng.randint(3, 14)
    favorable = math.comb(red, 2)
    conditioned = math.comb(red + blue, 2) - math.comb(blue, 2)
    answer = round(100 * favorable / conditioned, 2)
    return _item(
        identifier,
        difficulty,
        "conditional_sampling",
        (red, blue),
        f"An urn has {red} red and {blue} blue balls. Two are drawn without replacement. "
        "Given that at least one is red, what is the probability that both are red, as a percentage?",
        answer,
        0.01,
    )


def _committee_constraints(rng, identifier, difficulty):
    engineers, designers = rng.randint(5, 12), rng.randint(4, 10)
    committee_size = rng.choice((4, 5, 6))
    minimum_engineers = rng.randint(2, committee_size - 1)
    answer = sum(
        math.comb(engineers, chosen) * math.comb(designers, committee_size - chosen)
        for chosen in range(minimum_engineers, committee_size)
        if chosen <= engineers and 1 <= committee_size - chosen <= designers
    )
    return _item(
        identifier,
        difficulty,
        "committee_constraints",
        (engineers, designers, committee_size, minimum_engineers),
        f"From {engineers} engineers and {designers} designers, how many {committee_size}-person "
        f"committees contain at least {minimum_engineers} engineers and at least one designer?",
        answer,
    )


def _modular_exponentiation(rng, identifier, difficulty):
    base = rng.randint(7, 60)
    exponent = rng.randint(80, 800)
    modulus = rng.choice((29, 31, 37, 41, 43, 47, 53, 59, 61))
    return _item(
        identifier,
        difficulty,
        "modular_exponentiation",
        (base, exponent, modulus),
        f"What is the least nonnegative remainder of {base}^{exponent} modulo {modulus}?",
        pow(base, exponent, modulus),
    )


def _crt_search(moduli, residues):
    product = math.prod(moduli)
    for value in range(product):
        if all(value % modulus == residue for modulus, residue in zip(moduli, residues)):
            return value
    raise AssertionError("coprime CRT construction must resolve")


def _crt(rng, identifier, difficulty):
    moduli = rng.sample((7, 11, 13, 17, 19, 23), 3)
    product = math.prod(moduli)
    hidden = rng.randrange(product)
    residues = [hidden % modulus for modulus in moduli]
    return _item(
        identifier,
        difficulty,
        "crt",
        (*moduli, *residues),
        f"Find the least nonnegative x with remainders {residues[0]}, {residues[1]}, and "
        f"{residues[2]} modulo {moduli[0]}, {moduli[1]}, and {moduli[2]}, respectively.",
        hidden,
    )


def _diophantine_dp(a, b, c, target, xmax, ymax, zmax):
    ways = [0] * (target + 1)
    ways[0] = 1
    for coefficient, bound in ((a, xmax), (b, ymax), (c, zmax)):
        updated = [0] * (target + 1)
        for subtotal, count in enumerate(ways):
            if count:
                for value in range(bound + 1):
                    if subtotal + coefficient * value <= target:
                        updated[subtotal + coefficient * value] += count
        ways = updated
    return ways[target]


def _bounded_diophantine(rng, identifier, difficulty):
    while True:
        a, b, c = rng.sample(range(3, 13), 3)
        xmax, ymax, zmax = (rng.randint(5, 12) for _ in range(3))
        target = rng.randint(30, 100)
        answer = _diophantine_dp(a, b, c, target, xmax, ymax, zmax)
        if 2 <= answer <= 40:
            break
    return _item(
        identifier,
        difficulty,
        "bounded_diophantine",
        (a, b, c, target, xmax, ymax, zmax),
        f"How many integer triples (x,y,z) satisfy {a}x + {b}y + {c}z = {target}, with "
        f"0<=x<={xmax}, 0<=y<={ymax}, and 0<=z<={zmax}?",
        answer,
    )


def _inclusion_exclusion3(rng, identifier, difficulty):
    triple = rng.randint(2, 12)
    ab_only, ac_only, bc_only = (rng.randint(3, 18) for _ in range(3))
    only_a, only_b, only_c = (rng.randint(8, 35) for _ in range(3))
    ab, ac, bc = ab_only + triple, ac_only + triple, bc_only + triple
    a = only_a + ab_only + ac_only + triple
    b = only_b + ab_only + bc_only + triple
    c = only_c + ac_only + bc_only + triple
    union = only_a + only_b + only_c + ab_only + ac_only + bc_only + triple
    return _item(
        identifier,
        difficulty,
        "inclusion_exclusion3",
        (a, b, c, ab, ac, bc, triple),
        f"Sets A, B, C have sizes {a}, {b}, {c}; pairwise intersections |A∩B|={ab}, "
        f"|A∩C|={ac}, |B∩C|={bc}; and |A∩B∩C|={triple}. What is |A∪B∪C|?",
        union,
    )


def _recurrence_iter(a, b, u0, u1, n, modulus):
    previous, current = u0 % modulus, u1 % modulus
    for _ in range(2, n + 1):
        previous, current = current, (a * current + b * previous) % modulus
    return current if n else previous


def _parameterized_recurrence(rng, identifier, difficulty):
    a, b = rng.randint(2, 9), rng.randint(1, 8)
    u0, u1 = rng.randint(0, 30), rng.randint(0, 30)
    n = rng.randint(35, 120)
    modulus = rng.choice((97, 101, 103, 107, 109, 113))
    answer = _recurrence_iter(a, b, u0, u1, n, modulus)
    return _item(
        identifier,
        difficulty,
        "parameterized_recurrence",
        (a, b, u0, u1, n, modulus),
        f"Let u0={u0}, u1={u1}, and un=({a}u(n-1)+{b}u(n-2)) mod {modulus}. What is u{n}?",
        answer,
    )


def _arrangement_count(params):
    n, adjacent_a, adjacent_b, before_a, before_b, excluded, excluded_position = params

    @lru_cache(maxsize=None)
    def extend(prefix):
        if len(prefix) == n:
            locations = {person: index for index, person in enumerate(prefix)}
            return int(
                abs(locations[adjacent_a] - locations[adjacent_b]) == 1
                and locations[before_a] < locations[before_b]
                and locations[excluded] != excluded_position
            )
        return sum(extend(prefix + (person,)) for person in range(n) if person not in prefix)

    return extend(())


def _constrained_arrangements(rng, identifier, difficulty):
    n = rng.choice((7, 8))
    while True:
        adjacent_a, adjacent_b = rng.sample(range(n), 2)
        before_a, before_b = rng.sample(range(n), 2)
        excluded = rng.randrange(n)
        excluded_position = rng.randrange(n)
        params = (n, adjacent_a, adjacent_b, before_a, before_b, excluded, excluded_position)
        answer = _arrangement_count(params)
        if answer:
            break
    labels = [chr(ord("A") + index) for index in range(n)]
    return _item(
        identifier,
        difficulty,
        "constrained_arrangements",
        params,
        f"{', '.join(labels)} stand in a line. {labels[adjacent_a]} and {labels[adjacent_b]} "
        f"must be adjacent; {labels[before_a]} must be before {labels[before_b]}; and "
        f"{labels[excluded]} cannot occupy position {excluded_position + 1}. How many arrangements are possible?",
        answer,
    )


_MAKERS = {
    "percent_chain": _percent_chain,
    "average_update": _average_update,
    "linear_equation": _linear_equation,
    "ratio_conversion": _ratio_conversion,
    "quadratic_sequence": _quadratic_sequence,
    "combined_rates": _combined_rates,
    "system_2x2": _system_2x2,
    "conditional_sampling": _conditional_sampling,
    "committee_constraints": _committee_constraints,
    "modular_exponentiation": _modular_exponentiation,
    "crt": _crt,
    "bounded_diophantine": _bounded_diophantine,
    "inclusion_exclusion3": _inclusion_exclusion3,
    "parameterized_recurrence": _parameterized_recurrence,
    "constrained_arrangements": _constrained_arrangements,
}


def _matrix_multiply(left, right, modulus):
    return (
        (
            (left[0][0] * right[0][0] + left[0][1] * right[1][0]) % modulus,
            (left[0][0] * right[0][1] + left[0][1] * right[1][1]) % modulus,
        ),
        (
            (left[1][0] * right[0][0] + left[1][1] * right[1][0]) % modulus,
            (left[1][0] * right[0][1] + left[1][1] * right[1][1]) % modulus,
        ),
    )


def _recurrence_matrix(a, b, u0, u1, n, modulus):
    if n == 0:
        return u0 % modulus
    power = n - 1
    result = ((1, 0), (0, 1))
    base = ((a, b), (1, 0))
    while power:
        if power & 1:
            result = _matrix_multiply(result, base, modulus)
        base = _matrix_multiply(base, base, modulus)
        power //= 2
    return (result[0][0] * u1 + result[0][1] * u0) % modulus


def independent_answer(item):
    """Compute ground truth through an expression independent of its generator."""
    p = item["params"]
    kind = item["kind"]
    if kind == "percent_chain":
        return _decimal2(
            Decimal(p[0])
            * (Decimal(1) + Decimal(p[1]) / Decimal(100))
            * (Decimal(1) - Decimal(p[2]) / Decimal(100))
        )
    if kind == "average_update":
        return round((p[0] + p[2]) / (p[1] + 1), 2)
    if kind == "linear_equation":
        return (p[2] - p[1]) // p[0]
    if kind == "ratio_conversion":
        return p[2] // (p[0] + p[1]) * p[0]
    if kind == "quadratic_sequence":
        return p[0] * p[3] ** 2 + p[1] * p[3] + p[2]
    if kind == "combined_rates":
        return round(math.prod(p) / sum(math.prod(p) // value for value in p), 2)
    if kind == "system_2x2":
        a, b, c, d, e, f = p
        return (e * d - b * f) // (a * d - b * c)
    if kind == "conditional_sampling":
        red, blue = p
        valid_pairs = [(a, b) for a in range(red + blue) for b in range(a + 1, red + blue)
                       if a < red or b < red]
        red_pairs = [(a, b) for a, b in valid_pairs if a < red and b < red]
        return round(100 * len(red_pairs) / len(valid_pairs), 2)
    if kind == "committee_constraints":
        engineers, designers, size, minimum = p
        labels = [(group, number) for group, total in (("e", engineers), ("d", designers))
                  for number in range(total)]
        return sum(
            1
            for chosen in itertools.combinations(labels, size)
            if sum(group == "e" for group, _ in chosen) >= minimum
            and any(group == "d" for group, _ in chosen)
        )
    if kind == "modular_exponentiation":
        result = 1
        for _ in range(p[1]):
            result = result * p[0] % p[2]
        return result
    if kind == "crt":
        return _crt_search(p[:3], p[3:])
    if kind == "bounded_diophantine":
        a, b, c, target, xmax, ymax, zmax = p
        return sum(
            a * x + b * y + c * z == target
            for x in range(xmax + 1)
            for y in range(ymax + 1)
            for z in range(zmax + 1)
        )
    if kind == "inclusion_exclusion3":
        a, b, c, ab, ac, bc, abc = p
        return a + b + c - ab - ac - bc + abc
    if kind == "parameterized_recurrence":
        return _recurrence_matrix(*p)
    if kind == "constrained_arrangements":
        n, adjacent_a, adjacent_b, before_a, before_b, excluded, excluded_position = p
        count = 0
        for order in itertools.permutations(range(n)):
            location = {person: position for position, person in enumerate(order)}
            count += (
                abs(location[adjacent_a] - location[adjacent_b]) == 1
                and location[before_a] < location[before_b]
                and location[excluded] != excluded_position
            )
        return count
    raise ValueError(kind)


def generate_pool(seed=20260712):
    rng = random.Random(seed)
    pool = []
    questions = set()
    for difficulty, kinds in TEMPLATES.items():
        for kind in kinds:
            seen_params = set()
            for index in range(20):
                identifier = f"math-{difficulty}-{kind}-{index + 1:02d}"
                for _ in range(100):
                    item = _MAKERS[kind](rng, identifier, difficulty)
                    signature = tuple(item["params"])
                    if signature not in seen_params and item["q"] not in questions:
                        break
                else:
                    raise ValueError(f"could not generate unique {kind} item")
                seen_params.add(signature)
                questions.add(item["q"])
                if independent_answer(item) != item["answer"]:
                    raise ValueError(f"independent verification failed: {identifier}")
                pool.append(item)
    return pool


def sample_pool(pool, seed, count_per_template=2):
    rng = random.Random(seed)
    selected = []
    for difficulty in ("easy", "med", "hard"):
        for kind in TEMPLATES[difficulty]:
            candidates = [
                item
                for item in pool
                if item["difficulty"] == difficulty and item["kind"] == kind
            ]
            selected.extend(rng.sample(candidates, count_per_template))
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--out", type=Path, default=Path("math_pool.json"))
    parser.add_argument("--sample-out", type=Path)
    args = parser.parse_args()
    pool = generate_pool(args.seed)
    args.out.write_text(json.dumps(pool, indent=2) + "\n")
    if args.sample_out:
        args.sample_out.write_text(json.dumps(sample_pool(pool, args.seed), indent=2) + "\n")


if __name__ == "__main__":
    main()
