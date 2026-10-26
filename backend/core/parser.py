"""
Python AST-based code parser.
Extracts functions, methods, imports, and call relationships.
Falls back gracefully if tree-sitter is unavailable.
"""
from __future__ import annotations
import ast
import logging
import re
from pathlib import Path
from typing import List, Optional

from core.models import FunctionUnit

logger = logging.getLogger(__name__)


class PythonASTParser:
    """
    Parses Python source files using the stdlib ast module.
    Extracts:
      - top-level functions
      - class methods
      - imports
      - function calls (best-effort)
      - line ranges
      - source code
    """

    def parse_file(self, file_path: Path, repo_root: Path) -> List[FunctionUnit]:
        """Parse a single Python file. Returns list of FunctionUnits."""
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Cannot read %s: %s", file_path, exc)
            return []

        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            logger.warning("Syntax error in %s: %s", file_path, exc)
            return []

        relative_path = str(file_path.relative_to(repo_root))
        source_lines = source.splitlines()
        imports = self._extract_imports(tree)
        units: List[FunctionUnit] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        unit = self._extract_function(
                            item, source_lines, relative_path,
                            class_name=node.name, imports=imports
                        )
                        if unit:
                            units.append(unit)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only top-level functions (not inside a class)
                if not self._is_method(node, tree):
                    unit = self._extract_function(
                        node, source_lines, relative_path,
                        class_name=None, imports=imports
                    )
                    if unit:
                        units.append(unit)

        # Resolve call relationships within the file
        self._resolve_calls(units)
        return units

    def _is_method(self, func_node: ast.FunctionDef, tree: ast.AST) -> bool:
        """Return True if this function is a method inside a class."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if item is func_node:
                        return True
        return False

    def _extract_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        source_lines: List[str],
        file_path: str,
        class_name: Optional[str],
        imports: List[str],
    ) -> Optional[FunctionUnit]:
        """Extract a FunctionUnit from an AST function node."""
        try:
            start_line = node.lineno
            end_line = node.end_lineno or node.lineno
            # Extract source code for this function
            func_source = "\n".join(source_lines[start_line - 1: end_line])
            calls = self._extract_calls(node)
            return FunctionUnit(
                file_path=file_path,
                class_name=class_name,
                function_name=node.name,
                start_line=start_line,
                end_line=end_line,
                source_code=func_source,
                imports=imports,
                calls=calls,
                called_by=[],
            )
        except Exception as exc:
            logger.warning("Failed to extract function %s: %s", node.name, exc)
            return None

    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract all import statements as strings."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
        return imports

    def _extract_calls(self, func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
        """Extract names of functions called within this function."""
        calls = set()
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
        return sorted(calls)

    def _resolve_calls(self, units: List[FunctionUnit]) -> None:
        """Populate called_by by inverting the calls graph within the file."""
        name_to_unit = {u.function_name: u for u in units}
        for unit in units:
            for callee_name in unit.calls:
                if callee_name in name_to_unit:
                    callee = name_to_unit[callee_name]
                    if unit.function_name not in callee.called_by:
                        callee.called_by.append(unit.function_name)


class MultiFileParser:
    """Parses an entire repository and resolves cross-file call relationships."""

    def __init__(self, language: str = "python"):
        self.language = language
        self._python_parser = PythonASTParser()
        self._js_parser: Optional[object] = None

    def _get_js_parser(self):
        if self._js_parser is None:
            from core.js_parser import JavaScriptParser
            self._js_parser = JavaScriptParser()
        return self._js_parser

    def parse_repository(self, source_files: List[Path], repo_root: Path) -> List[FunctionUnit]:
        """Parse all source files and return indexed FunctionUnits."""
        all_units: List[FunctionUnit] = []
        for file_path in source_files:
            if self.language == "python":
                units = self._python_parser.parse_file(file_path, repo_root)
            elif self.language in ("javascript", "typescript"):
                units = self._get_js_parser().parse_file(file_path, repo_root)
            else:
                logger.warning("No parser for language: %s", self.language)
                units = []
            all_units.extend(units)

        # Cross-file call resolution
        self._resolve_cross_file_calls(all_units)
        logger.info("Parsed %d functions across %d files", len(all_units), len(source_files))
        return all_units

    def _resolve_cross_file_calls(self, units: List[FunctionUnit]) -> None:
        """Attempt to resolve called_by relationships across files."""
        name_to_units: dict[str, List[FunctionUnit]] = {}
        for u in units:
            name_to_units.setdefault(u.function_name, []).append(u)

        for unit in units:
            for callee_name in unit.calls:
                if callee_name in name_to_units:
                    for callee in name_to_units[callee_name]:
                        if unit.function_name not in callee.called_by:
                            callee.called_by.append(unit.function_name)
