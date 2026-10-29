# Split the v69 iris texture into layers with crisp edges, keeping every shape where it is:
#   base      = original minus baked highlights (inpainted) and minus the red fringe, lightly sharpened
#   pupil     = ellipse fitted to the original pupil, original colours, anti-aliased edge
#   highlight = big catch-light (fitted ellipse) + small reflections (smoothed blobs), flat colours
# Output: layered_v16/tex{L,R}_iris_{base,pupil,hl}.png  + preview.  usage: python iris_layers_v16.py
import numpy as np, cv2, json
from PIL import Image
from pathlib import Path
D = Path(__file__).parent; O = D / 'layered_v16'; O.mkdir(exist_ok=True)
SS = 4  # supersampling for anti-aliased masks
import sys; PTH = 0.3; SHARP = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0

def aa_mask(binary, smooth=1.5):
    """binary uint8 0/1 -> anti-aliased float alpha with smooth, crisp contour"""
    h, w = binary.shape
    up = cv2.resize(binary.astype(np.float32), (w*SS, h*SS), interpolation=cv2.INTER_LINEAR)
    up = cv2.GaussianBlur(up, (0, 0), smooth*SS)
    up = (up > 0.5).astype(np.float32)
    return cv2.resize(up, (w, h), interpolation=cv2.INTER_AREA)

def ellipse_alpha(shape, ell):
    h, w = shape
    up = np.zeros((h*SS, w*SS), np.uint8)
    (cx, cy), (ax, ay), ang = ell
    cv2.ellipse(up, ((cx*SS, cy*SS), (ax*SS, ay*SS), ang), 255, -1, cv2.LINE_AA)
    return cv2.resize(up.astype(np.float32)/255, (w, h), interpolation=cv2.INTER_AREA)

report = {}
for side in 'LR':
    src = np.array(Image.open(D / f'tex{side}_iris_teacher_v69.png').convert('RGBA'))
    rgb = src[..., :3].copy(); A = src[..., 3]; m = A > 128
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(float); S, V = hsv[..., 1], hsv[..., 2]
    ys, xs = np.nonzero(m); cyi, cxi = ys.mean(), xs.mean()
    pcx, pcy, pa = cxi, cyi + 60, 60
    # --- big catch-light: low-saturation bright blob above the pupil, ellipse fit
    mk = ((S < 110) & (V > 170) & m).astype(np.uint8); n, lab, st, cen = cv2.connectedComponentsWithStats(mk)
    cand = [i for i in range(1, n) if 400 < st[i, 4] < 6000 and cen[i, 1] < pcy and st[i, 3] < 120]
    di = max(cand, key=lambda i: st[i, 4])
    cnts, _ = cv2.findContours((lab == di).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    dell = cv2.fitEllipse(max(cnts, key=len))
    dmask = (lab == di)
    # --- pupil: darker (V<202) blob just below the catch-light, convex hull (fills the catch-light notch)
    # radial edge search from a seed inside the pupil (below the catch-light): first radius where
    # smoothed V climbs past the pupil/iris midpoint; angles blocked by the catch-light are interpolated
    Vs = cv2.GaussianBlur(V, (0, 0), 2.5)
    c = np.array([dell[0][0], dell[0][1] + dell[1][1] * 1.55])
    vin = np.median(Vs[int(c[1]) - 8:int(c[1]) + 8, int(c[0]) - 8:int(c[0]) + 8])
    ang = np.linspace(0, 2*np.pi, 180, endpoint=False); rad = np.full(len(ang), np.nan)
    dot = ellipse_alpha(A.shape, dell) > 0.3
    for k, t in enumerate(ang):
        d = np.array([np.cos(t), np.sin(t)])
        for r in range(8, 140):
            x, y = (c + d * r).astype(int)
            if not m[y, x]: break
            if dot[y, x]: break
            if Vs[y, x] > vin + PTH * (225 - vin): rad[k] = r; break
    ok = ~np.isnan(rad); rad = np.interp(np.arange(len(ang)), np.arange(len(ang))[ok], rad[ok], period=len(ang))
    rad = np.convolve(np.r_[rad[-4:], rad, rad[:4]], np.ones(9)/9, 'valid')
    hull = np.stack([c[0] + rad*np.cos(ang), c[1] + rad*np.sin(ang)], 1).astype(np.int32)[:, None, :]
    pmask = np.zeros(A.shape, np.uint8); cv2.fillPoly(pmask, [hull], 1)
    pell = cv2.fitEllipse(hull)
    dcol = np.percentile(rgb[dmask], 85, axis=0)
    # --- small reflections: locally brighter & less saturated blobs, left of / above the pupil
    Vb = cv2.GaussianBlur(V, (0, 0), 12); Sb = cv2.GaussianBlur(S, (0, 0), 12)
    loc = ((V - Vb > 18) & (Sb - S > 15) & m).astype(np.uint8)
    n, lab2, st2, cen2 = cv2.connectedComponentsWithStats(loc)
    small = [i for i in range(1, n) if 50 < st2[i, 4] < 700 and cen2[i, 1] < pcy and cen2[i, 0] < pcx - pa*0.6
             and np.hypot(cen2[i, 0]-dell[0][0], cen2[i, 1]-dell[0][1]) > 40 and st2[i, 0] > xs.min() + 25]
    smask = np.isin(lab2, small)
    # --- highlight layer
    hl_a = np.maximum(ellipse_alpha(A.shape, dell), aa_mask(smask.astype(np.uint8), 1.2) * 0.85)
    hl = np.zeros((*A.shape, 4), np.float32)
    hl[..., :3] = dcol
    if small:
        scol = np.percentile(rgb[smask], 80, axis=0); w = aa_mask(smask.astype(np.uint8), 1.2)
        hl[..., :3] = hl[..., :3] * (1 - w[..., None]) + scol * w[..., None]
    hl[..., 3] = hl_a * 255 * m
    # --- base: inpaint highlights and red fringe, then gentle unsharp mask
    rem = (dmask | smask).astype(np.uint8)
    rem = cv2.dilate(rem, np.ones((7, 7), np.uint8))
    H = hsv[..., 0]
    red = (((H < 12) | (H > 135)) & (S > 40) & m)
    hole = (rem > 0).astype(np.uint8)
    # inpaint inside the iris only: pad outside with nearest iris colour first
    # red/magenta fringe at the lid edges -> same brightness, iris blue hue
    hz = hsv.copy(); hz[..., 0] = np.where(red, 114, hz[..., 0]); hz[..., 1] = np.where(red, np.minimum(S, 170) * 0.85, S)
    rgb2 = np.where(red[..., None], cv2.cvtColor(hz.astype(np.uint8), cv2.COLOR_HSV2RGB), rgb)
    base = cv2.inpaint(rgb2, hole, 9, cv2.INPAINT_TELEA)
    blur = cv2.GaussianBlur(base.astype(np.float32), (0, 0), 2.0)
    base = np.clip(base + SHARP * (base - blur), 0, 255)
    base_rgba = np.dstack([base, A]).astype(np.uint8)
    # --- pupil layer: original (inpainted) colours, crisp ellipse edge, slightly deeper core
    pa_ = aa_mask(pmask, 2.0)
    # extend the pupil's interior colours to its rim so the edge is crisp instead of a soft blend
    inner = cv2.erode(pmask, np.ones((13, 13), np.uint8)) > 0
    pfill = cv2.inpaint(np.clip(base, 0, 255).astype(np.uint8), (~inner).astype(np.uint8), 7, cv2.INPAINT_TELEA)
    pup = np.dstack([pfill, pa_ * 0]).astype(np.uint8)   # pupil stays in base (auto contour changed its shape)
    for nm, im in (('base', base_rgba), ('hl', hl.clip(0, 255).astype(np.uint8))):
        Image.fromarray(im).save(O / f'tex{side}_iris_{nm}.png')
    # composite check (straight alpha over)
    comp = base.astype(np.float32)
    for L in (pup.astype(np.float32), hl):
        al = L[..., 3:4] / 255; comp = comp * (1 - al) + L[..., :3] * al
    Image.fromarray(np.dstack([comp, A]).astype(np.uint8)).save(O / f'tex{side}_iris_composite.png')
    report[side] = {'pupil_ellipse': [list(map(float, pell[0])), list(map(float, pell[1])), float(pell[2])],
                    'catchlight_ellipse': [list(map(float, dell[0])), list(map(float, dell[1])), float(dell[2])],
                    'catchlight_rgb': dcol.round().tolist(), 'small_reflections': len(small),
                    'red_px': int(red.sum()), 'inpaint_px': int(hole.sum())}
    dbg = onbg_tmp = None
    # preview: original | base | composite
    bb = (ys.min()-5, ys.max()+5, xs.min()-5, xs.max()+5)
    def crop(im): return im[bb[0]:bb[1], bb[2]:bb[3]]
    def onbg(rgba):
        al = rgba[..., 3:4].astype(float) / 255; return (rgba[..., :3] * al + 60 * (1 - al)).astype(np.uint8)
    hl_on = onbg(np.dstack([hl[..., :3], hl[..., 3]]).clip(0, 255).astype(np.uint8))
    ov = onbg(src).copy(); cv2.drawContours(ov, [hull], -1, (255, 255, 0), 1); cv2.ellipse(ov, dell, (255, 0, 255), 1)
    prev = np.hstack([crop(ov), crop(onbg(base_rgba)), crop(hl_on), crop(onbg(np.dstack([comp, A]).astype(np.uint8)))])
    Image.fromarray(prev).save(O / f'preview_{side}.png')
(O / 'report.json').write_text(json.dumps(report, indent=1))
print(json.dumps(report, indent=1))
