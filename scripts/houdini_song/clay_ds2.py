# gray clay check of dancer 2 (Workbench, single gray, studio light, MMD outline solidify off); same framing as view_ds2.py
# usage: blender -b FILE -P [prev_ds2.py] -P clay_ds2.py -- OUT_PREFIX f1,f2  (env VIEW_DEG)
import bpy, sys, math
a = sys.argv[sys.argv.index('--')+1:]; out, frames = a[0], [int(x) for x in a[1].split(',')]
sc = bpy.context.scene
for o in bpy.data.collections['AiboSet'].all_objects if 'AiboSet' in bpy.data.collections else []: o.hide_render = True
for o in bpy.data.objects:
    if o.type == 'MESH' and not o.name.startswith('DS2_') and o.parent and o.parent.name == 'CharaKit_Weights_8cf2bc8c_Rig': o.hide_render = True
    if o.type == 'MESH':
        for m in o.modifiers:
            if m.type == 'SOLIDIFY' or 'edge' in m.name.lower() or 'outline' in m.name.lower(): m.show_render = False
    if o.name.startswith('Set_'): o.hide_render = True
for n in ('Skirt_Vellum','Acc_BB','Hair','Hair_Front','SkirtBow_BL','SkirtBow_BR','SkirtBow_FL','SkirtBow_FR'):
    if n in bpy.data.objects: bpy.data.objects[n].hide_render = True
sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading
sh.light = 'STUDIO'; sh.color_type = 'SINGLE'; sh.single_color = (0.6, 0.6, 0.6); sh.show_cavity = True; sh.cavity_type = 'WORLD'
sh.background_type = 'VIEWPORT' if hasattr(sh, 'background_type') else None
sc.world.color = (0.12, 0.12, 0.12) if sc.world else None; sc.render.film_transparent = False
rig = bpy.data.objects['DS2_Rig']
cd = bpy.data.cameras.new('C'); cd.lens = 50; cam = bpy.data.objects.new('C', cd); sc.collection.objects.link(cam); sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 700, 1000, 100; sc.render.use_compositing = False
A = math.radians(float(__import__('os').environ.get('VIEW_DEG', '0')))
for f in frames:
    sc.frame_set(f); h = rig.matrix_world @ rig.pose.bones['mixamorig:Hips'].head
    cam.location = (h.x + 1.1*math.cos(A), h.y + 1.1*math.sin(A), h.z - 0.05); cam.rotation_euler = (math.radians(90), 0, math.radians(90) + A)
    sc.render.filepath = f'{out}_{f}.png'; bpy.ops.render.render(write_still=True)
