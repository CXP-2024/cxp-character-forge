import bpy, sys, os, numpy as np
from mathutils.kdtree import KDTree
# Blend each Tripo-textured strand into the old hair texture near the cut where it meets the rest of the hair,
# so the texture flows continuously across the split (weight 1 at the cut -> 0 at DIST).
out = sys.argv[sys.argv.index('--') + 1]; names = sys.argv[sys.argv.index('--') + 2].split(','); DIST = float(os.environ.get('RB', '0.035'))
for a in [o for o in bpy.data.objects if o.type == 'ARMATURE']: a.data.pose_position = 'REST'
bpy.context.scene.frame_set(0)
hair = bpy.data.objects['Hair']; hm = hair.data
kd = KDTree(len(hm.vertices))
for v in hm.vertices: kd.insert(v.co, v.index)
kd.balance()
oim = [n.image for n in hm.materials[hm.polygons[0].material_index].node_tree.nodes if n.type == 'TEX_IMAGE'][0]
OP = np.array(oim.pixels[:], np.float32).reshape(oim.size[1], oim.size[0], 4)[..., :3]; OH, OW = OP.shape[:2]
newimg = None; NP = None; total = 0
for nm in names:
    ob = bpy.data.objects[nm]; me = ob.data
    tu = me.uv_layers['TripoUV'].data; ou = [l for l in me.uv_layers if l.name != 'TripoUV'][0].data
    if newimg is None:
        newimg = [n.image for n in me.materials[0].node_tree.nodes if n.type == 'TEX_IMAGE'][0]
        NP = np.array(newimg.pixels[:], np.float32).reshape(newimg.size[1], newimg.size[0], 4); NH, NW = NP.shape[:2]
    cut = {v.index for v in me.vertices if kd.find(v.co)[2] < 1e-6}
    segs = []
    for e in me.edges:
        a_, b_ = e.vertices
        if a_ in cut and b_ in cut: segs.append([me.vertices[a_].co[:], me.vertices[b_].co[:]])
    if not segs: print('no cut on', nm); continue
    S = np.array(segs); A = S[:, 0]; AB = S[:, 1] - A; L2 = np.maximum((AB * AB).sum(1), 1e-12)
    co = np.array([v.co[:] for v in me.vertices])
    for p in me.polygons:
        vs = list(p.vertices); us = [tu[l].uv for l in p.loop_indices]; os_ = [ou[l].uv for l in p.loop_indices]
        for k in range(1, len(us) - 1):
            P3 = co[[vs[0], vs[k], vs[k + 1]]]
            AQ = P3[:, None, :] - A[None]; t = np.clip((AQ * AB[None]).sum(2) / L2[None], 0, 1)
            if np.linalg.norm(AQ - t[..., None] * AB[None], axis=2).min() > DIST + 0.01: continue
            T2 = np.array([[us[j].x * NW, us[j].y * NH] for j in (0, k, k + 1)]); O2 = np.array([os_[j][:] for j in (0, k, k + 1)])
            x0, y0 = np.maximum(np.floor(T2.min(0) - 2).astype(int), 0); x1, y1 = np.minimum(np.ceil(T2.max(0) + 2).astype(int), [NW - 1, NH - 1])
            X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax, ay), (bx, by), (cx, cy) = T2; den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-12: continue
            w0 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den; w1 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den; w2 = 1 - w0 - w1
            ins = (w0 > -0.1) & (w1 > -0.1) & (w2 > -0.1)
            if not ins.any(): continue
            Wc = np.clip(np.stack([w0[ins], w1[ins], w2[ins]], 1), 0, None); Wc /= np.maximum(Wc.sum(1, keepdims=True), 1e-6)
            Q = Wc @ P3; AQ = Q[:, None, :] - A[None]; t = np.clip((AQ * AB[None]).sum(2) / L2[None], 0, 1)
            d = np.linalg.norm(AQ - t[..., None] * AB[None], axis=2).min(1)
            w = np.clip(1 - d / DIST, 0, 1); w = w * w * (3 - 2 * w)
            OU = Wc @ O2; oc = OP[np.clip((OU[:, 1] * OH).astype(int), 0, OH - 1), np.clip((OU[:, 0] * OW).astype(int), 0, OW - 1)]
            blk = NP[y0:y1 + 1, x0:x1 + 1, :3]; T = blk[ins]; blk[ins] = T * (1 - w[:, None]) + oc * w[:, None]; total += int((w > 0).sum())
    print('INFO', nm, 'cut edges', len(segs))
dst = bpy.path.abspath('//') + 'Tripo_strands_rootblend.png'
tmp = bpy.data.images.new('t', newimg.size[0], newimg.size[1], alpha=True); tmp.pixels.foreach_set(NP.ravel()); tmp.filepath_raw = dst; tmp.file_format = 'PNG'; tmp.save(); bpy.data.images.remove(tmp)
ni = bpy.data.images.load(dst, check_existing=False); ni.pack(); n_ = newimg.name; newimg.user_remap(ni); bpy.data.images.remove(newimg); ni.name = n_
print('INFO blended texels', total)
bpy.context.scene.frame_set(1); bpy.ops.wm.save_as_mainfile(filepath=out)
