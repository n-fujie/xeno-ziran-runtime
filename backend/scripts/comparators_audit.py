"""Audit of the prior methods a non-redundancy claim would have to be compared with: is there a formal implementation in the repositories on this machine, and is it
connected to a Study Engine environment as an arm? A method that has a name but no implementation, or an implementation that is not an arm, is NOT compared.
Probes the file system (sources are searched for markers of each method; imports into the study layers are searched for connections). Changes nothing."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BIM = REPO.parent
ROOTS = [
    REPO / "backend" / "xzr",
    REPO / "research",
    BIM / "pa-simulation-environment" / "src",
    BIM / "ziran-xeno-simulator" / "embodied",
    BIM / "ziran-xeno-simulator" / "comparison",
]
STUDY_LAYERS = [REPO / "backend" / "xzr" / "study", REPO / "backend" / "xzr" / "totalobs", REPO / "backend" / "xzr" / "hpo"]
EXT = {".py", ".ts"}

# (method, reference to verify before use in a paper, implementation markers, how a connection to a study environment would appear)
DEF = r"(?:def|class|function|const|export\s+function)\s+\w*"
METHODS = [
    (
        "Active Inference",
        "Friston et al. 2015, Active inference and epistemic value (expected free energy: pragmatic + epistemic)",
        DEF + r"(?:expected_free_energy|expectedFreeEnergy|ActiveInference|efe\b|vfe\b)",
        r"post_active_inference|aif_vendor|active_inference",
    ),
    (
        "Active Learning",
        "Settles 2009, Active learning literature survey (uncertainty sampling, query by committee, expected error reduction)",
        DEF + r"(?:uncertainty_sampling|query_by_committee|QueryByCommittee|active_learning|ActiveLearner)",
        r"active_learning|uncertainty_sampling",
    ),
    (
        "Active Sensing / information-gain sensor selection",
        "e.g. Chaloner & Verdinelli 1995, Bayesian experimental design (expected information gain)",
        DEF + r"(?:information_gain|expected_information|select_sensor|sensor_selection|active_sensing)",
        r"sensor_selection|active_sensing|information_gain",
    ),
    (
        "Bayesian Optimization",
        "Shahriari et al. 2016, Taking the human out of the loop (Gaussian process, acquisition function)",
        DEF + r"(?:expected_improvement|gaussian_process|GaussianProcess|acquisition_function|bayes\w*opt)",
        r"bayes_opt|gaussian_process",
    ),
    (
        "Adaptive control",
        "Astrom & Wittenmark, Adaptive control (self-tuning, model-reference)",
        DEF + r"(?:pid_controller|PIDController|model_reference_adaptive|self_tuning|adaptive_control)",
        r"adaptive_control|pid_controller",
    ),
    (
        "The project's own prior adaptive observation procedure (ARDS existing-blind)",
        "King et al. 2009 (Adam); Williams et al. 2015 (Eve); Kitano 2021 (Nobel Turing Challenge) are the broader family; this procedure is the project's own earlier one",
        r"existingBlind|EXISTING-blind",
        r"existing_blind|existingBlind",
    ),
]
FILES = {
    "Active Inference": r"expected_free_energy|aif_vendor|policy_selection|generative_model"
}  # implementations whose function names are terse (efe, vfe)
PROSE = ("lineage.py", "nonredundancy", "comparators_audit", "programme_templates", "totalobs_templates", "protocol_audit")


def scan(pattern: str, roots: list[Path]) -> list[str]:
    rx = re.compile(pattern, re.I)
    hits = []
    for r in roots:
        if not r.exists():
            continue
        for p in r.rglob("*"):
            if (
                p.suffix in EXT
                and p.is_file()
                and "node_modules" not in p.parts
                and "__pycache__" not in p.parts
                and not any(x in str(p) for x in PROSE)
            ):
                try:
                    if rx.search(p.read_text(errors="ignore")):
                        hits.append(str(p.relative_to(BIM)))
                except OSError:
                    pass
    return sorted(hits)


def audit() -> list[dict]:
    out = []
    for name, ref, marker, conn in METHODS:
        impl = scan(marker, ROOTS)
        if name in FILES:
            impl += [
                str(p.relative_to(BIM)) for r in ROOTS if r.exists() for p in r.rglob("*.py") if re.search(FILES[name], p.name)
            ]
        impl = sorted({h for h in impl if "/tests/" not in h and "test_" not in h})
        connected = scan(conn, STUDY_LAYERS)
        in_env = name.startswith("The project") and any("ards/loop2" in h for h in impl)
        status = (
            "implemented as an arm in a study environment (ARDS existing-blind in the ARDS-HPO shared environment, test replicates only)"
            if in_env
            else "implemented elsewhere; NOT connected to any study environment as an arm"
            if impl and not connected
            else "connected"
            if impl and connected
            else "not implemented"
        )
        out.append(
            {
                "method": name,
                "reference_to_verify": ref,
                "implementation_files": impl[:6],
                "imports_into_study_layers": connected[:6],
                "status": status,
                "compared_in_this_repository": in_env,
            }
        )
    return out


NOTES = [
    "ARDS EXISTING-E (loop/existing.ts) is oracle-informed: it reads the simulator's truth, so it is NOT information-matched and cannot support a non-redundancy claim; the observer-side re-implementation (existing-blind) is the comparator.",
    "HPO random-matched is a control (same number of random valid changes), not a prior method.",
    "A prior method counts as compared only when it is an arm with the same information, intervention authority, change authority and computation budget as the P/A arm (docs/research/COMPARATORS.md).",
]

if __name__ == "__main__":
    res = {"methods": audit(), "notes": NOTES}
    Path(sys.argv[1]).write_text(json.dumps(res, indent=1))
    for m in res["methods"]:
        print(f"{m['method']:52s} {m['status']}")
