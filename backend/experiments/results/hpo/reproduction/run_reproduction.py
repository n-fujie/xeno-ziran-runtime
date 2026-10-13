import json, sys, time
from pathlib import Path
from xzr.hpo import experiments as X
OUT = Path(sys.argv[1])
if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    print("protocol", X.protocol_hash()[:12], "pinned", X.PROTOCOL_SHA256[:12], flush=True)
    for name, fn in [("hpo002", lambda: X.hpo002(360, 7)), ("hpo001", lambda: X.hpo001(64, 7)),
                     ("general", lambda: X.generalization(64, 7)), ("hpo003", lambda: X.hpo003(96, 7, 64))]:
        t = time.time(); print("===", name, time.strftime("%H:%M:%S"), flush=True)
        X.write(name, fn(), root=OUT)
        print("done", name, round(time.time() - t), "s", flush=True)
    print("=== all done", flush=True)
