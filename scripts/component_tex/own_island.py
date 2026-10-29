import bpy, bmesh, sys, numpy as np
from mathutils import Vector
# Give face FI its own UV island in an unused square of its texture (shape-preserving), so later projection does not collide.
args = sys.argv[sys.argv.index('--') + 1:]
out = args[0]; FIS = [int(x) for x in args[1].split(',')]; SZ = int(args[2]) if len(args) > 2 else 256
body = bpy.data.objects['Body']; me = body.data
mi = me.polygons[FIS[0]].material_index
img = [n.image for n in me.materials[mi].node_tree.nodes if n.type == 'TEX_IMAGE'][0]; W, H = img.size
uvl = me.uv_layers.active.data
tex = np.array(img.pixels[:], np.float32).reshape(H, W, 4)
cov = np.zeros((H // 16 + 1, W // 16 + 1), bool)
for p in me.polygons:
    if p.material_index != mi: continue
    us = [uvl[l].uv for l in p.loop_indices]
    x0 = int(min(u.x for u in us) * W) // 16; x1 = int(max(u.x for u in us) * W) // 16
    y0 = int(min(u.y for u in us) * H) // 16; y1 = int(max(u.y for u in us) * H) // 16
    cov[max(0, y0 - 1):y1 + 2, max(0, x0 - 1):x1 + 2] = True
for fi in FIS:
    n = SZ // 16 + 2
    spot = None
    for by in range(0, cov.shape[0] - n):
        for bx in range(0, cov.shape[1] - n):
            if not cov[by:by + n, bx:bx + n].any(): spot = (bx, by); break
        if spot: break
    assert spot, 'no free space'
    ox, oy = (spot[0] + 1) * 16 / W, (spot[1] + 1) * 16 / H
    p = me.polygons[fi]; V = [me.vertices[v].co for v in p.vertices]
    e1 = (V[1] - V[0]).normalized(); nrm = (V[1] - V[0]).cross(V[2] - V[0]).normalized(); e2 = nrm.cross(e1)
    loc = [Vector(((v - V[0]).dot(e1), (v - V[0]).dot(e2))) for v in V]
    lo = Vector((min(q.x for q in loc), min(q.y for q in loc))); ext = max(max(q.x for q in loc) - lo.x, max(q.y for q in loc) - lo.y)
    s = (SZ / W) / ext
    old = [uvl[li].uv.copy() for li in p.loop_indices]
    new = [Vector((ox + (q.x - lo.x) * s, oy + (q.y - lo.y) * s)) for q in loc]
    for li, u in zip(p.loop_indices, new): uvl[li].uv = u
    # copy original texels into the new island (barycentric remap old->new), so parts outside any later projection keep their look
    A = [Vector((u.x * W, u.y * H)) for u in new]; O = [Vector((u.x * W, u.y * H)) for u in old]
    for k in range(1, len(A) - 1):
        a, b, c = A[0], A[k], A[k + 1]; oa, ob, oc = O[0], O[k], O[k + 1]
        den = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y)
        for y in range(int(min(a.y, b.y, c.y)) - 2, int(max(a.y, b.y, c.y)) + 3):
            for x in range(int(min(a.x, b.x, c.x)) - 2, int(max(a.x, b.x, c.x)) + 3):
                w0 = ((b.y - c.y) * (x + .5 - c.x) + (c.x - b.x) * (y + .5 - c.y)) / den; w1 = ((c.y - a.y) * (x + .5 - c.x) + (a.x - c.x) * (y + .5 - c.y)) / den; w2 = 1 - w0 - w1
                if min(w0, w1, w2) < -0.05: continue
                q = oa * w0 + ob * w1 + oc * w2
                tex[y, x] = tex[min(H - 1, max(0, int(q.y))), min(W - 1, max(0, int(q.x)))]
    cov[spot[1]:spot[1]+n, spot[0]:spot[0]+n] = True
dst = out.replace('.blend', '_tex.png')
tmp = bpy.data.images.new('isl_tmp', W, H, alpha=True); tmp.pixels.foreach_set(tex.ravel()); tmp.filepath_raw = dst; tmp.file_format = 'PNG'; tmp.save(); bpy.data.images.remove(tmp)
ni = bpy.data.images.load(dst, check_existing=False); ni.pack(); nm = img.name; img.user_remap(ni); bpy.data.images.remove(img); ni.name = nm
bpy.ops.wm.save_as_mainfile(filepath=out)
print('INFO island at px', int(ox * W), int(oy * H), 'size', SZ)
