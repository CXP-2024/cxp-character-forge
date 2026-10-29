# Splice the approved 0-1800 caches with the new 1740-END segment (smoothstep blend over 1740-1800) -> full-song MDDs.
# usage: python splice_song.py OUTDIR OLD_SKIRT_MDD OLD_ACC_DIR SEGDIR [SEG_START=1740] [BLEND_END=1800]
import numpy as np, struct, sys, json
from pathlib import Path
OUT = Path(sys.argv[1]); OUT.mkdir(exist_ok=True)
OLD_SK, OLD_ACC, SEG = Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
S0 = int(sys.argv[5]) if len(sys.argv) > 5 else 1740; B1 = int(sys.argv[6]) if len(sys.argv) > 6 else 1800
def rd(p):
    d = open(p, 'rb').read(); n, v = struct.unpack('>2i', d[:8]); return np.frombuffer(d[8+4*n:], '>f4').reshape(n, v, 3).astype(np.float32)
def wr(p, a):
    with open(p, 'wb') as h:
        h.write(struct.pack('>2i', len(a), a.shape[1])); h.write((np.arange(len(a)) / 30).astype('>f4').tobytes()); h.write(a.astype('>f4').tobytes())
def splice(old, seg):
    n = S0 + len(seg); out = np.zeros((n,) + old.shape[1:], np.float32)
    out[:S0] = old[:S0]; out[S0:] = seg
    for f in range(S0, B1 + 1):
        u = (f - S0) / (B1 - S0); w = u * u * (3 - 2 * u)
        out[f] = (1 - w) * old[f] + w * seg[f - S0]
    j = np.linalg.norm(np.diff(out[S0 - 5:B1 + 6], axis=0), axis=2).max(1) * 1000
    return out, float(j.max()), float(np.linalg.norm(old[B1] - seg[B1 - S0], axis=1).max() * 1000)
rep = {}
old = rd(OLD_SK); seg = np.load(SEG / 'skirt_refined.npy')
out, jm, dm = splice(old, seg); wr(OUT / 'skirt_f0rest.mdd', out); rep['skirt'] = dict(frames=len(out), seam_jerk_mm=round(jm, 1), diff_at_1800_mm=round(dm, 1))
for k in ('Acc_BB', 'SkirtBow_BL', 'SkirtBow_BR', 'SkirtBow_FL', 'SkirtBow_FR'):
    old = rd(OLD_ACC / f'{k}_f0rest.mdd'); seg = rd(SEG / f'{k}.mdd')
    out, jm, dm = splice(old, seg); wr(OUT / f'{k}_f0rest.mdd', out); rep[k] = dict(frames=len(out), seam_jerk_mm=round(jm, 1), diff_at_1800_mm=round(dm, 1))
(OUT / 'splice_report.json').write_text(json.dumps(rep, indent=1)); print(json.dumps(rep))
