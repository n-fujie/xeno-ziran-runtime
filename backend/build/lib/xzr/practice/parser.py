"""Deterministic grammar for interventions typed into the Philosophical Practice console.

The parser maps a line of text onto exactly one structured :class:`Command` or raises
:class:`ParseError` with suggestions. It never guesses by similarity of meaning. If a language model is
integrated later, its only role is to emit lines in this grammar.

Targets: ``c123`` / ``#123`` / ``configuration 123`` (one configuration), ``@3.1.0`` (cluster address),
or the name of a set defined by the scenario.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

NUM = r"(-?\d+(?:\.\d+)?)"
NAME = r"([A-Za-z0-9_@#.\-:]+)"
LIST = r"([A-Za-z0-9_\-]+(?:\s*,\s*[A-Za-z0-9_\-]+)*)"
ARROW = r"\s*(?:->|→|=>|to)\s*"


@dataclass
class Command:
    op: str
    args: dict = field(default_factory=dict)
    text: str = ""

    def to_json(self) -> dict:
        return {"op": self.op, "args": self.args, "text": self.text}


class ParseError(ValueError):
    def __init__(self, msg: str, suggestions: list[str] | None = None):
        super().__init__(msg)
        self.suggestions = suggestions or []


GRAMMAR: list[tuple[str, str, str]] = [
    # (op, regex, example)
    ("remove_concept", rf"(?:remove|delete|drop) concept {NAME}$", "remove concept human"),
    ("restore_concept", rf"(?:restore|reintroduce|introduce) concept {NAME}$", "restore concept human"),
    ("weaken", rf"weaken (?:commitment|claim) {NAME}(?: by {NUM})?$", "weaken commitment K2 by 0.5"),
    ("strengthen", rf"strengthen (?:commitment|claim) {NAME}(?: by {NUM})?$", "strengthen commitment K2 by 0.3"),
    ("withdraw", rf"withdraw (?:claim|commitment) {NAME}$", "withdraw claim K4"),
    ("assert", rf"(?:assert|introduce|commit to) (?:claim|commitment) {NAME}(?: (?:strength|at) {NUM})?$",
     "assert claim K4 strength 0.8"),
    ("revise", rf"revise (?:claim|commitment) {NAME} (?:strength|to) {NUM}$", "revise claim K3 strength 0.4"),
    ("introduce_claim",
     rf"introduce (?:new )?claim {NAME} uses {LIST}(?: binds (scale_threshold|gate|memory_condition|freeze) {NAME}"
     rf"(?: {NUM})?)?(?: from ([A-Za-z0-9_,\s]+))?$",
     "introduce claim K9 uses boundary binds gate B1 0.2 from K1"),
    ("reconnect", rf"reconnect (?:claim )?{NAME} from ([A-Za-z0-9_,\s]+)$", "reconnect K3 from K1,K5"),
    ("disconnect_claim", rf"disconnect (?:claim )?{NAME} from {NAME}$", "disconnect K3 from K2"),
    ("remove_boundary", rf"(?:remove|dissolve|open) boundary {NAME}$", "remove boundary B1"),
    ("restore_boundary", rf"restore boundary {NAME}$", "restore boundary B1"),
    ("set_boundary", rf"set boundary {NAME} (?:permeability|gate) (?:to )?{NUM}$", "set boundary B1 permeability 0.5"),
    ("set_threshold", rf"(?:change|set) (?:ignition )?threshold (?:of )?(?:configuration )?{NAME} (?:to )?{NUM}$",
     "change ignition threshold of configuration c42 to 0.6"),
    ("scale_threshold", rf"scale (?:ignition )?threshold (?:of )?{NAME} by {NUM}$", "scale threshold @3.1 by 1.3"),
    ("sever", rf"(?:sever|cut) (?:relation |connection )?{NAME}{ARROW}{NAME}$", "sever relation c12 -> c40"),
    ("connect", rf"connect {NAME}{ARROW}{NAME}(?: weight {NUM})?$", "connect c12 -> c40 weight 0.6"),
    ("memory_condition",
     rf"introduce (?:new )?memory condition(?: on| for)? {NAME}(?: decay {NUM})?(?: coupling {NUM})?$",
     "introduce new memory condition on @2.1 decay 0.98 coupling 0.3"),
    ("freeze", rf"freeze {NAME}$", "freeze @5.2"),
    ("inject", rf"inject {NUM} (?:at|into) {NAME}$", "inject 3 at @1.0.2"),
    ("compare", rf"compare(?: baseline)?(?: (?:against|vs\.?|with) intervention)?(?: horizon {NUM})?$",
     "compare baseline against intervention horizon 200"),
    ("apply", r"apply(?: intervention)?$", "apply"),
    ("discard", r"(?:discard|reset)(?: intervention)?$", "discard"),
    ("show", rf"(?:show|explain) (?:dependencies (?:of |for )?)?{NAME}$", "show dependencies human"),
    ("help", r"help$", "help"),
]
_COMPILED = [(op, re.compile(rx, re.IGNORECASE), ex) for op, rx, ex in GRAMMAR]


def _num(x: str | None, default: float | None = None) -> float | None:
    return default if x is None else float(x)


def _list(x: str | None) -> list[str]:
    return [s for s in re.split(r"[,\s]+", x or "") if s]


def parse(text: str) -> Command:
    line = " ".join(text.strip().split())
    line = line.rstrip(".;")
    if not line:
        raise ParseError("empty command", [ex for _, _, ex in GRAMMAR[:6]])
    for op, rx, _ in _COMPILED:
        m = rx.match(line)
        if not m:
            continue
        g = m.groups()
        args: dict
        if op in ("remove_concept", "restore_concept", "withdraw", "remove_boundary", "restore_boundary", "freeze",
                  "show"):
            args = {"name": g[0]}
        elif op == "weaken":
            args = {"claim": g[0], "factor": _num(g[1], 0.5)}
        elif op == "strengthen":
            args = {"claim": g[0], "amount": _num(g[1], 0.5)}
        elif op == "assert":
            args = {"claim": g[0], "strength": _num(g[1], 1.0)}
        elif op == "revise":
            args = {"claim": g[0], "strength": float(g[1])}
        elif op == "introduce_claim":
            args = {"claim": g[0], "uses": _list(g[1]), "binding": None, "premises": _list(g[5])}
            if g[2]:
                args["binding"] = {"op": g[2], "target": g[3], "factor": _num(g[4], 1.0)}
        elif op == "reconnect":
            args = {"claim": g[0], "premises": _list(g[1])}
        elif op == "disconnect_claim":
            args = {"claim": g[0], "premise": g[1]}
        elif op == "set_boundary":
            args = {"name": g[0], "permeability": float(g[1])}
        elif op == "set_threshold":
            args = {"target": g[0], "value": float(g[1])}
        elif op == "scale_threshold":
            args = {"target": g[0], "factor": float(g[1])}
        elif op == "sever":
            args = {"a": g[0], "b": g[1]}
        elif op == "connect":
            args = {"a": g[0], "b": g[1], "weight": _num(g[2], 0.5)}
        elif op == "memory_condition":
            args = {"target": g[0], "decay": _num(g[1]), "coupling": _num(g[2])}
        elif op == "inject":
            args = {"amount": float(g[0]), "target": g[1]}
        elif op == "compare":
            args = {"horizon": int(float(g[0])) if g[0] else 150}
        else:
            args = {}
        return Command(op, args, line)
    first = line.split()[0].lower()
    sugg = [ex for _, _, ex in GRAMMAR if ex.split()[0] == first] or [ex for _, _, ex in GRAMMAR]
    raise ParseError(f"not a recognized intervention: {line!r}", sugg[:8])


def help_text() -> list[str]:
    return [ex for _, _, ex in GRAMMAR]
