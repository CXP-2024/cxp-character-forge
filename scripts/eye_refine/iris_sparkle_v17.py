# Sparkle layer for the v16 iris (like 奥黛塔's 目光3 facets / 目光 rimmed dots, kept small and blue-white):
#  - thin cyan rim around the catch-light ellipse
#  - a few small diamond facets + dots along the light lower crescent
# Output layered_v16/tex{L,R}_iris_spark.png (RGBA, straight alpha). usage: python iris_sparkle_v17.py
import numpy as np, cv2, json
from PIL import Image
from pathlib import Path
RIM = False  # user removed the cyan ring around the catch-light (v17b)
D = Path(__file__).parent / 'layered_v16'; R = json.loads((D / 'report.json').read_text()); SS = 4
for side in 'LR':
    base = np.array(Image.open(D / f'tex{side}_iris_base.png').convert('RGBA'))
    A = base[..., 3] > 128; h, w = A.shape
    col = np.zeros((h*SS, w*SS, 3), np.float32); al = np.zeros((h*SS, w*SS), np.float32)
    def put(mask_fn, rgb, a):
        m = np.zeros((h*SS, w*SS), np.uint8); mask_fn(m); m = m.astype(np.float32) / 255 * a
        col[:] = col * (1 - m[..., None]) + np.array(rgb, np.float32) * m[..., None]; al[:] = np.maximum(al, m)
    (cx, cy), (ax, ay), ang = R[side]['catchlight_ellipse']
    # cyan rim (ring) around the catch-light
    if RIM: put(lambda m: cv2.ellipse(m, ((cx*SS, cy*SS), ((ax+6)*SS, (ay+6)*SS), ang), 255, 2*SS, cv2.LINE_AA), (140, 225, 255), 0.5)
    # lower crescent: bright region of the base below the catch-light; place facets on its upper edge
    hsv = cv2.cvtColor(base[..., :3], cv2.COLOR_RGB2HSV)
    bright = (hsv[..., 2] > 225) & (hsv[..., 1] < 120) & A
    ys, xs = np.nonzero(A); top, bot = ys.min(), ys.max(); midx = (xs.min() + xs.max()) / 2; half = (xs.max() - xs.min()) / 2
    pts = []
    for fx in (-0.30, 0.04, 0.32):
        x = int(midx + fx * half); col_b = np.nonzero(bright[:, x])[0]
        col_b = col_b[col_b > cy + ay]
        if len(col_b): pts.append((x, int(col_b.min()) + 10))
    for k, ((x, y), sz, dy, a_) in enumerate(zip(pts, (7, 10, 6), (6, -4, 10), (0.7, 0.85, 0.6))):
        s = sz * SS; y = y + dy
        dia = np.array([[x*SS, y*SS - s*1.5], [x*SS + s, y*SS], [x*SS, y*SS + s*1.5], [x*SS - s, y*SS]], np.int32)
        put(lambda m, d=dia: cv2.fillConvexPoly(m, d, 255, cv2.LINE_AA), (235, 248, 255), a_)
    # two tiny round sparkles near the rim of the iris (upper-right / lower-left)
    for (fx, fy, r) in ((0.55, 0.30, 5), (-0.50, 0.78, 4)):
        x = midx + fx * half; y = top + fy * (bot - top)
        put(lambda m, x=x, y=y, r=r: cv2.circle(m, (int(x*SS), int(y*SS)), r*SS, 255, -1, cv2.LINE_AA), (230, 245, 255), 0.9)
    col = cv2.resize(col, (w, h), interpolation=cv2.INTER_AREA); al = cv2.resize(al, (w, h), interpolation=cv2.INTER_AREA)
    al = al * A
    straight = (col / np.maximum(al[..., None], 1e-4)).clip(0, 255)
    out = np.dstack([straight, al * 255]).astype(np.uint8)
    Image.fromarray(out).save(D / f'tex{side}_iris_spark.png')
    # preview over composite
    comp = np.array(Image.open(D / f'tex{side}_iris_composite.png').convert('RGBA')).astype(np.float32)
    a = al[..., None]; comp[..., :3] = comp[..., :3] * (1 - a) + col * (al[..., None] > 0)
    bg = comp[..., :3] * (comp[..., 3:] / 255) + 60 * (1 - comp[..., 3:] / 255)
    Image.fromarray(bg[top-5:bot+5, xs.min()-5:xs.max()+5].astype(np.uint8)).save(D / f'preview_spark_{side}.png')
    print(side, 'facets', len(pts))
