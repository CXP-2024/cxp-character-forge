# v17 iris glow/sparkle on top of the v16 layered iris (both dancers share Iris_L/Iris_R materials):
#   sparkle layer (rim + facets) alpha-over, 奥黛塔's sp2_6 glitter sphere (ADD) + Eye_s glass sphere (ADD),
#   emission strength boost so bloom picks up the bright parts.
# Usage: blender -b IN.blend -P ds_iris_glow.py -- OUT.blend [glitter=0.45] [glass=0.35] [emit=1.15]
import bpy, sys, os
a = sys.argv[sys.argv.index('--')+1:]; OUT = a[0]
GL = float(a[1]) if len(a) > 1 else 0.45; GS = float(a[2]) if len(a) > 2 else 0.35; EM = float(a[3]) if len(a) > 3 else 1.15
D = os.path.join(os.environ.get('EYE_LAYER_DIR', 'layered_v16'), '')   # output of iris_layers_v16.py
OD = os.path.join(os.environ.get('REF_PMX_DIR', ''), '')   # MMD model folder that provides tex/sp2_6.png and spa/Eye_s.png (not bundled)
for side in 'LR':
    m = bpy.data.objects['Iris_' + side].data.materials[0]; nt = m.node_tree; L = nt.links.new
    for n in [n for n in nt.nodes if n.name.startswith('IrisGlow')]: nt.nodes.remove(n)
    N = lambda t, nm: (lambda n: (setattr(n, 'name', 'IrisGlow_' + nm), n)[1])(nt.nodes.new(t))
    em = [n for n in nt.nodes if n.type == 'EMISSION'][0]
    hlmix = nt.nodes['IrisHL_mix']; hltex = nt.nodes['IrisHL_tex']
    uvsrc = hltex.inputs['Vector'].links[0].from_socket if hltex.inputs['Vector'].links else None
    # sparkle layer
    sp = N('ShaderNodeTexImage', 'spark'); sp.image = bpy.data.images.load(D + f'tex{side}_iris_spark.png', check_existing=True)
    sp.image.colorspace_settings.name = hltex.image.colorspace_settings.name; sp.interpolation = 'Cubic'; sp.extension = 'CLIP'
    if uvsrc: L(uvsrc, sp.inputs['Vector'])
    mx = N('ShaderNodeMix', 'sparkmix'); mx.data_type = 'RGBA'
    L(sp.outputs['Alpha'], mx.inputs[0]); L(hlmix.outputs[2], mx.inputs[6]); L(sp.outputs['Color'], mx.inputs[7])
    # view-normal matcap coords
    geo = N('ShaderNodeNewGeometry', 'geo'); vt = N('ShaderNodeVectorTransform', 'vt')
    vt.vector_type = 'NORMAL'; vt.convert_from = 'WORLD'; vt.convert_to = 'CAMERA'; L(geo.outputs['Normal'], vt.inputs[0])
    mp = N('ShaderNodeMapping', 'map'); mp.inputs['Scale'].default_value = (0.5, 0.5, 1); mp.inputs['Location'].default_value = (0.5, 0.5, 0)
    L(vt.outputs[0], mp.inputs[0])
    cur = mx.outputs[2]
    for nm, img, k in (('glitter', OD + 'tex/sp2_6.png', GL), ('glass', OD + 'spa/Eye_s.png', GS)):
        t = N('ShaderNodeTexImage', nm); t.image = bpy.data.images.load(img, check_existing=True); t.extension = 'EXTEND'
        L(mp.outputs[0], t.inputs[0])
        ad = N('ShaderNodeMix', nm + 'add'); ad.data_type = 'RGBA'; ad.blend_type = 'ADD'; ad.inputs[0].default_value = k
        L(cur, ad.inputs[6]); L(t.outputs['Color'], ad.inputs[7]); cur = ad.outputs[2]
    L(cur, em.inputs['Color'])
    em.inputs['Strength'].default_value = EM
    print('iris glow', side)
bpy.context.scene.frame_set(0)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('saved')
