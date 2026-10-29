# Run the skirt post chain (transfer -> refine -> transfer2 -> refine -> defold -> refine(8mm) -> defold -> contact)
# in parallel frame chunks with padding, then stitch.  Same scripts / arguments as run_hina.sh + chain_v79.sh.
# usage: python remote_post.py DIR [chunk=200] [pad=24] [workers=32]
import sys, os, shutil, subprocess, numpy as np, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
D = Path(sys.argv[1]).resolve(); CH = int(sys.argv[2]) if len(sys.argv) > 2 else 200
PAD = int(sys.argv[3]) if len(sys.argv) > 3 else 24; WK = int(sys.argv[4]) if len(sys.argv) > 4 else 32
S = Path(__file__).resolve().parent; PY = sys.executable
cloth = np.load(D / 'cloth.npy', mmap_mode='r'); mot = np.load(D / 'motion.npz'); N = cloth.shape[0]
keys = {k: mot[k] for k in mot.files}
chunks = [(a, min(a + CH, N)) for a in range(0, N, CH)]
work = D / 'chunks'; work.mkdir(exist_ok=True)
def prep(i, a, b):
    lo, hi = max(0, a - PAD), min(N, b + PAD); C = work / f'c{i:03d}'
    if C.exists(): shutil.rmtree(C)
    C.mkdir()
    for f in ('rest.npz', 'faces.json', 'pattern_rest.json'): shutil.copy(D / f, C / f)
    np.save(C / 'cloth.npy', np.asarray(cloth[lo:hi]))
    np.savez(C / 'motion.npz', **{k: (v[lo:hi] if v.ndim and v.shape[0] == N else v) for k, v in keys.items()})
    return C, lo, hi
def run(C):
    steps = [['transfer.py', C], ['refine.py', C, '0.006'],
             ['transfer2.py', C, '0.53', '0.58', '0.006', '0.004'], ['refine.py', C, '0.006'], 'cp:skirt_refined.npy:skirt_refined_prelayer.npy', ['defold.py', C],
             'cp:skirt_refined.npy:skirt_world.npy', ['refine.py', C, '0.008'], 'cp:skirt_refined.npy:skirt_refined_prelayer.npy', ['defold.py', C],
             'cp:skirt_refined.npy:skirt_defold2.npy', ['contact.py', C]]
    log = open(C / 'log.txt', 'w')
    for st in steps:
        if isinstance(st, str):
            _, s0, s1 = st.split(':'); shutil.copy(C / s0, C / s1); continue
        r = subprocess.run([PY, str(S / st[0])] + [str(x) for x in st[1:]], cwd=str(S), stdout=log, stderr=subprocess.STDOUT,
                           env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1'))
        if r.returncode: raise RuntimeError(f'{C.name} {st[0]} failed')
    return C
t0 = time.time()
prepped = [prep(i, a, b) for i, (a, b) in enumerate(chunks)]
print('chunks', len(prepped), 'prep s', round(time.time() - t0, 1), flush=True)
with ThreadPoolExecutor(WK) as ex: list(ex.map(run, [p[0] for p in prepped]))
print('chain s', round(time.time() - t0, 1), flush=True)
out = np.zeros((N,) + np.load(prepped[0][0] / 'skirt_contact.npy', mmap_mode='r').shape[1:], np.float32)
for (C, lo, hi), (a, b) in zip(prepped, chunks):
    out[a:b] = np.load(C / 'skirt_contact.npy')[a - lo:b - lo]
np.save(D / 'skirt_refined.npy', out)
print('STITCHED', out.shape, 'total s', round(time.time() - t0, 1), flush=True)
