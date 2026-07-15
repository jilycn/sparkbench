"""10 unseen edge probes for Part A judging (never shown to the model). 1 pt each."""
PROBES = [
    ("not_op", 'print(!(1 > 2));', [True]),
    ("string_eq", 'print("a" == "a"); print("a" != "b");', [True, True]),
    ("mod_loop", 'let i = 1; let s = 0; while (i <= 10) { if (i % 3 == 0) { s = s + i; } i = i + 1; } print(s);', [18]),
    ("and_in_while", 'let i = 0; let ok = true; while (ok && i < 4) { i = i + 1; if (i == 3) { ok = false; } } print(i);', [3]),
    ("return_in_while", 'func firstOver(limit) { let i = 0; while (true) { i = i + 7; if (i > limit) { return i; } } } print(firstOver(20));', [21]),
    ("curried", 'func add(a) { func inner(b) { func inner2(c) { return a + b + c; } return inner2; } return inner; } print(add(1)(2)(3));', [6]),
    ("closure_chain_shadow", 'let n = 100; func make(n) { func get() { return n; } return get; } let g = make(7); print(g()); print(n);', [7, 100]),
    ("deep_800", 'func count(n) { if (n == 0) { return 0; } return 1 + count(n - 1); } print(count(800));', [800]),
    ("arity_too_many", '__EXPECT_ARITY__ func f(a) { return a; } f(1, 2);', None),
    ("undef_in_func", '__EXPECT_UNDEF__ func f() { return ghost; } f();', None),
]

def run_probes(run, ArityError, UndefinedVariableError):
    results = {}
    for name, src, expect in PROBES:
        try:
            if src.startswith("__EXPECT_ARITY__"):
                try:
                    run(src.replace("__EXPECT_ARITY__", "", 1))
                    results[name] = False
                except ArityError:
                    results[name] = True
                except Exception:
                    results[name] = False
            elif src.startswith("__EXPECT_UNDEF__"):
                try:
                    run(src.replace("__EXPECT_UNDEF__", "", 1))
                    results[name] = False
                except UndefinedVariableError:
                    results[name] = True
                except Exception:
                    results[name] = False
            else:
                results[name] = (run(src) == expect)
        except Exception:
            results[name] = False
    return results

if __name__ == "__main__":
    import sys
    sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
    from interp import run, ArityError, UndefinedVariableError
    r = run_probes(run, ArityError, UndefinedVariableError)
    for k, v in r.items():
        print(("PASS" if v else "FAIL"), k)
    print(f"{sum(r.values())}/10")
