# `test_compat…[desktop-scipy]` — root-cause diagnosis (2026-10-20)

Test: `backend/tests/test_compat.py::test_engine_conformance_against_the_golden_fixture[desktop-scipy]` (the `ios-standins` variant passes).
Status: **FAILS in this environment, in the user's own checkout as well as in `feat/xb-tro`. Not caused by XB-TRO or by ARDS**
(no file under `lod/`, `_compat/`, `native/` or the test was changed by either).

## What differs

Against `tests/fixtures/conformance_reference.json` (generated natively on 2026-10-09 — `6804327`):

| scenario | exact fields that differ | observation fields |
|---|---|---|
| `small-600` | `hierarchy` only | (not listed: dynamics fingerprints equal) |
| `demo-3k` | `hierarchy` only | a few metrics differ in the 4th digit |
| `reason-lab` | `hierarchy` **and** all dynamics fingerprints (`fp_*`) | many metrics (it resolves address-based sets, so a different hierarchy changes the world) |

So the failure is a **different spatial hierarchy** (leaf paths of the recursive spectral bisection), not a numerical drift in the dynamics.

## Established mechanism (reproducible experiments, scripts and logs in this directory)

1. `hier_depth` — the first bisection matches the stored reference, and no node differs before depth 4 / 3 / 5 for `small-600` / `reason-lab` / `demo-3k` respectively; the first difference is inside sub-graphs of 75 / 375 / 188 nodes — all ≤ 400 nodes, i.e. the **dense `np.linalg.eigh` path** of `lod/hierarchy.py::_fiedler`.
2. `hier_sens` — the ARPACK path (> 400 nodes, tolerance 1e-4) is *not* the culprit: its first split (checked on `demo-3k` and `reason-lab`) is insensitive to start-vector perturbations from 1e-14 to 1e-6 and equals the reference.
3. `hier_dense` — in the two large cases the top eigenvalue of the sub-graph's normalised adjacency is **repeated** (λ1 − λ2 = 6.7e-16 and 4.4e-16): the induced sub-graph is **disconnected**, so "the second eigenvector" is any vector of a 2-D eigenspace — undefined by the data. Changing the LAPACK driver (`ev/evd/evr/evx`), permuting the node order, or using float32 changes the resulting split by 124–182 nodes. No variant reproduces the stored reference (58–187 nodes differ).
   The 75-node `small-600` case is connected (gap 9e-3) and differs by only **2 nodes** under the same perturbations: ties at the median of the sort — a smaller effect of the same kind.
4. `hier_count` — this is not an isolated case. Dense solves on disconnected sub-graphs per full hierarchy build: **130 (small-600), 294 (reason-lab), 184 (demo-3k)**; the ARPACK solves (2 / 6 / 14) are all on connected graphs.
5. `hier_torch` — an independent eigensolver (PyTorch `linalg.eigh`, float64 and float32) also fails to reproduce the reference (76–187 nodes) and disagrees with NumPy's (6 / 24 nodes).

**Conclusion (established):** the golden fixture records one arbitrary choice from an under-determined problem. `_fiedler` takes the eigenvector of the 2nd largest eigenvalue without handling a repeated eigenvalue (disconnected induced sub-graph), so the hierarchy — and everything that resolves addresses through it — depends on the eigensolver's rounding, not only on the graph.

## Why the result is arbitrary: an exact tie of hundreds of nodes (`hier_eigenspace.py`)

For the two degenerate sub-graphs the eigenspace of eigenvalue 1 is spanned by `D^{1/2}·1_component`, so the vector the algorithm sorts (`v·dinv`) is **mathematically constant on each connected component**: components of 362 + 13 nodes (`reason-lab`) and 185 + 3 nodes (`demo-3k`) — an exact tie of 362 and 185 nodes.

| quantity (sub-graph where the first difference appears) | `reason-lab` (375 nodes) | `demo-3k` (188 nodes) |
|---|---|---|
| connected components / sizes | 2 / [362, 13] | 2 / [185, 3] |
| relative spread of the *numerically computed* `v·dinv` inside a component (mathematically 0) | 1.3e-13, 5.7e-15 | 3.0e-14, 5.5e-16 |
| distinct splits reachable by rotating the numerically computed eigenvectors in the eigenspace (θ ∈ [0°,180°), 0.25° steps) | 318 | 213 |
| distinct splits with the **exact** tie-preserving vector (ties broken by node index) | **2** (which component comes first) | **2** |
| best disagreement of the stored reference with any of those splits | 157 (numerical) / 164 (exact) nodes | 60 / 90 nodes |

Reading: the *data* decide only one bit (which component is split off first); everything else is the order of the rounding noise inside the tie. The stored reference is not one of the two exact splits, nor a member of the numerical family sampled — it is one more noise-ordered outcome of the solver that produced it. **Sign and basis dependence is real**: rotating the basis of the 2-D eigenspace (a different but equally valid set of eigenvectors) changes the split; the code's sign convention (`dot(v, arange - m/2) < 0 → -v`) fixes only the overall sign, not the basis.

**Determinism**: for a fixed machine, library build and input order the same split is returned every time (the test is not flaky); it is a deterministic function of the solver's rounding, not of the graph alone. Permuting the node order, changing the LAPACK driver, or float32 changes it (`hier_dense.log`).

**LAPACK / OS / library differences**: NumPy's `eigh` here is Apple Accelerate (dynamically linked); a second implementation (PyTorch) and the SciPy drivers `ev/evd/evr/evx` all give different splits among themselves and from the reference.

## Mathematically valid ways to compare (proposals; nothing was changed)

The current exact comparison of the hierarchy digest asks a solver-dependent quantity to be bit-equal. Numerically equivalent outcomes are therefore reported as failures. Options that respect the mathematics:

1. **Remove the ill-posedness at the source (algorithm change).** Before any eigen-solve, split a disconnected induced sub-graph along its connected components (exact, solver-free), assign components to the halves by a data-determined rule (for example by size, then by smallest node index), and run the spectral step only on connected sub-graphs, where the Fiedler direction is unique up to sign. The hierarchy then becomes a function of the graph. This regenerates `_compat/hierarchies/*.npz`, both conformance fixtures and every result that resolves addresses on these scenarios, so it needs the owner's decision.
2. **Compare structural invariants instead of identities** for the desktop path: every split balanced (|size difference| ≤ 1), every leaf path unique-prefix consistent, the fraction of edges kept inside clusters at each of the four levels within a stated band of the reference's value. These are properties the algorithm guarantees or should preserve across solvers. They cannot replace the identity check for `reason-lab`, whose dynamics depend on the exact address sets.
3. **Keep the exact check only where it is meaningful**: the `ios-standins` variant uses the stored reference (an identity by construction) and passes; the desktop-vs-reference identity can be demoted to a recorded, non-blocking observation with the statistics above.

None of these was applied: the failing test is unchanged, no expectation was edited, and no fixture was regenerated.

## What narrows the trigger (circumstantial, not a demonstration)

* The stored XB-TRO records of 2026-10-18 carry `provenance: python 3.12.13, numpy 2.5.3` (e.g. `final/records/A_standard.json`). The original checkout's virtual environment
  (`xeno-ziran-runtime/.venv`) has exactly numpy 2.5.3 and scipy 1.18.1, **installed on 2026-09-29 and unchanged since** (file dates). In that same environment the test fails today.
* NumPy's `eigh` in that environment links the **system** Accelerate framework dynamically (`otool -L numpy/linalg/_umath_linalg*.so`).
* The system install history lists **macOS 27.0.1 installed on 2026-10-19 07:21** (and Command Line Tools 27.0 the same day), i.e. after the 2026-10-18 verification and before this one.

So the Python-level inputs are unchanged and the system LAPACK is the part that changed. That is consistent with an Accelerate behaviour change on a degenerate eigenspace. It is **not demonstrated**: the previous OS cannot be restored, and the 2026-10-18 test run itself was recorded only as a count (360 passed), not with its environment details.

## Not established

* That the macOS update is the trigger (see above).
* Which already-published experiment results depend on a hierarchy that is not reproducible by recomputation here: **not re-run** (UNVERIFIED). Results stored as files are unaffected; recomputing them here could give different address sets for the scenarios with disconnected sub-graphs.

## Decision recorded

No fix and no fixture regeneration were made. The old expectation cannot be shown to be "wrong" independently — it is one valid output among many — and any algorithmic fix (for example splitting a disconnected sub-graph by its connected components before any eigen-solve) changes the hierarchy of the bundled scenarios, the iOS/Pyodide reference files in `_compat/hierarchies/`, the fixtures, and possibly published results. That is a change to the research instrument and needs a decision by the owner. Options:

1. Make the hierarchy well-defined on disconnected sub-graphs (deterministic component split), regenerate `_compat/hierarchies/*.npz` and both conformance fixtures, re-run the experiments that depend on the three scenarios, and document the version change.
2. Keep the algorithm; make the conformance test compare the hierarchy only through a platform-independent property (and keep an exact check on the `ios-standins` path, which uses the stored reference), documenting that the desktop hierarchy of these scenarios is solver-dependent.
3. Pin the environment (numpy/scipy/BLAS) of the reference — not possible for Accelerate across OS updates.

The test was **not** skipped or loosened. It remains failing and is reported as a pre-existing, unresolved failure.
