"""Operational series: ignition conditions and rules of the six registry kinds (engineering proxies).

An :class:`Operation` sees :class:`~xzr.hpo.observe.Observation` objects only and returns *requests* in operational
terms (gate this region's boundary, scale these thresholds, connect these clusters …). The field compiles requests
into runtime intervention records; an operation never reads or writes the world.

One operation can carry several kinds (a composite formed by coupling): it ignites when any of its kinds ignites and
acts with the rule of every kind that ignited. Its *kind label* is the kinds joined by ``∘``. Kinds, parameters,
instrument and region are mutable state — other operations and the field may change them (field.py), and every
change is recorded with its before/after state.

Ignition outcome of one kind at one sample:

    FIRED         the condition holds on observed values
    NOT_FIRED     the condition was evaluated on observed values and does not hold
    UNOBSERVABLE  a value the condition needs was not observed (the reason is kept) — never read as 'no difference'
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .observe import InstrumentSpec, Observation

FIRED, NOT_FIRED, UNOBSERVABLE = "FIRED", "NOT_FIRED", "UNOBSERVABLE"

# ignition parameters / rule parameters per kind (development values, frozen with the protocol)
DEFAULT_IGN: dict[str, dict[str, float]] = {  # calibrated on development seeds (gen 0–7, regime intermittent)
    "withdrawal": {"threshold": 0.004, "persist": 2, "cease_after": 6},
    "transduction": {"threshold": 0.08, "min_activity": 0.002, "cease_after": 6},
    "concrescence": {"threshold": 1.2, "cease_after": 6},
    "picturing": {"tolerance": 1.0, "persist": 2, "cease_after": 6},
    "assemblage": {"threshold": 0.004, "cease_after": 6},
    "closure": {"threshold": 0.5, "cease_after": 6},
}
DEFAULT_RULE: dict[str, dict[str, float]] = {
    "withdrawal": {"depth": 0.35},
    "transduction": {"factor": 0.88, "step_clusters": 1, "split_size": 90},
    "concrescence": {"span": 4, "alpha": 0.6, "deposit_clusters": 2},
    "picturing": {"rate": 0.35, "revise_after": 4, "damp": 1.15},
    "assemblage": {"links": 3, "open": 1.3, "blocked": 0.5},
    "closure": {"closure": 0.4, "coupling": 2, "reproduce": 0.6, "low": 0.004, "irritation": 3.0, "adapt": 0.95},
}
# channels each kind needs: channel → (minimum level, maximum window)
NEEDS: dict[str, dict[str, tuple[int, int]]] = {
    "withdrawal": {"boundary_flow": (1, 8)},
    "transduction": {"tension": (2, 4), "activity": (1, 8), "boundary_flow": (2, 8)},
    "concrescence": {"activity": (1, 8)},
    "picturing": {"activity": (1, 8)},
    "assemblage": {"boundary_flow": (0, 8), "activity": (0, 8)},
    "closure": {"recursion": (1, 8), "activity": (1, 8), "boundary_flow": (1, 8)},
}
# which needs are *essential* (a missing optional channel degrades the rule, a missing essential one blocks ignition)
ESSENTIAL: dict[str, tuple[str, ...]] = {
    "withdrawal": ("boundary_flow",), "transduction": ("tension",), "concrescence": ("activity",),
    "picturing": ("activity",), "assemblage": ("boundary_flow",), "closure": ("recursion",),
}
DEFAULT_INSTRUMENT: dict[str, InstrumentSpec] = {
    "withdrawal": InstrumentSpec(level=1, window=4, period=2),
    "transduction": InstrumentSpec(level=2, window=4, period=2),
    "concrescence": InstrumentSpec(level=1, window=4, period=2),
    "picturing": InstrumentSpec(level=1, window=4, period=2, noise=0.05),
    "assemblage": InstrumentSpec(level=0, window=4, period=2),
    "closure": InstrumentSpec(level=1, window=4, period=2),
}
# request types (the action signature of an operation is its count per type)
REQUEST_TYPES = ("gate_boundary", "gate_internal", "veil", "scale_threshold_down", "scale_threshold_up", "connect",
                 "sever", "inject", "deposit_memory", "archive", "revise", "split", "couple")


@dataclass
class Request:
    type: str  # one of REQUEST_TYPES
    kind: str  # the kind whose rule issued it
    nodes: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int32))
    to_nodes: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int32))
    value: float = 0.0
    count: int = 0
    standing: bool = False  # part of the operation's standing overlay (replaced on each act of that kind)
    detail: dict = field(default_factory=dict)


@dataclass
class Ignition:
    outcome: str
    kind: str
    reason: str = ""  # unobservability reason or a short note
    value: float | None = None  # the observed quantity the condition read
    cease_vote: bool = False  # this kind's cessation condition holds at this sample


@dataclass
class Operation:
    oid: str
    kinds: tuple[str, ...]
    region: np.ndarray
    instrument: InstrumentSpec
    ign: dict[str, dict[str, float]]
    rule: dict[str, dict[str, float]]
    status: str = "dormant"  # dormant | active | ceased | subsumed
    lineage: list[str] = field(default_factory=list)
    mem: dict[str, Any] = field(default_factory=dict)  # per-kind internal memory (picture, occasion, counters)
    budget: float = 1.0  # resources per sample (measurement + acts)
    signature: dict[str, int] = field(default_factory=lambda: {t: 0 for t in REQUEST_TYPES})
    milieu: np.ndarray | None = None  # transduction: the field it individuates within
    created_at: int = 0

    @property
    def label(self) -> str:
        return "∘".join(self.kinds)

    def needs(self) -> dict[str, tuple[int, int]]:
        out: dict[str, tuple[int, int]] = {}
        for k in self.kinds:
            for ch, (lv, w) in NEEDS[k].items():
                a = out.get(ch)
                out[ch] = (max(lv, a[0]), min(w, a[1])) if a else (lv, w)
        if self.mem.get("_needs_symbol"):
            out["symbol"] = (0, 64)
        if "picturing" in self.kinds and "activity_trend" in self.mem.get("_variables", ()):
            out["activity_trend"] = (1, 16)
        return out

    def snapshot(self) -> dict:
        """Compact state for the causal history (before/after of every change)."""
        return {"oid": self.oid, "label": self.label, "status": self.status, "region_size": int(len(self.region)),
                "instrument": self.instrument.to_dict(), "ign": deepcopy(self.ign), "rule": deepcopy(self.rule),
                "budget": round(float(self.budget), 6)}

    # ------------------------------------------------------------------------------------------------ ignition
    def evaluate(self, obs: Observation) -> list[Ignition]:
        out = []
        for k in self.kinds:
            miss = [ch for ch in ESSENTIAL[k] if obs.reason(ch, self._clusters_for(k, obs, ch)) != ""]
            if self.mem.get("_needs_symbol") and obs.reason("symbol") != "":
                miss.append("symbol")
            if miss:
                ch = miss[0]
                out.append(Ignition(UNOBSERVABLE, k, obs.reason(ch, self._clusters_for(k, obs, ch)) or "unmeasurable"))
                continue
            out.append(getattr(self, f"_ign_{k}")(obs, self.ign[k], self.mem.setdefault(k, {})))
        return out

    def _clusters_for(self, kind: str, obs: Observation, channel: str) -> np.ndarray | None:
        if channel == "boundary_flow":
            return None  # a matrix: missing rows are checked by the rule itself
        if kind == "transduction" and self.milieu is not None:
            return np.unique(obs.labels[self.milieu]) if obs.labels is not None else None
        return obs.own_clusters

    def _inflow(self, obs: Observation) -> tuple[float, np.ndarray] | None:
        f = obs.values.get("boundary_flow")
        if f is None or not len(obs.own_clusters):
            return None
        own = np.zeros(obs.n_clusters, bool)
        own[obs.own_clusters] = True
        sub = f[~own][:, own]
        if np.isnan(sub).all():
            return None
        per_source = np.nansum(sub, axis=1)
        return float(np.nansum(sub)) / max(1, len(self.region)), per_source

    def _ign_withdrawal(self, obs, p, m) -> Ignition:
        r = self._inflow(obs)
        if r is None:
            return Ignition(UNOBSERVABLE, "withdrawal", obs.reason("boundary_flow") or "boundary_invisible")
        contact, _ = r
        m["streak"] = m.get("streak", 0) + 1 if contact > p["threshold"] else 0
        fired = m["streak"] >= p["persist"]
        return Ignition(FIRED if fired else NOT_FIRED, "withdrawal", value=contact,
                        cease_vote=contact < 0.5 * p["threshold"])

    def _ign_transduction(self, obs, p, m) -> Ignition:
        lab = obs.labels
        dom = np.unique(lab[self.region])
        mil = np.setdiff1d(np.unique(lab[self.milieu]) if self.milieu is not None else dom, dom)
        if not len(mil):
            return Ignition(NOT_FIRED, "transduction", "milieu exhausted", value=0.0, cease_vote=True)
        ten, ok = obs.get("tension", mil)
        act, ok2 = obs.get("activity", dom)
        if not ok.any():
            return Ignition(UNOBSERVABLE, "transduction", obs.reason("tension", mil) or "boundary_invisible")
        tension = float(np.nanmean(ten))
        activity = float(np.nanmean(act)) if ok2.any() else 0.0
        fired = tension > p["threshold"] and activity >= p["min_activity"]
        return Ignition(FIRED if fired else NOT_FIRED, "transduction", value=tension,
                        cease_vote=tension < 0.5 * p["threshold"])

    def _ign_concrescence(self, obs, p, m) -> Ignition:
        act, ok = obs.get("activity", obs.own_clusters)
        if ok.sum() < 2:
            return Ignition(UNOBSERVABLE, "concrescence", obs.reason("activity", obs.own_clusters) or "too few clusters")
        a = act[ok]
        contrast = float(a.std() / (a.mean() + 1e-9))
        if m.get("occasion"):
            return Ignition(FIRED, "concrescence", "concrescing", value=contrast)
        fired = contrast > p["threshold"]
        return Ignition(FIRED if fired else NOT_FIRED, "concrescence", value=contrast,
                        cease_vote=contrast < 0.5 * p["threshold"])

    def _ign_picturing(self, obs, p, m) -> Ignition:
        act, ok = obs.get("activity", obs.own_clusters)
        if not ok.any():
            return Ignition(UNOBSERVABLE, "picturing", obs.reason("activity", obs.own_clusters) or "boundary_invisible")
        pic = m.get("picture")
        if pic is None or m.get("picture_level") != obs.level or len(pic) != len(act):
            m["picture"], m["picture_level"] = np.where(ok, act, 0.0), obs.level
            m["streak"] = 0
            return Ignition(NOT_FIRED, "picturing", "picture initialised", value=0.0)
        trend, tok = obs.get("activity_trend", obs.own_clusters)
        pred = np.where(tok, pic + 0.5 * np.nan_to_num(trend), pic) if len(trend) == len(pic) else pic
        err = float(np.mean(np.abs(act[ok] - pred[ok])) / (np.mean(act[ok]) + 1e-3))
        m["error"] = err
        m["errors"] = m.get("errors", 0) + 1
        m["error_sum"] = m.get("error_sum", 0.0) + err
        m["streak"] = m.get("streak", 0) + 1 if err > p["tolerance"] else 0
        if m["streak"] == 1:
            m["error_onset"] = obs.t
        m["obs"] = np.where(ok, act, pic)
        return Ignition(FIRED if m["streak"] >= p["persist"] else NOT_FIRED, "picturing", value=err)

    def _ign_assemblage(self, obs, p, m) -> Ignition:
        f = obs.values.get("boundary_flow")
        comp = obs.own_clusters
        if f is None or len(comp) < 2:
            return Ignition(UNOBSERVABLE, "assemblage", obs.reason("boundary_flow") or "single component")
        sub = f[np.ix_(comp, comp)]
        if np.isnan(sub).all():
            return Ignition(UNOBSERVABLE, "assemblage", "boundary_invisible")
        flow = float(np.nansum(sub)) / max(1, len(self.region))
        m["flow"] = flow
        return Ignition(FIRED if flow > p["threshold"] else NOT_FIRED, "assemblage", value=flow,
                        cease_vote=flow < 0.25 * p["threshold"])

    def _ign_closure(self, obs, p, m) -> Ignition:
        rec, ok = obs.get("recursion", obs.own_clusters)
        act, ok2 = obs.get("activity", obs.own_clusters)
        if obs.reason("recursion", obs.own_clusters) not in ("",):
            return Ignition(UNOBSERVABLE, "closure", obs.reason("recursion", obs.own_clusters))
        activity = float(np.nanmean(act)) if ok2.any() else 0.0
        m["activity"] = activity
        if not ok.any():  # no ignition caused in the region: no recursion to read (not unobservable)
            return Ignition(NOT_FIRED, "closure", "no caused ignitions", value=0.0, cease_vote=activity == 0.0)
        recursion = float(np.nanmean(rec))
        return Ignition(FIRED if recursion > p["threshold"] else NOT_FIRED, "closure", value=recursion,
                        cease_vote=activity == 0.0)

    # ------------------------------------------------------------------------------------------------ rules
    def act(self, obs: Observation, fired: list[str], archive: list[dict]) -> list[Request]:
        reqs: list[Request] = []
        for k in fired:
            reqs += getattr(self, f"_act_{k}")(obs, self.rule[k], self.mem.setdefault(k, {}), archive)
        return reqs

    def _nodes_of(self, obs: Observation, clusters: np.ndarray) -> np.ndarray:
        assert obs.labels is not None
        return np.flatnonzero(np.isin(obs.labels, clusters)).astype(np.int32)

    def _act_withdrawal(self, obs, p, m, archive) -> list[Request]:
        out = [Request("gate_boundary", "withdrawal", self.region, value=p["depth"], standing=True,
                       detail={"direction": "both"}),
               Request("veil", "withdrawal", self.region, value=1.0 - p["depth"], standing=True),
               Request("archive", "withdrawal", self.region, detail={"what": "veil", "opacity": 1.0 - p["depth"]})]
        if not m.get("vicar_open"):
            r = self._inflow(obs)
            if r is not None and np.nansum(r[1]) > 0:
                own = np.zeros(obs.n_clusters, bool)
                own[obs.own_clusters] = True
                src_cluster = np.flatnonzero(~own)[int(np.nanargmax(r[1]))]
                out.append(Request("connect", "withdrawal", self._nodes_of(obs, np.array([src_cluster])), self.region,
                                   value=0.5, count=1, detail={"vicar": True}))
                m["vicar_open"] = True
        return out

    def _act_transduction(self, obs, p, m, archive) -> list[Request]:
        lab = obs.labels
        dom = np.unique(lab[self.region])
        mil = np.unique(lab[self.milieu]) if self.milieu is not None else dom
        cand = np.setdiff1d(mil, dom)
        f = obs.values.get("boundary_flow")
        if f is not None and not np.isnan(f[np.ix_(dom, cand)]).all():
            score = np.nansum(f[np.ix_(dom, cand)], axis=0) + np.nansum(f[np.ix_(cand, dom)], axis=1)
            front = cand[score > 0] if (score > 0).any() else cand
        else:  # no observed flow: address siblings (addresses are public), nearest codes first
            front = cand
        ten, _ = obs.get("tension", front)
        order = np.argsort(-np.nan_to_num(ten, nan=-1.0), kind="stable")
        pick = front[order[:int(p["step_clusters"])]]
        if not len(pick):
            return []
        new = self._nodes_of(obs, pick)
        self.region = np.union1d(self.region, new).astype(np.int32)
        out = [Request("scale_threshold_down", "transduction", self.region, value=p["factor"], standing=True)]
        if len(self.region) > p["split_size"]:
            out.append(Request("split", "transduction", self.region))
        return out

    def _act_concrescence(self, obs, p, m, archive) -> list[Request]:
        act, ok = obs.get("activity", obs.own_clusters)
        key = (obs.level, obs.own_clusters.tobytes())
        if m.get("occasion_key") != key:  # categories or nexus changed mid-occasion: the occasion starts afresh
            m["occasion"], m["occasion_key"] = [], key
        occ = m.setdefault("occasion", [])
        occ.append(np.where(ok, act, np.nan))
        if len(occ) < int(p["span"]):
            return []
        datum = np.nanmean(np.vstack(occ), axis=0)
        m["occasion"] = []
        m["occasions"] = m.get("occasions", 0) + 1
        datum = np.nan_to_num(datum)
        top = obs.own_clusters[np.argsort(-datum, kind="stable")[:int(p["deposit_clusters"])]]
        scale = float(datum.max()) if datum.max() > 0 else 0.0
        out = [Request("archive", "concrescence", self._nodes_of(obs, top),
                       detail={"what": "datum", "clusters": top.tolist(), "level": obs.level,
                               "datum": [round(float(x), 6) for x in datum], "t": obs.t})]
        if scale > 0:
            out.append(Request("deposit_memory", "concrescence", self._nodes_of(obs, top), value=p["alpha"]))
        return out

    def _act_picturing(self, obs, p, m, archive) -> list[Request]:
        out: list[Request] = []
        pic, cur = m.get("picture"), m.get("obs")
        if pic is None or cur is None:
            return out
        prior = m.get("prior")
        m["picture"] = pic + p["rate"] * (cur - pic)
        if prior is not None and len(prior) == len(pic):
            m["picture"] = 0.8 * m["picture"] + 0.2 * prior
        if m.get("streak", 0) >= p["revise_after"] and obs.level < 3:
            out.append(Request("revise", "picturing", detail={"level": obs.level + 1,
                                                               "error_onset": m.get("error_onset", obs.t)}))
            m["streak"] = 0
        pred = m["picture"]
        hot = obs.own_clusters[pred > max(2.0 * float(np.mean(pred)), 1e-9)]
        if len(hot):
            out.append(Request("scale_threshold_up", "picturing", self._nodes_of(obs, hot), value=p["damp"],
                               standing=True))
        return out

    def _act_assemblage(self, obs, p, m, archive) -> list[Request]:
        lab = obs.labels
        comp = obs.own_clusters
        out: list[Request] = []
        prev = m.get("prev_flow")
        flow = m.get("flow", 0.0)
        if prev is not None and flow < p["blocked"] * prev:
            # line of flight: cut internal links, connect to the most active macro cluster not yet a component
            act, ok = obs.get("activity")
            cand = np.setdiff1d(np.flatnonzero(ok), comp)
            out.append(Request("sever", "assemblage", self.region, count=int(p["links"])))
            if len(cand):
                tgt = cand[int(np.argmax(act[cand]))]
                out.append(Request("connect", "assemblage", self.region, self._nodes_of(obs, np.array([tgt])),
                                   value=0.4, count=int(p["links"]), detail={"line_of_flight": True,
                                                                             "extends_region": True}))
            m["flights"] = m.get("flights", 0) + 1
        else:
            parts = [np.intersect1d(self.region, np.flatnonzero(lab == c)) for c in comp]
            parts = [x for x in parts if len(x)]
            for a, b in zip(parts, parts[1:], strict=False):
                out.append(Request("connect", "assemblage", a, b, value=0.4, count=int(p["links"])))
            out.append(Request("gate_internal", "assemblage", self.region, value=p["open"], standing=True))
        m["prev_flow"] = flow
        return out

    def _act_closure(self, obs, p, m, archive) -> list[Request]:
        out: list[Request] = []
        r = self._inflow(obs)
        own = np.zeros(obs.n_clusters, bool)
        own[obs.own_clusters] = True
        keep = np.zeros(0, np.int32)
        if r is not None and np.nansum(r[1]) > 0:
            srcs = np.flatnonzero(~own)
            order = np.argsort(-np.nan_to_num(r[1]), kind="stable")[:int(p["coupling"])]
            coupling = srcs[order]
            keep = self._nodes_of(obs, coupling)
            m["irritation"] = m.get("irritation", 0.0) + float(np.nansum(r[1][order])) / max(1, len(self.region)) * 10
        out.append(Request("gate_boundary", "closure", self.region, to_nodes=keep, value=p["closure"], standing=True,
                           detail={"direction": "in"}))
        out.append(Request("veil", "closure", self.region, value=1.0 - p["closure"], standing=True))
        if m.get("activity", 0.0) < p["low"]:
            out.append(Request("inject", "closure", self.region, value=p["reproduce"]))
        if m.get("irritation", 0.0) > p["irritation"]:
            m["adapt"] = m.get("adapt", 1.0) * p["adapt"]
            m["irritation"] = 0.0
            m["adaptations"] = m.get("adaptations", 0) + 1
        if m.get("adapt", 1.0) != 1.0:
            out.append(Request("scale_threshold_down", "closure", self.region, value=m["adapt"], standing=True,
                               detail={"self_adjustment": True}))
        return out


def make(oid: str, kind: str, region: np.ndarray, t: int = 0, instrument: InstrumentSpec | None = None,
         milieu: np.ndarray | None = None, ign: dict | None = None, rule: dict | None = None) -> Operation:
    return Operation(oid, (kind,), np.asarray(region, np.int32), instrument or DEFAULT_INSTRUMENT[kind],
                     {kind: {**DEFAULT_IGN[kind], **(ign or {})}}, {kind: {**DEFAULT_RULE[kind], **(rule or {})}},
                     milieu=milieu, created_at=t)
