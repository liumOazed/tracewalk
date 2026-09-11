"""Runtime tracer: actually execute the entry file once, as if you had typed
`python entry.py [args...]`, and count how many times each function defined
under the project root gets called.

Uses sys.setprofile rather than sys.settrace: profile events fire only on
call/return/c_call (no per-line events), which is both simpler and cheaper
for a pure call-counter. The profile function is global for the process --
Python dispatches a fresh 'call' event to it for every new frame regardless
of what any ancestor frame's handling decided, so filtering out
uninteresting frames never hides calls made from inside them.
"""

from __future__ import annotations

import collections
import os
import sys
import traceback

from .discover import DEFAULT_EXCLUDE_DIRS


class TraceResult:
    def __init__(self):
        self.counts: dict[tuple[str, int], int] = {}
        self.crashed = False
        self.crash_summary = ""


def _is_excluded(rel_path: str, exclude_dirs) -> bool:
    parts = rel_path.split("/")
    return any(p in exclude_dirs for p in parts[:-1])


def run_and_trace(
    entry_path: str,
    root: str,
    valid_keys: set,
    argv: list[str] | None = None,
) -> TraceResult:
    """valid_keys: the set of (rel_path, lineno) pairs the static AST pass
    already found. Only call events matching one of these are counted --
    that's what keeps a file's own module-level `import` execution (whose
    frame can legitimately report the same line number as a function
    defined at the top of that file) from being mistaken for a call to
    that function.
    """
    entry_abs = os.path.abspath(entry_path)
    root_abs = os.path.abspath(root)
    argv = argv or []

    counts: collections.Counter = collections.Counter()
    exclude_dirs = DEFAULT_EXCLUDE_DIRS

    def profiler(frame, event, arg):
        if event != "call":
            return
        code = frame.f_code
        if code.co_name.startswith("<"):
            # '<module>' (a file's own top-level execution -- its frame can
            # report the same starting line as a function defined on line 1
            # of that file), plus '<listcomp>'/'<genexpr>'/'<lambda>' etc.,
            # none of which are named functions we're tracking.
            return
        filename = frame.f_code.co_filename
        try:
            rel = os.path.relpath(filename, root_abs)
        except ValueError:
            return  # e.g. different drive on Windows
        if rel.startswith(".."):
            return  # outside the project root -- stdlib, site-packages, etc.
        rel = rel.replace(os.sep, "/")
        if _is_excluded(rel, exclude_dirs):
            return
        key = (rel, frame.f_code.co_firstlineno)
        if key in valid_keys:
            counts[key] += 1

    with open(entry_abs, "r", encoding="utf-8", errors="replace") as fh:
        source = fh.read()
    code = compile(source, entry_abs, "exec")

    entry_dir = os.path.dirname(entry_abs)
    old_argv = sys.argv
    old_path = list(sys.path)
    result = TraceResult()

    sys.argv = [entry_abs] + argv
    sys.path.insert(0, root_abs)
    sys.path.insert(0, entry_dir)

    module_globals = {
        "__name__": "__main__",
        "__file__": entry_abs,
        "__builtins__": __builtins__,
    }

    sys.setprofile(profiler)
    try:
        exec(code, module_globals)
    except SystemExit:
        pass
    except BaseException:
        result.crashed = True
        result.crash_summary = traceback.format_exc()
    finally:
        sys.setprofile(None)
        sys.argv = old_argv
        sys.path[:] = old_path

    result.counts = dict(counts)
    return result
