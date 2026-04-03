# scanner_python.py
from __future__ import annotations

import ast
import os
from typing import Optional, List, Dict, Any

from scanner_base import ScannerBase, SymbolTable


def _is_stub_body(body: list) -> bool:
    if not body:
        return True
    if len(body) == 1:
        node = body[0]
        if isinstance(node, ast.Pass):
            return True
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            return True  # "..." or docstring only
    if len(body) == 2:
        first, second = body
        is_docstring = isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
        is_pass_or_ellipsis = isinstance(second, ast.Pass) or (
            isinstance(second, ast.Expr) and isinstance(second.value, ast.Constant)
        )
        if is_docstring and is_pass_or_ellipsis:
            return True
    return False


def _annotation_name(node) -> Optional[str]:
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _annotation_name(node.value)
    return None


class _CallCollector(ast.NodeVisitor):
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def visit_Call(self, node: ast.Call):
        # Count positional args (exclude *args splats) and named keyword args (exclude **kwargs unpacks)
        n_args = sum(1 for a in node.args if not isinstance(a, ast.Starred))
        has_star_args = any(isinstance(a, ast.Starred) for a in node.args)
        n_kwargs = sum(1 for kw in node.keywords if kw.arg is not None)
        has_kwargs_unpack = any(kw.arg is None for kw in node.keywords)
        extra = {"has_star_args": has_star_args, "has_kwargs_unpack": has_kwargs_unpack}
        if isinstance(node.func, ast.Name):
            self.calls.append({"symbol": node.func.id, "line": getattr(node, "lineno", None),
                                "kind": "name", "n_args": n_args, "n_kwargs": n_kwargs, **extra})
        elif isinstance(node.func, ast.Attribute):
            self.calls.append({"symbol": node.func.attr, "line": getattr(node, "lineno", None),
                                "kind": "attr", "n_args": n_args, "n_kwargs": n_kwargs, **extra})
        self.generic_visit(node)


class _EnvVarCollector(ast.NodeVisitor):
    def __init__(self):
        self.hard: List[Dict] = []
        self.soft: List[Dict] = []

    @staticmethod
    def _str_key(node) -> Optional[str]:
        if isinstance(node, ast.Index):  # Python 3.8 compat
            node = node.value
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    def visit_Subscript(self, node: ast.Subscript):
        # os.environ["KEY"]
        if (isinstance(node.value, ast.Attribute) and node.value.attr == "environ"
                and isinstance(node.value.value, ast.Name) and node.value.value.id == "os"):
            key = self._str_key(node.slice)
            if key:
                self.hard.append({"var_name": key, "line": getattr(node, "lineno", None)})
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if not isinstance(node.func, ast.Attribute):
            self.generic_visit(node)
            return
        attr, val = node.func.attr, node.func.value
        is_environ_get = (attr == "get" and isinstance(val, ast.Attribute)
                          and val.attr == "environ" and isinstance(val.value, ast.Name)
                          and val.value.id == "os")
        is_getenv = (attr == "getenv" and isinstance(val, ast.Name) and val.id == "os")
        if (is_environ_get or is_getenv) and node.args:
            key = self._str_key(node.args[0])
            if key:
                has_default = len(node.args) > 1 or any(kw.arg == "default" for kw in node.keywords)
                entry = {"var_name": key, "line": getattr(node, "lineno", None)}
                (self.soft if has_default else self.hard).append(entry)
        self.generic_visit(node)


class PythonScanner(ScannerBase):
    def supports(self, path: str) -> bool:
        return path.endswith(".py") and os.path.isfile(path)

    def scan(self, path: str) -> Optional[SymbolTable]:
        try:
            src = open(path, "r", encoding="utf-8").read()
            tree = ast.parse(src, filename=path)
        except Exception:
            return None

        module_name = os.path.splitext(os.path.basename(path))[0]
        st = SymbolTable(module_name=module_name, path=path)

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                st.exports.append(node.name)
                args = node.args
                params = [a for a in args.args if a.arg not in ("self", "cls")]
                n_total = len(params)
                n_required = n_total - len(args.defaults)
                st.functions[node.name] = {
                    "n_required": n_required,
                    "n_total": n_total,
                    "has_varargs": args.vararg is not None,
                    "has_varkw": args.kwarg is not None,
                    "return_annotation": _annotation_name(node.returns),
                    "is_stub": _is_stub_body(node.body),
                    "line": getattr(node, "lineno", None),
                }
            elif isinstance(node, ast.ClassDef):
                st.exports.append(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        st.exports.append(t.id)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    st.exports.append(node.target.id)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    st.imports.append(alias.name)
                    st.imported_symbols.append(alias.asname or alias.name.split(".")[-1])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    st.imports.append(node.module)
                for alias in node.names:
                    st.imported_symbols.append(alias.asname or alias.name)
                    st.from_imports.append({"module": node.module, "name": alias.name,
                                            "asname": alias.asname,
                                            "line": getattr(node, "lineno", None)})

        cc = _CallCollector()
        cc.visit(tree)
        st.calls = cc.calls

        ev = _EnvVarCollector()
        ev.visit(tree)
        st.env_vars_hard = ev.hard
        st.env_vars_soft = ev.soft

        return st
