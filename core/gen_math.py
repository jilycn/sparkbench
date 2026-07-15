#!/usr/bin/env python3
"""Generate the deterministic SparkBench v2 stratified math pool."""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path


def _item(identifier, difficulty, kind, params, question, answer, tol=0.0):
    return {"id": identifier, "difficulty": difficulty, "kind": kind, "params": params,
            "q": question + " Answer format: {\"answer\": <number>}.", "answer": answer,
            "tol": tol, "numeric": True}


def _easy(rng, identifier, difficulty):
    kind = identifier % 4
    if kind == 0:
        price, discount, tax = rng.randint(80, 800), rng.choice((5, 10, 15, 20)), rng.choice((4, 6, 8, 10))
        return _item(f"{difficulty}-{identifier:03}", difficulty, "discount_tax", [price, discount, tax],
                     f"A device costs ${price}, is discounted {discount}%, then has {tax}% tax added.",
                     round(price * (1 - discount / 100) * (1 + tax / 100), 2), 0.01)
    if kind == 1:
        total, n, removed = rng.randint(500, 1200), rng.randint(8, 16), rng.randint(10, 90)
        return _item(f"{difficulty}-{identifier:03}", difficulty, "average_remove", [total, n, removed],
                     f"The sum of {n} numbers is {total}. After removing {removed}, what is the new average?",
                     round((total - removed) / (n - 1), 2), 0.01)
    if kind == 2:
        base, exponent, modulus = rng.randint(5, 17), rng.randint(20, 80), rng.choice((11, 13, 17, 19))
        return _item(f"{difficulty}-{identifier:03}", difficulty, "modpow", [base, exponent, modulus],
                     f"What is the remainder when {base}^{exponent} is divided by {modulus}?",
                     pow(base, exponent, modulus))
    a, b, c = rng.randint(20, 90), rng.randint(10, 50), rng.randint(4, 19)
    return _item(f"{difficulty}-{identifier:03}", difficulty, "linear", [a, b, c],
                 f"Solve for x: {a}x + {b} = {c * a + b}.", c)


def _medium(rng, identifier, difficulty):
    kind = identifier % 4
    if kind == 0:
        first, second = rng.randint(4, 12), rng.randint(8, 20)
        return _item(f"{difficulty}-{identifier:03}", difficulty, "work_rate", [first, second],
                     f"A job takes worker A {first} hours and worker B {second} hours alone. How many hours together?",
                     round(1 / (1 / first + 1 / second), 2), 0.01)
    if kind == 1:
        engineers, designers = rng.randint(7, 14), rng.randint(8, 15)
        return _item(f"{difficulty}-{identifier:03}", difficulty, "committee", [engineers, designers],
                     f"How many committees use 2 of {engineers} engineers and 3 of {designers} designers?",
                     math.comb(engineers, 2) * math.comb(designers, 3))
    if kind == 2:
        left, right, speed_a, speed_b = rng.randint(200, 800), 0, rng.randint(35, 90), rng.randint(35, 90)
        distance = left - right
        return _item(f"{difficulty}-{identifier:03}", difficulty, "meeting", [distance, speed_a, speed_b],
                     f"Two trains are {distance} km apart and travel toward each other at {speed_a} and {speed_b} km/h. When meet?",
                     round(distance / (speed_a + speed_b), 2), 0.01)
    x, y = rng.randint(3, 15), rng.randint(5, 20)
    return _item(f"{difficulty}-{identifier:03}", difficulty, "two_equations", [x, y],
                 f"3 apples and 2 bananas cost {3*x + 2*y}. One apple and 4 bananas cost {x + 4*y}. What is one apple's cost?", x)


def _hard(rng, identifier, difficulty):
    kind = identifier % 4
    if kind == 0:
        a, b, c = rng.choice((7, 11, 13)), rng.choice((17, 19, 23)), rng.choice((29, 31, 37))
        value = rng.randint(1, a * b * c - 1)
        residues = [value % a, value % b, value % c]
        return _item(f"{difficulty}-{identifier:03}", difficulty, "crt", [a, b, c, *residues],
                     f"Find the least nonnegative x with remainders {residues[0]}, {residues[1]}, {residues[2]} modulo {a}, {b}, {c}.",
                     _crt(a, b, c, *residues))
    if kind == 1:
        n, k = rng.randint(18, 40), rng.randint(5, 12)
        return _item(f"{difficulty}-{identifier:03}", difficulty, "binomial", [n, k],
                     f"Compute the binomial coefficient C({n}, {k}).", math.comb(n, k))
    if kind == 2:
        start, end = rng.randint(20, 80), rng.randint(100, 220)
        return _item(f"{difficulty}-{identifier:03}", difficulty, "sum_squares", [start, end],
                     f"Compute the sum of squares from {start} through {end}, inclusive.",
                     _sum_squares(end) - _sum_squares(start - 1))
    principal, rate, years = rng.randint(1000, 9000), rng.choice((3, 4, 5, 6, 7)), rng.randint(5, 12)
    return _item(f"{difficulty}-{identifier:03}", difficulty, "compound", [principal, rate, years],
                 f"What is ${principal} compounded annually at {rate}% for {years} years?",
                 round(principal * (1 + rate / 100) ** years, 2), 0.01)


def _sum_squares(n):
    return n * (n + 1) * (2 * n + 1) // 6


def _crt(a, b, c, ra, rb, rc):
    for value in range(a * b * c):
        if value % a == ra and value % b == rb and value % c == rc:
            return value
    raise AssertionError("coprime CRT construction must resolve")


def generate_pool(seed=20260712):
    rng = random.Random(seed)
    makers = {"easy": _easy, "med": _medium, "hard": _hard}
    pool = []
    for difficulty in ("easy", "med", "hard"):
        for index in range(100):
            pool.append(makers[difficulty](rng, index, difficulty))
    return pool


def independent_answer(item):
    """A separately expressed verifier used by tests and materialization."""
    p = item["params"]
    kind = item["kind"]
    if kind == "discount_tax": return round(p[0] * (100 - p[1]) * (100 + p[2]) / 10000, 2)
    if kind == "average_remove": return round((p[0] - p[2]) / (p[1] - 1), 2)
    if kind == "modpow": return pow(*p)
    if kind == "linear": return (p[2] * p[0] + p[1] - p[1]) // p[0]
    if kind == "work_rate": return round((p[0] * p[1]) / (p[0] + p[1]), 2)
    if kind == "committee": return math.factorial(p[0]) // (2 * math.factorial(p[0] - 2)) * (math.factorial(p[1]) // (6 * math.factorial(p[1] - 3)))
    if kind == "meeting": return round(p[0] / sum(p[1:]), 2)
    if kind == "two_equations": return p[0]
    if kind == "crt": return _crt(*p)
    if kind == "binomial": return math.comb(*p)
    if kind == "sum_squares": return _sum_squares(p[1]) - _sum_squares(p[0] - 1)
    if kind == "compound": return round(p[0] * pow(1 + p[1] / 100, p[2]), 2)
    raise ValueError(kind)


def sample_pool(pool, seed, count_per_difficulty=10):
    rng = random.Random(seed)
    selected = []
    for difficulty in ("easy", "med", "hard"):
        selected.extend(rng.sample([item for item in pool if item["difficulty"] == difficulty], count_per_difficulty))
    return selected


def stress_suite():
    return [
        _item("stress-crt", "stress", "crt", [17, 19, 23, 8, 4, 7], "Find least x with remainders 8, 4, 7 modulo 17, 19, 23.", _crt(17, 19, 23, 8, 4, 7)),
        _item("stress-binomial", "stress", "binomial", [52, 11], "Compute C(52, 11).", math.comb(52, 11)),
        _item("stress-squares", "stress", "sum_squares", [1, 10000], "Compute the sum of squares from 1 through 10000.", _sum_squares(10000)),
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--out", type=Path, default=Path("."))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "math_pool.json").write_text(json.dumps(generate_pool(args.seed), indent=2) + "\n")
    (args.out / "math_stress.json").write_text(json.dumps(stress_suite(), indent=2) + "\n")


if __name__ == "__main__":
    main()
