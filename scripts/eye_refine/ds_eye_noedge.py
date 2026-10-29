# Remove the native MMD outline (mmd_edge_preview solidify shell) from the moving eye area of both dancers.
# Closing lids fold the skin; the thin inverted-hull shell then shows as jagged dark lines along the lids (seen at 2609).
# Vertices moved by any eye/brow shape key (QC_*, AP_jito, EA_* eye keys) plus RING edge-rings around them get edge
# weight 0; the face silhouette and the rest of the outline keep their weights.
# Usage: blender -b IN.blend -P ds_eye_noedge.py -- OUT.blend [RING=2]
import bpy, sys, numpy as np
a = sys.argv[sys.argv.index('--') + 1:]; OUT = a[0]; RING = int(a[1]) if len(a) > 1 else 2
EYE = lambda n: n.startswith('QC_') or n in ('AP_jito',) or (n.startswith('EA_') and ('eye' in n or 'blink' in n or 'brow' in n))
for name in ('Body', 'DS2_Body'):
    o = bpy.data.objects[name]; me = o.data; n = len(me.vertices); key = me.shape_keys
    base = np.zeros(n * 3); key.key_blocks[0].data.foreach_get('co', base); base = base.reshape(-1, 3)
    sel = np.zeros(n, bool)
    for kb in key.key_blocks[1:]:
        if EYE(kb.name):
            c = np.zeros(n * 3); kb.data.foreach_get('co', c); sel |= np.linalg.norm(c.reshape(-1, 3) - base, axis=1) > 1e-5
    ev = np.zeros(len(me.edges) * 2, int); me.edges.foreach_get('vertices', ev); ev = ev.reshape(-1, 2)
    for _ in range(RING):
        grow = sel.copy(); grow[ev[sel[ev[:, 0]], 1]] = True; grow[ev[sel[ev[:, 1]], 0]] = True; sel = grow
    vg = o.vertex_groups['mmd_edge_preview']; vg.add(np.nonzero(sel)[0].tolist(), 0.0, 'REPLACE')
    print(name, 'edge weight 0 on', int(sel.sum()), 'eye-area verts')
bpy.context.scene.frame_set(0)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('saved', OUT)
