import bpy, sys, json, glob, math
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
# Put the Tripo texture of a combined strand piece back on its Hair_S## objects (new UV 'TripoUV' + material).
R, tag, out = sys.argv[sys.argv.index('--') + 1:][:3]
man = json.load(open(R + 'manifest.json'))[tag]; owner = man['owner']
s = bpy.context.scene
for a in [o for o in bpy.data.objects if o.type == 'ARMATURE']: a.data.pose_position = 'REST'
s.frame_set(0); bpy.context.view_layer.update()
path = sorted(glob.glob(R + f'jobs/{tag}/assets/*.glb'))[-1]
before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=path)
ret = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
Rinv = Matrix(man['R']).inverted(); rv, rt, ruv, img = [], [], [], None
for o in ret:
    m = o.data; m.calc_loop_triangles(); uv = m.uv_layers.active.data; base = len(rv)
    rv += [Rinv @ (o.matrix_world @ v.co) for v in m.vertices]
    for t in m.loop_triangles: rt.append(tuple(base + i for i in t.vertices)); ruv.append([uv[l].uv.copy() for l in t.loops])
    for mat in m.materials:
        for n in mat.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED' and n.inputs['Base Color'].links:
                src = n.inputs['Base Color'].links[0].from_node
                while src.type != 'TEX_IMAGE' and src.inputs and src.inputs[0].links: src = src.inputs[0].links[0].from_node
                if src.type == 'TEX_IMAGE': img = src.image
objs = {}
for nm, fi in owner: objs.setdefault(nm, []).append(fi)
tv = []
for nm in objs:
    ob = bpy.data.objects[nm]; tv += [ob.matrix_world @ v.co for v in ob.data.vertices]
lo = Vector([min(v[i] for v in tv) for i in range(3)]); hi = Vector([max(v[i] for v in tv) for i in range(3)])
rlo = Vector([min(v[i] for v in rv) for i in range(3)]); rhi = Vector([max(v[i] for v in rv) for i in range(3)])
f = max(hi - lo) / max(rhi - rlo); rv = [(v - (rlo + rhi) / 2) * f + (lo + hi) / 2 for v in rv]
bvh = BVHTree.FromPolygons(rv, rt, all_triangles=True)
dst = R + f'textures/{tag}_tripo.png'; img.filepath_raw = dst; img.file_format = 'PNG'; img.save()
im = bpy.data.images.load(dst, check_existing=False); im.name = f'Tripo_{tag}'; im.pack()
mat = bpy.data.materials.new(f'Hair_{tag}'); mat.use_nodes = True; nt = mat.node_tree; nt.nodes.clear()
un = nt.nodes.new('ShaderNodeUVMap'); un.uv_map = 'TripoUV'; tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = im
e = nt.nodes.new('ShaderNodeEmission'); o_ = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(un.outputs[0], tx.inputs[0]); nt.links.new(tx.outputs[0], e.inputs[0]); nt.links.new(e.outputs[0], o_.inputs[0])
for nm in objs:
    ob = bpy.data.objects[nm]; me = ob.data; M = ob.matrix_world
    uv = me.uv_layers.get('TripoUV') or me.uv_layers.new(name='TripoUV')
    for p in me.polygons:
        ctr = M @ p.center; _, _, tj, _ = bvh.find_nearest(ctr); tri = rt[tj]
        a, b, c = (rv[k] for k in tri); ua, ub, uc = (Vector((u.x, u.y, 0)) for u in ruv[tj])
        for l in p.loop_indices:
            vp = M @ me.vertices[me.loops[l].vertex_index].co
            # sample on the same Tripo triangle when close, else nearest
            loc, n, tk, d = bvh.find_nearest(vp.lerp(ctr, 0.02))
            if tk != tj:
                a2, b2, c2 = (rv[k] for k in rt[tk]); q = barycentric_transform(loc, a2, b2, c2, *(Vector((u.x, u.y, 0)) for u in ruv[tk]))
            else:
                q = barycentric_transform(vp, a, b, c, ua, ub, uc)
            uv.data[l].uv = (q.x, q.y)
    me.materials.clear(); me.materials.append(mat)
    for p in me.polygons: p.material_index = 0
for o in ret: bpy.data.objects.remove(o)
print('INFO restored', list(objs), 'tex', list(img.size))
s.frame_set(1); bpy.ops.wm.save_as_mainfile(filepath=out)
