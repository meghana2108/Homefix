"""Pull a Python function out of a model reply, and read names from the user's message."""

from __future__ import annotations

import ast
import re

_FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n(.*?)```", re.DOTALL)
_DEF = re.compile(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", re.MULTILINE)
_IMPORT = re.compile(r"^\s*((?:import\s+[\w., ]+|from\s+[\w.]+\s+import\s+[^\n#]+?))\s*$", re.MULTILINE)


def find_target(message: str) -> str | None:
    m = _DEF.search(message)
    return m.group(1) if m else None


def _defines(code: str, name: str | None) -> bool:
    names = _DEF.findall(code)
    if not names:
        return False
    return name is None or name in names


def extract_code(text: str, target_name: str | None = None) -> str | None:
    blocks = _FENCE.findall(text)
    # Prefer python-tagged blocks, then untagged, then any other.
    ranked = sorted(blocks, key=lambda b: 0 if b[0].lower() in ("python", "py") else 1 if not b[0] else 2)
    for _, body in ranked:
        if _defines(body, target_name):
            return body
    if blocks:
        return None
    try:
        ast.parse(text)
    except SyntaxError:
        return None
    return text if _defines(text, target_name) else None


def stub_imports(message: str) -> list[str]:
    return [m.group(1).strip() for m in _IMPORT.finditer(message)]
