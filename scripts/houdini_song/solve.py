# Houdini Vellum skirt solve (hython). Adapted from the Codex/Claude aipai_vellum_v24 pipeline: one cone cloth layer,
# waist rows soft-pinned to the animated hips (matchanimation), animated real leg mesh + ground as colliders,
# warm-up holding the first dance pose. Blender (x,y,z) <-> Houdini (x,z,-y)*S.
# usage: hython solve.py DIR [warm]
import hou, numpy as np, json, time, sys
from pathlib import Path
P = Path(sys.argv[1]); warm = int(sys.argv[2]) if len(sys.argv) > 2 else 45; S = 1.7
OV = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
pat = json.loads((P / 'pattern_rest.json').read_text()); mot = np.load(P / 'motion.npz'); N = len(mot['frames'])
def to_h(b): b = np.asarray(b); return np.stack([b[..., 0], b[..., 2], -b[..., 1]], -1) * S
hou.hipFile.clear(suppress_save_prompt=True); hou.setFps(30); hou.playbar.setFrameRange(1, warm + N)
g = hou.node('/obj').createNode('geo', 'DeepSeek_Skirt', run_init_scripts=False)
geom = hou.Geometry(); pts = geom.createPoints(to_h(np.array(pat['vertices'])).tolist())
for f in pat['faces']:
    pr = geom.createPolygon()
    for i in f: pr.addVertex(pts[i])
grp = geom.createPointGroup('waist')
for i in pat['pin']: grp.add(pts[i])
src_path = P / 'skirt_rest.bgeo.sc'; geom.saveToFile(str(src_path))
src = g.createNode('file', 'skirt_source'); src.parm('file').set(src_path.as_posix())
anim = g.createNode('python', 'animated_waist'); anim.setInput(0, src)
anim.parm('python').set(f"""import hou, numpy as np
P='{P.as_posix()}'; S={S}; warm={warm}
m=np.load(P+'/motion.npz', mmap_mode='r'); N=m['hips'].shape[0]
f=max(0,min(N-1,int(hou.frame())-warm-1)); H=np.array(m['hips'][f])
g=hou.pwd().geometry(); a=np.array([q.position() for q in g.points()])
b=np.stack([a[:,0],-a[:,2],a[:,1]],1)/S; b=b@H[:3,:3].T+H[:3,3]; b=np.stack([b[:,0],b[:,2],-b[:,1]],1)*S
g.setPointFloatAttribValues('P', b.astype(np.float32).ravel().tolist())
""")
c = g.createNode('vellumconstraints', 'skirt_cloth'); c.setInput(0, anim)
for k, v in {'constrainttype': 'cloth', 'pingroup': 'waist', 'matchanimation': 1, 'domass': 'calcuniform', 'density': .2,
             'dothickness': 'on', 'thickness': .004, 'stretchstiffness': 1e8, 'bendstiffness': .04, 'stretchdampingratio': .05,
             'benddampingratio': .12, **OV.get('cloth', {})}.items():
    try: c.parm(k).set(v)
    except Exception as e: print('PARM', k, e)
legs = g.createNode('python', 'animated_legs')
legs.parm('python').set(f"""import hou, numpy as np, json
P='{P.as_posix()}'; S={S}; warm={warm}
m=np.load(P+'/motion.npz', mmap_mode='r'); N=m['legs'].shape[0]; f=max(0,min(N-1,int(hou.frame())-warm-1))
a=np.array(m['legs'][f]); a=np.stack([a[:,0],a[:,2],-a[:,1]],1)*S
g=hou.pwd().geometry(); pts=g.createPoints(a.tolist())
for face in json.load(open(P+'/faces.json'))['legs']:
    q=g.createPolygon()
    for i in face: q.addVertex(pts[i])
""")
floor = g.createNode('python', 'ground'); floor.parm('python').set("import hou\ng=hou.pwd().geometry();p=g.createPoints([(-5,0.0,-5),(-5,0.0,5),(5,0.0,5),(5,0.0,-5)]);f=g.createPolygon()\nfor q in p:f.addVertex(q)")
col = g.createNode('merge', 'colliders'); col.setInput(0, legs); col.setInput(1, floor)
solver = g.createNode('vellumsolver', 'skirt_solve'); solver.setInput(0, c, 0); solver.setInput(1, c, 1); solver.setInput(2, col)
for k, v in {'substeps': 8, 'niter': 200, 'collisionsiter': 15, 'postcollisioniter': 10, **OV.get('solver', {})}.items():
    try: solver.parm(k).set(v)
    except Exception as e: print('PARM', k, e)
solver.setDisplayFlag(True); g.layoutChildren(); hou.hipFile.save(str(P / 'DeepSeek_Skirt_Vellum.hiplc'))
pin = np.array(pat['pin']); res = []; t0 = time.time(); stats = []
for f in range(1, warm + N + 1):
    hou.setFrame(f); geo = solver.geometry()
    if geo is None or solver.errors(): raise RuntimeError(solver.errors())
    vv = np.array(geo.pointFloatAttribValues('P'), np.float32).reshape(-1, 3); assert np.isfinite(vv).all()
    tgt = np.array(anim.geometry().pointFloatAttribValues('P'), np.float32).reshape(-1, 3)
    res.append(vv); stats.append({'frame': f, 'pin_err': float(np.linalg.norm(vv[pin] - tgt[pin], axis=1).max())})
    if f % 30 == 0: print('SOLVE', f, 'of', warm + N, 's', round(time.time() - t0, 1), 'pin_err', round(stats[-1]['pin_err'], 4), flush=True)
R = np.array(res); B = np.stack([R[..., 0], -R[..., 2], R[..., 1]], -1) / S          # back to Blender coords
np.save(P / 'cloth.npy', B[warm:].astype(np.float32))
(P / 'simulation_report.json').write_text(json.dumps({'frames': N, 'warm': warm, 'points': int(R.shape[1]), 'seconds': time.time() - t0, 'stats': stats}, indent=1))
print('DONE', B.shape, flush=True)
