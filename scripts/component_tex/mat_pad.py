import bpy, sys, os, json, numpy as np
# (1) listed faces: beige/gold 'other' texels -> face navy; (2) rebuild UV padding of the material's texture (grow islands outward).
out = sys.argv[sys.argv.index('--') + 1]; MAT = sys.argv[sys.argv.index('--') + 2]; FIX = json.loads(sys.argv[sys.argv.index('--') + 3]); PAD = int(os.environ.get('PAD', '8'))
me = bpy.data.objects['Body'].data; uvl = me.uv_layers.active.data
mi = [i for i, m in enumerate(me.materials) if m and m.name == MAT][0]
im = [n.image for n in me.materials[mi].node_tree.nodes if n.type == 'TEX_IMAGE'][0]; W, H = im.size
px = np.array(im.pixels[:], np.float32).reshape(H, W, 4); inside = np.zeros((H, W), bool)
same = {i for i, m in enumerate(me.materials) if m and m.use_nodes and any(n.type == 'TEX_IMAGE' and n.image == im and not any(x.type == 'UVMAP' for x in m.node_tree.nodes) for n in m.node_tree.nodes)}
print('INFO mats sharing image', [me.materials[i].name for i in same])
navy = lambda c: (c[..., 2] - c[..., 0] > 0.12) & (c.mean(-1) < 0.45)
nfix = 0
for p in me.polygons:
    if p.material_index not in same: continue
    us = [uvl[l].uv for l in p.loop_indices]
    for k in range(1, len(us) - 1):
        A = np.array([[us[j].x * W, us[j].y * H] for j in (0, k, k + 1)])
        x0, y0 = np.maximum(np.floor(A.min(0)).astype(int), 0); x1, y1 = np.minimum(np.ceil(A.max(0)).astype(int), [W - 1, H - 1])
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = A; den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12: continue
        w0 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den; w1 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den; w2 = 1 - w0 - w1
        ins = (w0 >= -0.01) & (w1 >= -0.01) & (w2 >= -0.01); inside[y0:y1 + 1, x0:x1 + 1] |= ins
        if p.index in FIX:
            blk = px[y0:y1 + 1, x0:x1 + 1, :3]; T = blk[ins]; nv = navy(T)
            if nv.any():
                bad = ~nv & (T.mean(1) <= 0.75); T[bad] = np.median(T[nv], 0); blk[ins] = T; nfix += int(bad.sum())
rgb = px[..., :3].copy(); have = inside.copy(); grown = 0
for _ in range(PAD):
    acc = np.zeros_like(rgb); cnt = np.zeros((H, W), np.float32)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        sh = np.roll(np.roll(have, dy, 0), dx, 1); acc += np.roll(np.roll(rgb, dy, 0), dx, 1) * sh[..., None]; cnt += sh
    g = (~have) & (cnt > 0); rgb[g] = acc[g] / cnt[g][:, None]; have |= g; grown += int(g.sum())
px[..., :3] = rgb
dst = bpy.path.abspath('//') + f'../textures/{MAT}_pad.png'
tmp = bpy.data.images.new('t', W, H, alpha=True); tmp.pixels.foreach_set(px.ravel()); tmp.filepath_raw = dst; tmp.file_format = 'PNG'; tmp.save(); bpy.data.images.remove(tmp)
ni = bpy.data.images.load(dst, check_existing=False); ni.pack(); nm = im.name; im.user_remap(ni); bpy.data.images.remove(im); ni.name = nm
print('INFO fixed texels', nfix, 'padding grown', grown)
bpy.ops.wm.save_as_mainfile(filepath=out)
