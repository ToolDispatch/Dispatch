from __future__ import annotations

import os
import re
from typing import Optional

from scanner_base import ScannerBase, SymbolTable

# Matches: from module_name import name1, name2
# Covers both python3 -c "..." inline blocks and heredoc (<<PYEOF) patterns.
_FROM_IMPORT_RE = re.compile(r'\bfrom\s+(\w+)\s+import\s+([\w]+(?:\s*,\s*[\w]+)*)')


class BashScanner(ScannerBase):
    def supports(self, path: str) -> bool:
        return path.endswith(".sh") and os.path.isfile(path)

    def scan(self, path: str) -> Optional[SymbolTable]:
        try:
            src = open(path, "r", encoding="utf-8").read()
        except Exception:
            return None

        module_name = os.path.splitext(os.path.basename(path))[0]
        st = SymbolTable(module_name=module_name, path=path)

        lines = src.splitlines()
        for lineno, line in enumerate(lines, start=1):
            for match in _FROM_IMPORT_RE.finditer(line):
                module = match.group(1).strip()
                names_raw = match.group(2).strip()
                names = [n.strip() for n in names_raw.split(",") if n.strip()]
                st.imports.append(module)
                for name in names:
                    st.imported_symbols.append(name)
                    st.from_imports.append({
                        "module": module,
                        "name": name,
                        "asname": None,
                        "line": lineno,
                    })

        return st
