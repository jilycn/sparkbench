#!/usr/bin/env python3
"""Generate 10 multi-step math problems with programmatic ground truth -> math_suite.json"""
import json, math, random

random.seed(20260712)
P = []

# 1 discount chain + tax
p = random.randint(200, 900); a = random.choice([10, 15, 20]); b = random.choice([5, 12, 25]); t = random.choice([7, 8, 9])
ans = round(p * (1 - a/100) * (1 - b/100) * (1 + t/100), 2)
P.append({"id": "m1", "q": f"A jacket costs ${p}. It is discounted {a}%, then an additional {b}% off the reduced price. Finally {t}% sales tax is added. What is the final price in dollars? Answer format: {{\"answer\": <number>}} (round to 2 decimals)", "answer": ans, "tol": 0.01})

# 2 work rate
x = random.randint(4, 9); y = random.randint(10, 18)
ans = round(1 / (1/x + 1/y), 2)
P.append({"id": "m2", "q": f"Worker A paints a room alone in {x} hours. Worker B does it alone in {y} hours. Working together at these rates, how many hours to paint one room? Answer format: {{\"answer\": <number>}} (round to 2 decimals)", "answer": ans, "tol": 0.01})

# 3 mixture
m1_ = random.randint(3, 8); pc1 = random.choice([10, 20, 30]); m2_ = random.randint(2, 6); pc2 = random.choice([50, 60, 70])
ans = round((m1_*pc1 + m2_*pc2) / (m1_+m2_), 2)
P.append({"id": "m3", "q": f"You mix {m1_} liters of a {pc1}% acid solution with {m2_} liters of a {pc2}% acid solution. What is the acid concentration percentage of the mixture? Answer format: {{\"answer\": <number>}} (round to 2 decimals)", "answer": ans, "tol": 0.01})

# 4 compound interest
pr = random.choice([1000, 2500, 4000]); r = random.choice([4, 6, 8]); yrs = random.choice([3, 5])
ans = round(pr * (1 + r/100) ** yrs, 2)
P.append({"id": "m4", "q": f"${pr} is invested at {r}% annual compound interest. What is the total amount after {yrs} years? Answer format: {{\"answer\": <number>}} (round to 2 decimals)", "answer": ans, "tol": 0.01})

# 5 trains meet
d = random.choice([300, 420, 540]); v1 = random.randint(40, 70); v2 = random.randint(50, 90)
ans = round(d / (v1 + v2), 2)
P.append({"id": "m5", "q": f"Two trains start at the same time from stations {d} km apart, heading toward each other at {v1} km/h and {v2} km/h. After how many hours do they meet? Answer format: {{\"answer\": <number>}} (round to 2 decimals)", "answer": ans, "tol": 0.01})

# 6 LCM bells
vals = random.sample([4, 6, 9, 10, 14, 15], 3)
ans = math.lcm(*vals)
P.append({"id": "m6", "q": f"Three bells ring every {vals[0]}, {vals[1]}, and {vals[2]} minutes. They all ring together at noon. After how many minutes do they next all ring together? Answer format: {{\"answer\": <int>}}", "answer": ans, "tol": 0})

# 7 committees
ga = random.randint(6, 9); gb = random.randint(7, 10)
ans = math.comb(ga, 2) * math.comb(gb, 3)
P.append({"id": "m7", "q": f"A committee needs exactly 2 members chosen from {ga} engineers and exactly 3 members chosen from {gb} designers. How many different committees are possible? Answer format: {{\"answer\": <int>}}", "answer": ans, "tol": 0})

# 8 modular power
base = random.randint(7, 13); ex = random.randint(50, 90); mod = random.choice([11, 13, 17])
ans = pow(base, ex, mod)
P.append({"id": "m8", "q": f"What is the remainder when {base}^{ex} is divided by {mod}? Answer format: {{\"answer\": <int>}}", "answer": ans, "tol": 0})

# 9 average after removal
n = random.randint(8, 12); avg = random.randint(50, 80); rem = random.randint(20, 45)
total = n * avg
ans = round((total - rem) / (n - 1), 2)
P.append({"id": "m9", "q": f"The average of {n} numbers is {avg}. One number, {rem}, is removed. What is the average of the remaining {n-1} numbers? Answer format: {{\"answer\": <number>}} (round to 2 decimals)", "answer": ans, "tol": 0.01})

# 10 linear system
import fractions
aa = random.randint(2, 5); bb = random.randint(6, 12)   # true prices
X = 3*aa + 2*bb; Y = aa + 4*bb
P.append({"id": "m10", "q": f"3 apples and 2 bananas cost ${X}. 1 apple and 4 bananas cost ${Y}. What does one apple cost in dollars? Answer format: {{\"answer\": <number>}}", "answer": aa, "tol": 0.01})

json.dump(P, open("math_suite.json", "w"), indent=2)
print(f"{len(P)} problems")
for p in P:
    print(p["id"], "=", p["answer"])
