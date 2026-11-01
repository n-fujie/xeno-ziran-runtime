"""A finite synthetic world for the model-against-sensor comparison of the AI-law line (R14-R16): eight Boolean variables (256 states), six intervention conditions, two observation modes.

This is **this implementation's** world, written from the operational description in the request (8 Booleans, 256 states, 6 conditions, 1,536 comparisons, a hidden stipulated condition ``q``, ACCESS_ONLY and EXPANDED observation). The
world of the manuscript's Appendix O was not available, so its counts (model access 32, 32, 32, 32, 40, 60; sensor access 32, 32, 32, 32, 32, 42; disagreements 8 and 18) are **not** reproduced and nothing here is calibrated to them.
Everything is SYNTHETIC: the numbers say what the world defined here does, and nothing about any institution, law or person.

Variables (bit order a = 1 ... h = 128)
  a, b, c  the conditions of eligibility (c is the one that a correction can repair)
  d        a claim has been received
  e        a correction has been declared
  f        a plan exists
  g        the gate / approval is given
  h        the hidden stipulated condition q: the downstream holder still keeps the old denial (it is not part of the model's inputs and is seen only in the EXPANDED mode)
"""

from __future__ import annotations

from typing import Any

BITS = ("a", "b", "c", "d", "e", "f", "g", "h")
CONDITIONS = ("BASE", "RECEIPT_ONLY", "DECLARATION_ONLY", "PLAN_ONLY", "EXEC_GATE", "EXEC_LINKED")
MODES = ("ACCESS_ONLY", "EXPANDED")
N_STATES = 1 << len(BITS)


def bit(s: int, name: str) -> bool:
    return bool(s >> BITS.index(name) & 1)


def pack(**kw: bool | int) -> int:
    return sum(1 << BITS.index(k) for k, v in kw.items() if v)


def baseline_access(s: int) -> bool:
    return bit(s, "a") and bit(s, "b") and bit(s, "c")


def model_access(s: int, cond: str) -> bool:
    """What the institution's model computes: an execution is expected to restore access to whoever has lodged a claim (under the gate; linked, also with a plan). Nothing else changes access."""
    y0 = baseline_access(s)
    if cond == "EXEC_GATE":
        return y0 or (bit(s, "d") and bit(s, "g"))
    if cond == "EXEC_LINKED":
        return y0 or (bit(s, "d") and bit(s, "f") and bit(s, "g"))
    return y0


def sensor_access(s: int, cond: str) -> bool:
    """What the synthetic sensor reports (the stipulated truth of the world): an execution restores access only where the downstream holder is clear of the old denial (not h); a gate execution without a linked plan repairs only
    those whose single gap is c (a and b hold)."""
    y0 = baseline_access(s)
    if cond == "EXEC_GATE":
        return y0 or (bit(s, "d") and bit(s, "g") and bit(s, "a") and bit(s, "b") and not bit(s, "h"))
    if cond == "EXEC_LINKED":
        return y0 or (bit(s, "d") and bit(s, "f") and bit(s, "g") and not bit(s, "h"))
    return y0


def observe(s: int, cond: str, mode: str) -> dict[str, Any]:
    """One observation. ACCESS_ONLY returns the model's and the sensor's access. EXPANDED adds the hidden condition q, which the experimenter stipulated: it is not something the observation device found by itself."""
    if mode not in MODES or cond not in CONDITIONS:
        raise ValueError("unknown mode or condition")
    m, sn = model_access(s, cond), sensor_access(s, cond)
    out: dict[str, Any] = {"model": m, "sensor": sn, "mismatch": m != sn, "mode": mode, "q": None, "cause_identified": False}
    if mode == "EXPANDED":
        out["q"] = bit(s, "h")
        out["cause_identified"] = bool(m != sn and bit(s, "h"))
    return out


# ------------------------------------------------------------------------------------------------ an equal-information Boolean comparator (a different coding of the same inputs)
_MASK = {"a": 1, "b": 2, "c": 4, "d": 8, "e": 16, "f": 32, "g": 64, "h": 128}


def boolean_model(s: int, cond: str) -> bool:
    """The ordinary Boolean model with exactly the information of the world's model: bit masks, no history, no versions, no events. Its answer is the model's."""
    y0 = (s & 7) == 7
    if cond == "EXEC_GATE":
        return y0 or (s & (_MASK["d"] | _MASK["g"])) == (_MASK["d"] | _MASK["g"])
    if cond == "EXEC_LINKED":
        return y0 or (s & (_MASK["d"] | _MASK["f"] | _MASK["g"])) == (_MASK["d"] | _MASK["f"] | _MASK["g"])
    return y0


def boolean_sensor(s: int, cond: str) -> bool:
    y0 = (s & 7) == 7
    if cond == "EXEC_GATE":
        return y0 or (s & (_MASK["d"] | _MASK["g"] | _MASK["a"] | _MASK["b"] | _MASK["h"])) == (_MASK["d"] | _MASK["g"] | _MASK["a"] | _MASK["b"])
    if cond == "EXEC_LINKED":
        return y0 or (s & (_MASK["d"] | _MASK["f"] | _MASK["g"] | _MASK["h"])) == (_MASK["d"] | _MASK["f"] | _MASK["g"])
    return y0


def enumerate_world() -> dict[str, Any]:
    """All 256 states under all 6 conditions (1,536 comparisons), in both observation modes: counts of access by the model and by the sensor, the disagreements, how many of them the EXPANDED mode attributes to q, and the
    agreement of the equal-information Boolean comparator."""
    per: dict[str, dict[str, int]] = {}
    boolean_agree_model = boolean_agree_sensor = comparisons = 0
    for cond in CONDITIONS:
        m = s_ = mm = ident = 0
        for s in range(N_STATES):
            o_a, o_e = observe(s, cond, "ACCESS_ONLY"), observe(s, cond, "EXPANDED")
            m += o_a["model"]
            s_ += o_a["sensor"]
            mm += o_a["mismatch"]
            ident += o_e["cause_identified"]
            comparisons += 1
            boolean_agree_model += boolean_model(s, cond) == o_a["model"]
            boolean_agree_sensor += boolean_sensor(s, cond) == o_a["sensor"]
        per[cond] = {"model_access": m, "sensor_access": s_, "disagreements": mm, "cause_identified_expanded": ident, "cause_identified_access_only": 0}
    return {"states": N_STATES, "conditions": list(CONDITIONS), "comparisons": comparisons, "per_condition": per, "boolean_model_agrees": boolean_agree_model, "boolean_sensor_agrees": boolean_agree_sensor,
            "historical_counts_reproduced": False,
            "note": "this implementation's own world; the manuscript's Appendix O counts were not available and are not reproduced"}
