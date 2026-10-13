"""Ziran System — Heterogeneous Philosophical Operations (HPO).

An experiment layer on top of the runtime. Several *operational series* — engineering proxies named after the
philosophical operations they approximate (``registry.py``) — run inside one simulated world, ignite under
configuration-dependent conditions, act on the world only through runtime intervention records, and can change one
another's ignition conditions, rules, instruments, resources, history and partition (``field.py``). Every change is
stored with its state before and after and its causes (``causal.py``).

Separation of what the world is and what an operation can know:

    world.py       the simulated world: engine, exogenous input stream, true state (read by the harness only)
    observe.py     instruments: what an operation can observe, at which resolution, period and through which boundary;
                   every value that cannot be observed carries a reason (never a zero)
    operations.py  the operational series; they see Observations only and return requests (acts), never touch the world
    field.py       configuration + interaction engine: ignition, competition, coupling, splitting, transformation,
                   cessation, re-ignition, history reinsertion, reclassification
    reconfig.py    HPO-003: changes of the experiment's own settings, inside a whitelisted sandbox schema
    experiments.py HPO-001 / HPO-002 / HPO-003 protocols, paired runs and analysis

Nothing here is a formalisation of a philosophical system, and no result of this layer is evidence for or against a
philosophical doctrine: the proxies are named after their sources so the correspondence (and its limits) can be
inspected, see ``registry.py`` and docs/HPO.md.
"""
