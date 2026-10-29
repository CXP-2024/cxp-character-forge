import bpy, bmesh, json, math, sys, numpy as np
from mathutils import Vector, Matrix
# Old-version recipe: solid smooth gold buttons (replace corset buttons), solid navy placket buttons, solid gold crosses on puff sleeves.
out = sys.argv[sys.argv.index('--') + 1]
s = bpy.context.scene
rig = [o for o in bpy.data.objects if o.name.endswith('_Rig')][0]; keep = rig.data.pose_position
rig.data.pose_position = 'REST'; s.frame_set(0); bpy.context.view_layer.update()
body = bpy.data.objects['Body']; me = body.data; M = body.matrix_world; ga = me.attributes['body_group']
vg_names = {g.index: g.name for g in body.vertex_groups}
# ---- loose components of the buttons group
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
seen = set(); comps = []
for f0 in bm.faces:
    if f0.index in seen or ga.data[f0.index].value != 15: continue
    st = [f0]; seen.add(f0.index); c = []
    while st:
        f = st.pop(); c.append(f.index)
        for e in f.edges:
            for g in e.link_faces:
                if g.index not in seen: seen.add(g.index); st.append(g)
    if len(c) < 500: comps.append(c)
bm.free()
def info(c):
    vs = sorted({v for i in c for v in me.polygons[i].vertices})
    P = [M @ me.vertices[v].co for v in vs]; ctr = sum(P, Vector()) / len(P)
    n = sum(((M.to_3x3() @ me.polygons[i].normal) * me.polygons[i].area for i in c), Vector()).normalized()
    # outward normal: pointing away from body axis
    radial = Vector((ctr.x - 0.04, ctr.y, 0)).normalized()
    if n.dot(radial) < 0: n = -n
    r = max((p - ctr).length for p in P)
    w = {}
    for v in vs:
        for g in me.vertices[v].groups: w[vg_names[g.group]] = w.get(vg_names[g.group], 0) + g.weight / len(vs)
    return dict(vs=vs, ctr=ctr, n=n, r=r, w=w)
gold, navy = [], []
for c in comps:
    d = info(c)
    if 0.645 < d['ctr'].z < 0.69 and 0.018 < abs(d['ctr'].y) < 0.042: gold.append((c, d))
    elif d['ctr'].x > 0.09 and abs(d['ctr'].y) < 0.01 and 0.69 < d['ctr'].z < 0.75: navy.append((c, d))
print('gold', len(gold), 'navy', len(navy))
# ---- materials (unlit-friendly: emission with facing-based shading + rim highlight, so it reads as metal without lights)
def metal(name, dark, light, spec):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.35
    ramp = nt.nodes.new('ShaderNodeValToRGB'); el = ramp.color_ramp.elements
    el[0].position = 0.0; el[0].color = (*light, 1); el[1].position = 1.0; el[1].color = (*dark, 1)
    mid = el.new(0.55); mid.color = (*[(a + b) / 2 for a, b in zip(light, dark)], 1)
    hi = el.new(0.08); hi.color = (*spec, 1)
    nt.links.new(lw.outputs['Facing'], ramp.inputs['Fac'])
    e = nt.nodes.new('ShaderNodeEmission'); o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(ramp.outputs['Color'], e.inputs['Color']); nt.links.new(e.outputs[0], o.inputs[0])
    return m
m_gold = metal('Solid_Gold', (0.42, 0.25, 0.05), (0.95, 0.72, 0.30), (1.0, 0.93, 0.7))
m_navy = metal('Solid_NavyButton', (0.02, 0.03, 0.10), (0.16, 0.20, 0.42), (0.55, 0.62, 0.85))
def place(obj, ctr, n, w):
    q = n.to_track_quat('Z', 'Y'); obj.matrix_world = Matrix.Translation(ctr) @ q.to_matrix().to_4x4()
    bpy.context.view_layer.update(); obj.data.transform(obj.matrix_world); obj.matrix_world = Matrix.Identity(4)
    for name, val in w.items():
        if val < 0.02: continue
        g = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name); g.add(list(range(len(obj.data.vertices))), val, 'REPLACE')
    obj.parent = rig; obj.matrix_parent_inverse = rig.matrix_world.inverted()
    md = obj.modifiers.new('Armature', 'ARMATURE'); md.object = rig
    for col in body.users_collection:
        if obj.name not in col.objects: col.objects.link(obj)
    for col in list(obj.users_collection):
        if col not in body.users_collection: col.objects.unlink(obj)
def button(name, d, mat, scale=0.95):
    bmb = bmesh.new()
    bmesh.ops.create_uvsphere(bmb, u_segments=32, v_segments=16, radius=1.0)
    for v in bmb.verts: v.co = Vector((v.co.x, v.co.y, max(v.co.z, -0.15) * 0.42))     # domed button
    # rim ring
    ring = bmesh.ops.create_circle(bmb, cap_ends=False, segments=32, radius=1.0)
    me2 = bpy.data.meshes.new(name); bmb.to_mesh(me2); bmb.free()
    r = d['r'] * scale; me2.transform(Matrix.Scale(r, 4))
    for p in me2.polygons: p.use_smooth = True
    me2.materials.append(mat)
    o = bpy.data.objects.new(name, me2); s.collection.objects.link(o)
    place(o, d['ctr'] - d['n'] * r * 0.15, d['n'], d['w']); return o
made = []
for k, (c, d) in enumerate(sorted(gold, key=lambda x: (x[1]['ctr'].x, x[1]['ctr'].y, x[1]['ctr'].z))): made.append(button(f'GoldButton_{k:02}', d, m_gold))
for k, (c, d) in enumerate(sorted(navy, key=lambda x: x[1]['ctr'].z)): made.append(button(f'NavyButton_{k:02}', d, m_navy, 0.9))
# ---- crosses on puff sleeves: gold texel clusters near y +-0.12, z ~0.79
uvl = me.uv_layers.active.data; cache = {}
def pix(mi):
    if mi not in cache:
        im = [n.image for n in me.materials[mi].node_tree.nodes if n.type == 'TEX_IMAGE'][0]
        cache[mi] = (im, np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4))
    return cache[mi]
goldf = []
for p in me.polygons:
    if ga.data[p.index].value != 12: continue
    c3 = M @ p.center
    if not (0.10 < abs(c3.y) < 0.14 and 0.77 < c3.z < 0.81): continue
    im, px = pix(p.material_index); H, W = px.shape[:2]
    u = sum((uvl[l].uv for l in p.loop_indices), Vector((0, 0))) / len(p.loop_indices)
    c = px[min(H - 1, int(u.y * H)), min(W - 1, int(u.x * W)), :3]
    if c[0] - c[2] > 0.18 and c[0] > 0.45: goldf.append(p.index)
cl = []
for i in goldf:
    c3 = M @ me.polygons[i].center
    for k in cl:
        if (k['c'] - c3).length < 0.015: k['ids'].append(i); break
    else: cl.append(dict(ids=[i], c=c3))
crosses = []
for k, cc in enumerate(cl):
    ids = cc['ids']; P = [M @ me.polygons[i].center for i in ids]; ctr = sum(P, Vector()) / len(P)
    n = sum(((M.to_3x3() @ me.polygons[i].normal) * me.polygons[i].area for i in ids), Vector()).normalized()
    size = max(0.009, min(0.016, 2 * max((p - ctr).length for p in P)))
    vs = sorted({v for i in ids for v in me.polygons[i].vertices}); w = {}
    for v in vs:
        for g in me.vertices[v].groups: w[vg_names[g.group]] = w.get(vg_names[g.group], 0) + g.weight / len(vs)
    bmc = bmesh.new()
    for sx, sy, ty in ((0.16, 1.0, 0.1), (0.62, 0.15, 0.28)):          # vertical bar, crossbar slightly above centre
        r = bmesh.ops.create_cube(bmc, size=1.0)['verts']
        for v in r: v.co = Vector((v.co.x * sx, v.co.y * sy + (ty if sy < 0.5 else 0), v.co.z * 0.14 + 0.07))
    bmesh.ops.bevel(bmc, geom=list(bmc.edges), offset=0.025, segments=2, affect='EDGES')
    me3 = bpy.data.meshes.new(f'SleeveCross_{k}'); bmc.to_mesh(me3); bmc.free(); me3.transform(Matrix.Scale(size * 0.5, 4))
    me3.materials.append(m_gold)
    o = bpy.data.objects.new(f'SleeveCross_{k}', me3); s.collection.objects.link(o)
    up = Vector((0, 0, 1)); xax = up.cross(n).normalized(); yax = n.cross(xax)
    R = Matrix((xax, yax, n)).transposed().to_4x4()
    o.matrix_world = Matrix.Translation(ctr + n * 0.0005) @ R; bpy.context.view_layer.update(); o.data.transform(o.matrix_world); o.matrix_world = Matrix.Identity(4)
    place(o, Vector(), Vector((0, 0, 1)), w); crosses.append(o)
    # paint the old gold texels of these faces with the surrounding navy
    im, px = pix(me.polygons[ids[0]].material_index); H, W = px.shape[:2]
    for i in ids:
        us = [uvl[l].uv for l in me.polygons[i].loop_indices]
        x0 = int(min(u.x for u in us) * W) - 2; x1 = int(max(u.x for u in us) * W) + 3; y0 = int(min(u.y for u in us) * H) - 2; y1 = int(max(u.y for u in us) * H) + 3
        blk = px[max(0, y0):y1, max(0, x0):x1, :3]
        if blk.size == 0: continue
        g = (blk[..., 0] - blk[..., 2] > 0.1) | (blk.mean(2) > 0.45)
        navyc = np.median(px[max(0, y0 - 12):y1 + 12, max(0, x0 - 12):x1 + 12, :3].reshape(-1, 3)[(px[max(0, y0 - 12):y1 + 12, max(0, x0 - 12):x1 + 12, :3].reshape(-1, 3).mean(1) < 0.3)], 0) if True else None
        if np.isnan(navyc).any(): continue
        blk[g] = navyc
print('crosses', len(crosses), [len(c['ids']) for c in cl])
for mi, (im, px) in cache.items():
    im.pixels.foreach_set(px.ravel()); im.update()
    dst = bpy.path.abspath('//') + f'../textures/sleeves_nocross_{mi}.png'
    tmp = bpy.data.images.new('t', im.size[0], im.size[1], alpha=True); tmp.pixels.foreach_set(px.ravel()); tmp.filepath_raw = dst; tmp.file_format = 'PNG'; tmp.save(); bpy.data.images.remove(tmp)
    ni = bpy.data.images.load(dst, check_existing=False); ni.pack(); nm = im.name; im.user_remap(ni); bpy.data.images.remove(im); ni.name = nm
# ---- delete old button geometry
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
dead = {i for c, d in gold + navy for i in c}
bmesh.ops.delete(bm, geom=[bm.faces[i] for i in dead], context='FACES')
bm.to_mesh(me); bm.free(); me.update()
rig.data.pose_position = keep; s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=out)
print('INFO buttons', len(made), 'crosses', len(crosses), 'deleted faces', len(dead))
