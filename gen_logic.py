#!/usr/bin/env python3
"""Generate logic puzzles with brute-force-verified unique answers -> logic_suite.json"""
import itertools, json, random

random.seed(20260711)
puzzles = []

# ---- 1-3: Knights & Knaves (knight=truth, knave=lies), brute-forced ----
def kk_solve(n, checks):
    sols = [a for a in itertools.product([True, False], repeat=n) if all(c(a) for c in checks)]
    return sols

names3 = ["Aris", "Bo", "Cyra"]
# P1: Aris: "Bo is a knave". Bo: "Aris and Cyra are the same kind". Cyra: "I am a knight".
c1 = [lambda a: a[0] == (not a[1]),
      lambda a: a[1] == ((a[0] == a[2])),
      lambda a: a[2] == a[2] or True]  # "I am a knight" always consistent -> constraint: statement truth == speaker type
c1[2] = lambda a: a[2] == (a[2])
puzzles.append({
    "id": "kk1",
    "q": "On an island, knights always tell the truth and knaves always lie. Three islanders: Aris says 'Bo is a knave.' Bo says 'Aris and Cyra are the same kind.' Cyra says 'I am a knight.' Cyra is known to be of the opposite kind to Bo. For each of Aris, Bo, Cyra answer knight or knave. Answer format: {\"Aris\":\"knight|knave\",\"Bo\":...,\"Cyra\":...}",
    "check": "kk1"})
# add external constraint Cyra opposite Bo for uniqueness
c1b = c1 + [lambda a: a[2] != a[1]]
s1 = kk_solve(3, c1b)
assert len(s1) == 1, f"kk1 not unique: {s1}"
puzzles[-1]["answer"] = {n: ("knight" if v else "knave") for n, v in zip(names3, s1[0])}

# P2: 4 people
names4 = ["Dax", "Eli", "Fern", "Gus"]
c2 = [lambda a: a[0] == (a[1] and a[2]),                    # Dax: "Eli and Fern are both knights"
      lambda a: a[1] == (not a[3]),                          # Eli: "Gus is a knave"
      lambda a: a[2] == (a[0] != a[3]),                      # Fern: "Dax and Gus are different kinds"
      lambda a: a[3] == (sum(a) == 2),                       # Gus: "Exactly two of us are knights"
      lambda a: not a[1]]                                    # known fact: Eli is a knave
s2 = kk_solve(4, c2)
assert len(s2) == 1, f"kk2 not unique: {s2}"
puzzles.append({
    "id": "kk2",
    "q": "Knights always tell truth, knaves always lie. Dax says 'Eli and Fern are both knights.' Eli says 'Gus is a knave.' Fern says 'Dax and Gus are different kinds.' Gus says 'Exactly two of the four of us are knights.' It is also known that Eli is a knave. For each of Dax, Eli, Fern, Gus answer knight or knave. Answer format: {\"Dax\":...,\"Eli\":...,\"Fern\":...,\"Gus\":...}",
    "answer": {n: ("knight" if v else "knave") for n, v in zip(names4, s2[0])},
    "check": "exact"})

# ---- 3: Grid puzzle 4 houses (color, pet, drink) ----
colors = ["red", "blue", "green", "white"]
pets = ["cat", "dog", "fish", "bird"]
drinks = ["tea", "coffee", "milk", "juice"]
sols = []
for pc in itertools.permutations(colors):
    for pp in itertools.permutations(pets):
        for pd in itertools.permutations(drinks):
            # positions 0..3 left to right
            def pos(seq, v): return seq.index(v)
            if pos(pc, "red") != 0: continue                       # red house is leftmost
            if abs(pos(pp, "cat") - pos(pc, "blue")) != 1: continue  # cat owner next to blue house
            if pos(pd, "milk") != pos(pc, "green"): continue       # green house drinks milk
            if pos(pp, "dog") != 3: continue                       # dog in rightmost house
            if pos(pd, "tea") != pos(pp, "cat"): continue          # cat owner drinks tea
            if abs(pos(pd, "coffee") - pos(pd, "milk")) != 1: continue  # coffee next to milk
            if pos(pc, "white") == 1: continue                     # white house is not second
            if pos(pp, "fish") >= pos(pp, "bird"): continue        # fish is left of bird
            if pos(pd, "juice") != 3: continue                     # juice drinker rightmost
            if pos(pc, "blue") != 1: continue                      # blue house position 2
            sols.append((pc, pp, pd))
assert len(sols) == 1, f"grid not unique: {len(sols)}"
pc, pp, pd = sols[0]
fish_pos = pp.index("fish")
puzzles.append({
    "id": "grid1",
    "q": "Four houses in a row, positions 1-4 left to right. Each house has a unique color (red, blue, green, white), pet (cat, dog, fish, bird), drink (tea, coffee, milk, juice). Clues: 1) The red house is leftmost. 2) The cat owner lives next to the blue house. 3) The green house's owner drinks milk. 4) The dog lives in the rightmost house. 5) The cat owner drinks tea. 6) The coffee drinker lives next to the milk drinker. 7) The white house is not in position 2. 8) The fish is somewhere left of the bird. 9) The juice drinker lives in the rightmost house. 10) The blue house is in position 2. Which position (1-4) has the fish, and what color is that house? Answer format: {\"position\": <int>, \"color\": \"<color>\"}",
    "answer": {"position": fish_pos + 1, "color": pc[fish_pos]},
    "check": "exact"})

# ---- 4: Seating circle ----
# 5 people round table: brute force
ppl = ["P", "Q", "R", "S", "T"]
seat_sols = []
for perm in itertools.permutations(ppl[1:]):
    arr = ["P"] + list(perm)  # fix P at seat 0 (rotational symmetry broken by clue seats numbered)
    for rot in range(5):
        a = arr[rot:] + arr[:rot]
        def idx(x): return a.index(x)
        def adj(x, y): return abs(idx(x) - idx(y)) in (1, 4)
        if idx("P") != 0: continue                 # P sits in seat 1 (index 0)
        if not adj("Q", "P"): continue             # Q next to P
        if adj("R", "P"): continue                 # R not next to P
        if idx("S") == 2: continue                 # S not in seat 3
        if not adj("T", "R"): continue             # T next to R
        if adj("T", "Q"): continue                 # T not adjacent to Q
        if idx("Q") != 1: continue                 # Q clockwise-next to P (seat 2)
        seat_sols.append(tuple(a))
seat_sols = sorted(set(seat_sols))
assert len(seat_sols) == 1, f"seat not unique: {seat_sols}"
arrangement = seat_sols[0]
puzzles.append({
    "id": "seat1",
    "q": "Five people P,Q,R,S,T sit at a round table with seats numbered 1-5 clockwise. P sits in seat 1. Q sits in seat 2 (immediately clockwise of P). R is not adjacent to P. S is not in seat 3. T is adjacent to R but NOT adjacent to Q. Who sits in each seat? Answer format: {\"1\":\"P\",\"2\":...,\"3\":...,\"4\":...,\"5\":...}",
    "answer": {str(i + 1): arrangement[i] for i in range(5)},
    "check": "exact"})

# ---- 5: Number deduction ----
# unique x: 2-digit, digit sum 11, divisible by 4, tens digit > units digit
cands = [x for x in range(10, 100) if sum(map(int, str(x))) == 11 and x % 4 == 0 and str(x)[0] > str(x)[1]]
assert len(cands) == 1, cands
puzzles.append({
    "id": "num1",
    "q": "Find the two-digit number where: digits sum to 11, the number is divisible by 4, and the tens digit is greater than the units digit. Answer format: {\"number\": <int>}",
    "answer": {"number": cands[0]},
    "check": "exact"})

# ---- 6: Scheduling ----
# 5 tasks A-E one per day Mon-Fri
tasks = ["A", "B", "C", "D", "E"]
days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
sch_sols = []
for perm in itertools.permutations(range(5)):
    d = dict(zip(tasks, perm))  # task -> day index
    if d["A"] >= d["C"]: continue          # A before C
    if d["B"] != d["A"] + 1: continue      # B immediately after A
    if d["D"] == 0 or d["D"] == 4: continue  # D not Mon or Fri
    if d["E"] != 4 and d["E"] != 0: continue  # E is Mon or Fri
    if d["E"] == 0: continue               # E is not Mon
    if d["C"] <= d["D"]: continue          # C after D
    sch_sols.append(d)
assert len(sch_sols) == 1, sch_sols
d = sch_sols[0]
puzzles.append({
    "id": "sched1",
    "q": "Five tasks A,B,C,D,E scheduled one per day Mon-Fri. Constraints: A is before C. B is the day immediately after A. D is not on Mon or Fri. E is on Mon or Fri, but not Mon. C is after D. Which day is each task? Answer format: {\"A\":\"Mon|Tue|Wed|Thu|Fri\",\"B\":...,\"C\":...,\"D\":...,\"E\":...}",
    "answer": {t: days[d[t]] for t in tasks},
    "check": "exact"})

# ---- 7: Truth chain / implication ----
# brute force over 4 booleans: rain, wind, cold, snow
imp_sols = []
for rain, wind, cold, snow in itertools.product([True, False], repeat=4):
    if (rain and not cold): continue           # if rain then cold
    if (cold and not (wind or snow)): continue  # if cold then wind or snow
    if snow != (not rain): continue            # snows iff no rain
    if not wind: continue                      # wind is true
    if rain: continue                          # given: no rain... need uniqueness; instead: exactly? let's collect
    imp_sols.append((rain, wind, cold, snow))
# constraints as stated give: no-rain, wind, snow?, cold? -> check uniqueness with extra clue "cold is true"
imp_sols = [(r, w, c, s) for (r, w, c, s) in
            [(r, w, c, s) for r, w, c, s in itertools.product([True, False], repeat=4)]
            if (not r or c) and (not c or (w or s)) and (s == (not r)) and w and c and (not w or not r)]
assert len(imp_sols) == 1, imp_sols
r, w, c, s = imp_sols[0]
puzzles.append({
    "id": "logic1",
    "q": "Four weather facts (each true or false): rain, wind, cold, snow. Rules: If it rains, it is cold. If it is cold, there is wind or snow (or both). It snows if and only if it does not rain. If there is wind, it does not rain. There IS wind. It IS cold. Determine rain and snow. Answer format: {\"rain\": true|false, \"snow\": true|false}",
    "answer": {"rain": r, "snow": s},
    "check": "exact"})

# ---- 8: Ordering/race ----
race_sols = []
for perm in itertools.permutations(["U", "V", "W", "X", "Y"]):
    p = {name: i for i, name in enumerate(perm)}  # 0 = first
    if p["U"] >= p["V"]: continue        # U beat V
    if abs(p["W"] - p["U"]) != 1: continue  # W finished adjacent to U
    if p["X"] == 0: continue             # X not first
    if p["Y"] != 4 and p["X"] != 4: continue  # Y or X last
    if p["V"] != 2: continue             # V finished third
    if p["W"] >= p["V"]: continue        # W beat V
    if p["W"] != 0: continue             # W was first
    if p["Y"] != 4: continue             # Y was last
    race_sols.append(perm)
race_sols = sorted(set(race_sols))
assert len(race_sols) == 1, race_sols
puzzles.append({
    "id": "race1",
    "q": "Five runners U,V,W,X,Y finish a race, no ties. U beat V. W finished immediately before or after U. X was not first. Either Y or X was last. V finished exactly third. W beat V. W was first. Y was last. Give finishing order first to last. Answer format: {\"order\": [\"first\",...,\"last\"]}",
    "answer": {"order": list(race_sols[0])},
    "check": "exact"})

# ---- 9: Set intersection counting ----
# 30 students, 18 math, 15 physics, 6 neither -> both = 18+15-(30-6)=9
both = 18 + 15 - (30 - 6)
puzzles.append({
    "id": "count1",
    "q": "In a class of 30 students, 18 study math, 15 study physics, and 6 study neither. How many study both math and physics? Answer format: {\"both\": <int>}",
    "answer": {"both": both},
    "check": "exact"})

# ---- 10: State search: water jugs ----
# 5L and 3L jugs, measure exactly 4L: min steps (fill/empty/pour counts as 1) -> BFS
from collections import deque
def jug_bfs():
    start = (0, 0); target = 4
    seen = {start}; q = deque([(start, 0)])
    while q:
        (a, b), d = q.popleft()
        if a == target or b == target: return d
        nxt = [(5, b), (a, 3), (0, b), (a, 0)]
        pour = min(a, 3 - b); nxt.append((a - pour, b + pour))
        pour2 = min(b, 5 - a); nxt.append((a + pour2, b - pour2))
        for s2 in nxt:
            if s2 not in seen:
                seen.add(s2); q.append((s2, d + 1))
    return -1
steps = jug_bfs()
puzzles.append({
    "id": "jug1",
    "q": "You have a 5-liter jug and a 3-liter jug, both empty, and unlimited water. Each action is one step: completely fill a jug, completely empty a jug, or pour from one jug to the other until the source is empty or the target is full. What is the minimum number of steps to have exactly 4 liters in one jug? Answer format: {\"steps\": <int>}",
    "answer": {"steps": steps},
    "check": "exact"})

json.dump(puzzles, open("logic_suite.json", "w"), indent=2)
print(f"{len(puzzles)} puzzles generated, all brute-force verified unique")
for p in puzzles:
    print(p["id"], "->", json.dumps(p["answer"]))
