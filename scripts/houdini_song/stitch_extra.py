# stitch extra per-frame arrays from the chunk dirs (same chunking as remote_post.py)
import sys, numpy as np
from pathlib import Path
D = Path(sys.argv[1]); CH = int(sys.argv[2]); PAD = int(sys.argv[3]); names = sys.argv[4:]
N = np.load(D / 'cloth.npy', mmap_mode='r').shape[0]
chunks = [(a, min(a + CH, N)) for a in range(0, N, CH)]
for nm in names:
    first = np.load(D / 'chunks' / 'c000' / nm, mmap_mode='r'); out = np.zeros((N,) + first.shape[1:], first.dtype)
    for i, (a, b) in enumerate(chunks):
        lo = max(0, a - PAD); out[a:b] = np.load(D / 'chunks' / f'c{i:03d}' / nm)[a - lo:b - lo]
    np.save(D / nm, out); print('stitched', nm, out.shape)
