# tracewalk

Run a Python entry point once and see which functions across your project
actually fired -- rolled up into a folder → file → function tree, with
anything that never ran flagged.

## Install

```
pip install tracewalk-0.1.0-py3-none-any.whl
```

(or, from the source folder: `pip install .`)

## Use

From inside your project folder:

```
tracewalk                 # auto-detects main.py / app.py / run.py / manage.py / __main__.py / start.py / cli.py
tracewalk bot.py          # or name the entry file explicitly -- required if none of the above exist
tracewalk bot.py -- --live --symbol BTC   # anything after `--` is forwarded to your script's argv
tracewalk --root ../api app.py --open     # trace a project elsewhere and open the report when done
```

This actually executes your entry file once (as `python bot.py` would), so
anything it normally does -- hitting a real API, placing a real order,
writing to a real file -- will genuinely happen. Point it at a run you'd
be comfortable making anyway (a dry-run/paper-trading mode, a dev config,
a small sample input), not a production trigger.

## Output

Two files land in your project folder (or `--out DIR` if given):

- `trace.json` -- the raw folder/file/function tree with call counts.
- `trace_report.html` -- a self-contained report; double-click it, no
  server needed. Click any folder or file to expand it; functions that
  were never called during the run are flagged.

## How it works

1. **Static pass** -- walks every `.py` file under the project root (skipping
   `venv`, `__pycache__`, `.git`, `node_modules`, and similar) and parses each
   with `ast` to list every function and method defined, regardless of
   whether it ever runs.
2. **Dynamic pass** -- runs your entry file once under `sys.setprofile`,
   counting how many times each of those functions is actually called.
3. The two are merged by (file, line number) so renamed-but-identical
   function names never get confused, and rolled into the tree the report
   renders.

## Limitations (v0.1)

- Only named `def`/`async def` functions and methods are tracked --
  lambdas and dynamically-generated code aren't shown as separate rows.
- One run = one trace. If your program only exercises one code path per
  run (e.g. a CLI with subcommands), run it multiple times against the
  same `--out` and merge manually for now -- multi-run merging is a
  natural next step.
- Traces the whole process for that one run, so very long-lived programs
  (servers that don't exit) should be stopped with Ctrl+C once they've
  done what you want to measure; tracewalk still writes a report from
  whatever was captured before the interrupt propagates.
