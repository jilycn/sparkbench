import sys

sys.setrecursionlimit(50000)


class InterpreterError(Exception):
    pass


class UndefinedVariableError(InterpreterError):
    pass


class ArityError(InterpreterError):
    pass


# ---------- Tokenizer ----------

class Token:
    __slots__ = ('type', 'value', 'pos')
    def __init__(self, type_, value, pos):
        self.type = type_
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"


def tokenize(source):
    tokens = []
    i = 0
    n = len(source)
    while i < n:
        if source[i].isspace():
            i += 1
            continue
        if source[i] == '/' and i + 1 < n and source[i + 1] == '/':
            while i < n and source[i] != '\n':
                i += 1
            continue
        if source[i].isdigit():
            j = i
            has_dot = False
            while j < n and (source[j].isdigit() or source[j] == '.'):
                if source[j] == '.':
                    if has_dot:
                        break
                    has_dot = True
                j += 1
            s = source[i:j]
            if has_dot:
                tokens.append(Token('FLOAT', float(s), i))
            else:
                tokens.append(Token('INT', int(s), i))
            i = j
            continue
        if source[i] == '"':
            j = i + 1
            while j < n and source[j] != '"':
                if source[j] == '\\':
                    j += 1
                j += 1
            raw = source[i + 1:j]
            raw = raw.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
            tokens.append(Token('STRING', raw, i))
            i = j + 1
            continue
        if source[i].isalpha() or source[i] == '_':
            j = i
            while j < n and (source[j].isalnum() or source[j] == '_'):
                j += 1
            word = source[i:j]
            keywords = {'let', 'if', 'else', 'while', 'func', 'print', 'return', 'true', 'false', 'nil'}
            if word in keywords:
                tokens.append(Token(word, word, i))
            else:
                tokens.append(Token('IDENT', word, i))
            i = j
            continue
        if i + 1 < n and source[i:i + 2] in ('&&', '||', '==', '!=', '<=', '>='):
            tokens.append(Token('OP', source[i:i + 2], i))
            i += 2
            continue
        if source[i] in '+-*/%=!<>();{}(),':
            ttype = 'OP' if source[i] in '+-*/%=!<>' else 'PUNCT'
            tokens.append(Token(ttype, source[i], i))
            i += 1
            continue
        raise InterpreterError(f"Unexpected character {source[i]!r} at pos {i}")
    tokens.append(Token('EOF', None, n))
    return tokens


# ---------- AST ----------

class IntegerLit:
    __slots__ = ('value',)
    def __init__(self, value):
        self.value = value

class FloatLit:
    __slots__ = ('value',)
    def __init__(self, value):
        self.value = value

class StringLit:
    __slots__ = ('value',)
    def __init__(self, value):
        self.value = value

class BoolLit:
    __slots__ = ('value',)
    def __init__(self, value):
        self.value = value

class NilLit:
    pass

class Var:
    __slots__ = ('name',)
    def __init__(self, name):
        self.name = name

class BinOp:
    __slots__ = ('left', 'op', 'right')
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

class UnaryOp:
    __slots__ = ('op', 'operand')
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand

class If:
    __slots__ = ('cond', 'then_body', 'else_body')
    def __init__(self, cond, then_body, else_body=None):
        self.cond = cond
        self.then_body = then_body
        self.else_body = else_body

class While:
    __slots__ = ('cond', 'body')
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body

class FuncDef:
    __slots__ = ('name', 'params', 'body')
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body

class FuncCall:
    __slots__ = ('func', 'args')
    def __init__(self, func, args):
        self.func = func
        self.args = args

class Return:
    __slots__ = ('expr',)
    def __init__(self, expr=None):
        self.expr = expr

class Let:
    __slots__ = ('name', 'value')
    def __init__(self, name, value):
        self.name = name
        self.value = value

class Assign:
    __slots__ = ('name', 'value')
    def __init__(self, name, value):
        self.name = name
        self.value = value

class Print:
    __slots__ = ('expr',)
    def __init__(self, expr):
        self.expr = expr

class Block:
    __slots__ = ('stmts',)
    def __init__(self, stmts):
        self.stmts = stmts


# ---------- Parser ----------

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, type_=None, value=None):
        tok = self.peek()
        if type_ is not None and tok.type != type_:
            raise InterpreterError(f"Expected {type_}, got {tok.type} at pos {tok.pos}")
        if value is not None and tok.value != value:
            raise InterpreterError(f"Expected {value!r}, got {tok.value!r} at pos {tok.pos}")
        return self.advance()

    def parse(self):
        stmts = self._parse_stmts()
        return Block(stmts)

    # ---- Statement parsing ----

    def _parse_stmts(self):
        stmts = []
        while self.peek().type != 'EOF' and self.peek().value != '}':
            stmts.append(self._parse_stmt())
            if self.peek().type == 'PUNCT' and self.peek().value == ';':
                self.advance()
        return stmts

    def _parse_stmt(self):
        tok = self.peek()
        if tok.type == 'let':
            return self._parse_let()
        if tok.type == 'if':
            return self._parse_if()
        if tok.type == 'while':
            return self._parse_while()
        if tok.type == 'func':
            return self._parse_func()
        if tok.type == 'print':
            return self._parse_print()
        if tok.type == 'return':
            return self._parse_return()
        if tok.type == 'IDENT':
            return self._parse_expr_stmt()
        if tok.type == 'PUNCT' and tok.value == '{':
            return self._parse_block()
        raise InterpreterError(f"Unexpected token {tok} at pos {tok.pos}")

    def _parse_let(self):
        self.expect('let')
        name = self.expect('IDENT').value
        self.expect(value='=')
        value = self._parse_expr()
        return Let(name, value)

    def _parse_block(self):
        self.expect(value='{')
        stmts = self._parse_stmts()
        self.expect(value='}')
        return Block(stmts)

    def _parse_if(self):
        self.expect('if')
        self.expect(value='(')
        cond = self._parse_expr()
        self.expect(value=')')
        then_body = self._parse_block()
        else_body = None
        if self.peek().type == 'else':
            self.advance()
            else_body = self._parse_block()
        return If(cond, then_body, else_body)

    def _parse_while(self):
        self.expect('while')
        self.expect(value='(')
        cond = self._parse_expr()
        self.expect(value=')')
        body = self._parse_block()
        return While(cond, body)

    def _parse_func(self):
        self.expect('func')
        name = self.expect('IDENT').value
        self.expect(value='(')
        params = self._parse_param_list()
        self.expect(value=')')
        body = self._parse_block()
        return FuncDef(name, params, body)

    def _parse_param_list(self):
        params = []
        if self.peek().type == 'PUNCT' and self.peek().value == ')':
            return params
        while True:
            params.append(self.expect('IDENT').value)
            if self.peek().type == 'PUNCT' and self.peek().value == ')':
                break
            self.expect(value=',')
        return params

    def _parse_print(self):
        self.expect('print')
        self.expect(value='(')
        expr = self._parse_expr()
        self.expect(value=')')
        return Print(expr)

    def _parse_return(self):
        self.expect('return')
        if self.peek().type == 'PUNCT' and self.peek().value == ';':
            return Return()
        expr = self._parse_expr()
        return Return(expr)

    def _parse_expr_stmt(self):
        name = self.expect('IDENT').value
        if self.peek().type == 'PUNCT' and self.peek().value == '(':
            self.advance()
            args = self._parse_arg_list()
            self.expect(value=')')
            return FuncCall(Var(name), args)
        self.expect(value='=')
        value = self._parse_expr()
        return Assign(name, value)

    def _parse_arg_list(self):
        args = []
        if self.peek().type == 'PUNCT' and self.peek().value == ')':
            return args
        while True:
            args.append(self._parse_expr())
            if self.peek().type == 'PUNCT' and self.peek().value == ')':
                break
            self.expect(value=',')
        return args

    # ---- Expression parsing (precedence climbing) ----

    def _parse_expr(self):
        return self._parse_or()

    def _parse_or(self):
        left = self._parse_and()
        while self.peek().type == 'OP' and self.peek().value == '||':
            self.advance()
            right = self._parse_and()
            left = BinOp(left, '||', right)
        return left

    def _parse_and(self):
        left = self._parse_equality()
        while self.peek().type == 'OP' and self.peek().value == '&&':
            self.advance()
            right = self._parse_equality()
            left = BinOp(left, '&&', right)
        return left

    def _parse_equality(self):
        left = self._parse_comparison()
        while self.peek().type == 'OP' and self.peek().value in ('==', '!='):
            op = self.advance().value
            right = self._parse_comparison()
            left = BinOp(left, op, right)
        return left

    def _parse_comparison(self):
        left = self._parse_additive()
        while self.peek().type == 'OP' and self.peek().value in ('<', '>', '<=', '>='):
            op = self.advance().value
            right = self._parse_additive()
            left = BinOp(left, op, right)
        return left

    def _parse_additive(self):
        left = self._parse_multiplicative()
        while self.peek().type == 'OP' and self.peek().value in ('+', '-'):
            op = self.advance().value
            right = self._parse_multiplicative()
            left = BinOp(left, op, right)
        return left

    def _parse_multiplicative(self):
        left = self._parse_unary()
        while self.peek().type == 'OP' and self.peek().value in ('*', '/', '%'):
            op = self.advance().value
            right = self._parse_unary()
            left = BinOp(left, op, right)
        return left

    def _parse_unary(self):
        if self.peek().type == 'OP' and self.peek().value in ('-', '!'):
            op = self.advance().value
            operand = self._parse_unary()
            return UnaryOp(op, operand)
        return self._parse_primary()

    def _parse_primary(self):
        tok = self.peek()
        if tok.type == 'INT':
            self.advance()
            return IntegerLit(tok.value)
        if tok.type == 'FLOAT':
            self.advance()
            return FloatLit(tok.value)
        if tok.type == 'STRING':
            self.advance()
            return StringLit(tok.value)
        if tok.type == 'true':
            self.advance()
            return BoolLit(True)
        if tok.type == 'false':
            self.advance()
            return BoolLit(False)
        if tok.type == 'nil':
            self.advance()
            return NilLit()
        if tok.type == 'IDENT':
            name = self.advance().value
            if self.peek().type == 'PUNCT' and self.peek().value == '(':
                self.advance()
                args = self._parse_arg_list()
                self.expect(value=')')
                return FuncCall(Var(name), args)
            return Var(name)
        if tok.type == 'PUNCT' and tok.value == '(':
            self.advance()
            expr = self._parse_expr()
            self.expect(value=')')
            return expr
        raise InterpreterError(f"Unexpected token in expression: {tok} at pos {tok.pos}")


# ---------- Interpreter ----------

class _Return(Exception):
    def __init__(self, value):
        self.value = value


class Env:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def define(self, name, value):
        self.vars[name] = value

    def lookup(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent is not None:
            return self.parent.lookup(name)
        raise UndefinedVariableError(f"Undefined variable: {name}")

    def assign(self, name, value):
        if name in self.vars:
            self.vars[name] = value
        elif self.parent is not None:
            self.parent.assign(name, value)
        else:
            raise UndefinedVariableError(f"Undefined variable: {name}")


class Closure:
    def __init__(self, func_def, env):
        self.func_def = func_def
        self.env = env


class Interpreter:
    def __init__(self):
        self.env = Env()
        self.output = []

    def run(self, ast):
        self._eval_stmts(ast.stmts)
        return self.output

    def _eval_stmts(self, stmts):
        for stmt in stmts:
            self._eval_stmt(stmt)

    def _eval_stmt(self, stmt):
        if isinstance(stmt, Let):
            val = self._eval(stmt.value)
            self.env.define(stmt.name, val)

        elif isinstance(stmt, Assign):
            val = self._eval(stmt.value)
            self.env.assign(stmt.name, val)

        elif isinstance(stmt, If):
            if self._eval(stmt.cond):
                self._eval_stmt(stmt.then_body)
            elif stmt.else_body is not None:
                self._eval_stmt(stmt.else_body)

        elif isinstance(stmt, While):
            while self._eval(stmt.cond):
                self._eval_stmt(stmt.body)

        elif isinstance(stmt, FuncDef):
            self.env.define(stmt.name, Closure(stmt, self.env))

        elif isinstance(stmt, Print):
            self.output.append(self._eval(stmt.expr))

        elif isinstance(stmt, Return):
            if stmt.expr is not None:
                raise _Return(self._eval(stmt.expr))
            raise _Return(None)

        elif isinstance(stmt, Block):
            old = self.env
            self.env = Env(parent=old)
            try:
                self._eval_stmts(stmt.stmts)
            finally:
                self.env = old

        elif isinstance(stmt, FuncCall):
            self._eval(stmt)

        else:
            raise InterpreterError(f"Unknown statement: {type(stmt)}")

    def _eval(self, node):
        if isinstance(node, IntegerLit):
            return node.value
        if isinstance(node, FloatLit):
            return node.value
        if isinstance(node, StringLit):
            return node.value
        if isinstance(node, BoolLit):
            return node.value
        if isinstance(node, NilLit):
            return None
        if isinstance(node, Var):
            return self.env.lookup(node.name)
        if isinstance(node, BinOp):
            return self._eval_binop(node)
        if isinstance(node, UnaryOp):
            return self._eval_unary(node)
        if isinstance(node, FuncCall):
            return self._eval_func_call(node)
        raise InterpreterError(f"Unknown expression: {type(node)}")

    def _eval_binop(self, node):
        op = node.op
        if op == '||':
            left = self._eval(node.left)
            if left:
                return left
            return self._eval(node.right)
        if op == '&&':
            left = self._eval(node.left)
            if not left:
                return left
            return self._eval(node.right)
        if op == '==':
            return self._eval(node.left) == self._eval(node.right)
        if op == '!=':
            return self._eval(node.left) != self._eval(node.right)
        if op == '<':
            return self._eval(node.left) < self._eval(node.right)
        if op == '>':
            return self._eval(node.left) > self._eval(node.right)
        if op == '<=':
            return self._eval(node.left) <= self._eval(node.right)
        if op == '>=':
            return self._eval(node.left) >= self._eval(node.right)
        if op == '+':
            left = self._eval(node.left)
            right = self._eval(node.right)
            if isinstance(left, str) or isinstance(right, str):
                return str(left) + str(right)
            return left + right
        if op == '-':
            return self._eval(node.left) - self._eval(node.right)
        if op == '*':
            return self._eval(node.left) * self._eval(node.right)
        if op == '/':
            return self._eval(node.left) / self._eval(node.right)
        if op == '%':
            return self._eval(node.left) % self._eval(node.right)
        raise InterpreterError(f"Unknown operator: {op}")

    def _eval_unary(self, node):
        if node.op == '-':
            return -self._eval(node.operand)
        if node.op == '!':
            return not self._eval(node.operand)
        raise InterpreterError(f"Unknown unary operator: {node.op}")

    def _eval_func_call(self, node):
        func = self._eval(node.func)
        args = [self._eval(a) for a in node.args]
        if not isinstance(func, Closure):
            raise InterpreterError("Not a function")
        fd = func.func_def
        if len(args) != len(fd.params):
            raise ArityError(
                f"Function '{fd.name}' expected {len(fd.params)} args, got {len(args)}"
            )
        old = self.env
        self.env = Env(parent=func.env)
        for p, a in zip(fd.params, args):
            self.env.define(p, a)
        try:
            result = None
            for s in fd.body.stmts:
                try:
                    self._eval_stmt(s)
                except _Return as ret:
                    result = ret.value
                    break
            return result
        finally:
            self.env = old


def run(source):
    tokens = tokenize(source)
    parser = Parser(tokens)
    ast = parser.parse()
    interp = Interpreter()
    return interp.run(ast)
