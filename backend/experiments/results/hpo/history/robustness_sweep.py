import traceback, time
from xzr.hpo import experiments as X
def safe(fn):
    def g(a):
        try: fn(a); return None
        except Exception: return (a, traceback.format_exc())
    return g
def j2(a): return X.hpo002_job((a, {**X.WORLD, "_range": "smoke"}, {}, X.HPO002_CONDITIONS, a == 0))
def jg(a): return X.general_job((a[0], a[1], "smoke"))
def j1(a): return X.hpo001_job((a, "smoke"))
def j3(a): return X.hpo003_job((a, "smoke"))
F = {"j2": j2, "jg": jg, "j1": j1, "j3": j3}
def run(arg):
    name, a = arg
    try: F[name](a); return None
    except Exception: return (name, a, traceback.format_exc())
if __name__ == "__main__":
    t=time.time()
    args = [("j2", i) for i in range(64)] + [("jg", (i, n)) for n in X.GENERAL_SETTINGS for i in range(16)] \
        + [("j1", i) for i in range(16)] + [("j3", i) for i in range(24)]
    errs = [e for e in X.run_pool(run, args, 7) if e]
    print("jobs", len(args), "errors", len(errs), "secs", round(time.time()-t))
    for e in errs[:3]: print(e[0], e[1]); print(e[2][-1500:])
