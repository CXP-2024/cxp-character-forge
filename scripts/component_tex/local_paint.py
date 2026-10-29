import bpy, bmesh, sys, json, math, numpy as np
from mathutils import Vector
from mathutils.geometry import barycentric_transform
# mode render: close-up texture render of face FI, camera saved to json
# mode project: project painted close-up back into the texture for faces within RADIUS of FI that face the camera
args = sys.argv[sys.argv.index('--') + 1:]
mode, fi, base = args[0], int(args[1]), args[2]
import os
RADIUS = float(os.environ.get('LPR', '0.03')); RES = 1024; SC = float(os.environ.get('LSC', '0.05')); AZ = float(os.environ.get('LAZ', '12')); EL = float(os.environ.get('LEL', '28'))
s = bpy.context.scene
for a in [o for o in bpy.data.objects if o.type == 'ARMATURE']: a.data.pose_position = 'REST'
s.frame_set(0); bpy.context.view_layer.update()
body = bpy.data.objects['Body']; me = body.data; M = body.matrix_world
C = Vector([float(x) for x in os.environ['LC'].split(',')]) if os.environ.get('LC') else M @ me.polygons[fi].center
d = Vector((math.cos(math.radians(AZ)) * math.cos(math.radians(EL)), math.sin(math.radians(AZ)) * math.cos(math.radians(EL)), math.sin(math.radians(EL))))
Q = (-d).to_track_quat('-Z', 'Y'); R3 = Q.to_matrix(); camloc = C + d * 2
if mode == 'render':
    for o in bpy.data.objects:
        if o.type == 'MESH': o.hide_render = o.name not in (('Body',) if os.environ.get('LNOHAIR') else ('Body', 'Hair'))
    s.render.engine = 'BLENDER_WORKBENCH'; sh = s.display.shading; sh.light = 'FLAT'; sh.color_type = 'TEXTURE'
    cam = bpy.data.objects.new('LP', bpy.data.cameras.new('LP')); s.collection.objects.link(cam); s.camera = cam; cam.data.type = 'ORTHO'; cam.data.ortho_scale = SC
    s.render.resolution_x = s.render.resolution_y = RES; cam.location = camloc; cam.rotation_euler = Q.to_euler()
    s.render.filepath = base + '_render.png'; bpy.ops.render.render(write_still=True)
    sh.light = 'STUDIO'; sh.color_type = 'SINGLE'; sh.single_color = (0.6, 0.6, 0.6)
    s.render.filepath = base + '_gray.png'; bpy.ops.render.render(write_still=True)
    if os.environ.get('LMASK'):
        for o in bpy.data.objects:
            if o.type == 'MESH': o.hide_render = not o.name.startswith(os.environ['LMASK'])
        s.render.film_transparent = True; s.render.image_settings.color_mode = 'RGBA'
        s.render.filepath = base + '_occ.png'; bpy.ops.render.render(write_still=True)
    print('INFO rendered')
else:
    paint = bpy.data.images.load(base + '_paint.png'); PW, PH = paint.size
    pp = np.array(paint.pixels[:], np.float32).reshape(PH, PW, 4)[..., :3]
    mk = None
    if os.path.exists(base + '_mask.png'):
        mi_ = bpy.data.images.load(base + '_mask.png'); mk = np.array(mi_.pixels[:], np.float32).reshape(PH, PW, 4)[..., 0]
    dg = bpy.context.evaluated_depsgraph_get()
    em = body.evaluated_get(dg).data; W = [M @ v.co for v in em.vertices]
    uvl = me.uv_layers.active.data
    Ri = R3.inverted()
    def to_px(p):
        L = Ri @ (p - camloc); return (L.x / SC + 0.5) * PW, (L.y / SC + 0.5) * PH      # pixels() rows are bottom-up
    cand = [p for p in me.polygons if (M @ p.center - C).length < RADIUS and (M.to_3x3() @ p.normal).dot(d) > float(os.environ.get('LFACE', '0.0'))]
    hidden_by_me = set()
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name != 'Body' and not o.hide_viewport: o.hide_viewport = True; hidden_by_me.add(o.name)
    bpy.context.view_layer.update(); dg2 = bpy.context.evaluated_depsgraph_get()
    sel = []
    for p in cand:
        pc = M @ p.center
        pts = [pc] + [pc.lerp(M @ me.vertices[v].co, 0.7) for v in p.vertices]
        vis = False
        for q in pts:
            Lq = Ri @ (q - camloc)
            if abs(Lq.x) > SC / 2 or abs(Lq.y) > SC / 2: continue
            ok, hp, n_, idx, ob, _ = s.ray_cast(dg2, q + d * 0.5, -d)
            if ok and (idx == p.index or (hp - q).length < 0.0015): vis = True; break
        if vis: sel.append(p)
    print('cand', len(cand), 'visible', len(sel), 'has_center', any(p.index == fi for p in sel))
    by_img = {}
    for p in sel: by_img.setdefault(p.material_index, []).append(p)
    n_tex = 0
    for mi, polys in by_img.items():
        m = me.materials[mi]; img = [n.image for n in m.node_tree.nodes if n.type == 'TEX_IMAGE'][0]
        TW, TH = img.size; tp = np.array(img.pixels[:], np.float32).reshape(TH, TW, 4)
        for p in polys:
            vs = [W[v] for v in p.vertices]; us = [uvl[l].uv for l in p.loop_indices]
            for k in range(1, len(vs) - 1):
                tri = (0, k, k + 1); U = [Vector((us[i].x * TW, us[i].y * TH, 0)) for i in tri]; V3 = [vs[i] for i in tri]
                x0 = int(max(0, min(u.x for u in U))); x1 = int(min(TW - 1, max(u.x for u in U)) + 1)
                y0 = int(max(0, min(u.y for u in U))); y1 = int(min(TH - 1, max(u.y for u in U)) + 1)
                for y in range(y0, y1 + 1):
                    for x in range(x0, x1 + 1):
                        q = Vector((x + 0.5, y + 0.5, 0))
                        # inside test via barycentric
                        a, b, c = U
                        den = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y)
                        if abs(den) < 1e-9: continue
                        w0 = ((b.y - c.y) * (q.x - c.x) + (c.x - b.x) * (q.y - c.y)) / den
                        w1 = ((c.y - a.y) * (q.x - c.x) + (a.x - c.x) * (q.y - c.y)) / den; w2 = 1 - w0 - w1
                        if min(w0, w1, w2) < -0.02: continue
                        P3 = V3[0] * w0 + V3[1] * w1 + V3[2] * w2
                        px, py = to_px(P3)
                        if 0 <= px < PW - 1 and 0 <= py < PH - 1:
                            a_ = 1.0 if mk is None else mk[int(py), int(px)]
                            if a_ <= 0.004: continue
                            tp[y, x, :3] = tp[y, x, :3] * (1 - a_) + pp[int(py), int(px)] * a_; n_tex += 1
        img.pixels.foreach_set(tp.ravel()); img.update()
        dst = base + f'_tex_{mi}.png'
        tmp = bpy.data.images.new('lp_tmp', TW, TH, alpha=True); tmp.pixels.foreach_set(tp.ravel())
        tmp.filepath_raw = dst; tmp.file_format = 'PNG'; tmp.save(); bpy.data.images.remove(tmp)
        newimg = bpy.data.images.load(dst, check_existing=False); newimg.pack()
        img.user_remap(newimg); nm = img.name; bpy.data.images.remove(img); newimg.name = nm
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name in hidden_by_me: o.hide_viewport = False      # restore viewport visibility before saving
    bpy.ops.wm.save_as_mainfile(filepath=args[3])
    print('INFO projected faces', len(sel), 'texels', n_tex)
