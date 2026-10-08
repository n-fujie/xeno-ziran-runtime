"""Run bench_one.py configurations sequentially under a safety guard (temporary harness).

    python guard.py OUT.jsonl RSS_LIMIT_MB TIME_LIMIT_S  MODE:N:STEPS:SEED[:CKPT] ...

Each configuration runs in its own process; the guard samples its RSS every 0.5 s and kills it when RSS exceeds
the limit or the time limit passes, recording the failure instead of a result. Stops the sequence at the first
failure (no larger configuration is attempted after an unsafe one).
"""
import json
import subprocess
import sys
import time

HERE = "/private/tmp/claude-501/-Users-user-Desktop-BIM/dcb36de2-4dd5-4451-aecd-272ab49a0cdc/scratchpad/cap"
PY = "/Users/user/Desktop/BIM/xeno-ziran-runtime/.venv/bin/python"


def rss(pid: int) -> float:
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return int(out) / 1024 if out else 0.0


def swap_used_mb() -> float:
    out = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout
    return float(out.split("used = ")[1].split("M")[0])


def main() -> None:
    out_path, limit, tlimit = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    for spec in sys.argv[4:]:
        args = spec.split(":")
        t0 = time.time()
        swap0 = swap_used_mb()
        p = subprocess.Popen([PY, f"{HERE}/bench_one.py", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env={"OMP_NUM_THREADS": "1", "PATH": "/usr/bin:/bin",
                                             "BENCH_CALIB": f"{HERE}/calibration-private.json"})
        peak, reason = 0.0, None
        while p.poll() is None:
            r = rss(p.pid)
            peak = max(peak, r)
            if r > limit:
                reason = f"RSS {r:.0f} MB > limit {limit:.0f} MB"
            elif time.time() - t0 > tlimit:
                reason = f"time {time.time() - t0:.0f} s > limit {tlimit:.0f} s"
            if reason:
                p.kill()
                break
            time.sleep(0.5)
        stdout, stderr = p.communicate()
        rec = {"spec": spec, "guard_peak_rss_mb": round(peak, 1), "guard_wall_s": round(time.time() - t0, 1),
               "swap_used_mb_before": swap0, "swap_used_mb_after": swap_used_mb()}
        if reason or p.returncode != 0:
            rec["status"] = "FAILED"
            rec["failure"] = reason or f"exit {p.returncode}: {stderr[-800:]}"
        else:
            rec["status"] = "OK"
            rec.update(json.loads(stdout.strip().splitlines()[-1]))
        with open(out_path, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(json.dumps({k: rec.get(k) for k in ("spec", "status", "failure", "init_total_s", "init_hierarchy_s",
                                                  "steps_per_s", "segment_steps_per_s", "peak_rss_mb",
                                                  "guard_peak_rss_mb", "wall_s", "edges_alive_initial")}), flush=True)
        if rec["status"] != "OK":
            break


if __name__ == "__main__":
    main()
