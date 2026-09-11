"""Merges the static function inventory (discover.py) with the dynamic call
counts (tracer.py) into the nested folder -> file -> function tree the
report page expects: {"type": "folder"|"file"|"fn", "name": ..., "children": [...]}
with "fn" leaves carrying a "calls" integer.

Functions are matched between the two passes by (relative file path, the
line number the `def` starts on) rather than by name, since that's stable
across Python versions and immune to name collisions between, say, two
different classes' `__init__`.
"""

from __future__ import annotations

from .discover import FileEntry


def _insert(tree: dict, file_entry: FileEntry, counts: dict):
    parts = file_entry.rel_path.split("/")
    *folders, filename = parts
    cursor = tree
    for folder in folders:
        cursor = cursor.setdefault(folder, {})

    fn_nodes = []
    for fn in file_entry.functions:
        calls = counts.get((file_entry.rel_path, fn.lineno), 0)
        fn_nodes.append({"type": "fn", "name": fn.qualname + "()", "calls": calls})

    cursor[filename] = {"__file__": True, "children": fn_nodes}


def _to_nodes(d: dict) -> list:
    nodes = []
    for key in sorted(d.keys(), key=str.lower):
        val = d[key]
        if val.get("__file__"):
            if val["children"]:
                nodes.append({"type": "file", "name": key, "children": val["children"]})
        else:
            child_nodes = _to_nodes(val)
            if child_nodes:
                nodes.append({"type": "folder", "name": key + "/", "children": child_nodes})
    return nodes


def build_tree(file_entries: list[FileEntry], counts: dict, entry_rel: str) -> dict:
    """entry_rel: the traced entry file's path relative to root, used only
    to label the synthetic top node -- the entry file still appears as a
    normal file in the tree if it defines any functions of its own.
    """
    raw: dict = {}
    for fe in file_entries:
        _insert(raw, fe, counts)

    children = _to_nodes(raw)
    return {"type": "run", "name": f"python {entry_rel}", "children": children}


def compute_stats(tree_children: list) -> dict:
    """Quick totals for a CLI summary line -- the report page recomputes
    its own aggregates client-side, this is just for the terminal.
    """
    total = used = unused_files = 0

    def walk(node):
        nonlocal total, used, unused_files
        if node["type"] == "fn":
            total += 1
            if node["calls"] > 0:
                used += 1
            return
        file_total = file_used = 0
        for c in node.get("children", []):
            before_total, before_used = total, used
            walk(c)
            if node["type"] == "file" and c["type"] == "fn":
                file_total += total - before_total
                file_used += used - before_used
        if node["type"] == "file" and file_total > 0 and file_used == 0:
            unused_files += 1

    for c in tree_children:
        walk(c)

    return {"total": total, "used": used, "unused_files": unused_files}
