import bpy, sys, json, glob, math, os
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
R = os.environ['TEX_JOB_DIR'].rstrip('/') + '/'   # job dir (manifest.json, input/, textures/)
out_blend = sys.argv[sys.argv.index('--') + 1]
groups = sys.argv[sys.argv.index('--') + 2].split(',')
man = json.load(open(R + 'manifest.json'))
s = bpy.context.scene
rig = [o for o in bpy.data.objects if o.name.endswith('_Rig')][0]; keep = rig.data.pose_position
rig.data.pose_position = 'REST'; s.frame_set(0); bpy.context.view_layer.update()
body = bpy.data.objects['Body']; me = body.data; M = body.matrix_world
em = body.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
evco = [M @ v.co for v in em.vertices]
uvl = me.uv_layers.active.data
report = {}
os.makedirs(R + 'textures', exist_ok=True)
for tag in groups:
    fids = man[tag]['face_ids']; tgt = [me.polygons[i] for i in fids]
    path = sorted(glob.glob(R + f'jobs/{tag}/assets/*.glb'))[-1]
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=path)
    ret = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    rv, rt, ruv, img = [], [], [], None
    Rinv = Matrix.Rotation(math.pi / 2, 4, 'Z')
    for o in ret:
        m = o.data; m.calc_loop_triangles(); uv = m.uv_layers.active.data; base = len(rv)
        rv += [Rinv @ (o.matrix_world @ v.co) for v in m.vertices]
        for t in m.loop_triangles: rt.append(tuple(base + i for i in t.vertices)); ruv.append([uv[l].uv.copy() for l in t.loops])
        for mat in m.materials:
            for n in (mat.node_tree.nodes if mat and mat.node_tree else []):
                if n.type == 'BSDF_PRINCIPLED' and n.inputs['Base Color'].links:
                    src = n.inputs['Base Color'].links[0].from_node
                    while src.type != 'TEX_IMAGE' and src.inputs and src.inputs[0].links: src = src.inputs[0].links[0].from_node
                    if src.type == 'TEX_IMAGE' and src.image: img = src.image
    tv = [evco[v] for p in tgt for v in p.vertices]
    lo = Vector([min(v[i] for v in tv) for i in range(3)]); hi = Vector([max(v[i] for v in tv) for i in range(3)])
    rlo = Vector([min(v[i] for v in rv) for i in range(3)]); rhi = Vector([max(v[i] for v in rv) for i in range(3)])
    f = max(hi - lo) / max(rhi - rlo); rv = [(v - (rlo + rhi) / 2) * f + (lo + hi) / 2 for v in rv]
    kd = KDTree(len(tgt))
    for i, p in enumerate(tgt): kd.insert(sum((evco[v] for v in p.vertices), Vector()) / 3, i)
    kd.balance(); done = set(); tol = max(hi - lo) * 3e-4
    for ti, tri in enumerate(rt):
        c = (rv[tri[0]] + rv[tri[1]] + rv[tri[2]]) / 3; _, i, d = kd.find(c)
        if d > tol: continue
        p = tgt[i]
        for li in p.loop_indices:
            vp = evco[me.loops[li].vertex_index]; k = min(range(3), key=lambda k: (rv[tri[k]] - vp).length); uvl[li].uv = ruv[ti][k]
        done.add(i)
    bvh = BVHTree.FromPolygons(rv, rt, all_triangles=True); miss = 0
    for i, p in enumerate(tgt):
        if i in done: continue
        miss += 1
        for li in p.loop_indices:
            vp = evco[me.loops[li].vertex_index]; loc, n, tj, d = bvh.find_nearest(vp); tri = rt[tj]
            a, b, c = (rv[k] for k in tri); ua, ub, uc = (Vector((u.x, u.y, 0)) for u in ruv[tj])
            q = barycentric_transform(loc, a, b, c, ua, ub, uc); uvl[li].uv = (q.x, q.y)
    dst = R + f'textures/{tag}_BaseColor_tripo.png'
    img.filepath_raw = dst; img.file_format = 'PNG'; img.save()
    im = bpy.data.images.load(dst, check_existing=False); im.name = f'Tripo_{tag}_BaseColor'; im.pack()
    mat = bpy.data.materials.new(f'Tripo_{tag}'); mat.use_nodes = True; nt = mat.node_tree; nt.nodes.clear()
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = im; e = nt.nodes.new('ShaderNodeEmission'); o_ = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(tn.outputs['Color'], e.inputs['Color']); nt.links.new(e.outputs['Emission'], o_.inputs['Surface'])
    me.materials.append(mat); mi = len(me.materials) - 1
    for p in tgt: p.material_index = mi
    report[tag] = dict(faces=len(tgt), matched=len(done), fallback=miss, scale=f, image=list(img.size))
    for o in ret: bpy.data.objects.remove(o)
rig.data.pose_position = keep; s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print('INFO', json.dumps(report))
