# Iris material -> layered: base texture + crisp highlight layer (alpha-over), same UVs. Keeps alpha from base.
# Usage: blender -b IN.blend -P ds_iris_layers.py -- OUT.blend [parallax=0.0]
import bpy, sys, os
a = sys.argv[sys.argv.index('--')+1:]; OUT = a[0]; PAR = float(a[1]) if len(a) > 1 else 0.0
D = os.path.join(os.environ.get('EYE_LAYER_DIR', 'layered_v16'), '')   # output of iris_layers_v16.py
for side in 'LR':
    m = bpy.data.objects['Iris_' + side].data.materials[0]; nt = m.node_tree; L = nt.links.new
    tex = [n for n in nt.nodes if n.type == 'TEX_IMAGE'][0]
    old = tex.image
    tex.image = bpy.data.images.load(D + f'tex{side}_iris_base.png', check_existing=True)
    tex.image.alpha_mode = old.alpha_mode; tex.image.colorspace_settings.name = old.colorspace_settings.name
    for n in [n for n in nt.nodes if n.name.startswith('IrisHL')]: nt.nodes.remove(n)
    uvsrc = tex.inputs['Vector'].links[0].from_socket if tex.inputs['Vector'].links else None
    hl = nt.nodes.new('ShaderNodeTexImage'); hl.name = 'IrisHL_tex'; hl.interpolation = 'Cubic'
    hl.image = bpy.data.images.load(D + f'tex{side}_iris_hl.png', check_existing=True)
    hl.image.colorspace_settings.name = old.colorspace_settings.name; hl.extension = 'CLIP'
    hl.location = tex.location.x, tex.location.y - 320
    if uvsrc: L(uvsrc, hl.inputs['Vector'])
    if PAR:
        # optional: tiny view-dependent shift of the catch-light layer
        uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.name = 'IrisHL_uv'
        geo = nt.nodes.new('ShaderNodeNewGeometry'); geo.name = 'IrisHL_geo'
        vt = nt.nodes.new('ShaderNodeVectorTransform'); vt.name = 'IrisHL_vt'; vt.vector_type = 'NORMAL'; vt.convert_from = 'WORLD'; vt.convert_to = 'CAMERA'
        L(geo.outputs['Normal'], vt.inputs[0])
        sc = nt.nodes.new('ShaderNodeVectorMath'); sc.name = 'IrisHL_sc'; sc.operation = 'SCALE'; sc.inputs['Scale'].default_value = PAR; L(vt.outputs[0], sc.inputs[0])
        ad = nt.nodes.new('ShaderNodeVectorMath'); ad.name = 'IrisHL_add'; ad.operation = 'ADD'
        L(uvsrc if uvsrc else uvn.outputs['UV'], ad.inputs[0]); L(sc.outputs[0], ad.inputs[1]); L(ad.outputs[0], hl.inputs['Vector'])
    em = [n for n in nt.nodes if n.type == 'EMISSION'][0]
    src = em.inputs['Color'].links[0].from_socket
    mx = nt.nodes.new('ShaderNodeMix'); mx.name = 'IrisHL_mix'; mx.data_type = 'RGBA'
    L(hl.outputs['Alpha'], mx.inputs[0]); L(src, mx.inputs[6]); L(hl.outputs['Color'], mx.inputs[7])
    L(mx.outputs[2], em.inputs['Color'])
    print('iris', side, 'base', tex.image.name, 'hl', hl.image.name, 'emission src was', src.node.name)
bpy.context.scene.frame_set(0)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('saved')
