import bpy, json, math, os, sys
from mathutils import Vector, Matrix
# Combine chosen Hair_S## objects into one export piece for Tripo; outward = -X (back of head) -> Tripo front (-Y).
R, names, tag = sys.argv[sys.argv.index('--') + 1:][:3]
names = names.split(',')
for d in ('input', 'reference', 'jobs', 'textures'): os.makedirs(R + d, exist_ok=True)
s = bpy.context.scene
rig = [o for o in bpy.data.objects if o.name.endswith('_Rig')][0]; rig.data.pose_position = 'REST'; s.frame_set(0); bpy.context.view_layer.update()
hair = bpy.data.objects['Hair']; hm = hair.data
oim = [n.image for n in hm.materials[hm.polygons[0].material_index].node_tree.nodes if n.type == 'TEX_IMAGE'][0]
verts, faces, uvs, owner = [], [], [], []
for nm in names:
    ob = bpy.data.objects[nm]; me = ob.data; base = len(verts); uvl = me.uv_layers[0].data
    verts += [ob.matrix_world @ v.co for v in me.vertices]
    for p in me.polygons:
        faces.append([base + v for v in p.vertices]); uvs.append([uvl[l].uv.copy() for l in p.loop_indices]); owner.append((nm, p.index))
mesh = bpy.data.meshes.new(tag); mesh.from_pydata(verts, [], faces); mesh.update()
uv = mesh.uv_layers.new(name='SourceUV')
for f, u in zip(mesh.polygons, uvs):
    for l, x in zip(f.loop_indices, u): uv.data[l].uv = x
m = bpy.data.materials.new('Src'); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
un = nt.nodes.new('ShaderNodeUVMap'); un.uv_map = 'SourceUV'; tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = oim
e = nt.nodes.new('ShaderNodeEmission'); o = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(un.outputs[0], tx.inputs[0]); nt.links.new(tx.outputs[0], e.inputs[0]); nt.links.new(e.outputs[0], o.inputs[0]); mesh.materials.append(m)
ob = bpy.data.objects.new('P_' + tag, mesh); s.collection.objects.link(ob)
for o_ in s.objects: o_.hide_render = o_ is not ob
eng = [x.identifier for x in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
s.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in eng else 'BLENDER_EEVEE_NEXT'; s.render.resolution_x = s.render.resolution_y = 1254
w = s.world or bpy.data.worlds.new('W'); s.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.3, 0.32, 0.36, 1)
s.view_settings.view_transform = 'Standard'; s.view_settings.look = 'None'
cam = bpy.data.objects.new('GC', bpy.data.cameras.new('GC')); s.collection.objects.link(cam); s.camera = cam; cam.data.type = 'ORTHO'
gm = bpy.data.materials.new('Clay'); gm.use_nodes = True; nt = gm.node_tree; nt.nodes.clear()
d_ = nt.nodes.new('ShaderNodeBsdfDiffuse'); d_.inputs[0].default_value = (.55, .55, .55, 1); o_ = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(d_.outputs[0], o_.inputs[0])
sun = bpy.data.objects.new('GS', bpy.data.lights.new('GS', 'SUN')); s.collection.objects.link(sun); sun.data.energy = 3
P = [v.co for v in mesh.vertices]; lo = Vector([min(p[a] for p in P) for a in range(3)]); hi = Vector([max(p[a] for p in P) for a in range(3)]); c = (lo + hi) / 2
out = Vector((-1, 0, 0)); Rm = out.to_track_quat('-Y', 'Z').to_matrix().to_4x4().inverted()
cam.data.ortho_scale = max(hi.y - lo.y, hi.z - lo.z) * 1.12
for lab, sg in (('front', 1), ('back', -1)):
    dv = out * sg; cam.location = c + dv * 2; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
    sun.hide_render = True; s.render.filepath = R + f'reference/{tag}_{lab}_source.png'; bpy.ops.render.render(write_still=True)
    mesh.materials[0] = gm; sun.hide_render = False; sun.rotation_euler = (dv + Vector((0, 0, 0.8))).to_track_quat('Z', 'Y').to_euler()
    s.render.filepath = R + f'reference/{tag}_{lab}_gray.png'; bpy.ops.render.render(write_still=True); mesh.materials[0] = m
T = Matrix.Scale(1 / max(hi - lo), 4) @ Rm @ Matrix.Translation(-c)
cu = mesh.uv_layers.new(name='ComponentUV'); mesh.uv_layers.active = cu
bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.005); bpy.ops.object.mode_set(mode='OBJECT')
for v in mesh.vertices: v.co = T @ v.co
mesh.uv_layers.remove(mesh.uv_layers['SourceUV']); mesh.materials.clear(); g2 = bpy.data.materials.new('In'); mesh.materials.append(g2)
bpy.ops.export_scene.gltf(filepath=R + f'input/{tag}.glb', use_selection=True, export_apply=True, export_animations=False, export_skins=False, export_morph=False, export_yup=True)
json.dump({tag: dict(owner=owner, R=[list(r) for r in Rm])}, open(R + 'manifest.json', 'w'))
print('INFO piece', tag, len(faces))
