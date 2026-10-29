# Extend both DeepSeek dancers' actions from frame 1801 to the end of the song (frames 0-1800 untouched),
# extend the scene range and swap the 60 s audio strip for the full song (same alignment).
# Usage: blender -b IN.blend -P ds_extend.py -- OUT.blend AUDIO
import bpy, sys, os, numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index('--')+1:]; OUT, AUDIO = a[0], a[1]
RT = os.environ.get('RETARGET_DIR', 'retarget') + '/'
names = open(RT + 'ds_hime_names.txt', encoding='utf8').read().split('\n'); idx = {n: i for i, n in enumerate(names)}
sc = bpy.context.scene
F0 = 1801

def fcurves_of(act):
    out = []
    for l in act.layers:
        for st in l.strips:
            for cb in st.channelbags: out.extend(cb.fcurves)
    return out

def extend(rig, tag):
    T = np.load(RT + f'{tag}_rot_full.npy').astype(np.float64); H = np.load(RT + f'{tag}_hips_full.npy').astype(np.float64)
    NF = T.shape[0]
    bones = rig.data.bones; Lm = {b.name: np.array(b.matrix_local) for b in bones}
    order = sorted(bones, key=lambda b: len(b.parent_recursive))
    quat = {n: np.zeros((NF - F0, 4)) for n in names}; hloc = np.zeros((NF - F0, 3))
    for k, f in enumerate(range(F0, NF)):
        for b in order:
            n = b.name; Rt = T[f, idx[n]]
            if b.parent is None:
                Rr = Lm[n][:3, :3]; Rb = Rr.T @ Rt; hloc[k] = Rr.T @ (H[f] - Lm[n][:3, 3])
            else:
                rel = np.linalg.inv(Lm[b.parent.name]) @ Lm[n]; Rb = (T[f, idx[b.parent.name]] @ rel[:3, :3]).T @ Rt
            u, _, vt = np.linalg.svd(Rb); quat[n][k] = np.array(Matrix((u @ vt).tolist()).to_quaternion())
    act = rig.animation_data.action; fcs = {(fc.data_path, fc.array_index): fc for fc in fcurves_of(act)}
    def append(path, i, vals, grp):
        fc = fcs.get((path, i))
        if fc is None:
            fc = act.fcurve_ensure_for_datablock(rig, path, index=i, group_name=grp); fcs[(path, i)] = fc
        kp = fc.keyframe_points
        # drop any keys at/after F0 (none expected), then append
        n0 = len(kp); co = np.empty(n0 * 2); kp.foreach_get('co', co)
        keep = co[0::2] < F0 - 0.5
        if not keep.all():
            for j in reversed(np.nonzero(~keep)[0]): kp.remove(kp[int(j)], fast=True)
            n0 = len(kp); co = np.empty(n0 * 2); kp.foreach_get('co', co)
        interp = kp[0].interpolation if n0 else 'LINEAR'
        kp.add(len(vals)); new = np.empty((n0 + len(vals)) * 2); new[:n0 * 2] = co
        new[n0 * 2::2] = np.arange(F0, F0 + len(vals)); new[n0 * 2 + 1::2] = vals
        kp.foreach_set('co', new)
        for j in range(n0, n0 + len(vals)): kp[j].interpolation = interp
        fc.update()
        return fc
    for n in names:
        path = f'pose.bones["{n}"].rotation_quaternion'
        last = np.array([fcs[(path, i)].evaluate(F0 - 1) if (path, i) in fcs else 0.0 for i in range(4)])
        q = quat[n]
        if (path, 0) in fcs and np.dot(q[0], last) < 0: q[0] = -q[0]
        for f in range(1, len(q)):
            if np.dot(q[f], q[f-1]) < 0: q[f] = -q[f]
        for i in range(4): append(path, i, q[:, i], n)
    for i in range(3): append('pose.bones["mixamorig:Hips"].location', i, hloc[:, i], 'mixamorig:Hips')
    sc.frame_set(F0 - 1); a0 = {pb.name: pb.matrix.copy() for pb in rig.pose.bones}
    sc.frame_set(F0); jump = max((rig.pose.bones[n].matrix.translation - a0[n].translation).length for n in names)
    print('extended', rig.name, tag, 'to frame', NF - 1, 'seam max bone move mm', round(jump * 1000, 2))
    return NF - 1

end1 = extend(bpy.data.objects['CharaKit_Weights_8cf2bc8c_Rig'], 'hime')
end2 = extend(bpy.data.objects['DS2_Rig'], 'hina')
END = min(end1, end2); sc.frame_end = END
# audio: replace the 60 s strip, keep its alignment
se = sc.sequence_editor
old = [s for s in se.strips_all if s.type == 'SOUND']
for s in old: print('old audio', s.name, s.sound.filepath, 'start', s.frame_start, 'offset', s.frame_offset_start, 'final', s.frame_final_start, s.frame_final_end)
st = old[0].frame_start if old else 1
ch = old[0].channel if old else 1
for s in old: se.strips.remove(s)
snd = se.strips.new_sound('Aipai_full', AUDIO, ch, int(round(st)))
print('new audio start', snd.frame_start, 'end', snd.frame_final_end, 'scene end', END)
sc.frame_set(0)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('saved', OUT)
