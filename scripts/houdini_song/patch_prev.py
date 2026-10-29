# Preview: drop a real-skirt window solve (NPY, frames A..B) into a copy of the dancer-2 song cache with a short fade-in.
# usage: python patch_prev.py SRC_DIR OUT_DIR NPY A [fade=10] [fade_out=0]
import numpy as np, struct, shutil, sys
from pathlib import Path
SRC, OUT, NPY, A = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], int(sys.argv[4]); FD = int(sys.argv[5]) if len(sys.argv) > 5 else 10; FO = int(sys.argv[6]) if len(sys.argv) > 6 else 0
OUT.mkdir(exist_ok=True)
for f in SRC.glob('*.mdd'):
    if f.name != 'skirt_f0rest.mdd': shutil.copy(f, OUT / f.name)
d = open(SRC / 'skirt_f0rest.mdd', 'rb').read(); n, nv = struct.unpack('>2i', d[:8]); hdr = d[:8 + 4 * n]
X = np.frombuffer(d[8 + 4 * n:], '>f4').reshape(n, nv, 3).copy(); new = np.load(NPY); assert new.shape[1] == nv, (new.shape, nv)
for i in range(len(new)):
    u = min(1, i / FD, (len(new) - 1 - i) / FO if FO else 1); w = u * u * (3 - 2 * u); X[A + i] = X[A + i] * (1 - w) + new[i] * w
open(OUT / 'skirt_f0rest.mdd', 'wb').write(hdr + X.astype('>f4').tobytes()); print('patched', A, A + len(new) - 1, 'nv', nv)
