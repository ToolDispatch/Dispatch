from __future__ import annotations

from typing import Optional

from scanner_base import SymbolTable
from scanner_python import PythonScanner
from scanner_bash import BashScanner
from scanner_typescript import TypeScriptScanner
from scanner_dart import DartScanner


SCANNERS = [PythonScanner(), BashScanner(), TypeScriptScanner(), DartScanner()]


def scan_file(path: str) -> Optional[SymbolTable]:
    for s in SCANNERS:
        if s.supports(path):
            return s.scan(path)
    return None
