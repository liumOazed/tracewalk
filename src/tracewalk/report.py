"""Renders the merged trace tree to trace.json and a self-contained
trace_report.html (double-click to open, no server needed).
"""

from __future__ import annotations

import datetime
import html
import importlib.resources
import json
import os


def _load_template() -> str:
    ref = importlib.resources.files("tracewalk.templates").joinpath("report_template.html")
    return ref.read_text(encoding="utf-8")


def _safe_json_for_script(data: dict) -> str:
    # Guard against a stray "</script>" inside data breaking out of the
    # embedding <script> tag -- harmless for our own generated data, but
    # cheap insurance since function/file names come from the user's code.
    return json.dumps(data).replace("</", "<\\/")


def write_report(tree: dict, out_dir: str, project_name: str, entry_rel: str, crash_summary: str | None = None) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)

    json_path = os.path.join(out_dir, "trace.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(tree, fh, indent=2)

    if crash_summary:
        safe = html.escape(crash_summary)
        crash_banner = (
            '<div class="crash-banner"><strong>Heads up:</strong> the traced run raised an '
            "exception before finishing, so this report only reflects what executed up to "
            f"that point.<pre>{safe}</pre></div>"
        )
    else:
        crash_banner = ""

    template = _load_template()
    html_out = (
        template
        .replace("__PROJECT_NAME__", html.escape(project_name))
        .replace("__ENTRY__", html.escape(entry_rel))
        .replace("__GENERATED_AT__", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
        .replace("__CRASH_BANNER__", crash_banner)
        .replace("__TRACE_DATA_JSON__", _safe_json_for_script(tree))
    )

    html_path = os.path.join(out_dir, "trace_report.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html_out)

    return json_path, html_path
