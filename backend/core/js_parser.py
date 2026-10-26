"""
JavaScript / TypeScript parser.
Uses regex-based extraction since tree-sitter bindings are optional.
Extracts: functions, arrow functions, class methods, imports, calls, line ranges.
"""
from __future__ import annotations
import re
import logging
from pathlib import Path
from typing import List, Optional

from core.models import FunctionUnit

logger = logging.getLogger(__name__)

# ── Regex patterns ────────────────────────────────────────────────────────────

# Named function declarations:  function foo(...) {
RE_FUNC_DECL = re.compile(
    r'^[ \t]*(export\s+)?(default\s+)?(async\s+)?function\s+(\w+)\s*\(',
    re.MULTILINE,
)

# Arrow / const functions:  const foo = (...) => / const foo = async (...) =>
RE_ARROW = re.compile(
    r'^[ \t]*(export\s+)?(const|let|var)\s+(\w+)\s*=\s*(async\s+)?(?:\([^)]*\)|\w+)\s*=>',
    re.MULTILINE,
)

# Class declarations:  class Foo {
RE_CLASS = re.compile(r'^[ \t]*(export\s+)?(default\s+)?class\s+(\w+)', re.MULTILINE)

# Class methods (inside class body):  methodName(...) { or async methodName(...) {
RE_METHOD = re.compile(
    r'^[ \t]*(static\s+)?(async\s+)?(\w+)\s*\([^)]*\)\s*\{',
    re.MULTILINE,
)

# Imports:  import ... from '...'
RE_IMPORT = re.compile(r'^[ \t]*import\s+.+from\s+[\'"]([^\'"]+)[\'"]', re.MULTILINE)
RE_REQUIRE = re.compile(r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)', re.MULTILINE)

# Function calls:  foo(  or  this.foo(  or  obj.foo(
RE_CALL = re.compile(r'(?:this\.|(?:\w+\.))?(\w+)\s*\(', re.MULTILINE)

# Keywords that look like calls but are not
_NON_CALLS = {
    'if', 'for', 'while', 'switch', 'catch', 'function', 'class',
    'return', 'typeof', 'instanceof', 'new', 'delete', 'void',
    'import', 'export', 'async', 'await', 'yield', 'super',
    'constructor', 'get', 'set', 'static',
}


def _line_number(source: str, pos: int) -> int:
    """Return 1-based line number of character position in source."""
    return source[:pos].count('\n') + 1


def _end_line(source: str, start_pos: int) -> int:
    """
    Find the closing brace of a block starting at start_pos.
    Returns 1-based line number of closing brace.
    Falls back to start_line + 20 if no matching brace found.
    """
    lines = source.splitlines()
    start_line = _line_number(source, start_pos)
    depth = 0
    in_string = False
    string_char = None
    i = start_pos

    while i < len(source):
        ch = source[i]
        if in_string:
            if ch == '\\':
                i += 2
                continue
            if ch == string_char:
                in_string = False
        else:
            if ch in ('"', "'", '`'):
                in_string = True
                string_char = ch
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return _line_number(source, i)
        i += 1

    return min(start_line + 30, len(lines))


def _extract_calls(source_code: str) -> List[str]:
    calls = set()
    for m in RE_CALL.finditer(source_code):
        name = m.group(1)
        if name not in _NON_CALLS and len(name) > 1:
            calls.add(name)
    return sorted(calls)


def _extract_imports(source: str) -> List[str]:
    imports = []
    for m in RE_IMPORT.finditer(source):
        imports.append(m.group(1))
    for m in RE_REQUIRE.finditer(source):
        imports.append(m.group(1))
    return imports


class JavaScriptParser:
    """
    Regex-based JS/TS parser.
    Extracts top-level functions, arrow functions, and class methods.
    """

    def parse_file(self, file_path: Path, repo_root: Path) -> List[FunctionUnit]:
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Cannot read %s: %s", file_path, exc)
            return []

        relative_path = str(file_path.relative_to(repo_root)).replace("\\", "/")
        lines = source.splitlines()
        imports = _extract_imports(source)
        units: List[FunctionUnit] = []

        # ── Named function declarations ──────────────────────────────────
        for m in RE_FUNC_DECL.finditer(source):
            func_name = m.group(4)
            start_line = _line_number(source, m.start())
            end_line = _end_line(source, m.start())
            src = "\n".join(lines[start_line - 1: end_line])
            units.append(FunctionUnit(
                file_path=relative_path,
                class_name=None,
                function_name=func_name,
                start_line=start_line,
                end_line=end_line,
                source_code=src,
                imports=imports,
                calls=_extract_calls(src),
                called_by=[],
            ))

        # ── Arrow / const functions ──────────────────────────────────────
        for m in RE_ARROW.finditer(source):
            func_name = m.group(3)
            # Skip if already captured as named function
            if any(u.function_name == func_name for u in units):
                continue
            start_line = _line_number(source, m.start())
            end_line = _end_line(source, m.start())
            src = "\n".join(lines[start_line - 1: end_line])
            units.append(FunctionUnit(
                file_path=relative_path,
                class_name=None,
                function_name=func_name,
                start_line=start_line,
                end_line=end_line,
                source_code=src,
                imports=imports,
                calls=_extract_calls(src),
                called_by=[],
            ))

        # ── Class methods ────────────────────────────────────────────────
        for class_match in RE_CLASS.finditer(source):
            class_name = class_match.group(3)
            class_start = _line_number(source, class_match.start())
            class_end = _end_line(source, class_match.start())
            # Only search for methods within the class body
            class_source = "\n".join(lines[class_start - 1: class_end])
            class_offset = class_match.start()

            for method_match in RE_METHOD.finditer(class_source):
                method_name = method_match.group(3)
                if method_name in ('if', 'for', 'while', 'switch', 'catch', class_name):
                    continue
                # Calculate absolute position
                abs_pos = class_offset + method_match.start()
                start_line = _line_number(source, abs_pos)
                end_line = _end_line(source, abs_pos)
                src = "\n".join(lines[start_line - 1: end_line])
                units.append(FunctionUnit(
                    file_path=relative_path,
                    class_name=class_name,
                    function_name=method_name,
                    start_line=start_line,
                    end_line=end_line,
                    source_code=src,
                    imports=imports,
                    calls=_extract_calls(src),
                    called_by=[],
                ))

        # Deduplicate by (file, function, start_line)
        seen = set()
        deduped = []
        for u in units:
            key = (u.file_path, u.function_name, u.start_line)
            if key not in seen:
                seen.add(key)
                deduped.append(u)

        return deduped
