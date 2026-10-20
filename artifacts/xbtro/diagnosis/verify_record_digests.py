"""Recompute the results digest of every stored XB-TRO record and compare it with the digest stored in the record.

    cd backend && ../.venv/bin/python ../artifacts/xbtro/diagnosis/verify_record_digests.py

Read-only. Exit status 1 if any record does not match (a record edited after it was written would fail).
"""

import glob
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "backend"))
from xzr.xbtro.records import digest  # noqa: E402

bad = 0
for f in sorted(glob.glob(os.path.join(HERE, "..", "final", "records", "*.json"))):
    d = json.load(open(f))
    ok = digest(d["results"]) == d["digest"]
    bad += not ok
    print(f"{os.path.basename(f):42} stored digest == recomputed digest of results: {ok}")
print("records whose digest does not match:", bad)
sys.exit(1 if bad else 0)
