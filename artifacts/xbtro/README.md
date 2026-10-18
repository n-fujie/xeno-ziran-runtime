# XB-TRO verification artifacts

* `final/` — the final experiment records (JSON and CSV), `index.json` (record id, digest, seeds, code commit, seconds) and `SUMMARY.md`
  (generated from the records). Regenerate: `python backend/scripts/run_xbtro_final.py artifacts/xbtro/final` then
  `python backend/scripts/summarize_xbtro_final.py artifacts/xbtro/final`.
* `history/` — superseded measurements that are kept (the first version of Experiment G, with its explanation).
* `pyodide_s1.json` — the recording of the S1 body sequence made in the in-browser (Pyodide) runtime; compare with the desktop transports by
  `python backend/scripts/xbtro_paths.py artifacts/xbtro/pyodide_s1.json` (HTTP, native bridge and Pyodide: 210 values, identical at the
  recorded resolution of 6 decimals).
* `desktop_digests.json`, `browser_digests.json` — the digests of the standard small experiment set (4 seeds; `backend/scripts/xbtro_digests.py`)
  on the desktop and in the browser (Pyodide, no threads, cooperative job slices, built from the same commit): all 13 are equal.

Not covered: an iOS device (none was available). The embedded engine is the same bridge module, but no behaviour is claimed on iOS.
