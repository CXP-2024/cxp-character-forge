# Re-hang skirt accessories on a re-solved skirt window: bows follow rigidly (Kabsch on their nearest skirt points),
# Acc_BB vertices follow the mean displacement (new - old skirt) of their nearest skirt points. Anchors are picked once
# at frame A-1 in the old caches. Edits OUT_DIR in place (OUT_DIR/skirt_f0rest.mdd is the new skirt).
# usage: python acc_follow.py OLD_DIR OUT_DIR A B
import numpy as np, struct, sys
from pathlib import Path
from scipy.spatial import cKDTree
OLD, OUT = Path(sys.argv[1]), Path(sys.argv[2]); A, B = int(sys.argv[3]), int(sys.argv[4])
def rd(p):
    d = open(p, 'rb').read(); n, nv = struct.unpack('>2i', d[:8]); return d[:8 + 4 * n], np.frombuffer(d[8 + 4 * n:], '>f4').reshape(n, nv, 3).copy()
_, So = rd(OLD / 'skirt_f0rest.mdd'); _, Sn = rd(OUT / 'skirt_f0rest.mdd'); tree = cKDTree(So[A - 1])
for name in ('SkirtBow_BL', 'SkirtBow_BR', 'SkirtBow_FL', 'SkirtBow_FR', 'Acc_BB'):
    hdr, X = rd(OLD / f'{name}_f0rest.mdd'); Y = X.copy()
    if name.startswith('SkirtBow'):
        _, nn = tree.query(X[A - 1].mean(0), 24)
        for f in range(A, B + 1):
            a = So[f, nn]; b = Sn[f, nn]; ac, bc = a.mean(0), b.mean(0); U, _, Wt = np.linalg.svd((a - ac).T @ (b - bc))
            R = U @ np.diag([1, 1, np.sign(np.linalg.det(U @ Wt))]) @ Wt; Y[f] = (X[f] - ac) @ R + bc
    else:
        dist, nn = tree.query(X[A - 1], 6); w = 1 / np.maximum(dist, 1e-3); w /= w.sum(1, keepdims=True)
        for f in range(A, B + 1): Y[f] = X[f] + ((Sn[f, nn] - So[f, nn]) * w[..., None]).sum(1)
    open(OUT / f'{name}_f0rest.mdd', 'wb').write(hdr + Y.astype('>f4').tobytes())
    print(name, 'max move mm', round(float(np.linalg.norm(Y - X, axis=2).max() * 1000), 1))
