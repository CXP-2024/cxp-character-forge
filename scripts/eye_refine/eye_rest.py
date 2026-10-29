# Rest/reset-pose single-eye close-up, same rule for MMD (奥黛塔/沃雅妮莎) and DeepSeek.
import bpy, sys, math
from mathutils import Vector
a = sys.argv[sys.argv.index('--')+1:]; out = a[0]; K = float(a[1]) if len(a) > 1 else 3.0
sc = bpy.context.scene
arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
mmd = [o for o in arms if '頭' in o.pose.bones]
if mmd:
    rig = mmd[0]; rig.data.pose_position = 'REST'
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.data.shape_keys:
            o.data.shape_keys.animation_data_clear()
            for kb in o.data.shape_keys.key_blocks[1:]: kb.value = 0
    sc.frame_set(0); E, H = ('目.R', '目.L'), '頭'
else:
    rig = bpy.data.objects['CharaKit_Weights_8cf2bc8c_Rig']; sc.frame_set(0); E, H = ('RightEye', 'LeftEye'), 'mixamorig:Head'
    if 'DS2Char' in bpy.data.collections:
        for o in bpy.data.collections['DS2Char'].objects: o.hide_render = True
bpy.context.view_layer.update()
pb = rig.pose.bones; W = lambda n: rig.matrix_world @ pb[n].head
e0, e1, hd = W(E[0]), W(E[1]), W(H)
if len(a) > 2 and a[2] == 'other': e0, e1 = e1, e0
ipd = (e0 - e1).length; mid = (e0 + e1) / 2; side = (e1 - e0).normalized()
up = (rig.matrix_world.to_3x3() @ (pb[H].matrix.to_3x3() @ Vector((0, 1, 0)))).normalized()
fwd = side.cross(up).normalized()
if fwd.dot(mid - hd) < 0: fwd = -fwd
cd = bpy.data.cameras.new('EyeCam'); cd.lens = 85; cd.sensor_fit = 'VERTICAL'; cd.sensor_height = 24; cd.clip_start = 0.003; cd.dof.use_dof = False
cam = bpy.data.objects.new('EyeCam', cd); sc.collection.objects.link(cam)
cam.location = e0 + fwd * (K * ipd); cam.rotation_euler = (-fwd).to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1600, 1000, 100
sc.render.filepath = out; bpy.ops.render.render(write_still=True)
print('EYE', 'ipd', round(ipd, 4), 'fwd', [round(x, 2) for x in fwd])
