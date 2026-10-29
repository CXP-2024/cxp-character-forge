# Point both dancers' skirt/bow caches to the full-song MDDs; dancer 1 hair: 1801-frame skinned MDD -> armature skinning
# (checked against the old cache on 0-1800).  Usage: blender -b IN.blend -P ds_attach_song.py -- OUT.blend DIR1 DIR2
import bpy, sys, numpy as np, struct
a = sys.argv[sys.argv.index('--')+1:]; OUT, D1, D2 = a[0], a[1].rstrip('/'), a[2].rstrip('/')
sc = bpy.context.scene; rig = bpy.data.objects['CharaKit_Weights_8cf2bc8c_Rig']
for pre, D in (('', D1), ('DS2_', D2)):
    for n, f in (('Skirt_Vellum', 'skirt_f0rest.mdd'), ('Acc_BB', 'Acc_BB_f0rest.mdd'), ('SkirtBow_BL', 'SkirtBow_BL_f0rest.mdd'),
                 ('SkirtBow_BR', 'SkirtBow_BR_f0rest.mdd'), ('SkirtBow_FL', 'SkirtBow_FL_f0rest.mdd'), ('SkirtBow_FR', 'SkirtBow_FR_f0rest.mdd')):
        o = bpy.data.objects[pre + n]; m = [x for x in o.modifiers if x.type == 'MESH_CACHE'][0]; m.filepath = D + '/' + f
        print('cache', o.name, '->', m.filepath)
# dancer 1 hair: compare cache vs armature at a few frames, then switch
def rd(p):
    d = open(p, 'rb').read(); n, v = struct.unpack('>2i', d[:8]); return np.frombuffer(d[8+4*n:], '>f4').reshape(n, v, 3)
for n in ('Hair', 'Hair_Front'):
    o = bpy.data.objects[n]; mc = [x for x in o.modifiers if x.type == 'MESH_CACHE'][0]; cache = rd(bpy.path.abspath(mc.filepath))
    mc.show_viewport = mc.show_render = False
    am = o.modifiers.new('Armature', 'ARMATURE'); am.object = rig; o.modifiers.move(o.modifiers.find(am.name), 0)
    errs = []
    for f in (1, 300, 900, 1500, 1800):
        sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get(); ev = o.evaluated_get(dg); me = ev.to_mesh()
        v = np.array([x.co[:] for x in me.vertices]); ev.to_mesh_clear()
        mw = np.array(o.matrix_world); v = v @ mw[:3, :3].T + mw[:3, 3]
        # solidify outline adds no verts in eval mesh? compare first len(cache) verts
        errs.append(float(np.linalg.norm(v[:cache.shape[1]] - cache[f], axis=1).max() * 1000))
    print('hair', n, 'armature vs old cache max mm per frame', [round(e, 2) for e in errs])
    if max(errs) < 2.0:
        o.modifiers.remove(mc); print('  switched to armature')
    else:
        o.modifiers.remove(am); mc.show_viewport = mc.show_render = True; print('  KEPT cache (mismatch)')
sc.frame_set(0)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('saved', OUT)
