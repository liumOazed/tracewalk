"""Command-line entry point for tracewalk.

    tracewalk                    # auto-detect the entry file in the cwd
    tracewalk run.py             # trace a specific entry file
    tracewalk bot.py -- --live   # forward args after `--` to the traced script
    tracewalk --root ../api app.py --open
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser

from .build import build_tree, compute_stats
from .discover import discover_project
from .report import write_report
from .tracer import run_and_trace

AUTO_DETECT_CANDIDATES = ["main.py", "app.py", "run.py", "manage.py", "__main__.py", "start.py", "cli.py"]


def find_entry(explicit: str | None, root: str) -> str:
    if explicit:
        candidate_abs = explicit if os.path.isabs(explicit) else os.path.join(root, explicit)
        if not os.path.isfile(candidate_abs):
            raise SystemExit(f"tracewalk: entry file not found: {explicit}")
        return os.path.relpath(candidate_abs, root).replace(os.sep, "/")

    found = [c for c in AUTO_DETECT_CANDIDATES if os.path.isfile(os.path.join(root, c))]
    if len(found) == 1:
        return found[0]
    if not found:
        tried = ", ".join(AUTO_DETECT_CANDIDATES)
        raise SystemExit(
            "tracewalk: couldn't auto-detect an entry file "
            f"(looked for: {tried}).\n"
            "Run again with the file explicitly, e.g.:  tracewalk your_script.py"
        )
    raise SystemExit(
        "tracewalk: found more than one possible entry file "
        f"({', '.join(found)}) -- pass one explicitly, e.g.:  tracewalk {found[0]}"
    )


def _split_passthrough(argv: list[str]) -> tuple[list[str], list[str]]:
    if "--" in argv:
        idx = argv.index("--")
        return argv[:idx], argv[idx + 1:]
    return argv, []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tracewalk",
        description="Run a Python entry point once and see which functions across your project actually fired.",
    )
    parser.add_argument(
        "entry", nargs="?", default=None,
        help="entry file to run, relative to --root (e.g. main.py, run.py). "
             "If omitted, tracewalk looks for a common name (main.py, app.py, run.py, ...).",
    )
    parser.add_argument("--root", default=".", help="project root to scan and trace (default: current directory)")
    parser.add_argument("--out", default=None, help="where to write trace.json / trace_report.html (default: --root)")
    parser.add_argument("--open", action="store_true", help="open trace_report.html in your browser when done")
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else argv
    cli_argv, script_argv = _split_passthrough(raw_argv)

    args = build_parser().parse_args(cli_argv)

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        raise SystemExit(f"tracewalk: no such directory: {args.root}")
    out_dir = os.path.abspath(args.out) if args.out else root

    entry_rel = find_entry(args.entry, root)
    entry_abs = os.path.join(root, entry_rel)

    print(f"tracewalk: scanning {root}")
    file_entries = discover_project(root)
    total_static_fns = sum(len(fe.functions) for fe in file_entries)
    print(f"tracewalk: found {total_static_fns} function(s) across {len(file_entries)} file(s)")

    valid_keys = {(fe.rel_path, fn.lineno) for fe in file_entries for fn in fe.functions}

    print(f"tracewalk: running python {entry_rel}" + (f" -- {' '.join(script_argv)}" if script_argv else ""))
    result = run_and_trace(entry_abs, root, valid_keys, argv=script_argv)
    if result.crashed:
        print("tracewalk: the traced run raised an exception -- the report will only reflect what ran before that", file=sys.stderr)

    tree = build_tree(file_entries, result.counts, entry_rel)
    stats = compute_stats(tree["children"])
    project_name = os.path.basename(root.rstrip(os.sep)) or root

    json_path, html_path = write_report(
        tree, out_dir, project_name, entry_rel,
        crash_summary=result.crash_summary if result.crashed else None,
    )

    pct = round(100 * stats["used"] / stats["total"]) if stats["total"] else 0
    print(f"tracewalk: {stats['used']}/{stats['total']} functions called ({pct}%) -- {stats['unused_files']} file(s) entirely unused")
    print(f"tracewalk: wrote {json_path}")
    print(f"tracewalk: wrote {html_path}")

    if args.open:
        webbrowser.open(f"file://{html_path}")

    return 1 if result.crashed else 0


if __name__ == "__main__":
    sys.exit(main())
