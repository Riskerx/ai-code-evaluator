"""Conservative AST policy and heuristic feedback, not a security sandbox."""

import ast
from pathlib import Path

MAX_SOURCE_BYTES = 64 * 1024
BLOCKED_NAMES = {
    "open", "input", "eval", "exec", "compile", "__import__", "getattr", "setattr",
    "delattr", "globals", "locals", "vars", "dir", "breakpoint", "help", "exit", "quit",
}


def read_source(path: Path) -> str:
    with path.open("rb") as handle:
        data = handle.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError("Submission exceeds the 64 KiB source limit")
    return data.decode("utf-8")


def analyze(source: str, function: str, arity: int) -> list[dict]:
    findings = []

    def add(severity, code, message, node=None):
        findings.append({"severity": severity, "code": code, "message": message,
                         "line": getattr(node, "lineno", None)})

    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        add("error", "source-size", "Submission exceeds 64 KiB")
        return findings
    try:
        tree = ast.parse(source)
        # Parsing alone accepts some invalid constructs, such as break outside a loop.
        compile(tree, "<submission>", "exec")
    except (SyntaxError, ValueError, RecursionError) as exc:
        add("error", "syntax", str(exc))
        return findings

    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == function]
    if len(functions) != 1:
        add("error", "entrypoint", f"Define exactly one top-level function named {function}")
    else:
        args = functions[0].args
        if (len(args.posonlyargs + args.args) != arity or args.vararg or args.kwarg
                or args.kwonlyargs):
            add("error", "signature", f"{function} must accept exactly {arity} positional argument(s)", functions[0])

    for node in tree.body:
        is_docstring = (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                        and isinstance(node.value.value, str))
        if not isinstance(node, ast.FunctionDef) and not is_docstring:
            add("error", "top-level", "Only function definitions and docstrings are allowed at module level", node)

    class Inspector(ast.NodeVisitor):
        loop_depth = 0
        current_function = None

        def generic_visit(self, node):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                add("error", "import", "Imports are disabled for these pure-Python exercises", node)
            if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom)):
                add("error", "unsupported", "Classes, async code, and generators are outside the submission contract", node)
            if isinstance(node, ast.Name) and (node.id in BLOCKED_NAMES or node.id.startswith("__")):
                add("error", "restricted-name", f"Restricted name: {node.id}", node)
            if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
                add("error", "restricted-attribute", "Private and dunder attribute access is disabled", node)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == self.current_function:
                add("warning", "recursion", "Direct recursion found; inspect base cases and stack usage", node)
            super().generic_visit(node)

        def visit_FunctionDef(self, node):
            if node.name.startswith("__"):
                add("error", "restricted-name", "Dunder function names are disabled", node)
            if node.decorator_list or getattr(node, "type_params", []):
                add("error", "function-definition", "Decorators and generic type parameters are disabled", node)
            for default in node.args.defaults + [x for x in node.args.kw_defaults if x is not None]:
                try:
                    ast.literal_eval(default)
                except (ValueError, TypeError, RecursionError):
                    add("error", "default-expression", "Default arguments must be literals", default)
            old_function, old_depth = self.current_function, self.loop_depth
            self.current_function, self.loop_depth = node.name, 0
            self.generic_visit(node)
            self.current_function, self.loop_depth = old_function, old_depth

        def visit_For(self, node):
            self.loop_depth += 1
            if self.loop_depth > 1:
                add("warning", "nested-loop", "Nested loop found; review input growth. This is not a complexity proof", node)
            self.generic_visit(node)
            self.loop_depth -= 1

        def visit_While(self, node):
            if isinstance(node.test, ast.Constant) and node.test.value:
                add("warning", "constant-loop", "Constant-true loop found; runtime timeout will catch nontermination", node)
            self.visit_For(node)

        def visit_ListComp(self, node):
            if self.loop_depth + len(node.generators) > 1:
                add("warning", "nested-loop", "Nested comprehension found; review input growth", node)
            old_depth = self.loop_depth
            self.loop_depth += len(node.generators)
            self.generic_visit(node)
            self.loop_depth = old_depth

        visit_SetComp = visit_ListComp
        visit_DictComp = visit_ListComp
        visit_GeneratorExp = visit_ListComp

    try:
        Inspector().visit(tree)
    except RecursionError:
        add("error", "ast-depth", "Submission is too deeply nested for AST inspection")
    return findings
