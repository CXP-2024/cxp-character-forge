import bpy, bmesh, sys, os, math, numpy as np
from mathutils import Vector
# Hand like the Genshin 沃雅妮莎 model: flat skin (face-matched), faint pink at fingertips / knuckles,
# nails only on the back side of the fingertips, no painted shading. Own material + own UV + own image.
out = sys.argv[sys.argv.index('--') + 1]; YMIN = 0.283; RES = 2048
BASE = np.array([0.99, 0.915, 0.89]); PINK = np.array([0.985, 0.80, 0.78]); NAIL = np.array([0.985, 0.875, 0.87]); RIM = np.array([0.90, 0.68, 0.68])
s = bpy.context.scene
rig = [o for o in bpy.data.objects if o.name.endswith('_Rig')][0]; rig.data.pose_position = 'REST'; s.frame_set(0); bpy.context.view_layer.update()
body = bpy.data.objects['Body']; me = body.data
bpy.ops.object.select_all(action='DESELECT'); body.select_set(True); bpy.context.view_layer.objects.active = body
# hand faces = the arm component beyond the wrist (cuff ruffles / band are separate components and stay untouched)
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); seen = set(); hand_ids = set()
for f0 in bm.faces:
    if f0.index in seen or abs(f0.calc_center_median().y) < 0.2: continue
    st = [f0]; seen.add(f0.index); c = []
    while st:
        f = st.pop(); c.append(f.index)
        for e in f.edges:
            for g in e.link_faces:
                if g.index not in seen: seen.add(g.index); st.append(g)
    if len(c) > 1000 and any(abs(bm.faces[i].calc_center_median().y) > 0.34 for i in c):
        hand_ids |= {i for i in c if abs(bm.faces[i].calc_center_median().y) > YMIN}
bm.free()
B = {b.name: (rig.matrix_world @ b.head_local, rig.matrix_world @ b.tail_local) for b in rig.data.bones}
fingers = []   # (side sign, tip point, axis, back dir, joints, name)
co = np.array([v.co[:] for v in me.vertices]); hv = sorted({v for i in hand_ids for v in me.polygons[i].vertices})
# fingers from the MESH (auto-rig finger bones do not sit on the Tripo fingers): beyond the palm the
# fingers are separate connected pieces; each piece's far end is a fingertip
adj = {}
for e in me.edges:
    a_, b_ = e.vertices; adj.setdefault(a_, []).append(b_); adj.setdefault(b_, []).append(a_)
YF = float(os.environ.get('YFING', '0.333'))
for sg in (1, -1):
    pool = {v for v in hv if co[v][1] * sg > YF}; seen2 = set(); pieces = []
    for v0 in pool:
        if v0 in seen2: continue
        st = [v0]; seen2.add(v0); comp = []
        while st:
            v = st.pop(); comp.append(v)
            for w in adj.get(v, []):
                if w in pool and w not in seen2: seen2.add(w); st.append(w)
        if len(comp) > 15: pieces.append(np.array(comp))
    pieces.sort(key=lambda c: -co[c][:, 0].mean())                    # +X (front) first: thumb
    for k, comp in enumerate(pieces):
        P = co[comp]; cen = P.mean(0); U, S, Vt = np.linalg.svd(P - cen); A = Vt[0] * np.sign(Vt[0][1] * sg)
        tip = P[np.argmax((P - cen) @ A)]
        name = 'Thumb' if k == 0 and len(pieces) == 5 else f'F{k}'
        back = np.array([0.55, 0, 0.83]) if name == 'Thumb' else np.array([0, 0, 1.0])
        back = back - A * (back @ A); back /= np.linalg.norm(back)
        joints = [tip - A * 0.011, tip - A * 0.021, tip - A * 0.033]
        fingers.append((sg, tip, A, back, joints, name))
        print('FINGER', sg, name, np.round(tip, 4), 'verts', len(comp))
def sm(x, a, b):          # smoothstep from a (0) to b (1)
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)
# own UV for the hand faces
huv_name = 'HandUV'; act = me.uv_layers.active.name; actr = [l.name for l in me.uv_layers if l.active_render][0]
hu = me.uv_layers.get(huv_name) or me.uv_layers.new(name=huv_name); me.uv_layers.active = hu
bpy.ops.object.mode_set(mode='EDIT'); bme = bmesh.from_edit_mesh(body.data); bme.faces.ensure_lookup_table()
for f in bme.faces: f.select_set(f.index in hand_ids)
bmesh.update_edit_mesh(body.data)
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.006, area_weight=0.0, scale_to_bounds=True)
bpy.ops.object.mode_set(mode='OBJECT'); me = body.data; me.uv_layers.active = me.uv_layers[act]; me.uv_layers[actr].active_render = True
hu = me.uv_layers[huv_name].data
vn = np.array([v.normal[:] for v in me.vertices])
img = np.ones((RES, RES, 4), np.float32); img[..., :3] = BASE
def shade(P, N, sg):
    col = np.broadcast_to(BASE, P.shape).copy(); wp = np.zeros(len(P)); wn = np.zeros(len(P))
    for fsg, tip, A, back, joints, name in fingers:
        if fsg != sg: continue
        d = tip - P; t = d @ A; lat = np.linalg.norm(d - np.outer(t, A), axis=1); nb = N @ back
        wp = np.maximum(wp, 0.30 * sm(-t, -0.012, 0.0) * (lat < 0.008))                                   # faint pink fingertip
        nl = 0.0075 if name == 'Thumb' else 0.0062; nw = 0.0040 if name == 'Thumb' else 0.0033
        e2 = ((t - nl * 0.55) / (nl * 0.55)) ** 2 + (lat / nw) ** 2                                   # rounded nail, ends ~0.5 mm short of the tip
        nail = sm(-e2, -1.0, -0.72) * sm(nb, 0.25, 0.5) * sm(t, 0.0002, 0.0008)
        wn = np.maximum(wn, nail)
        for j in joints:                                                                           # faint knuckle pink, back side only
            wp = np.maximum(wp, 0.16 * sm(-np.linalg.norm(P - j, axis=1), -0.0065, 0.0) * sm(nb, 0.0, 0.4))
    col = col * (1 - wp[:, None]) + PINK * wp[:, None]
    rim = np.clip(4 * wn * (1 - wn), 0, 1) * 0.38
    col = col * (1 - wn[:, None]) + NAIL * wn[:, None]
    col = col * (1 - rim[:, None]) + RIM * rim[:, None]
    return col
for i in hand_ids:
    p = me.polygons[i]; vs = list(p.vertices); us = [hu[l].uv for l in p.loop_indices]; sg = 1 if p.center.y > 0 else -1
    for k in range(1, len(vs) - 1):
        T = [0, k, k + 1]; A2 = np.array([[us[j].x * RES, us[j].y * RES] for j in T])
        V3 = co[[vs[j] for j in T]]; N3 = vn[[vs[j] for j in T]]
        x0, y0 = np.maximum(np.floor(A2.min(0) - 2).astype(int), 0); x1, y1 = np.minimum(np.ceil(A2.max(0) + 2).astype(int), RES - 1)
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = A2; den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12: continue
        w0 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den; w1 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den; w2 = 1 - w0 - w1
        ins = (w0 > -0.15) & (w1 > -0.15) & (w2 > -0.15)
        if not ins.any(): continue
        W3 = np.stack([w0[ins], w1[ins], w2[ins]], 1); P = W3 @ V3; N = W3 @ N3; N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-6)
        blk = img[y0:y1 + 1, x0:x1 + 1, :3]; blk[ins] = shade(P, N, sg)
dst = bpy.path.abspath('//') + '../textures/Hand_Skin_Voy.png'
im = bpy.data.images.new('Hand_Skin_Voy', RES, RES, alpha=True); im.pixels.foreach_set(img.ravel()); im.filepath_raw = dst; im.file_format = 'PNG'; im.save(); im.pack()
mat = bpy.data.materials.get('Hand_Skin') or bpy.data.materials.new('Hand_Skin'); mat.use_nodes = True; nt = mat.node_tree; nt.nodes.clear()
uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = huv_name; tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = im
e = nt.nodes.new('ShaderNodeEmission'); o = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(uvn.outputs[0], tx.inputs[0]); nt.links.new(tx.outputs[0], e.inputs[0]); nt.links.new(e.outputs[0], o.inputs[0])
if mat.name not in [m.name for m in me.materials if m]: me.materials.append(mat)
mi = [k for k, m in enumerate(me.materials) if m and m.name == mat.name][0]
for i in hand_ids: me.polygons[i].material_index = mi
s.frame_set(1); bpy.ops.wm.save_as_mainfile(filepath=out); print('INFO hand faces', len(hand_ids))
