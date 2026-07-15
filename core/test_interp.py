import pytest
from interp import run, InterpreterError, UndefinedVariableError, ArityError

# run(source) executes a program and returns the list of values passed to print()

# ---- basics ----
def test_print_literal():
    assert run('print(42);') == [42]

def test_arith():
    assert run('print(2 + 3 * 4);') == [14]

def test_parens():
    assert run('print((2 + 3) * 4);') == [20]

def test_div_float():
    assert run('print(10 / 4);') == [2.5]

def test_mod():
    assert run('print(17 % 5);') == [2]

def test_unary_minus():
    assert run('print(-3 + 10);') == [7]

def test_string_literal():
    assert run('print("hello");') == ["hello"]

def test_string_concat():
    assert run('print("ab" + "cd");') == ["abcd"]

def test_bool_and_nil():
    assert run('print(true); print(false); print(nil);') == [True, False, None]

# ---- variables & scoping ----
def test_let_and_use():
    assert run('let x = 5; print(x + 1);') == [6]

def test_reassign():
    assert run('let x = 1; x = x + 41; print(x);') == [42]

def test_block_scope_shadow():
    src = 'let x = 1; if (true) { let x = 99; print(x); } print(x);'
    assert run(src) == [99, 1]

def test_assign_outer_from_block():
    src = 'let x = 1; if (true) { x = 50; } print(x);'
    assert run(src) == [50]

def test_undefined_var():
    with pytest.raises(UndefinedVariableError):
        run('print(nope);')

def test_undefined_assign():
    with pytest.raises(UndefinedVariableError):
        run('zzz = 3;')

# ---- comparisons & logic ----
def test_compare_ops():
    assert run('print(3 < 5); print(5 <= 5); print(6 > 7); print(4 >= 4); print(1 == 1); print(1 != 2);') == [True, True, False, True, True, True]

def test_and_or_shortcircuit():
    # right side of && must not run when left is false (would raise undefined var)
    assert run('print(false && nope); print(true || nope);') == [False, True]

# ---- control flow ----
def test_if_else():
    assert run('if (2 > 1) { print("yes"); } else { print("no"); }') == ["yes"]

def test_while_loop():
    src = 'let i = 0; let s = 0; while (i < 5) { i = i + 1; s = s + i; } print(s);'
    assert run(src) == [15]

def test_nested_while():
    src = 'let t = 0; let i = 0; while (i < 3) { let j = 0; while (j < 3) { t = t + 1; j = j + 1; } i = i + 1; } print(t);'
    assert run(src) == [9]

# ---- functions ----
def test_func_basic():
    assert run('func add(a, b) { return a + b; } print(add(2, 3));') == [5]

def test_func_no_return_gives_nil():
    assert run('func f() { let a = 1; } print(f());') == [None]

def test_early_return():
    src = 'func f(x) { if (x > 0) { return "pos"; } return "neg"; } print(f(5)); print(f(-5));'
    assert run(src) == ["pos", "neg"]

def test_recursion_fib():
    src = 'func fib(n) { if (n < 2) { return n; } return fib(n-1) + fib(n-2); } print(fib(12));'
    assert run(src) == [144]

def test_mutual_recursion():
    src = ('func isEven(n) { if (n == 0) { return true; } return isOdd(n - 1); } '
           'func isOdd(n) { if (n == 0) { return false; } return isEven(n - 1); } '
           'print(isEven(10)); print(isOdd(7));')
    assert run(src) == [True, True]

def test_arity_error():
    with pytest.raises(ArityError):
        run('func f(a, b) { return a; } f(1);')

def test_first_class_function():
    src = 'func double(x) { return x * 2; } func apply(f, v) { return f(v); } print(apply(double, 21));'
    assert run(src) == [42]

# ---- closures ----
def test_closure_capture():
    src = ('func makeAdder(n) { func add(x) { return x + n; } return add; } '
           'let add5 = makeAdder(5); print(add5(10));')
    assert run(src) == [15]

def test_closure_counter_mutates_env():
    src = ('func makeCounter() { let n = 0; func inc() { n = n + 1; return n; } return inc; } '
           'let c = makeCounter(); print(c()); print(c()); print(c());')
    assert run(src) == [1, 2, 3]

def test_two_independent_closures():
    src = ('func makeCounter() { let n = 0; func inc() { n = n + 1; return n; } return inc; } '
           'let a = makeCounter(); let b = makeCounter(); print(a()); print(a()); print(b());')
    assert run(src) == [1, 2, 1]

# ---- deep recursion (stability: must not die with RecursionError) ----
def test_deep_recursion_500():
    src = 'func count(n) { if (n == 0) { return 0; } return 1 + count(n - 1); } print(count(500));'
    assert run(src) == [500]
