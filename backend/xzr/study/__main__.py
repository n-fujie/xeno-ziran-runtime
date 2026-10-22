"""``python -m xzr.study`` — command line for studies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import analysis, report, runner, templates
from . import protocol as P


def _study(path: str) -> runner.Study:
    p = Path(path)
    if not (p / "protocol.json").exists():
        sys.exit(f"{path}: not a study directory (no protocol.json)")
    return runner.Study(p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m xzr.study", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("templates", help="list protocol templates")
    n = sub.add_parser("new", help="write a protocol from a template")
    n.add_argument("template")
    n.add_argument("--out", required=True)
    n.add_argument("--seeds", type=int, default=None)
    n.add_argument("--mode", default=None)
    v = sub.add_parser("validate", help="validate a protocol file and print fairness issues")
    v.add_argument("protocol")
    c = sub.add_parser("create", help="create a study directory from a protocol file")
    c.add_argument("protocol")
    c.add_argument("--root", default=str(runner.DEFAULT_ROOT))
    r = sub.add_parser("run", help="execute (or resume) a study")
    r.add_argument("study")
    r.add_argument("--procs", type=int, default=1)
    r.add_argument("--inline", action="store_true")
    for name in ("status", "analyse", "report", "package", "stop"):
        s = sub.add_parser(name)
        s.add_argument("study")
    vf = sub.add_parser("verify", help="check a study directory against checksums.json")
    vf.add_argument("study")
    rp = sub.add_parser("reproduce", help="re-execute the registered protocol and compare")
    rp.add_argument("study")
    rp.add_argument("--out", required=True)
    rp.add_argument("--procs", type=int, default=1)
    am = sub.add_parser("amend", help="record a change to the protocol after registration")
    am.add_argument("study")
    am.add_argument("--path", required=True)
    am.add_argument("--value", required=True, help="JSON value")
    am.add_argument("--reason", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "templates":
        for k in templates.TEMPLATES:
            print(k)
    elif a.cmd == "new":
        kw = {}
        if a.seeds is not None:
            kw["n_seeds"] = a.seeds
        if a.mode and a.template == "revision-study":
            kw["mode"] = a.mode
        Path(a.out).write_text(json.dumps(templates.template(a.template, **kw), indent=1, ensure_ascii=False))
        print(a.out)
    elif a.cmd == "validate":
        doc = json.loads(Path(a.protocol).read_text())
        issues = P.validate(doc)
        print(
            json.dumps(
                {
                    "issues": issues,
                    "fairness_undeclared": [] if issues else P.fairness_issues(doc),
                    "digest": P.digest(doc),
                    "runs": P.n_runs(doc) if not issues else None,
                },
                indent=1,
            )
        )
        return 1 if issues else 0
    elif a.cmd == "create":
        st = runner.Study.create(json.loads(Path(a.protocol).read_text()), Path(a.root))
        print(st.path)
    elif a.cmd == "run":
        print(json.dumps(_study(a.study).execute(procs=a.procs, inline=a.inline), indent=1))
    elif a.cmd == "status":
        print(json.dumps(_study(a.study).status(), indent=1))
    elif a.cmd == "stop":
        _study(a.study).stop()
    elif a.cmd == "analyse":
        an = analysis.analyse(_study(a.study))
        print(an["criteria"]["verdict"])
    elif a.cmd == "report":
        st = _study(a.study)
        an = analysis.analyse(st)
        print(json.dumps(report.build(st, an), indent=1))
    elif a.cmd == "package":
        print(report.package(_study(a.study)))
    elif a.cmd == "verify":
        res = report.verify(Path(a.study))
        print(json.dumps(res, indent=1))
        return 0 if res["ok"] else 1
    elif a.cmd == "reproduce":
        new, cmp = runner.reproduce(_study(a.study), Path(a.out), procs=a.procs)
        print(json.dumps({"new": str(new.path), **cmp}, indent=1))
        return 0 if cmp["identical_share"] == 1.0 else 2
    elif a.cmd == "amend":
        print(json.dumps(_study(a.study).amend(a.path, json.loads(a.value), a.reason), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
