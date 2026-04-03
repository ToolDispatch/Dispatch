# scanner_base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class SymbolTable:
    module_name: str
    path: str
    exports: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    imported_symbols: List[str] = field(default_factory=list)
    calls: List[Dict[str, Any]] = field(default_factory=list)  # {symbol, line, kind, n_args, n_kwargs}
    from_imports: List[Dict[str, Any]] = field(default_factory=list)
    state_writes: List[str] = field(default_factory=list)
    state_reads: List[str] = field(default_factory=list)
    env_vars_read: List[str] = field(default_factory=list)
    # Stage 1 new fields
    functions: Dict[str, Dict] = field(default_factory=dict)
    env_vars_hard: List[Dict] = field(default_factory=list)  # [{var_name, line}]
    env_vars_soft: List[Dict] = field(default_factory=list)  # [{var_name, line}]


class ScannerBase(ABC):
    @abstractmethod
    def supports(self, path: str) -> bool: ...

    @abstractmethod
    def scan(self, path: str) -> Optional[SymbolTable]: ...
