from __future__ import annotations
import os, re
from typing import Optional
from scanner_base import ScannerBase, SymbolTable

_IMPORT_RE = re.compile(r"import\s+'([^']+)'(?:\s+show\s+([\w\s,]+))?(?:\s+hide\s+[\w\s,]+)?;")
_CLASS_RE = re.compile(r'^(?:abstract\s+)?class\s+(\w+)', re.MULTILINE)
_MIXIN_RE = re.compile(r'^mixin\s+(\w+)', re.MULTILINE)
_ENUM_RE = re.compile(r'^enum\s+(\w+)', re.MULTILINE)
_FUNC_RE = re.compile(
    r'^([\w<>\[\]?,\s]+?)\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*(?:\([^)]*\)[^)]*)*)\)\s*(?:async\s*)?\{',
    re.MULTILINE)
_CALL_RE = re.compile(r'\b([a-zA-Z_]\w*)\s*\(([^)]*)\)')
_ENV_KEY_RE = re.compile(r"(?:dotenv\.env|Platform\.environment)\['([A-Z_][A-Z0-9_]*)'\]")
_ENV_SOFT_RE = re.compile(r"(?:dotenv\.env|Platform\.environment)\['([A-Z_][A-Z0-9_]*)'\]\s*\?\?")
_STUB_RE = re.compile(r'throw\s+(?:UnimplementedError|UnsupportedError)\s*\(')
_SKIP = {'if','for','while','switch','catch','assert','return','new','class','import',
         'void','final','const','var','super','this','await','async','yield','print'}
_DART_TYPES = {'void','bool','int','double','num','String','List','Map','Set','Future',
               'Stream','Widget','BuildContext','State','dynamic','Object','Iterable',
               'Duration','DateTime','Color','Key','GlobalKey'}

def _parse_dart_params(s):
    s = s.strip()
    if not s: return {"n_required": 0, "n_total": 0, "has_varargs": False}
    n_required = n_total = 0
    opt_pos = re.search(r'\[([^\]]*)\]', s)
    named = re.search(r'\{([^}]*)\}', s)
    base = s[:s.index('[')] if opt_pos else (s[:s.index('{')] if named else s)
    for p in [x.strip() for x in base.split(',') if x.strip()]: n_total += 1; n_required += 1
    if opt_pos:
        for p in [x.strip() for x in opt_pos.group(1).split(',') if x.strip()]: n_total += 1
    if named:
        for p in [x.strip() for x in named.group(1).split(',') if x.strip()]:
            n_total += 1
            if p.startswith('required '): n_required += 1
    return {"n_required": n_required, "n_total": n_total, "has_varargs": False}

def _count_args(s):
    s = s.strip()
    if not s: return 0
    depth = 0; count = 1
    for ch in s:
        if ch in '([{': depth += 1
        elif ch in ')]}': depth -= 1
        elif ch == ',' and depth == 0: count += 1
    return count

class DartScanner(ScannerBase):
    def supports(self, path): return path.endswith('.dart')

    def scan(self, path) -> Optional[SymbolTable]:
        try: src = open(path, 'r', encoding='utf-8').read()
        except Exception: return None
        st = SymbolTable(module_name=os.path.splitext(os.path.basename(path))[0], path=path)
        lines = src.splitlines()

        for lineno, line in enumerate(lines, 1):
            for m in _IMPORT_RE.finditer(line):
                mod = m.group(1); st.imports.append(mod)
                if m.group(2):
                    for n in [x.strip() for x in m.group(2).split(',') if x.strip()]:
                        st.imported_symbols.append(n)
                        st.from_imports.append({'module': mod, 'name': n, 'asname': None, 'line': lineno})

        for m in _CLASS_RE.finditer(src): st.exports.append(m.group(1))
        for m in _MIXIN_RE.finditer(src): st.exports.append(m.group(1))
        for m in _ENUM_RE.finditer(src): st.exports.append(m.group(1))

        for m in _FUNC_RE.finditer(src):
            ret = m.group(1).strip(); name = m.group(2).strip(); params = m.group(3) or ''
            rt_base = ret.split('<')[0].strip().split()[-1] if ret else ''
            if name in _SKIP or not rt_base: continue
            if not (rt_base in _DART_TYPES or rt_base[0].isupper() or rt_base == 'void'): continue
            arity = _parse_dart_params(params)
            lineno = src[:m.start()].count('\n') + 1
            rest = src[m.end()-1:]  # from opening {
            depth = 0; body_end = 0
            for i, ch in enumerate(rest):
                if ch == '{': depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0: body_end = i; break
            body = rest[1:body_end].strip()
            is_stub = not body or bool(_STUB_RE.search(body))
            st.functions[name] = {**arity, 'has_varkw': False, 'return_annotation': ret or None, 'is_stub': is_stub, 'line': lineno}
            if name not in st.exports: st.exports.append(name)

        for lineno, line in enumerate(lines, 1):
            if line.strip().startswith('//'): continue
            for m in _CALL_RE.finditer(line):
                n = m.group(1)
                if n not in _SKIP:
                    st.calls.append({'symbol': n, 'line': lineno, 'kind': 'name',
                                     'n_args': _count_args(m.group(2)) if m.group(2).strip() else 0,
                                     'n_kwargs': 0, 'has_star_args': False, 'has_kwargs_unpack': False})

        for lineno, line in enumerate(lines, 1):
            for m in _ENV_SOFT_RE.finditer(line): st.env_vars_soft.append({'var_name': m.group(1), 'line': lineno})
            for m in _ENV_KEY_RE.finditer(line):
                if not any(e['var_name'] == m.group(1) and e['line'] == lineno for e in st.env_vars_soft):
                    st.env_vars_hard.append({'var_name': m.group(1), 'line': lineno})

        st.exports = list(dict.fromkeys(st.exports))
        return st
