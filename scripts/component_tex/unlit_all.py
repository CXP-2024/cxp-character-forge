import bpy, sys
# Make every mesh material unlit: Image Texture (its own UV) -> Emission -> Output. MToon disabled. No lighting/shading at all.
out = sys.argv[sys.argv.index('--') + 1]
done = []
mats = {m for o in bpy.data.objects if o.type == 'MESH' for m in o.data.materials if m}
for m in mats:
    if not m.use_nodes: continue
    nt = m.node_tree
    tex = [n for n in nt.nodes if n.type == 'TEX_IMAGE' and n.image and n.image.size[0] > 8]
    if not tex: continue
    # prefer the texture feeding a Principled Base Color, otherwise the largest image
    pick = None
    for n in nt.nodes:
        if n.type == 'BSDF_PRINCIPLED' and n.inputs['Base Color'].links:
            src = n.inputs['Base Color'].links[0].from_node
            if src.type == 'TEX_IMAGE' and src.image: pick = src
    pick = pick or max(tex, key=lambda n: n.image.size[0] * n.image.size[1])
    img = pick.image
    uvname = None
    if pick.inputs['Vector'].links and pick.inputs['Vector'].links[0].from_node.type == 'UVMAP':
        uvname = pick.inputs['Vector'].links[0].from_node.uv_map
    try: m.vrm_addon_extension.mtoon1.enabled = False
    except Exception: pass
    nt.nodes.clear()
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img; t.location = (-400, 0)
    if uvname:
        u = nt.nodes.new('ShaderNodeUVMap'); u.uv_map = uvname; u.location = (-650, 0); nt.links.new(u.outputs[0], t.inputs[0])
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Strength'].default_value = 1.0
    o = nt.nodes.new('ShaderNodeOutputMaterial'); o.location = (250, 0)
    nt.links.new(t.outputs['Color'], e.inputs['Color']); nt.links.new(e.outputs['Emission'], o.inputs['Surface'])
    m.use_backface_culling = False
    done.append((m.name, img.name))
s = bpy.context.scene
s.view_settings.view_transform = 'Standard'; s.view_settings.look = 'None'; s.view_settings.exposure = 0; s.view_settings.gamma = 1
bpy.ops.wm.save_as_mainfile(filepath=out)
print('INFO', done)
