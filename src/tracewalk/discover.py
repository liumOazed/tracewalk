"""Static discovery: walk a project directory and list every function/method
defined in every .py file, via the ast module. This is the denominator half
of the report -- "how many functions exist" -- independent of whether any
of them ever ran.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field

DEFAULT_EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".hg",
    ".svn",
    "venv",
    ".venv",
    "env",
    ".env",
    "virtualenv",
    "node_modules",
    "build",
    "dist",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "site-packages",
}


@dataclass
class FunctionDef:
    qualname: str
    lineno: int


@dataclass
class FileEntry:
    rel_path: str  # forward-slash relative path from project root
    functions: list = field(default_factory=list)  # list[FunctionDef]


class _FunctionVisitor(ast.NodeVisitor):
    """Walks a module's AST, tracking enclosing class/function names so a
    method shows up as 'ClassName.method' rather than just 'method'.
    """

    def __init__(self):
        self.stack: list[str] = []
        self.results: list[FunctionDef] = []

    def _handle_function(self, node):
        qualname = ".".join(self.stack + [node.name])
        self.results.append(FunctionDef(qualname=qualname, lineno=node.lineno))
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node):
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._handle_function(node)

    def visit_ClassDef(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()


def extract_functions(file_path: str) -> list[FunctionDef]:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=file_path)
    except (SyntaxError, ValueError, OSError):
        return []
    visitor = _FunctionVisitor()
    visitor.visit(tree)
    return visitor.results


def discover_project(root: str, exclude_dirs=None) -> list[FileEntry]:
    """Returns one FileEntry per .py file under root that defines at least
    one function or method. Files with zero functions are omitted -- there's
    nothing to report on for a pure-constants or empty __init__.py.
    """
    exclude_dirs = set(exclude_dirs) if exclude_dirs else set(DEFAULT_EXCLUDE_DIRS)
    entries: list[FileEntry] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in exclude_dirs and not d.startswith(".") and not d.endswith(".egg-info")
        ]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            full_path = os.path.join(dirpath, filename)
            functions = extract_functions(full_path)
            if not functions:
                continue
            rel_path = os.path.relpath(full_path, root).replace(os.sep, "/")
            entries.append(FileEntry(rel_path=rel_path, functions=functions))

    return entries
