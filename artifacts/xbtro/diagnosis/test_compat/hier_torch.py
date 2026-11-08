import sys, numpy as np, torch
sys.dont_write_bytecode = True
z = np.load('/private/tmp/claude-501/-Users-user-Desktop-BIM/c8087b50-1670-488b-afed-5830b085b01e/scratchpad/subgraphs.npz')
print("numpy", np.__version__, "torch", torch.__version__, "torch BLAS/LAPACK:", torch.backends.mkl.is_available() and "MKL" or "no-MKL", torch.__config__.show().count("Accelerate") and "Accelerate" or "")
for name in ["small-600", "reason-lab", "demo-3k"]:
    norm, dinv, refbit = z[f"{name}__norm"], z[f"{name}__dinv"], z[f"{name}__refbit"]; mm = len(dinv)
    def split(vec):
        v = vec * dinv
        if np.dot(v, np.arange(mm) - mm/2) < 0: v = -v
        o = np.argsort(v, kind="stable"); lab = np.zeros(mm, int); lab[o[mm//2:]] = 1; return lab
    mism = lambda l: int(min((l != refbit).sum(), (l == refbit).sum()))
    a = split(np.linalg.eigh(norm)[1][:, -2])
    b = split(torch.linalg.eigh(torch.from_numpy(norm))[1][:, -2].numpy())
    c = split(torch.linalg.eigh(torch.from_numpy(norm).float())[1][:, -2].double().numpy())
    print(f"{name} ({mm} nodes): numpy.eigh vs reference {mism(a)}; torch.eigh(f64) vs reference {mism(b)}; torch.eigh(f32) vs reference {mism(c)}; "
          f"torch(f64) vs numpy {int(min((a!=b).sum(), (a==b).sum()))}")
