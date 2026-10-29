# Splice several real-skirt window solves into a copy of a song cache. Windows are given in order as NPY:START; each
# fades in over FD frames (from the old cache for the first window, from the previous window where they overlap,
# starting XO frames into the overlap) and the last one fades back to the old cache over FO frames.
# usage: python splice_windows.py SRC_DIR OUT_DIR FD XO FO NPY:START [NPY:START ...]
import numpy as np, struct, shutil, sys
from pathlib import Path
SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2]); FD, XO, FO = map(int, sys.argv[3:6])
W = [(np.load(a.rsplit(':', 1)[0]), int(a.rsplit(':', 1)[1])) for a in sys.argv[6:]]
OUT.mkdir(exist_ok=True)
for f in SRC.glob('*.mdd'):
    if f.name != 'skirt_f0rest.mdd': shutil.copy(f, OUT / f.name)
d = open(SRC / 'skirt_f0rest.mdd', 'rb').read(); n, nv = struct.unpack('>2i', d[:8]); hdr = d[:8 + 4 * n]
X = np.frombuffer(d[8 + 4 * n:], '>f4').reshape(n, nv, 3).copy()
ss = lambda u: (lambda c: c * c * (3 - 2 * c))(np.clip(u, 0, 1))
for k, (Y, A) in enumerate(W):
    s0 = A if k == 0 else A + XO
    for i in range(len(Y)):
        f = A + i; w = ss((f - s0) / FD) if f >= s0 else 0.0
        if k == len(W) - 1 and FO: w = min(w, ss((len(Y) - 1 - i) / FO))
        X[f] = X[f] * (1 - w) + Y[i] * w
    print('window', A, A + len(Y) - 1, 'blend from', s0)
open(OUT / 'skirt_f0rest.mdd', 'wb').write(hdr + X.astype('>f4').tobytes())
