# Upper-eyelid shadow on DeepSeek eye whites (like 奥黛塔/沃雅妮莎): per-vertex attribute 'lid_shadow'
# measured from the visible upper lid line (rest pose, rays toward the face front), then darkens the white.
# Usage: blender -b IN.blend -P ds_lidshadow.py -- OUT.blend [band=0.38] [soft=0.10] [r,g,b]
import bpy, sys, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index('--')+1:]
OUT = a[0]; BAND = float(a[1]) if len(a) > 1 else 0.38; SOFT = float(a[2]) if len(a) > 2 else 0.10
BAND2 = float(a[4]) if len(a) > 4 else BAND * 1.8; TAIL = float(a[5]) if len(a) > 5 else 0.45
COL = tuple(float(x) for x in a[3].split(',')) if len(a) > 3 else (0.55, 0.55, 0.65)
rig = bpy.data.objects['CharaKit_Weights_8cf2bc8c_Rig']; bpy.context.scene.frame_set(0); bb = rig.pose.bones
UP = (rig.matrix_world.to_3x3() @ (bb['mixamorig:Head'].matrix.to_3x3() @ Vector((0, 1, 0)))).normalized()
SIDE = (bb['LeftEye'].head - bb['RightEye'].head).normalized()
FWD = SIDE.cross(UP).normalized()
if FWD.x < 0: FWD = -FWD
UP = FWD.cross(SIDE).normalized()                # orthonormal view frame (same as eye_rest camera)
print('VIEW fwd', [round(x, 3) for x in FWD], 'up', [round(x, 3) for x in UP])
# use the posed frame-0 geometry and rays toward the front camera position, so the lid line matches the render
sc = bpy.context.scene; sc.frame_set(0); dg = bpy.context.evaluated_depsgraph_get()
def evald(name):
    o = bpy.data.objects[name].evaluated_get(dg); me = o.to_mesh(); mw = o.matrix_world
    V = [mw @ v.co for v in me.vertices]; F = [p.vertices[:] for p in me.polygons]; o.to_mesh_clear(); return V, F
BV, BF = evald('Body'); occ = BVHTree.FromPolygons(BV, BF)
pb = rig.pose.bones; eL = rig.matrix_world @ pb['LeftEye'].head; eR = rig.matrix_world @ pb['RightEye'].head
IPD = (eL - eR).length
for side in ('L', 'R'):
    o = bpy.data.objects['EyeWhite_' + side]; me = o.data
    PV, _ = evald('EyeWhite_' + side); P = np.array([v[:] for v in PV])
    camp = (eL if side == 'L' else eR) + FWD * (3.0 * IPD)
    vis = np.zeros(len(P), bool)
    for i, p in enumerate(P):
        d = camp - Vector(p); L = d.length; d.normalize()
        hit = occ.ray_cast(Vector(p) + d * 1e-4, d, L)
        vis[i] = hit[0] is None
    y, z = P @ np.array(SIDE), P @ np.array(UP)
    bins = np.linspace(y.min(), y.max(), 41); idx = np.clip(np.digitize(y, bins) - 1, 0, 39)
    top = np.full(40, np.nan); bot = np.full(40, np.nan)
    for b in range(40):
        m = vis & (idx == b)
        if m.sum() >= 2: top[b] = z[m].max(); bot[b] = z[m].min()
    ok = ~np.isnan(top); xs = np.arange(40)
    top = np.interp(xs, xs[ok], top[ok]); bot = np.interp(xs, xs[ok], bot[ok])
    # smooth the lid line a little
    k = np.array([1, 1, 1]) / 3; top = np.convolve(np.pad(top, 1, mode='edge'), k, 'valid'); bot = np.convolve(np.pad(bot, 1, mode='edge'), k, 'valid')
    cy = (y - bins[0]) / (bins[1] - bins[0]) - 0.5
    tz = np.interp(cy, xs, top); bz = np.interp(cy, xs, bot)
    h = np.maximum(tz - bz, 1e-4)
    H0 = float(np.median((top - bot)[ok]))   # constant thickness => boundary runs parallel to the lid curve
    # perpendicular distance to the upper-lid polyline (so the band hugs the lid even where it slopes steeply)
    cx = bins[:-1] + (bins[1] - bins[0]) / 2
    LP = np.c_[np.linspace(cx[0], cx[-1], 400), np.interp(np.linspace(cx[0], cx[-1], 400), cx, top)]
    Q = np.c_[y, z]
    dist = np.sqrt(((Q[:, None, :] - LP[None, :, :]) ** 2).sum(-1)).min(1)
    t = np.where(z > tz, -1.0, dist / H0)
    def ss(e0, e1, x):
        u = np.clip((x - e0) / (e1 - e0), 0, 1); return u * u * (3 - 2 * u)
    # two-tone: core shadow near the lid, then a lighter tail that fades out (TAIL = relative strength)
    s = (1 - TAIL) * (1 - ss(BAND - SOFT, BAND + SOFT, t)) + TAIL * (1 - ss(BAND, BAND2, t))
    s[t < 0] = 1.0
    at = me.attributes.get('lid_shadow') or me.attributes.new('lid_shadow', 'FLOAT', 'POINT')
    at.data.foreach_set('value', s.astype(np.float32))
    print('EYEWHITE', side, 'visible', int(vis.sum()), 'of', len(P), 'opening mm', round(float(np.median(h[vis])) * 1000, 1))
    m = me.materials[0]; nt = m.node_tree
    for nd in [n for n in nt.nodes if n.name.startswith('Lid')]: nt.nodes.remove(nd)
    em = [n for n in nt.nodes if n.type == 'EMISSION'][0]; src = em.inputs['Color'].links[0].from_socket
    an = nt.nodes.new('ShaderNodeAttribute'); an.name = 'LidAttr'; an.attribute_name = 'lid_shadow'; an.attribute_type = 'GEOMETRY'
    mx = nt.nodes.new('ShaderNodeMix'); mx.name = 'LidMix'; mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'
    nt.links.new(an.outputs['Fac'], mx.inputs[0]); nt.links.new(src, mx.inputs[6]); mx.inputs[7].default_value = (*COL, 1)
    nt.links.new(mx.outputs[2], em.inputs['Color'])
bpy.context.scene.frame_set(0)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('saved')
