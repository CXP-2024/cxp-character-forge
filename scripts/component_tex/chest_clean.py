import bpy, sys, os, numpy as np
from mathutils import Vector
# Texture clean-up on Body around the solid buttons and the chest:
#  A) gold corset buttons: old painted button / shadow texels around each GoldButton -> local navy
#  B) chest placket: old painted navy buttons on the white -> local white
#  C) cleavage: blue smear on skin -> local skin
out = sys.argv[sys.argv.index('--') + 1]
s = bpy.context.scene
rig = [o for o in bpy.data.objects if o.name.endswith('_Rig')][0]; keep = rig.data.pose_position
rig.data.pose_position = 'REST'; s.frame_set(0); bpy.context.view_layer.update()
body = bpy.data.objects['Body']; me = body.data; uvl = me.uv_layers.active.data
dg = bpy.context.evaluated_depsgraph_get()
def obj_info(o):
    e = o.evaluated_get(dg); P = [o.matrix_world @ v.co for v in e.data.vertices]; c = sum(P, Vector()) / len(P)
    return c, max((p - c).length for p in P)
gold = [obj_info(o) for o in bpy.data.objects if o.name.startswith('GoldButton')]
navy = [obj_info(o) for o in bpy.data.objects if o.name.startswith('NavyButton')]
imgs = {}
def img(mi):
    if mi not in imgs:
        nodes = me.materials[mi].node_tree.nodes; im = [n.image for n in nodes if n.type == 'TEX_IMAGE' and n.image]
        if not im or any(n.type == 'UVMAP' for n in nodes): imgs[mi] = None
        else: imgs[mi] = (im[0], np.array(im[0].pixels[:], np.float32).reshape(im[0].size[1], im[0].size[0], 4))
    return imgs[mi]
def tri_pixels(p, W, H):
    us = [uvl[l].uv for l in p.loop_indices]
    for k in range(1, len(us) - 1):
        A = np.array([[us[j].x * W, us[j].y * H] for j in (0, k, k + 1)])
        x0, y0 = np.maximum(np.floor(A.min(0) - 3).astype(int), 0); x1, y1 = np.minimum(np.ceil(A.max(0) + 3).astype(int), [W - 1, H - 1])
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = A; den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12: continue
        w0 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den; w1 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den; w2 = 1 - w0 - w1
        e_ = -float(os.environ.get('TRIPAD', '0.05')); ins = (w0 > e_) & (w1 > e_) & (w2 > e_)
        if ins.any(): yield x0, y0, x1, y1, ins
cnt = {'A': 0, 'B': 0, 'C': 0}
def fix(p, kind, want, bad_fn, ref_fn):
    r = img(p.material_index)
    if r is None: return
    im, px = r; H, W = px.shape[:2]
    for x0, y0, x1, y1, ins in tri_pixels(p, W, H):
        nb = px[max(0, y0 - 40):y1 + 40, max(0, x0 - 40):x1 + 40, :3].reshape(-1, 3); ref = nb[ref_fn(nb)]
        if len(ref) < 30: continue
        med = np.median(ref, 0); blk = px[y0:y1 + 1, x0:x1 + 1, :3]; T = blk[ins]; bad = bad_fn(T, med)
        if bad.any(): T[bad] = med; blk[ins] = T; cnt[kind] += int(bad.sum())
is_navy = lambda c: (c[:, 2] - c[:, 0] > 0.1) & (c.mean(1) < 0.45) & (c.mean(1) > 0.1)
is_white = lambda c: c.mean(1) > 0.78
is_skin = lambda c: (c[:, 0] > 0.75) & (c[:, 0] > c[:, 2] + 0.04) & (c[:, 1] > 0.6)
def face_is_skin(p):
    r = img(p.material_index)
    if r is None: return False
    px = r[1]; H, W = px.shape[:2]; us = [uvl[l].uv for l in p.loop_indices]; c0 = sum(us, Vector((0, 0))) / len(us)
    cs = np.array([px[min(H - 1, int(u.y * H)), min(W - 1, int(u.x * W)), :3] for u in [c0] + [c0.lerp(u, 0.7) for u in us]])
    return is_skin(cs).mean() > 0.5
BM = {}
def markB(p):
    r = img(p.material_index)
    if r is None: return
    im, px = r; H, W = px.shape[:2]
    m = BM.setdefault(p.material_index, (np.zeros((H, W), bool), np.zeros((H, W), bool)))
    for x0, y0, x1, y1, ins in tri_pixels(p, W, H):
        T = px[y0:y1 + 1, x0:x1 + 1, :3]
        bad = (T.mean(2) < float(os.environ.get('BMEAN', '0.72'))) & (T[..., 2] - T[..., 0] > float(os.environ.get('BBR', '0.04')))
        m[0][y0:y1 + 1, x0:x1 + 1] |= bad & ins; m[1][y0:y1 + 1, x0:x1 + 1] |= ins
for p in me.polygons:
    c = p.center
    if any((c - g).length < rr * 1.9 for g, rr in gold):
        fix(p, 'A', 'navy', lambda T, m: np.abs(T - m).max(1) > 0.07, is_navy)
    elif c.x > 0.07 and abs(c.y) < 0.022 and 0.685 < c.z < 0.765:
        (None if os.environ.get('SKIPB') else markB(p))
    elif c.x > 0.05 and abs(c.y) < 0.045 and 0.755 < c.z < 0.83 and face_is_skin(p):
        fix(p, 'C', 'skin', lambda T, m: (T[:, 2] > T[:, 0] + 0.02) & (T.mean(1) < 0.8), is_skin)
def gblur(a, s):
    r = int(3 * s); k = np.exp(-0.5 * (np.arange(-r, r + 1) / s) ** 2); k /= k.sum()
    pad = [(r, r), (0, 0)] + [(0, 0)] * (a.ndim - 2)
    a = np.apply_along_axis(lambda v: np.convolve(v, k, 'valid'), 0, np.pad(a, pad, mode='edge'))
    pad = [(0, 0), (r, r)] + [(0, 0)] * (a.ndim - 2)
    return np.apply_along_axis(lambda v: np.convolve(v, k, 'valid'), 1, np.pad(a, pad, mode='edge'))
def dilate(m, n):
    o = m.copy()
    for dy in range(-n, n + 1):
        for dx in range(-n, n + 1): o |= np.roll(np.roll(m, dy, 0), dx, 1)
    return o
for mi, (bad, region) in BM.items():
    im, px = imgs[mi]
    ys, xs = np.where(bad)
    if not len(ys): continue
    y0, y1, x0, x1 = max(0, ys.min() - 120), ys.max() + 121, max(0, xs.min() - 120), xs.max() + 121
    sub = px[y0:y1, x0:x1, :3]; bb = dilate(bad[y0:y1, x0:x1], int(os.environ.get('BDIL', '14'))) & region[y0:y1, x0:x1]
    good = (~bb).astype(np.float32)
    for sig in (5, 12, 28):
        num = gblur(sub * good[..., None], sig); den = gblur(good, sig)[..., None]
        est = num / np.maximum(den, 1e-4); sel = bb & (den[..., 0] > 0.15)
        sub[sel] = est[sel]; good[sel] = 1.0; bb &= ~sel
    cnt['B'] += int(bad.sum())
for mi, r in imgs.items():
    if r is None: continue
    im, px = r; dst = bpy.path.abspath('//') + f'../textures/chestclean_{mi}.png'
    tmp = bpy.data.images.new('t', im.size[0], im.size[1], alpha=True); tmp.pixels.foreach_set(px.ravel()); tmp.filepath_raw = dst; tmp.file_format = 'PNG'; tmp.save(); bpy.data.images.remove(tmp)
    ni = bpy.data.images.load(dst, check_existing=False); ni.pack(); nm = im.name; im.user_remap(ni); bpy.data.images.remove(im); ni.name = nm
print('INFO texels', cnt, 'gold', len(gold), 'navy', len(navy))
rig.data.pose_position = keep; s.frame_set(1); bpy.ops.wm.save_as_mainfile(filepath=out)
