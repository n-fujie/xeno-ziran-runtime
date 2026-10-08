"""``xzr`` — command-line interface to the XENO ZIRAN SIMULATOR research runtime.

    xzr presets                         list the bundled experiment presets
    xzr validate CONFIG                 check a preset name or configuration file; print the effective configuration
    xzr run CONFIG [--seeds N] [--seed0 S] [--out DIR] [--procs P]
                                        run an experiment into a new directory (never overwrites)
    xzr compare RESULT_A RESULT_B       cell-by-cell change of detection status between two runs
    xzr export RESULT [--format csv|json]
    xzr study NAME [--procs P]          the long published studies (results in backend/experiments/results)
    xzr --version

Exit codes: 0 success; 1 the experiment ran but recorded failures (or the command failed at run time);
2 invalid usage or configuration. Everything runs locally; no network access is needed or made.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__

STUDIES = {
    "matrix": "resolution matrix (63 conditions; hours on 8 cores; resumable)",
    "disconnection": "targeted disconnection study",
    "topology_triggers": "cut / reconfiguration trigger distinction",
    "adaptivity": "world-responsive revision (adaptivity) study",
    "clusters": "multiple interacting reasoning clusters",
    "compression": "long-run compression (up to 40,000 steps)",
    "reduction": "primitive reduction study (~25 min on 8 cores)",
    "reason": "reasoning-layer non-redundancy suite",
}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="xzr", description="XENO ZIRAN SIMULATOR research runtime: run, compare and "
                                "export operational experiments. Experimental instruments, not an ontology.")
    p.add_argument("--version", action="version", version=f"xzr {__version__}")
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    sub.add_parser("presets", help="list the bundled experiment presets")
    v = sub.add_parser("validate", help="validate a preset or configuration file and print the effective configuration")
    v.add_argument("config", help="preset name or path to a configuration JSON file")

    r = sub.add_parser("run", help="run an experiment (preset or configuration file)")
    r.add_argument("config", help="preset name or path to a configuration JSON file")
    r.add_argument("--seeds", type=int, help="override the number of engine seeds")
    r.add_argument("--seed0", type=int, help="override the first engine seed")
    r.add_argument("--out", default="xzr-results", help="output root (default ./xzr-results)")
    r.add_argument("--procs", type=int, default=4, help="worker processes (default 4)")
    r.add_argument("--json", action="store_true", help="print the result JSON instead of the summary")

    c = sub.add_parser("compare", help="compare the detection status of two results")
    c.add_argument("a", help="result.json or run directory (A)")
    c.add_argument("b", help="result.json or run directory (B)")
    c.add_argument("--json", action="store_true", help="print every cell as JSON")

    e = sub.add_parser("export", help="export a result as CSV (one row per status cell) or JSON")
    e.add_argument("result", help="result.json or run directory")
    e.add_argument("--format", choices=("csv", "json"), default="csv")
    e.add_argument("--output", help="write to this file instead of stdout (refuses to overwrite)")

    s = sub.add_parser("study", help="run one of the long published studies (writes backend/experiments/results)")
    s.add_argument("name", choices=sorted(STUDIES))
    s.add_argument("--procs", type=int, default=7)
    return p


def _fail(msg: str, code: int = 2) -> int:
    print(f"xzr: error: {msg}", file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    from . import presets, results

    if args.command == "presets":
        for name in presets.names():
            cfg = presets.load(name)
            print(f"{name:24s} {cfg['kind']:10s} seeds {cfg['seeds']:>2}  {cfg.get('description', '')}")
        return 0

    if args.command == "validate":
        try:
            cfg = presets.load(args.config)
        except presets.ConfigError as e:
            return _fail(str(e))
        print(json.dumps(presets.effective(cfg), indent=1))
        return 0

    if args.command == "run":
        try:
            cfg = presets.load(args.config)
            if args.seeds is not None or args.seed0 is not None:
                cfg = {**cfg, **({"seeds": args.seeds} if args.seeds is not None else {}),
                       **({"seed0": args.seed0} if args.seed0 is not None else {})}
                presets.validate(cfg)
        except presets.ConfigError as e:
            return _fail(str(e))
        if args.procs < 1:
            return _fail("--procs must be ≥ 1")
        eff = presets.effective(cfg)
        try:
            run_dir = results.execute(eff, Path(args.out), args.procs)
        except results.RunExistsError as e:
            return _fail(str(e))
        res = results.load(run_dir)
        print(json.dumps(res, indent=1) if args.json else (run_dir / "summary.txt").read_text())
        print(f"results: {run_dir}", file=sys.stderr)
        return 1 if res["failures"] else 0

    if args.command == "compare":
        try:
            a, b = results.load(args.a), results.load(args.b)
        except (OSError, ValueError) as e:
            return _fail(str(e))
        cmp_ = results.compare(a, b)
        if args.json:
            print(json.dumps(cmp_, indent=1))
        else:
            print(f"A = {cmp_['a']}  B = {cmp_['b']}")
            for k, n in sorted(cmp_["counts"].items()):
                print(f"  {k:18s} {n}")
            for row in cmp_["cells"]:
                if row["label"] != "same":
                    print(f"  {row['label']:18s} {row['condition']} / {row['comparison']} / {row['measure']}: "
                          f"{row['a']} → {row['b']}")
            print(cmp_["note"])
        return 0

    if args.command == "export":
        try:
            res = results.load(args.result)
        except (OSError, ValueError) as e:
            return _fail(str(e))
        text = results.export_csv(res) if args.format == "csv" else json.dumps(res, indent=1)
        if args.output:
            out = Path(args.output)
            if out.exists():
                return _fail(f"{out} exists; refusing to overwrite")
            out.write_text(text)
        else:
            sys.stdout.write(text)
        return 0

    if args.command == "study":
        import os
        for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
            os.environ.setdefault(var, "1")  # one BLAS thread per worker process
        from .experiments.escalation.harness import RESULTS  # backend/experiments/results/resolution
        if not (RESULTS.parents[2] / "pyproject.toml").exists():
            return _fail("`xzr study` writes the published result files of a source checkout "
                         "(backend/experiments/results); run it from a clone of the repository, not an installed copy. "
                         "Use `xzr run` for experiments anywhere.")
        if args.name == "reduction":
            from .experiments.reduction import main as reduction_main
            reduction_main(str(RESULTS.parent / "reduction.json"))
        elif args.name == "reason":
            from .experiments.reason import main as reason_main
            reason_main(str(RESULTS.parent / "reason.json"), args.procs)
        elif args.name == "matrix":
            from .experiments.escalation.matrix import design
            from .experiments.escalation.runner import run_conditions
            conds, omitted = design()
            run_conditions(conds, RESULTS / "matrix.json", args.procs, meta={"omitted": omitted, "conditions": len(conds)})
        else:
            import importlib
            importlib.import_module(f"xzr.experiments.escalation.{args.name}").main(args.procs)
        return 0
    return _fail(f"unknown command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
