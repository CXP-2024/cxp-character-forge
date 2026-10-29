# Inter-layer glue pairs for solve_real2.py: points closer than DIST in rest space but far apart along the mesh surface
# (geodesic > max(3*d, d+GAP)), i.e. a point on one layer and the point right under it on the next layer. Waist-bound and
# tiny detached points are excluded; at most PER links per point, shortest first.
# usage: python glue_pairs.py DIR [dist=0.03] [per=2] [gap=0.02]
import numpy as np, json, sys, collections
from pathlib import Path
P = Path(sys.argv[1]); OV = {'dist': float(sys.argv[2]) if len(sys.argv) > 2 else 0.03, 'per': int(sys.argv[3]) if len(sys.argv) > 3 else 2,
                            'gap': float(sys.argv[4]) if len(sys.argv) > 4 else 0.02}
GL = OV; GD = OV['dist']
V = np.load(P / 'rest.npz')['skirt']; fc = json.loads((P / 'faces.json').read_text()); blend = np.load(P / 'binding.npz')['blend']
tris = np.array([[q[0], q[k], q[k + 1]] for q in fc['skirt'] for k in range(1, len(q) - 1)])
par = list(range(len(V)))
def find(a):
    while par[a] != a: par[a] = par[par[a]]; a = par[a]
    return a
for t in tris:
    for a, b in ((t[0], t[1]), (t[1], t[2])): par[find(a)] = find(b)
roots = collections.Counter(find(i) for i in range(len(V))); small = np.array([roots[find(i)] < 200 for i in range(len(V))])
GL = OV.get('glue', {}); GD = GL.get('dist', 0.03)
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
E = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]); el = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)
Gm = coo_matrix((np.r_[el, el], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])), shape=(len(V), len(V))).tocsr()
cand = [(i, j) for i, j in cKDTree(V).query_pairs(GD) if blend[i] < 1 and blend[j] < 1 and not small[i] and not small[j]]
I = np.array([c[0] for c in cand]); J = np.array([c[1] for c in cand]); ed = np.linalg.norm(V[I] - V[J], axis=1)
geo_d = np.full(len(I), np.inf)
for src in np.unique(I):
    m = I == src; dd = dijkstra(Gm, indices=src, limit=GL.get('geo', 0.12)); geo_d[m] = dd[J[m]]
keep = geo_d > np.maximum(3 * ed, ed + GL.get('gap', 0.02))
pairs = np.stack([I[keep], J[keep]], 1); pd = ed[keep]
o = np.argsort(pd); used = collections.Counter(); sel = []
for k in o:                                     # at most N links per point, shortest first
    a, b = pairs[k]
    if used[a] < GL.get('per', 2) and used[b] < GL.get('per', 2): sel.append(k); used[a] += 1; used[b] += 1
pairs = pairs[sel]; print('glue links', len(pairs), 'points', len(used), flush=True)
np.save(P / '_glue_pairs.npy', pairs)
print('mean link mm', round(float(np.linalg.norm(V[pairs[:, 0]] - V[pairs[:, 1]], axis=1).mean() * 1000), 1))
