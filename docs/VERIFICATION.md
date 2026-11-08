# Verification — the Brassier Machine as an evidence ledger

Code: `backend/xzr/verification/` (`brassier.py`, `demo.py`), route `backend/xzr/service/verification.py` (`/api/verification/brassier/demo`, local runtime only, 403 when `XZR_PUBLIC=1`), view `?view=verification` (`frontend/src/views/verification/`), tests `backend/tests/test_verification.py` (9) and `VerificationView.test.tsx` (3). The package is excluded from the iOS and browser bundles by `ios/scripts/stage_engine.py`.

**Source classification: NEW EXECUTION on SYNTHETIC worlds.** Nothing here describes a real system, and the earlier Brassier Machine documents (R35, R37, OEII-R11) are **not in this repository**: the seven checks follow the integration directive's list of functions, and their mapping onto the earlier six filters and the S/W division is **not verified**.

## What it is, and what it is not

A ledger. It takes the evidence of a run (observations, interventions, comparisons, with seeds and provenance) and keeps, for each ontological claim, a verdict **SUPPORTED / WITHHELD / WITHDRAWN**, the evidence for it (negative results included), and the conditions that would revise or withdraw it. It holds **no authority** over what is real: no function returns "true", "real" or "exists", and every verdict says `authority: none`. It adds no ontological principle.

| check | what is recorded |
|---|---|
| independence | whether anything other than the stating model's own output stands behind the claim (`MODEL_ONLY` is flagged, not refuted) |
| source fidelity | whether a passage of an outside theory is registered for the claim (`NOT_APPLICABLE` without a source); it does not judge the reading |
| world warrant | supporting, contradicting and inconclusive world evidence; contradicting items are listed and kept |
| interventional identification, equivalence (`identify`) | whether competing mechanisms agree under the protocol in force and, if so, whether a discriminating protocol (more sensors, an intervention, a longer window) separates them: `IDENTIFIED` by it, `PARTLY_IDENTIFIED`, or **`OPEN`** |
| revision | which revision of an instrument, variable or state space would reopen the claim (recorded, not decided) |
| withdrawal | the reasons a claim is held back or withdrawn, and its stated withdrawal conditions |

`SUPPORTED` needs world evidence independent of the stating model and no unresolved equivalence; `WITHDRAWN` when the world evidence contradicts the claim; everything else is `WITHHELD`.

## The four acceptance conditions, as tested

1. **Existing results are not changed**: `with_brassier` returns the base results as the same object, unread (a test runs a real SBS simulation and compares the arrays before and after).
2. **Unresolved equivalence returns OPEN**: the `hidden_label` pair of the demonstration agrees under every protocol offered and is `OPEN`; `OPEN` is documented as not meaning "the same".
3. **Beside a standard comparison**: the same passive observations are scored by Gaussian AIC and BIC. For the `clamp_vs_free` pair the predictions are identical, so the criteria differ only through the parameter count; the ledger records the equivalence and that a `clamp` intervention separates the mechanisms.
4. **Negative results, seeds, intervention conditions and provenance are kept** in a digest-sealed record (`verify_record` fails if a verdict is changed or a negative result removed; both are tested).

Removal, disabling and reintroduction is the argument `enabled` (disabled: an empty ledger, base results identical).

**No truth leakage**: `identify` receives only functions from a protocol to observations; a test checks its signature and that swapping the labels of the mechanisms does not change the result. In the demonstration the generating mechanism is a function the verifier cannot inspect by name.

## The demonstration

Three synthetic pairs: `clamp_vs_free` (identical under passive observation; separated by the `clamp` intervention: `IDENTIFIED`), `hidden_label` (no protocol reaches the difference: `OPEN`), `gain_vs_offset` (differ already under passive observation). Three claims: one `SUPPORTED` (identified by the intervention), one `WITHHELD` (only the model's output, equivalence open), one `WITHDRAWN` (a contradicting observation, kept in the record).

## Not done

* No claim that the machine improves on standard methods: the demonstration only shows what it records that the standard comparison does not.
* No integration with the XB-TRO / GAISHO / SBS records yet: the ledger takes any evidence a caller supplies, but only the synthetic demonstration is wired.
* The view shows the demonstration; it is not yet a general research-records browser.
