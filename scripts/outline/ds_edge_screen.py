# Keep the native MMD outline at a constant on-screen width (as MMD does), matched to a reference frame (937 by default).
# Blender's mmd_edge_preview Solidify thickness is in world units, so close-ups (e.g. 527, head 0.57 m from the camera)
# get thick, heavy lines. Screen width ~ thickness * lens / distance, so every outline modifier gets a driver
#   thickness = T0 * (d / dREF) * (lensREF / lens), clamped to [MINF, MAXF] x T0
# with d = camera-to-head distance of that dancer (DS2_* objects follow DS2_Rig, the rest the first rig).
# Usage: blender -b IN.blend -P ds_edge_screen.py -- OUT.blend [REF_FRAME=937] [MINF=0.2] [MAXF=3]
import bpy, sys
a = sys.argv[sys.argv.index('--') + 1:]; OUT = a[0]
REF = int(a[1]) if len(a) > 1 else 937; MINF = float(a[2]) if len(a) > 2 else 0.2; MAXF = float(a[3]) if len(a) > 3 else 3.0
sc = bpy.context.scene; cam = sc.camera
RIGS = {'DS1': bpy.data.objects['CharaKit_Weights_8cf2bc8c_Rig'], 'DS2': bpy.data.objects['DS2_Rig']}
HEAD = 'mixamorig:Head'
sc.frame_set(REF)
ref = {k: ((r.matrix_world @ r.pose.bones[HEAD].head) - cam.matrix_world.translation).length for k, r in RIGS.items()}
lens_ref = cam.data.lens
print('reference frame', REF, 'distance', {k: round(v, 3) for k, v in ref.items()}, 'lens', round(lens_ref, 2))
n = 0
for o in bpy.data.objects:
    for m in getattr(o, 'modifiers', []):
        if m.type != 'SOLIDIFY' or 'edge' not in m.name: continue
        who = 'DS2' if o.name.startswith('DS2_') else 'DS1'
        t0 = m.thickness; o[f'edge_t0_{m.name}'] = t0
        m.driver_remove('thickness'); fc = m.driver_add('thickness'); dv = fc.driver; dv.type = 'SCRIPTED'
        v = dv.variables.new(); v.name = 'd'; v.type = 'LOC_DIFF'
        v.targets[0].id = cam; v.targets[1].id = RIGS[who]; v.targets[1].bone_target = HEAD
        l = dv.variables.new(); l.name = 'lens'; l.type = 'SINGLE_PROP'; l.targets[0].id_type = 'CAMERA'; l.targets[0].id = cam.data; l.targets[0].data_path = 'lens'
        k = t0 * lens_ref / ref[who]
        dv.expression = f'{t0:.6f}*min({MAXF},max({MINF},({k / t0:.6f})*d/lens))'
        n += 1
print('outline drivers', n)
sc.frame_set(0)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('saved', OUT)
