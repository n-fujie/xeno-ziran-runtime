"""Optional interpretation of recurrent operational shapes.

Labels are attached *after* shape detection, to signatures that already exist. They read signature
axes only; they cannot reach the runtime, and removing this module changes nothing that is simulated.
Every label is shown together with the rule that produced it, so it can be contested.

Axis levels are relative (0 = lower third, 1 = middle third, 2 = upper third of clusters at that moment).
"""

from __future__ import annotations

from dataclasses import dataclass

DISCLAIMER = ("Interpretive labels are optional analogies attached to recurrent operational shapes. "
              "They are not detected categories and carry no predictive claim.")


@dataclass(frozen=True)
class Rule:
    label: str
    when: dict[str, tuple[int, ...]]  # axis -> accepted levels
    gloss: str

    def matches(self, axes: dict[str, int]) -> bool:
        return all(axes.get(a) in levels for a, levels in self.when.items())

    def describe(self) -> str:
        return " ∧ ".join(f"{a}∈{{{','.join(map(str, v))}}}" for a, v in self.when.items())


DEFAULT_RULES: tuple[Rule, ...] = (
    Rule("commitment-cluster-like", {"L": (2,), "M": (2,), "R": (1, 2)},
         "closed loops that remember and whose differences come back"),
    Rule("credit-like", {"R": (2,), "K": (2,), "I": (0, 1)},
         "retained difference that returns later rather than igniting now"),
    Rule("institution-like", {"K": (2,), "M": (2,), "L": (2,), "I": (0, 1)},
         "persistent, remembering closure with moderate ignition"),
    Rule("market-like", {"I": (2,), "L": (2,), "B": (0, 1)},
         "dense, looped, frequent ignition without a dominant bottleneck"),
    Rule("relay-like", {"B": (2,), "L": (0, 1)}, "many transition paths pass through; little closure"),
    Rule("reservoir-like", {"K": (2,), "I": (0,)}, "retains difference, rarely ignites"),
    Rule("burst-like", {"I": (2,), "K": (0,), "M": (0, 1)}, "frequent ignition, little retention"),
    Rule("dormant", {"I": (0,), "L": (0,), "R": (0,)}, "no ignition, closure or return at present"),
)


def interpret(shapes: list[dict], rules: tuple[Rule, ...] = DEFAULT_RULES) -> dict:
    out = []
    for s in shapes:
        hits = [{"label": r.label, "rule": r.describe(), "gloss": r.gloss} for r in rules if r.matches(s["axes"])]
        out.append({"signature": s["signature"], "labels": hits})
    return {"disclaimer": DISCLAIMER, "interpretations": out,
            "rules": [{"label": r.label, "rule": r.describe(), "gloss": r.gloss} for r in rules]}


def rules_from_json(items: list[dict] | None) -> tuple[Rule, ...]:
    if not items:
        return DEFAULT_RULES
    return tuple(Rule(i["label"], {k: tuple(v) for k, v in i["when"].items()}, i.get("gloss", "")) for i in items)
