import bpy, sys, json, os, numpy as np
from mathutils import Vector
from mathutils.geometry import barycentric_transform
# Seamless refill of the skirt patch under the ribbons: harmonic (Laplace) interpolation over the mesh surface.
# Boundary values = colours of the clean skirt right outside the patch, so the fill matches the surrounding shading exactly.
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chest_clean.py')).read().split("cnt = {")[0])
BOXES = json.loads(sys.argv[sys.argv.index('--') + 2])
inb = lambda c: any(all(b[k][0] < c[k] < b[k][1] for k in range(3)) for b in BOXES)
def face_cols(p, pts):
    r = img(p.material_index)
    if r is None: return None
    px = r[1]; H, W = px.shape[:2]; V = [me.vertices[v].co for v in p.vertices]; U = [uvl[l].uv.to_3d() for l in p.loop_indices]
    out = []
    for q in pts:
        best = None
        for k in range(1, len(V) - 1):
            u = barycentric_transform(q, V[0], V[k], V[k + 1], U[0], U[k], U[k + 1]); best = u
        out.append(px[min(H - 1, max(0, int(best.y * H))), min(W - 1, max(0, int(best.x * W))), :3])
    return out
def mostly_white(p):
    cs = face_cols(p, [p.center] + [p.center.lerp(me.vertices[v].co, 0.7) for v in p.vertices])
    return cs is not None and np.mean([c.mean() > 0.6 for c in cs]) > 0.5
def mostly_navy(p):
    cs = face_cols(p, [p.center] + [p.center.lerp(me.vertices[v].co, 0.7) for v in p.vertices])
    if cs is None: return False
    if not os.environ.get('HGOLDIN') and any(c[0] > c[2] + 0.05 and c[0] > 0.3 for c in cs): return False          # faces carrying the gold piping stay
    return np.mean([(c[2] - c[0] > 0.15 and c.mean() < 0.4) or (c[0] > c[2] + 0.05) for c in cs]) > float(os.environ.get('HNF', '0.85'))
EXCL = json.loads(os.environ.get('HEXCL', '[]'))
excl = lambda c: any(all(b[k][0] < c[k] < b[k][1] for k in range(3)) for b in EXCL)
if os.environ.get('HNAVY'):
    region = [p.index for p in me.polygons if inb(p.center) and not excl(p.center) and img(p.material_index) is not None and mostly_navy(p)]
else:
    region = [p.index for p in me.polygons if inb(p.center) and img(p.material_index) is not None and not mostly_white(p)]
rset = set(region)
v2f = {}
for p in me.polygons:
    for v in p.vertices: v2f.setdefault(v, []).append(p.index)
rv = sorted({v for i in region for v in me.polygons[i].vertices})
fixed = {}
for v in rv:
    outs = [j for j in v2f[v] if j not in rset and img(me.polygons[j].material_index) is not None]
    if not outs: continue
    cs = []
    for j in outs:
        q = me.polygons[j]
        if mostly_white(q): continue
        c = face_cols(q, [me.vertices[v].co.lerp(q.center, 0.25)])[0]
        if c[2] - c[0] > float(os.environ.get('BBR', '0.05')) and c.mean() < float(os.environ.get('BMX', '0.5')): cs.append(c)
    if cs: fixed[v] = np.mean(cs, 0)
print('INFO region faces', len(region), 'verts', len(rv), 'boundary fixed', len(fixed))
nb = {v: set() for v in rv}
for i in region:
    vs = me.polygons[i].vertices
    for a in vs:
        for b in vs:
            if a != b: nb[a].add(b)
col = {v: fixed.get(v, np.mean(list(fixed.values()), 0)) for v in rv}
for it in range(600):
    new = {}
    for v in rv:
        if v in fixed: new[v] = fixed[v]; continue
        ns = [col[u] for u in nb[v] if u in col]
        new[v] = np.mean(ns, 0) if ns else col[v]
    col = new
n = 0
for i in region:
    p = me.polygons[i]; r = img(p.material_index); im, px = r; H, W = px.shape[:2]
    us = [uvl[l].uv for l in p.loop_indices]; cs = [col[v] for v in p.vertices]
    for k in range(1, len(us) - 1):
        A = np.array([[us[j].x * W, us[j].y * H] for j in (0, k, k + 1)]); C3 = np.array([cs[0], cs[k], cs[k + 1]])
        x0, y0 = np.maximum(np.floor(A.min(0) - 3).astype(int), 0); x1, y1 = np.minimum(np.ceil(A.max(0) + 3).astype(int), [W - 1, H - 1])
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = A; den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12: continue
        w0 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den; w1 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den; w2 = 1 - w0 - w1
        ins = (w0 > -0.3) & (w1 > -0.3) & (w2 > -0.3)
        wc = np.clip(np.stack([w0, w1, w2], -1), 0, None); wc /= np.maximum(wc.sum(-1, keepdims=True), 1e-6)
        blk = px[y0:y1 + 1, x0:x1 + 1, :3]; blk[ins] = (wc @ C3)[ins]; n += int(ins.sum())
if os.environ.get('PIPE'):
    # white front panel boundary edges (white face next to non-white face) = where the piping runs
    import bmesh as _bm
    bmw = _bm.new(); bmw.from_mesh(me); bmw.faces.ensure_lookup_table()
    W0, W1 = [float(x) for x in os.environ['PIPE'].split(',')]
    wf = {p.index for p in me.polygons if p.index not in rset and abs(p.center.y) < 0.09 and p.center.x > 0.03 and 0.64 < p.center.z < 0.84 and img(p.material_index) is not None and mostly_white(p)}
    segs = []
    for e in bmw.edges:
        fs = [f.index for f in e.link_faces]
        m_ = (e.verts[0].co + e.verts[1].co) / 2
        if sum(1 for f in fs if f in wf) == 1 and 0.675 < m_.z < 0.79 and 0.025 < abs(m_.y) < 0.08 and m_.x > 0.04: segs.append([e.verts[0].co[:], e.verts[1].co[:]])
    segs = np.array(segs); print('INFO piping segs', len(segs))
    SA = segs[:, 0]; SB = segs[:, 1]; SAB = SB - SA; SL = np.maximum((SAB * SAB).sum(1), 1e-12)
    GOLD = np.array([0.85, 0.66, 0.30]); GOLD_D = np.array([0.55, 0.38, 0.14]); co3 = np.array([v.co[:] for v in me.vertices])
    for i in region:
        p = me.polygons[i]; im, px = img(p.material_index); H, W = px.shape[:2]
        us = [uvl[l].uv for l in p.loop_indices]; vs = list(p.vertices)
        for k in range(1, len(us) - 1):
            A2 = np.array([[us[j].x * W, us[j].y * H] for j in (0, k, k + 1)]); P3 = co3[[vs[0], vs[k], vs[k + 1]]]
            x0, y0 = np.maximum(np.floor(A2.min(0) - 3).astype(int), 0); x1, y1 = np.minimum(np.ceil(A2.max(0) + 3).astype(int), [W - 1, H - 1])
            X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax, ay), (bx, by), (cx, cy) = A2; den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-12: continue
            w0 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den; w1 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den; w2 = 1 - w0 - w1
            ins = (w0 > -0.3) & (w1 > -0.3) & (w2 > -0.3)
            if not ins.any(): continue
            wc = np.clip(np.stack([w0[ins], w1[ins], w2[ins]], 1), 0, None); wc /= np.maximum(wc.sum(1, keepdims=True), 1e-6)
            Q = wc @ P3; AQ = Q[:, None, :] - SA[None]; tt = np.clip((AQ * SAB[None]).sum(2) / SL[None], 0, 1)
            d = np.linalg.norm(AQ - tt[..., None] * SAB[None], axis=2).min(1)
            g = (d > W0) & (d < W1); gl = g & ((d < W0 + 0.0002) | (d > W1 - 0.0002))
            blk = px[y0:y1 + 1, x0:x1 + 1, :3]; T = blk[ins]; T[g] = GOLD; T[gl] = GOLD_D; blk[ins] = T
for mi, r in imgs.items():
    if r is None: continue
    im, px = r; dst = bpy.path.abspath('//') + f'../textures/skirtharm_{mi}.png'
    tmp = bpy.data.images.new('t', im.size[0], im.size[1], alpha=True); tmp.pixels.foreach_set(px.ravel()); tmp.filepath_raw = dst; tmp.file_format = 'PNG'; tmp.save(); bpy.data.images.remove(tmp)
    ni = bpy.data.images.load(dst, check_existing=False); ni.pack(); nm = im.name; im.user_remap(ni); bpy.data.images.remove(im); ni.name = nm
print('INFO harmonic texels', n, 'MEANCOL', ','.join('%.4f' % x for x in np.mean([col[v] for v in rv], 0)))
rig.data.pose_position = keep; s.frame_set(1); bpy.ops.wm.save_as_mainfile(filepath=out)
