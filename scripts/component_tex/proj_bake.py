import json, sys, os, numpy as np
from PIL import Image
from scipy import ndimage
# usage: proj_bake.py mesh.npz views.json imgdir out.png size
mesh, views_path, imgdir, outp = sys.argv[1:5]; S = int(sys.argv[5]) if len(sys.argv) > 5 else 4096
d = np.load(mesh); co, nrm, tri, tuv = d['co'], d['nrm'], d['tri'], d['tuv']
views = json.load(open(views_path))
FB = sys.argv[6] if len(sys.argv) > 6 else None          # fallback: npz with per-triangle old uv + image
if FB:
    fbz = d if FB.split('|')[0] == 'self' else np.load(FB.split('|')[0]); ouv = fbz['ouv']
    fbimg = np.asarray(Image.open(FB.split('|')[1]).convert('RGB')).astype(np.float32) / 255; FH, FW = fbimg.shape[:2]
    ouvmap = np.zeros((S, S, 2), np.float32)
# ---- rasterize triangles in UV space -> per-texel position and normal
pos = np.zeros((S, S, 3), np.float32); nor = np.zeros((S, S, 3), np.float32); cov = np.zeros((S, S), bool)
def raster(p2, H, W):
    """yield (ys, xs, w0, w1, w2) of pixel centers inside triangle p2 (3x2 pixel coords)"""
    x0, y0 = np.floor(p2.min(0)).astype(int); x1, y1 = np.ceil(p2.max(0)).astype(int)
    x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, W - 1), min(y1, H - 1)
    if x1 < x0 or y1 < y0: return None
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    (ax, ay), (bx, by), (cx, cy) = p2
    den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(den) < 1e-12: return None
    w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
    w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
    w2 = 1 - w0 - w1
    m = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
    if not m.any(): return None
    return (ys[m] - 0.5).astype(int), (xs[m] - 0.5).astype(int), w0[m], w1[m], w2[m]
BW = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [1 / 3, 1 / 3, 1 / 3], [.5, .5, 0], [0, .5, .5], [.5, 0, .5]], np.float32)
for t in range(len(tri)):
    uv = tuv[t]; p2 = np.stack([uv[:, 0] * S, (1 - uv[:, 1]) * S], 1)
    r = raster(p2, S, S)
    # sliver triangles: always write the pixels under their vertices, edge midpoints and centroid
    pts = BW @ p2; sx = np.clip(pts[:, 0].astype(int), 0, S - 1); sy = np.clip(pts[:, 1].astype(int), 0, S - 1)
    if r is None: ys, xs, w0, w1, w2 = sy, sx, BW[:, 0], BW[:, 1], BW[:, 2]
    else:
        ys, xs, w0, w1, w2 = r
        ys = np.concatenate([ys, sy]); xs = np.concatenate([xs, sx]); w0 = np.concatenate([w0, BW[:, 0]]); w1 = np.concatenate([w1, BW[:, 1]]); w2 = np.concatenate([w2, BW[:, 2]])
    i, j, k = tri[t]
    pos[ys, xs] = w0[:, None] * co[i] + w1[:, None] * co[j] + w2[:, None] * co[k]
    nn = w0[:, None] * nrm[i] + w1[:, None] * nrm[j] + w2[:, None] * nrm[k]
    nor[ys, xs] = nn / np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-8); cov[ys, xs] = True
    if FB: ouvmap[ys, xs] = w0[:, None] * ouv[t, 0] + w1[:, None] * ouv[t, 1] + w2[:, None] * ouv[t, 2]
print('covered texels', int(cov.sum()))
OCC = os.environ.get('OCC'); ZFILL = os.environ.get('ZFILL') == '1'; NOWHITE = os.environ.get('NOWHITE') == '1'
if OCC:
    oz = np.load(OCC); occo, otri = oz['co'], oz['tri']
P = pos[cov]; N = nor[cov]
POW = float(os.environ.get('POW', '2')); CONF = float(os.environ.get('CONF', '0.001')); HARM = os.environ.get('HARM') == '1'
CONSTFB = os.environ.get('CONSTFB')
def sample_view(name, v):
    M = np.array(v['matrix_world'], np.float32); Mi = np.linalg.inv(M); sc = v['ortho_scale']; R = v['res']
    img = np.asarray(Image.open(f'{imgdir}/{name}.png').convert('RGB').resize((R, R), Image.LANCZOS)).astype(np.float32) / 255
    def to_img(X):
        L = X @ Mi[:3, :3].T + Mi[:3, 3]
        return (L[:, 0] / sc + 0.5) * R, (0.5 - L[:, 1] / sc) * R, -L[:, 2]
    zb = np.full((R, R), np.inf, np.float32)
    srcs = [(co, tri)] + ([(occo, otri)] if OCC else [])
    for cc, tt in srcs:
        vx, vy, vd = to_img(cc)
        tx = vx[tt]; ty = vy[tt]
        keep = np.where((tx.min(1) < R) & (tx.max(1) > 0) & (ty.min(1) < R) & (ty.max(1) > 0))[0]
        for t in keep:
            i, j, k = tt[t]; p2 = np.array([[vx[i], vy[i]], [vx[j], vy[j]], [vx[k], vy[k]]])
            r = raster(p2, R, R)
            if r is None: continue
            ys, xs, w0, w1, w2 = r; np.minimum.at(zb, (ys, xs), w0 * vd[i] + w1 * vd[j] + w2 * vd[k])
    px, py, dep = to_img(P)
    inside = (px >= 0) & (px < R - 1) & (py >= 0) & (py < R - 1)
    xi = np.clip(px.astype(int), 0, R - 1); yi = np.clip(py.astype(int), 0, R - 1)
    zmin = ndimage.minimum_filter(zb, size=3)
    vis = inside & (dep <= zmin[yi, xi] + 0.0015)
    facing = np.clip(-(N @ np.array(v['dir'], np.float32)), 0, 1)
    w = np.where(vis, facing ** POW, 0).astype(np.float32)
    x0 = np.floor(px).astype(int).clip(0, R - 2); y0 = np.floor(py).astype(int).clip(0, R - 2); fx = (px - x0)[:, None]; fy = (py - y0)[:, None]
    col = (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)
    if NOWHITE: w = np.where(col.min(1) > 0.82, 0, w).astype(np.float32)
    mp = f'{imgdir}/{name}_mask.png'
    if os.path.exists(mp):        # blanked regions of the input: this view carries no information there
        mk = np.asarray(Image.open(mp).convert('L').resize((R, R), Image.NEAREST)) > 127
        w = np.where(mk[np.clip(py.astype(int), 0, R - 1), np.clip(px.astype(int), 0, R - 1)], 0, w).astype(np.float32)
    return w, col.astype(np.float32)
cache = {}
acc = np.zeros((len(P), 3), np.float32); wsum = np.zeros(len(P), np.float32)
for name, v in views.items():
    w, col = sample_view(name, v); cache[name] = (w.astype(np.float16), col.astype(np.float16))
    acc += col * w[:, None]; wsum += w
    print(name, 'visible texels', int((w > 0).sum()), flush=True)
if HARM:
    cons = acc / np.maximum(wsum, 1e-6)[:, None]
    acc = np.zeros((len(P), 3), np.float32); wsum2 = np.zeros(len(P), np.float32)
    rng = np.random.default_rng(0)
    for name in views:
        w, col = cache[name]; w = w.astype(np.float32); col = col.astype(np.float32)
        m = np.where((w > 0.3) & (wsum > w + 0.2))[0]          # overlap with other views
        if len(m) > 2000:
            m = rng.choice(m, min(len(m), 200000), replace=False)
            for c in range(3):
                A_ = np.c_[col[m, c], np.ones(len(m))]; g, o = np.linalg.lstsq(A_, cons[m, c], rcond=None)[0]
                g = float(np.clip(g, 0.7, 1.3)); o = float(np.clip(o, -0.15, 0.15)); col[:, c] = np.clip(col[:, c] * g + o, 0, 1)
            print('harm', name, 'ok', flush=True)
        acc += col * w[:, None]; wsum2 += w
    wsum = wsum2
out = np.zeros((S, S, 3), np.float32); have = np.zeros((S, S), bool)
ok = wsum > CONF
tmp = np.zeros((len(P), 3), np.float32); tmp[ok] = acc[ok] / wsum[ok, None]
if CONSTFB:
    cfb = np.array([float(x) for x in CONSTFB.split(',')], np.float32); a = np.clip(wsum / 0.25, 0, 1)[:, None]
    tmp = np.where(ok[:, None], tmp, cfb) * a + cfb * (1 - a); ok = np.ones(len(P), bool)
if FB:
    ou = ouvmap[cov]; fx = np.clip((ou[:, 0] * FW).astype(int), 0, FW - 1); fy = np.clip(((1 - ou[:, 1]) * FH).astype(int), 0, FH - 1)
    fcol = fbimg[fy, fx]; a = np.clip(wsum / 0.25, 0, 1)[:, None]
    tmp = tmp * a + fcol * (1 - a); ok = np.ones(len(P), bool)
if ZFILL:
    z = P[:, 2]; seen = wsum > 0.25; bins = np.floor(z / 0.006).astype(int)
    fillc = np.zeros((len(P), 3), np.float32)
    ub = np.unique(bins)
    med = {}
    for b in ub:
        m = seen & (bins == b)
        if m.sum() > 50: med[b] = np.median(tmp[m], 0)
    keys = np.array(sorted(med)); vals = np.array([med[k] for k in keys])
    for c in range(3): fillc[:, c] = np.interp(bins, keys, vals[:, c])
    fillc *= float(os.environ.get('ZDARK', '0.82'))     # inner/hidden sides slightly darker
    a = np.clip(wsum / 0.25, 0, 1)[:, None]
    tmp = tmp * a + fillc * (1 - a); ok = np.ones(len(P), bool)
    zmin_ = float(os.environ.get('ZMIN', '-9'))
    ok[(P[:, 2] < zmin_) & (wsum < 0.25)] = False                 # below ZMIN: nearest-fill instead
    fz = os.environ.get('FORCEZ')
    if fz:
        hi_ = P[:, 2] > float(fz); tmp[hi_] = fillc[hi_]; print('forced', int(hi_.sum()))
SKINREF = os.environ.get('SKINREF')       # path of the original texture: its skin texels become flat skin
if SKINREF:
    oimg = np.asarray(Image.open(SKINREF).convert('RGB')).astype(np.float32) / 255; OH, OW = oimg.shape[:2]
    om = np.zeros((S, S, 2), np.float32); ouv_ = d['ouv']
    for t in range(len(tri)):
        uv = tuv[t]; p2 = np.stack([uv[:, 0] * S, (1 - uv[:, 1]) * S], 1); r = raster(p2, S, S)
        if r is None: continue
        ys, xs, w0, w1, w2 = r; om[ys, xs] = w0[:, None] * ouv_[t, 0] + w1[:, None] * ouv_[t, 1] + w2[:, None] * ouv_[t, 2]
    ou = om[cov]; oc = oimg[np.clip(((1 - ou[:, 1]) * OH).astype(int), 0, OH - 1), np.clip((ou[:, 0] * OW).astype(int), 0, OW - 1)]
    sk = (oc[:, 0] > 0.72) & (oc[:, 0] - oc[:, 2] > 0.07) & (oc[:, 1] > 0.5)
    tmp[sk] = np.array([float(x) for x in os.environ.get('SKINCOL', '0.984,0.867,0.847').split(',')], np.float32); ok = ok | sk
    print('skin texels', int(sk.sum()))
if os.environ.get('NOSKY') == '1':
    r_, g_, b_ = tmp[:, 0], tmp[:, 1], tmp[:, 2]; sky = (b_ > 0.55) & (b_ - r_ > 0.25) & (g_ > 0.3)
    wsky = np.clip((b_ - r_ - 0.25) / 0.2, 0, 1) * sky; tmp = tmp * (1 - wsky[:, None]) + np.array([0.95, 0.95, 0.97], np.float32) * wsky[:, None]
out[cov] = tmp; have[cov] = ok
print('unseen covered texels', int((cov & ~have).sum()))
# fill unseen / padding by nearest painted texel
idx = ndimage.distance_transform_edt(~have, return_distances=False, return_indices=True)
filled = out[idx[0], idx[1]]
Image.fromarray((np.clip(filled, 0, 1) * 255 + 0.5).astype(np.uint8)).save(outp)
print('saved', outp)
