# Vellum solve on the REAL multi-layer skirt mesh (apron, navy panels, underskirt, frills) instead of the cone proxy.
# - waist band (binding blend>=1) and tiny detached parts are hard-pinned to the skinned skirt (matchanimation);
# - the waist blend zone (0<blend<1) is soft-pinned so the layers hang from the waist like the design;
# - layers collide with each other (self collision) and with the legs + ground;
# - warm-up starts from the REST pose (T-pose: legs and skirt clear of each other) and moves to the first segment
#   frame, so the cloth never starts trapped inside a leg.  Blender (x,y,z) <-> Houdini (x,z,-y)*S.
# v2: + inter-layer glue (rest-length distance links between points that are close in space but far apart along the
#   mesh, i.e. stacked layers) so the underskirt cannot peel off the navy panels; leg collision friction off (self friction kept) so cloth slides
#   off a thigh instead of sticking to it; tiny detached strips follow the nearest cloth rigidly in the output.
#   optional 'goal' (soft pin of all free points to the skinned design shape) + higher bend keep the petticoat volume.
#   glue pairs come from glue_pairs.py (run with normal python: hython has no scipy).
# usage: hython solve_real2.py DIR warm SEG0 SEG1 OUT.npy [json overrides]
import hou, numpy as np, json, time, sys
from pathlib import Path
P = Path(sys.argv[1]); warm = int(sys.argv[2]); SEG0, SEG1, OUT = int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
OV = json.loads(sys.argv[6]) if len(sys.argv) > 6 else {}; S = 1.7; N = SEG1 - SEG0 + 1; HOLD = 15
rest = np.load(P / 'rest.npz'); V = rest['skirt']; fc = json.loads((P / 'faces.json').read_text())
blend = np.load(P / 'binding.npz')['blend']
tris = np.array([[q[0], q[k], q[k + 1]] for q in fc['skirt'] for k in range(1, len(q) - 1)])
# tiny detached components (bow fins etc.) -> hard pin
import collections
par = list(range(len(V)))
def find(a):
    while par[a] != a: par[a] = par[par[a]]; a = par[a]
    return a
for t in tris:
    for a, b in ((t[0], t[1]), (t[1], t[2])): par[find(a)] = find(b)
roots = collections.Counter(find(i) for i in range(len(V)))
small = np.array([roots[find(i)] < 200 for i in range(len(V))])
GL = OV.get('glue', {}); pairs = np.load(GL.get('pairs', str(P / '_glue_pairs.npy'))); print('glue links', len(pairs), flush=True)
hard = (blend >= 1) | small; soft = (blend > 0) & (blend < 1) & ~hard
print('points', len(V), 'hard', int(hard.sum()), 'soft', int(soft.sum()), 'free', int((~hard & ~soft).sum()), flush=True)
def to_h(b): b = np.asarray(b, np.float64); return np.stack([b[..., 0], b[..., 2], -b[..., 1]], -1) * S
np.save(P / '_real_hard.npy', np.nonzero(hard)[0]); np.save(P / '_real_soft.npy', np.nonzero(soft)[0])
hou.hipFile.clear(suppress_save_prompt=True); hou.setFps(30); hou.playbar.setFrameRange(1, warm + N)
g = hou.node('/obj').createNode('geo', 'DeepSeek_RealSkirt', run_init_scripts=False)
geom = hou.Geometry(); pts = geom.createPoints(to_h(V).tolist())
for t in tris:
    pr = geom.createPolygon()
    for i in t: pr.addVertex(pts[int(i)])
tg = geom.createPrimGroup('tris')
for pr in geom.prims(): tg.add(pr)
glg = geom.createPrimGroup('glue')
for a, b in pairs:
    pl = geom.createPolygon(is_closed=False); pl.addVertex(pts[int(a)]); pl.addVertex(pts[int(b)]); glg.add(pl)
gh = geom.createPointGroup('hardpin'); gs = geom.createPointGroup('softpin')
for i in np.nonzero(hard)[0]: gh.add(pts[int(i)])
for i in np.nonzero(soft)[0]: gs.add(pts[int(i)])
gf = geom.createPointGroup('freept')
for i in np.nonzero(~hard & ~soft)[0]: gf.add(pts[int(i)])
src_path = P / 'skirt_real_rest.bgeo.sc'; geom.saveToFile(str(src_path))
src = g.createNode('file', 'skirt_source'); src.parm('file').set(src_path.as_posix())
# animated target = skinned skirt; during warm-up: rest -> SEG0 (smoothstep), then hold
FRAMEFN = f"""
def fr():
    import hou
    k = int(hou.frame()); w = {warm}; h = {HOLD}
    if k <= w - h:
        u = (k - 1) / max(w - h - 1, 1); u = u * u * (3 - 2 * u); return None, u
    if k <= w: return None, 1.0
    return {SEG0} + min({N} - 1, k - w - 1), None
"""
anim = g.createNode('python', 'skinned_target'); anim.setInput(0, src)
anim.parm('python').set(FRAMEFN + f"""
import numpy as np
P='{P.as_posix()}'; S={S}
m=np.load(P+'/motion.npz', mmap_mode='r'); r=np.load(P+'/rest.npz')['skirt']
f,u=fr()
b=np.array(m['skirt'][f]) if f is not None else r*(1-u)+np.array(m['skirt'][{SEG0}])*u
b=np.stack([b[:,0],b[:,2],-b[:,1]],1)*S
hou.pwd().geometry().setPointFloatAttribValues('P', b.astype(np.float32).ravel().tolist())
""")
cl = g.createNode('vellumconstraints', 'cloth'); cl.setInput(0, anim)
for k, v in {'constrainttype': 'cloth', 'group': 'tris', 'grouptype': 'prims', 'domass': 'calcuniform', 'density': .2, 'dothickness': 'on', 'thickness': .0025,
             'stretchstiffness': 1e8, 'bendstiffness': .02, 'stretchdampingratio': .05, 'benddampingratio': .1, **OV.get('cloth', {})}.items():
    try: cl.parm(k).set(v)
    except Exception as e: print('PARM cloth', k, e)
gc = g.createNode('vellumconstraints', 'layer_glue'); gc.setInput(0, cl, 0); gc.setInput(1, cl, 1)
for k, v in {'constrainttype': 'distance', 'group': 'glue', 'grouptype': 'prims', 'stretchstiffness': GL.get('stiff', 50.0),
             'stretchstiffnessexp': 0, 'stretchdampingratio': .1, 'dothickness': 'off'}.items():
    try: gc.parm(k).set(v)
    except Exception as e: print('PARM glue', k, e)
ph = g.createNode('vellumconstraints', 'pin_hard'); ph.setInput(0, gc, 0); ph.setInput(1, gc, 1)
for k, v in {'constrainttype': 'pin', 'group': 'hardpin', 'grouptype': 'points', 'pintype': 'hard', 'matchanimation': 1}.items():
    try: ph.parm(k).set(v)
    except Exception as e: print('PARM pinh', k, e)
ps = g.createNode('vellumconstraints', 'pin_soft'); ps.setInput(0, ph, 0); ps.setInput(1, ph, 1)
for k, v in {'constrainttype': 'pin', 'group': 'softpin', 'grouptype': 'points', 'pintype': 'soft', 'matchanimation': 1,
             'pinrotation': 'none', 'stretchstiffness': OV.get('softpin', 40.0), 'stretchstiffnessexp': 0}.items():
    try: ps.parm(k).set(v)
    except Exception as e: print('PARM pins', k, e)
last = ps
if OV.get('goal', 0) > 0:                      # petticoat volume: weak pull of free points toward the designed (skinned) shape
    pg = g.createNode('vellumconstraints', 'pin_goal'); pg.setInput(0, ps, 0); pg.setInput(1, ps, 1); last = pg
    for k, v in {'constrainttype': 'pin', 'group': 'freept', 'grouptype': 'points', 'pintype': 'soft', 'matchanimation': 1,
                 'pinrotation': 'none', 'stretchstiffness': OV['goal'], 'stretchstiffnessexp': 0}.items():
        try: pg.parm(k).set(v)
        except Exception as e: print('PARM goal', k, e)
legs = g.createNode('python', 'legs')
legs.parm('python').set(FRAMEFN + f"""
import numpy as np, json
P='{P.as_posix()}'; S={S}
m=np.load(P+'/motion.npz', mmap_mode='r'); r=np.load(P+'/rest.npz')['legs']
def L(k):
    f,u=fr() if k is None else (k,None)
    a=np.array(m['legs'][f]) if f is not None else r*(1-u)+np.array(m['legs'][{SEG0}])*u
    return np.stack([a[:,0],a[:,2],-a[:,1]],1)*S
a=L(None); k=int(hou.frame())
prev=L(None) if k<=1 else None
hou.setFrame(k-1) if False else None
g=hou.pwd().geometry(); pts=g.createPoints(a.tolist())
for face in json.load(open(P+'/faces.json'))['legs']:
    q=g.createPolygon()
    for i in face: q.addVertex(pts[i])
""")
floor = g.createNode('python', 'ground'); floor.parm('python').set("import hou\ng=hou.pwd().geometry();p=g.createPoints([(-5,0.0,-5),(-5,0.0,5),(5,0.0,5),(5,0.0,-5)]);f=g.createPolygon()\nfor q in p:f.addVertex(q)")
vel = g.createNode('trail', 'leg_vel'); vel.setInput(0, legs)
try: vel.parm('result').set(3)       # compute velocity
except Exception as e: print('PARM trail', e)
col = g.createNode('merge', 'colliders'); col.setInput(0, vel); col.setInput(1, floor)
solver = g.createNode('vellumsolver', 'solve'); solver.setInput(0, last, 0); solver.setInput(1, last, 1); solver.setInput(2, col)
for k, v in {'friction': OV.get('friction', 0), 'substeps': 10, 'niter': 150, 'collisionsiter': 25, 'postcollisioniter': 15, 'doselfcollisions': 1, **OV.get('solver', {})}.items():
    try: solver.parm(k).set(v)
    except Exception as e: print('PARM solver', k, e)
solver.setDisplayFlag(True); g.layoutChildren(); hou.hipFile.save(str(P / 'DeepSeek_RealSkirt.hiplc'))
res = []; t0 = time.time()
for f in range(1, warm + N + 1):
    hou.setFrame(f); geo = solver.geometry()
    if geo is None or solver.errors(): raise RuntimeError(solver.errors())
    vv = np.array(geo.pointFloatAttribValues('P'), np.float32).reshape(-1, 3); assert np.isfinite(vv).all()
    res.append(vv)
    if f % 20 == 0: print('SOLVE', f, 'of', warm + N, 's', round(time.time() - t0, 1), flush=True)
R = np.array(res); B = np.stack([R[..., 0], -R[..., 2], R[..., 1]], -1) / S
B = B[warm:]
# tiny detached strips: rigid-follow (Kabsch) the 12 nearest cloth points in rest space
cr = np.nonzero(~small)[0]
for root in set(find(i) for i in np.nonzero(small)[0]):
    m = np.array([find(i) == root for i in range(len(V))]); nn = cr[np.argsort(np.linalg.norm(V[cr] - V[m].mean(0), axis=1))[:12]]
    a0 = V[nn] - V[nn].mean(0); s0 = V[m] - V[nn].mean(0)
    for f in range(len(B)):
        b = B[f, nn]; bc = b.mean(0); U, _, Wt = np.linalg.svd(a0.T @ (b - bc)); d = np.sign(np.linalg.det(U @ Wt))
        Rm = U @ np.diag([1, 1, d]) @ Wt; B[f, m] = s0 @ Rm + bc
np.save(OUT, B.astype(np.float32)); print('DONE', B.shape, round(time.time() - t0, 1), flush=True)
