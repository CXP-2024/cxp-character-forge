import bpy, bmesh, json, math, os
from mathutils import Vector, Matrix
# Old-version (V11 body_components_v2) recipe on the new model:
# 4 groups, front source render with original texture, mesh centred / unit-scaled / rotated so front faces -Y, exported for Tripo.
R = os.environ['TEX_JOB_DIR'].rstrip('/') + '/'   # job dir (manifest.json, input/, textures/)
os.makedirs(R + 'input', exist_ok=True); os.makedirs(R + 'reference', exist_ok=True)
s = bpy.context.scene
rig = [o for o in bpy.data.objects if o.name.endswith('_Rig')][0]; rig.data.pose_position = 'REST'; s.frame_set(0); bpy.context.view_layer.update()
body = bpy.data.objects['Body']; me = body.data; ga = me.attributes['body_group']; M = body.matrix_world
dg = bpy.context.evaluated_depsgraph_get(); em = body.evaluated_get(dg).data
evco = [M @ v.co for v in em.vertices]
def group_of(p):
    g = ga.data[p.index].value; z = (M @ p.center).z
    if g == 10: return 'torso'
    if g == 12: return 'sleeves'
    if g in (11, 16): return 'skirt'
    if g == 13: return 'legs'
    if g == 14: return 'torso' if z > 0.66 else ('legs' if z < 0.13 else 'skirt')
    return None
groups = {}
for p in me.polygons:
    t = group_of(p)
    if t: groups.setdefault(t, []).append(p.index)
src_img = [n.image for n in bpy.data.materials['tripo_mat_2d0dc00d'].node_tree.nodes if n.type == 'TEX_IMAGE' and n.image][0]
ma = bpy.data.materials.new('SourceGuide'); ma.use_nodes = True; nt = ma.node_tree; nt.nodes.clear()
tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = src_img; uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'SourceUV'
e = nt.nodes.new('ShaderNodeEmission'); out = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(uvn.outputs[0], tx.inputs[0]); nt.links.new(tx.outputs[0], e.inputs[0]); nt.links.new(e.outputs[0], out.inputs[0])
for o in s.objects: o.hide_render = True
eng = [x.identifier for x in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
s.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in eng else 'BLENDER_EEVEE_NEXT'
s.render.resolution_x = s.render.resolution_y = 1254; s.render.film_transparent = False
w = s.world or bpy.data.worlds.new('W'); s.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.3, 0.32, 0.36, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 1
s.view_settings.view_transform = 'Standard'; s.view_settings.look = 'None'
cam = bpy.data.objects.new('GuideCam', bpy.data.cameras.new('GuideCam')); s.collection.objects.link(cam); s.camera = cam; cam.data.type = 'ORTHO'
srcuv = me.uv_layers.active.data
man = {}
for tag, fids in groups.items():
    vids = sorted({v for fi in fids for v in me.polygons[fi].vertices}); rev = {v: i for i, v in enumerate(vids)}
    mesh = bpy.data.meshes.new(tag); mesh.from_pydata([evco[v] for v in vids], [], [[rev[v] for v in me.polygons[fi].vertices] for fi in fids]); mesh.update()
    ob = bpy.data.objects.new('T_' + tag, mesh); s.collection.objects.link(ob)
    uv = mesh.uv_layers.new(name='SourceUV')
    for f, fi in zip(mesh.polygons, fids):
        for li, oli in zip(f.loop_indices, me.polygons[fi].loop_indices): uv.data[li].uv = srcuv[oli].uv
    mesh.materials.append(ma)
    pts = [v.co for v in mesh.vertices]; lo = Vector([min(v[a] for v in pts) for a in range(3)]); hi = Vector([max(v[a] for v in pts) for a in range(3)]); c = (lo + hi) / 2
    cam.data.ortho_scale = max(hi.z - lo.z, hi.y - lo.y) * 1.13
    ob.hide_render = False
    for ang, lab in ((0, 'front'), (math.pi, 'back')):
        cam.location = c + Vector((2 * math.cos(ang), 2 * math.sin(ang), 0)); cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
        s.render.filepath = R + f'reference/{tag}_{lab}_source.png'; bpy.ops.render.render(write_still=True)
    ob.hide_render = True
    # own packed UV for the Tripo upload
    cu = mesh.uv_layers.new(name='ComponentUV'); mesh.uv_layers.active = cu
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.context.scene.tool_settings.use_uv_select_sync = True
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action='SELECT'); bpy.ops.uv.average_islands_scale(); bpy.ops.uv.pack_islands(rotate=True, scale=True, margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')
    T = Matrix.Scale(1 / max(hi - lo), 4) @ Matrix.Rotation(-math.pi / 2, 4, 'Z') @ Matrix.Translation(-c)
    for v in mesh.vertices: v.co = T @ v.co
    mesh.uv_layers.remove(mesh.uv_layers['SourceUV']); mesh.materials.clear()
    gray = bpy.data.materials.new(tag + '_Input'); gray.diffuse_color = (.6, .6, .6, 1); mesh.materials.append(gray)
    bpy.ops.export_scene.gltf(filepath=R + f'input/{tag}.glb', use_selection=True, export_apply=True, export_animations=False, export_skins=False, export_morph=False, export_yup=True)
    man[tag] = dict(face_ids=fids, faces=len(fids), T=[list(r) for r in T])
json.dump(man, open(R + 'manifest.json', 'w'))
print('INFO', {k: v['faces'] for k, v in man.items()})
