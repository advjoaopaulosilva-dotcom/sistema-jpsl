"""Filme de lançamento — nova identidade visual de João Paulo Silva Lopes (v2, cinematográfica).

Renderiza video-lancamento/saida/lancamento_identidade_2026.mp4
(9:16, 2160x3840, 30 fps, H.264 + AAC).

Linguagem: ambiente Marinho escuro com feixes de luz volumétricos; as marcas tratadas
como peças de metal acetinado (bisel, reflexo, sombra), câmera com perspectiva real e
profundidade de campo. As silhuetas vêm SEMPRE dos arquivos oficiais: o que muda é só
a luz e o material, nunca a forma.

Uso:  python3 render.py              render completo
      python3 render.py --preview    quadros-chave em PNG (saida/preview_*.png)
Dependências: pillow, numpy, scipy, imageio-ffmpeg.
"""
import os, sys, subprocess, wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage
from scipy.signal import fftconvolve

from geometry import OLD, NEW, OLD_COLLAPSE

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "saida")
W, H, FPS, DUR = 2160, 3840, 30, 16.0
NFRAMES = int(DUR * FPS)
F0 = np.array([W / 2, H / 2])
FOCAL = 3400.0
Q = 4  # fator das camadas de baixa resolução (luz, sombra, bloom)


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255


MARINHO, PETROLEO = hexc("#162235"), hexc("#1C3A42")
GRAFITE, LATAO, PAPEL = hexc("#3B4048"), hexc("#A48E6A"), hexc("#F5F4F0")

# ------------------------------------------------------------------ util
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))

def seg(t, t0, t1):
    return clamp((t - t0) / (t1 - t0))

def ease(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2

def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3

def ease_sine(x):
    x = clamp(x)
    return 0.5 - 0.5 * np.cos(np.pi * x)

def up(arr, size):
    """Amplia um campo float (baixa resolução) para `size` = (w, h)."""
    return np.asarray(Image.fromarray(np.ascontiguousarray(arr, np.float32), "F").resize(size, Image.BILINEAR))

def down(arr, size):
    return np.asarray(Image.fromarray(np.ascontiguousarray(arr, np.float32), "F").resize(size, Image.BOX))

# ------------------------------------------------------------------ assets
def load_assets():
    A = {}
    nova = Image.open(os.path.join(HERE, "assets/logo_nova_oficial.webp"))
    assert nova.mode == "RGBA"
    al = np.asarray(nova)[..., 3]
    ys, xs = np.where(al > 0)
    bbox_c = ((xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2)
    A["sn"] = 0.92                                    # margem livre > 1/3 do símbolo (manual)
    nw, nh = round(nova.width * A["sn"]), round(nova.height * A["sn"])
    A["nova_final"] = nova.getchannel("A").resize((nw, nh), Image.LANCZOS)   # única reamostragem
    A["nova_final_f"] = np.asarray(A["nova_final"], np.float32) / 255
    A["nova_off"] = np.array([round(F0[0] - bbox_c[0] * A["sn"]), round(F0[1] - bbox_c[1] * A["sn"])], float)
    A["nova_split"] = 900
    global SYM_WORLD
    SYM_WORLD = A["nova_off"] + np.array([1017.0, 441.5]) * A["sn"]

    old = Image.open(os.path.join(HERE, "assets/logo_antiga.jpg")).convert("L")
    A["so"] = 2.65
    ys, xs = np.where(np.asarray(old) < 146)
    ob = ((xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2)
    A["old_off"] = F0 - np.array(ob) * A["so"]
    A["old_split"] = 280
    big = old.filter(ImageFilter.GaussianBlur(0.45)).resize((old.width * 8, old.height * 8), Image.LANCZOS)
    L = np.asarray(big, np.float32)
    a = np.clip((243 - L) / (243 - 46), 0, 1)
    a = np.clip((a - 0.5) * 3.0 + 0.5, 0, 1)
    a = a * a * (3 - 2 * a)
    old_a = Image.fromarray((a * 255).astype(np.uint8))
    A["old_levels"] = {8: old_a, 4: old_a.resize((old.width * 4, old.height * 4), Image.LANCZOS),
                       2: old_a.resize((old.width * 2, old.height * 2), Image.LANCZOS)}

    yy, xx = np.mgrid[0:H // Q, 0:W // Q].astype(np.float32)
    A["xx"], A["yy"] = xx * Q + Q / 2, yy * Q + Q / 2
    rng = np.random.default_rng(2026)
    A["dither"] = ((rng.random((H, W), np.float32) + rng.random((H, W), np.float32) - 1.0) * 1.1 / 255)
    hz = ndimage.gaussian_filter1d(rng.standard_normal(4096), 14, mode="wrap")
    A["haze"] = (hz - hz.min()) / (hz.max() - hz.min())
    hz2 = ndimage.gaussian_filter1d(rng.standard_normal(4096), 40, mode="wrap")
    A["haze2"] = (hz2 - hz2.min()) / (hz2.max() - hz2.min())
    return A

# ------------------------------------------------------------------ timeline
MOVES = {  # traço: (início, fim) do movimento
    "L": (5.3, 6.2), "V1": (5.5, 6.6),
    "D1": (6.15, 7.7), "V2": (6.25, 7.78), "D2": (6.35, 7.85), "R": (6.55, 7.95),
}
OLD_SYM_C, OLD_SYM_H = np.array([137.0, 183.0]), 346.0
NEW_SYM_C, NEW_SYM_H = np.array([1017.0, 441.5]), 721.0
DIAMOND = [(687.75, 442.75), (1000.0, 130.5), (1312.25, 442.5), (1000.0, 755.0)]  # esq, topo, dir, base (manual, p. 2)


SYM_WORLD = None  # centro do novo símbolo no mundo (definido em load_assets)


def camera(t):
    """(centro no mundo, zoom). Identidade exata a partir de 14 s."""
    macro_c = np.array([655.0, 1640.0])
    if t < 2.2:
        k = seg(t, 0, 2.2)
        return macro_c + np.array([-90 + 140 * ease_sine(k), 50 * ease_sine(k)]), 3.1 - 0.3 * ease_sine(k)
    if t < 4.2:
        k = ease(seg(t, 2.2, 4.1))
        c0 = macro_c + np.array([50, 50])
        return c0 + (F0 - c0) * k, 2.8 + (1.0 - 2.8) * k
    if t < 14.0:
        # aproxima no símbolo durante a transformação e recua quando o nome aparece
        sym = SYM_WORLD + np.array([0.0, 30.0])
        k_in = ease(seg(t, 4.3, 7.4))
        k_out = ease(seg(t, 8.45, 10.3))
        c = F0 + (sym - F0) * k_in * (1 - k_out)
        c = c + np.array([22 * np.sin(np.pi * seg(t, 4.2, 11.0)), 0])
        z = 1.0 + 0.62 * k_in - 0.645 * k_out + 0.025 * ease_out(seg(t, 11.0, 14.0))
        return c, z
    return F0.copy(), 1.0


def tilt(t):
    """(yaw, pitch) em radianos da peça diante da câmera; zero a partir de 8 s."""
    if t < 2.2:
        k = ease_sine(seg(t, 0, 2.2)); yaw, pitch = 27 - 6 * k, -11 + 2 * k
    elif t < 4.2:
        k = ease(seg(t, 2.2, 4.2)); yaw, pitch = 21 - 14 * k, -9 + 6 * k
    else:
        k = ease(seg(t, 4.2, 8.0)); yaw, pitch = 7 * (1 - k), -3 * (1 - k)
    return np.radians(yaw), np.radians(pitch)


def params(t):
    P = {"t": t, "cam": camera(t), "tilt": tilt(t)}
    base = 0.18 + 0.82 * ease_sine(seg(t, 0.3, 2.6))
    if t < 8.3:
        m = 1 - 0.22 * ease_sine(seg(t, 7.8, 8.25))
    else:
        m = 0.78 + 0.36 * ease_out(seg(t, 8.3, 8.8)) - 0.14 * ease_sine(seg(t, 9.0, 10.8))
    P["key"] = base * m
    P["bg"] = ease_sine(seg(t, 0.0, 2.2)) * (m * 0.5 + 0.5)
    P["shafts"] = 0.85 + 0.45 * (ease_out(seg(t, 8.3, 8.9)) - ease_sine(seg(t, 9.2, 11.5))) * (t >= 8.3)
    P["shadow"] = 0.62
    k = ease(seg(t, 6.2, 8.3))
    P["albedo"] = np.array([0.80, 0.83, 0.88]) * (1 - k) + np.array([0.96, 0.95, 0.92]) * k
    P["satin"] = -0.6 + 1.2 * ease_sine(seg(t, 0, 16))
    P["glints"] = []
    for t0, t1, amt, col, wid in ((0.5, 3.2, 0.95, (1.0, 0.98, 0.95), 280),
                                   (8.3, 9.9, 1.05, (1.0, 0.80, 0.50), 210),
                                   (11.2, 13.8, 0.45, (1.0, 0.95, 0.86), 320)):
        k = seg(t, t0, t1)
        if 0 < k < 1:
            P["glints"].append((-1500 + 3000 * ease_sine(k), wid, amt * np.sin(np.pi * k), np.array(col)))
    yaw, _ = P["tilt"]
    P["dof"] = clamp(abs(yaw) / np.radians(20)) * (1 - ease(seg(t, 2.6, 4.0))) + 0.9 * (1 - ease(seg(t, 0.0, 1.5)))
    P["bloom"] = 0.55 + 0.5 * (ease_out(seg(t, 8.3, 8.7)) - ease_sine(seg(t, 8.9, 10.5))) * (t >= 8.3)
    P["guides"] = 1 - ease(seg(t, 8.3, 9.3)) if t > 4.8 else 0.0
    return P

# ------------------------------------------------------------------ geometria
def old_pose(t, A):
    """Sem o texto, o símbolo antigo desliza para o centro óptico da nova marca."""
    k = ease(seg(t, 4.6, 5.9))
    s2 = NEW_SYM_H * A["sn"] * 1.12 / OLD_SYM_H
    c2 = A["nova_off"] + NEW_SYM_C * A["sn"]
    s = A["so"] + (s2 - A["so"]) * k
    off = A["old_off"] + ((c2 - OLD_SYM_C * s2) - A["old_off"]) * k
    return off, s

def world_old(p, A, t):
    off, s = old_pose(t, A)
    return off + np.asarray(p, float) * s

def world_new(p, A):
    return A["nova_off"] + np.asarray(p, float) * A["sn"]

def vector_quads(t, A):
    quads = []
    for k in ("L", "V1", "D1", "V2", "D2", "R"):
        t0, t1 = MOVES[k]
        e = ease(seg(t, t0, t1))
        src = np.array([world_old(p, A, t) for p in OLD[k]])
        if k in OLD_COLLAPSE:
            dst = np.array([world_old(p, A, t) for p in OLD_COLLAPSE[k]])
            alpha = 1.0 - seg(t, t1 - 0.25, t1)
        else:
            dst = np.array([world_new(p, A) for p in NEW[k]])
            alpha = 1.0
        if alpha > 0:
            quads.append((src + (dst - src) * e, alpha))
    return quads

def to_plane(pts, cam):
    c, z = cam
    return (np.asarray(pts, float) - c) * z + F0

def homography(yaw, pitch):
    """Plano da peça (coords de tela) -> tela, girando em torno do centro do quadro."""
    cy, sy, cp, sp = np.cos(yaw), np.sin(yaw), np.cos(pitch), np.sin(pitch)
    R = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]) @ np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    M = np.array([[FOCAL * R[0, 0], FOCAL * R[0, 1], 0], [FOCAL * R[1, 0], FOCAL * R[1, 1], 0],
                  [R[2, 0], R[2, 1], FOCAL]])
    T = np.array([[1, 0, F0[0]], [0, 1, F0[1]], [0, 0, 1]])
    Ti = np.array([[1, 0, -F0[0]], [0, 1, -F0[1]], [0, 0, 1]])
    Hm = T @ M @ Ti
    return Hm / Hm[2, 2], R

def apply_h(Hm, pts):
    p = np.c_[np.asarray(pts, float), np.ones(len(pts))] @ Hm.T
    return p[:, :2] / p[:, 2:3]

# ------------------------------------------------------------------ máscaras (coordenadas de uma janela do plano)
def raster_layer(img, s, off, cam, k, win):
    c, z = cam
    x0, y0, x1, y1 = win
    a = k / (s * z)
    cx = k * ((x0 - F0[0]) / z + c[0] - off[0]) / s
    cy = k * ((y0 - F0[1]) / z + c[1] - off[1]) / s
    return np.asarray(img.transform((x1 - x0, y1 - y0), Image.AFFINE, (a, 0, cx, 0, a, cy), Image.BICUBIC),
                      np.float32) / 255

_masks = {}
def old_img(A, cam, part):
    s, z = A["so"], cam[1]
    lvl = min((l for l in (2, 4, 8) if l / (s * z) >= 0.75), default=8)
    key = (lvl, part)
    if key not in _masks:
        img = A["old_levels"][lvl]
        split = A["old_split"] * lvl
        m = Image.new("L", img.size, 0)
        ImageDraw.Draw(m).rectangle((0, 0, split - 1, img.height) if part == "sym" else (split, 0, img.width, img.height), fill=255)
        _masks[key] = Image.composite(img, Image.new("L", img.size, 0), m)
    return _masks[key], lvl

def draw_quads(quads, cam, win, SS=3):
    x0, y0, x1, y1 = win
    out = np.zeros((y1 - y0, x1 - x0), np.float32)
    fr = [(to_plane(q, cam) - (x0, y0), a) for q, a in quads]
    if not fr:
        return out
    allp = np.concatenate([q for q, _ in fr])
    bx0, by0 = np.maximum(np.floor(allp.min(0)).astype(int) - 4, 0)
    bx1, by1 = np.minimum(np.ceil(allp.max(0)).astype(int) + 4, (x1 - x0, y1 - y0))
    if bx1 <= bx0 or by1 <= by0:
        return out
    for q, a in fr:
        m = Image.new("L", ((bx1 - bx0) * SS, (by1 - by0) * SS), 0)
        ImageDraw.Draw(m).polygon([((x - bx0) * SS, (y - by0) * SS) for x, y in q], fill=255)
        m = np.asarray(m.resize((bx1 - bx0, by1 - by0), Image.BOX), np.float32) / 255 * a
        sub = out[by0:by1, bx0:bx1]
        out[by0:by1, bx0:bx1] = sub + m * (1 - sub)
    return out

def build_masks(t, P, A, win):
    """Retorna (forma p/ material, alfa final) na janela."""
    cam = P["cam"]
    shape = None
    alpha = None
    def add(m, op):
        nonlocal shape, alpha
        if op <= 0:
            return
        shape = m if shape is None else np.maximum(shape, m)
        mo = m * op
        alpha = mo if alpha is None else alpha + mo * (1 - alpha)

    old_op = ease_sine(seg(t, 0.2, 1.4)) * (1 - seg(t, 4.3, 4.7))
    if old_op > 0:
        img, lvl = old_img(A, cam, "sym")
        add(raster_layer(img, A["so"], A["old_off"], cam, lvl, win), old_op)
        txt_op = ease_sine(seg(t, 0.2, 1.4)) * (1 - ease_sine(seg(t, 3.95, 4.7)))
        if txt_op > 0:
            img, lvl = old_img(A, cam, "txt")
            add(raster_layer(img, A["so"], A["old_off"], cam, lvl, win), txt_op)

    vec_op = seg(t, 4.3, 4.7) * (1 - seg(t, 8.35, 8.8))
    if vec_op > 0:
        add(draw_quads(vector_quads(t, A), cam, win), vec_op)

    if t >= 8.35:
        exact = abs(cam[1] - 1) < 1e-9 and np.allclose(cam[0], F0)
        if exact:  # arquivo oficial colado pixel a pixel, sem nova reamostragem
            m = np.zeros((win[3] - win[1], win[2] - win[0]), np.float32)
            nf = A["nova_final_f"]
            ox, oy = int(A["nova_off"][0]) - win[0], int(A["nova_off"][1]) - win[1]
            m[oy:oy + nf.shape[0], ox:ox + nf.shape[1]] = nf
        else:
            m = raster_layer(A["nova_final"], 1.0, A["nova_off"], cam, 1.0, win)
        sym_op = ease_sine(seg(t, 8.35, 8.8))
        k = ease(seg(t, 9.5, 11.0))
        if k < 1 or sym_op < 1:
            ys = np.arange(win[1], win[3], dtype=np.float32)[:, None]
            xs = np.arange(win[0], win[2], dtype=np.float32)[None, :]
            split_y = to_plane([[0, A["nova_off"][1] + A["nova_split"] * A["sn"]]], cam)[0][1]
            lx0, lx1 = to_plane([[A["nova_off"][0], 0], [A["nova_off"][0] + 2000 * A["sn"], 0]], cam)[:, 0]
            front = lx0 - 300 + (lx1 - lx0 + 600) * k
            reveal = np.where(ys > split_y, np.clip((front - xs) / 300, 0, 1), sym_op)
            shape = m if shape is None else np.maximum(shape, m)
            mo = m * reveal
            alpha = mo if alpha is None else alpha + mo * (1 - alpha)
        else:
            add(m, 1.0)
    return shape, alpha

def draw_guides(t, P, A, win, crop):
    """Linhas de construção do manual (grade, arestas tracejadas, vértices em latão)."""
    op = P["guides"]
    if op <= 0:
        return None
    cam = P["cam"]
    cx0, cy0, cx1, cy1 = crop
    ox, oy = win[0] + cx0, win[1] + cy0
    SS = 2
    z = cam[1]
    def pt(p):  # coordenadas do arquivo novo -> pixels supersampled do recorte
        q = to_plane([world_new(p, A)], cam)[0]
        return ((q[0] - ox) * SS, (q[1] - oy) * SS)
    size = ((cx1 - cx0) * SS, (cy1 - cy0) * SS)
    grid = Image.new("L", size, 0); gd = ImageDraw.Draw(grid)
    brass = Image.new("L", size, 0); bd = ImageDraw.Draw(brass)
    X0, Y0 = DIAMOND[0][0], DIAMOND[1][1]
    cell = (DIAMOND[2][0] - DIAMOND[0][0]) / 8
    for i in range(-2, 11):
        k = ease(seg(t, 4.9 + 0.06 * abs(i - 4), 5.9 + 0.06 * abs(i - 4)))
        if k <= 0:
            continue
        half = (6 * cell) * k
        x = X0 + i * cell; y = Y0 + i * cell
        mid = Y0 + 4 * cell
        gd.line([pt((x, mid - half)), pt((x, mid + half))], fill=255, width=max(1, int(1.6 * z * SS)))
        midx = X0 + 4 * cell
        gd.line([pt((midx - half, y)), pt((midx + half, y))], fill=255, width=max(1, int(1.6 * z * SS)))
    # arestas ausentes do losango, tracejadas (esq->topo, base->dir)
    for a, b, t0 in ((DIAMOND[0], DIAMOND[1], 5.6), (DIAMOND[3], DIAMOND[2], 5.8)):
        k = ease(seg(t, t0, t0 + 1.0))
        a, b = np.array(a), np.array(b)
        L = np.linalg.norm(b - a); u = (b - a) / L
        dash, gap = 16.0, 11.0
        s = 0.0
        while s < L * k:
            e = min(s + dash, L * k)
            bd.line([pt(a + u * s), pt(a + u * e)], fill=255, width=max(1, int(2.6 * z * SS)))
            s += dash + gap
    for i, v in enumerate(DIAMOND):
        k = ease_out(seg(t, 6.0 + 0.12 * i, 6.35 + 0.12 * i))
        if k > 0:
            r = 9.0 * z * SS * k
            c = pt(v)
            bd.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=255)
    gsz = (cx1 - cx0, cy1 - cy0)
    # a grade se dissolve para as bordas (sem moldura quadrada)
    cc = (np.array(pt(((DIAMOND[0][0] + DIAMOND[2][0]) / 2, (DIAMOND[1][1] + DIAMOND[3][1]) / 2))) / SS)
    rad = 5.2 * cell * A["sn"] * z
    yy, xx = np.mgrid[0:gsz[1], 0:gsz[0]].astype(np.float32)
    fade = np.clip(1.25 - np.sqrt((xx - cc[0]) ** 2 + (yy - cc[1]) ** 2) / rad, 0, 1) ** 1.5
    g = np.asarray(grid.resize(gsz, Image.BOX), np.float32) / 255 * 0.16 * op * fade
    b = np.asarray(brass.resize(gsz, Image.BOX), np.float32) / 255 * 0.9 * op
    return g, b

# ------------------------------------------------------------------ material
def material(S, x0, y0, P, R):
    """Metal acetinado com bisel: normais a partir da distância à borda da silhueta."""
    B = S > 0.5
    d = ndimage.distance_transform_edt(B).astype(np.float32)
    d = np.where(B, d + (S - 1.0), 0.0)
    d = ndimage.gaussian_filter(d, 0.8)
    bev = 7.0 * P["cam"][1]
    u = np.clip(d / bev, 0, 1)
    h = (1 - (1 - u) ** 2) * bev * 0.8
    gy, gx = np.gradient(h)
    nz = 1 / np.sqrt(gx * gx + gy * gy + 1)
    nx, ny = -gx * nz, -gy * nz

    Lk = np.array([0.45, -0.62, 0.64]); Lk /= np.linalg.norm(Lk)
    Lp = R.T @ Lk                                      # luz fixa; a peça é que gira
    Hh = Lp + R.T @ np.array([0, 0, 1.0]); Hh /= np.linalg.norm(Hh)
    ndh = np.clip(nx * Hh[0] + ny * Hh[1] + nz * Hh[2], 0, 1)
    spec, sheen = ndh ** 90, ndh ** 12
    w = np.clip((1 - nz) * 2.4, 0, 1)                   # 0 na face, 1 no bisel
    l2 = np.array([Lp[0], Lp[1]]); l2 /= np.linalg.norm(l2) + 1e-6
    facing = (nx * l2[0] + ny * l2[1]) / (np.sqrt(nx * nx + ny * ny) + 1e-6)
    yy, xx = np.mgrid[y0:y0 + S.shape[0], x0:x0 + S.shape[1]].astype(np.float32)
    proj = ((xx - F0[0]) * 0.6 - (yy - F0[1]) * 0.8) / 900
    satin = 0.5 + 0.5 * np.tanh(proj * 1.3 + P["satin"])
    face = 0.74 + 0.22 * satin
    bevel = 0.14 + 1.05 * (0.5 + 0.5 * facing) ** 1.5
    lit = face * (1 - w) + bevel * w
    col = P["albedo"] * (lit * P["key"])[..., None]
    col += np.array([1.0, 0.97, 0.9]) * ((spec * 1.1 + sheen * 0.10) * P["key"])[..., None]
    dx, dy = 0.8, 0.6
    for pos, wid, amt, gcol in P["glints"]:
        gb = np.exp(-((((xx - F0[0]) * dx + (yy - F0[1]) * dy) - pos) / wid) ** 2)
        col += gcol * (gb * amt * (0.45 + 1.3 * w))[..., None]
    return col.astype(np.float32)

# ------------------------------------------------------------------ fundo
BEAMS = [(1.80, 0.060, 0.55), (1.95, 0.030, 0.45), (2.06, 0.075, 0.40), (2.22, 0.040, 0.35), (1.68, 0.045, 0.25)]

def background(t, P, A):
    X, Y = A["xx"], A["yy"]
    g = np.clip(Y / H, 0, 1)
    k = (g * g * (3 - 2 * g))[..., None]
    col = MARINHO * 1.0 * (1 - k) + MARINHO * 0.22 * k
    par = (P["cam"][0] - F0) * 0.06
    Sx, Sy = W * 1.05 - par[0], -H * 0.10 - par[1]
    dx, dy = X - Sx, Y - Sy
    r = np.sqrt(dx * dx + dy * dy) / H
    col = col + np.array([0.05, 0.09, 0.15]) * (np.exp(-(r / 0.6) ** 2) * 0.8)[..., None]
    th = np.arctan2(dy, dx)
    sh = np.zeros_like(X)
    for i, (a0, wd, amp) in enumerate(BEAMS):
        a = a0 + 0.035 * np.sin(t * 0.22 + i * 1.7)
        sh += amp * np.exp(-((th - a) / wd) ** 2)
    n = len(A["haze"])
    hz = A["haze"][((th + t * 0.004) * 900).astype(int) % n]
    hz2 = A["haze2"][((r * 3 - t * 0.02) * 400).astype(int) % n]
    sh *= (0.6 + 0.4 * hz) * (0.7 + 0.3 * hz2) * np.exp(-r * 1.2)
    col = col + np.array([0.13, 0.20, 0.30]) * (sh * P["shafts"])[..., None]
    vx, vy = (X - W / 2) / (W * 0.8), (Y - H * 0.45) / (H * 0.72)
    col = col * np.clip(1 - 0.5 * (vx * vx + vy * vy), 0, 1)[..., None] * P["bg"]
    return np.stack([up(col[..., i], (W, H)) for i in range(3)], -1)

# ------------------------------------------------------------------ quadro
def render_frame(i, A=None, debug=None):
    A = A or ASSETS
    t = i / FPS
    P = params(t)
    yaw, pitch = P["tilt"]
    flat = abs(yaw) < 1e-6 and abs(pitch) < 1e-6
    Hm, R = homography(yaw, pitch)
    if flat:
        win = (0, 0, W, H)
    else:  # janela do plano que cobre o quadro inteiro depois da perspectiva
        c = apply_h(np.linalg.inv(Hm), [(0, 0), (W, 0), (W, H), (0, H)])
        win = (int(np.floor(c[:, 0].min())) - 8, int(np.floor(c[:, 1].min())) - 8,
               int(np.ceil(c[:, 0].max())) + 8, int(np.ceil(c[:, 1].max())) + 8)

    img = background(t, P, A)
    S, AL = build_masks(t, P, A, win)
    lowA = np.zeros((H // Q, W // Q), np.float32)
    lowB = np.zeros((H // Q, W // Q), np.float32)
    region = None
    if S is not None and (S > 0.004).any():
        ys, xs = np.where(S > 0.004)
        pad = 24
        crop = [max(xs.min() - pad, 0), max(ys.min() - pad, 0),
                min(xs.max() + pad, S.shape[1]), min(ys.max() + pad, S.shape[0])]
        if P["guides"] > 0:  # garante espaço para as guias
            gp = to_plane([world_new(p, A) for p in DIAMOND], P["cam"]) - (win[0], win[1])
            m = 3.5 * (DIAMOND[2][0] - DIAMOND[0][0]) / 8 * A["sn"] * P["cam"][1]
            crop = [max(min(crop[0], int(gp[:, 0].min() - m)), 0), max(min(crop[1], int(gp[:, 1].min() - m)), 0),
                    min(max(crop[2], int(gp[:, 0].max() + m)), S.shape[1]), min(max(crop[3], int(gp[:, 1].max() + m)), S.shape[0])]
        cx0, cy0, cx1, cy1 = crop
        Sc, Ac = S[cy0:cy1, cx0:cx1], AL[cy0:cy1, cx0:cx1]
        col = material(Sc, win[0] + cx0, win[1] + cy0, P, R)
        Cp = col * Ac[..., None]
        Ap = Ac.copy()
        gl = draw_guides(t, P, A, win, crop)
        if gl is not None:  # guias ficam atrás da peça
            g, b = gl
            under = 1 - Ap
            gcol = np.array([0.70, 0.76, 0.84]) * P["key"]
            bcol = np.minimum(LATAO * 1.35, 1) * (0.6 + 0.4 * P["key"])
            Cp = Cp + (gcol * g[..., None] + bcol * b[..., None]) * under[..., None]
            Ap = Ap + (g + b - g * b) * under
        chans = [Cp[..., 0], Cp[..., 1], Cp[..., 2], Ap]
        if flat:
            ox0, oy0 = win[0] + cx0, win[1] + cy0
            outc = chans
        else:
            pc = apply_h(Hm, np.array([(cx0, cy0), (cx1, cy0), (cx1, cy1), (cx0, cy1)], float) + (win[0], win[1]))
            ox0, oy0 = max(int(np.floor(pc[:, 0].min())), 0), max(int(np.floor(pc[:, 1].min())), 0)
            ox1, oy1 = min(int(np.ceil(pc[:, 0].max())), W), min(int(np.ceil(pc[:, 1].max())), H)
            T_out = np.array([[1, 0, ox0], [0, 1, oy0], [0, 0, 1.0]])
            T_in = np.array([[1, 0, -(win[0] + cx0)], [0, 1, -(win[1] + cy0)], [0, 0, 1.0]])
            Mi = T_in @ np.linalg.inv(Hm) @ T_out
            Mi /= Mi[2, 2]
            coeffs = tuple(Mi.flatten()[:8])
            outc = [np.asarray(Image.fromarray(np.ascontiguousarray(ch, np.float32), "F").transform(
                (ox1 - ox0, oy1 - oy0), Image.PERSPECTIVE, coeffs, Image.BICUBIC)) for ch in chans]
            # profundidade de campo pela distância ao plano de foco
            if P["dof"] > 0.01:
                hh, ww = outc[3].shape
                sw, sh_ = max(ww // Q, 1), max(hh // Q, 1)
                gy_, gx_ = np.mgrid[0:sh_, 0:sw].astype(np.float32)
                pts = np.c_[gx_.ravel() * Q + ox0, gy_.ravel() * Q + oy0]
                pp = apply_h(np.linalg.inv(Hm), pts) - F0
                Z = (R[2, 0] * pp[:, 0] + R[2, 1] * pp[:, 1]).reshape(sh_, sw)
                mblur = np.clip(np.abs(Z) / 420, 0, 1) * P["dof"]
                mblur = np.clip(mblur + 0.8 * (1 - ease(seg(t, 0, 1.5))), 0, 1)
                mfull = up(mblur, (ww, hh))
                outc = [c * (1 - mfull) + up(ndimage.gaussian_filter(down(c, (sw, sh_)), 4.0), (ww, hh)) * mfull
                        for c in outc]
        Cp = np.stack(outc[:3], -1)
        Ap = np.clip(outc[3], 0, 1)
        hh, ww = Ap.shape
        region = (ox0, oy0, ox0 + ww, oy0 + hh)
        if debug is not None:
            debug["alpha"], debug["region"] = Ap, region
        # camadas de baixa resolução para sombra e bloom
        full = np.zeros((H, W), np.float32); full[oy0:oy0 + hh, ox0:ox0 + ww] = Ap
        lowA = down(full, (W // Q, H // Q))
        lum = Cp.mean(-1) / np.maximum(Ap, 1e-4)
        bright = np.clip(lum - 0.82, 0, None) * Ap
        fb = np.zeros((H, W), np.float32); fb[oy0:oy0 + hh, ox0:ox0 + ww] = bright
        lowB = down(fb, (W // Q, H // Q))

    # sombra projetada (luz do alto à direita) + sombra de contato
    if lowA.any():
        z = P["cam"][1]
        s1 = ndimage.shift(ndimage.gaussian_filter(lowA, 9 * z), (34 * z / Q, -22 * z / Q), order=1)
        s2 = ndimage.shift(ndimage.gaussian_filter(lowA, 1.2 * z), (8 * z / Q, -5 * z / Q), order=1)
        shadow = np.clip(0.55 * s1 + 0.4 * s2, 0, 0.9) * P["shadow"] * P["bg"]
        img = img * (1 - up(shadow, (W, H)))[..., None]
    if region is not None:
        x0, y0, x1, y1 = region
        sub = img[y0:y1, x0:x1]
        img[y0:y1, x0:x1] = sub * (1 - Ap[..., None]) + Cp
    if lowB.any():
        b = ndimage.gaussian_filter(lowB, 5) * 0.6 + ndimage.gaussian_filter(lowB, 22) * 0.9
        img = img + up(b * P["bloom"], (W, H))[..., None] * np.array([1.0, 0.94, 0.84])
    # ombro suave nos realces + dithering fixo
    img = np.where(img < 0.85, img, 0.85 + 0.15 * (1 - np.exp(-(img - 0.85) / 0.15)))
    img = img + A["dither"][..., None]
    return np.clip(img * 255 + 0.5, 0, 255).astype(np.uint8)

# ------------------------------------------------------------------ som
def render_audio(path, sr=48000):
    n = int(DUR * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(7)
    dry = np.zeros((n, 2)); send = np.zeros((n, 2))

    def lp(x, fc):
        k = max(int(sr / fc), 1)
        return np.convolve(x, np.ones(k) / k, "same")

    def bp(x, lo, hi):
        return lp(x, hi) - lp(x, lo)

    def put(sig, g=1.0, pan=0.0, rev=0.0):
        st = np.stack([sig * (1 - pan) ** 0.5, sig * (1 + pan) ** 0.5], 1) * g
        dry[:] += st; send[:] += st * rev

    # 0–4 s: ar do ambiente e um grave profundo que "acende" com a luz
    nz = rng.standard_normal(n)
    room = bp(nz, 60, 400) * np.clip(t / 1.5, 0, 1) * np.clip((8.0 - t) / 1.0, 0, 1)
    put(room, 0.05)
    e = np.clip((t - 0.2) / 1.8, 0, 1) ** 2 * np.exp(-np.clip(t - 2.0, 0, None) / 1.6)
    put((np.sin(2 * np.pi * 36.7 * t) + 0.5 * np.sin(2 * np.pi * 55.0 * t) + 0.2 * np.sin(2 * np.pi * 110.3 * t)) * e, 0.30, 0, 0.3)
    shimmer = sum(np.sin(2 * np.pi * f * t + i) for i, f in enumerate((1760.0, 2217.5, 2637.0)))
    put(shimmer * np.sin(np.pi * np.clip((t - 0.5) / 2.7, 0, 1)) ** 2, 0.006, 0.2, 1.0)

    # transformação: cliques metálicos precisos + ar em movimento + subida discreta
    def tick(t0, pitch, g, pan):
        x = t - t0; on = x >= 0; xc = np.clip(x, 0, None)
        click = bp(rng.standard_normal(n), 2500, 9000) * np.exp(-xc / 0.004) * on
        ring = sum(a * np.sin(2 * np.pi * pitch * r * xc) for r, a in ((1, 1), (2.76, 0.4), (5.4, 0.2))) * np.exp(-xc / 0.09) * on
        put(click * 0.35 + ring * 0.25, g, pan, 0.6)

    for k, (t0, t1) in MOVES.items():
        pan = {"L": -0.5, "V1": -0.2, "D1": -0.35, "V2": 0.0, "D2": 0.3, "R": 0.5}[k]
        tick(t0, 1900, 0.06, pan)
        tick(t1, 1250 if k in ("L", "V1") else 1480, 0.10, pan)
    tick(4.6, 980, 0.07, 0.0)
    sp = np.zeros(n)
    for k, (t0, t1) in MOVES.items():
        x = np.clip((t - t0) / (t1 - t0), 0, 1)
        sp += np.sin(np.pi * x) ** 2
    put(bp(rng.standard_normal(n), 150, 1100) * sp, 0.10, 0, 0.4)
    rise = np.clip((t - 5.0) / 2.9, 0, 1) ** 2 * (t < 7.95)
    put(bp(rng.standard_normal(n), 800, 5000) * rise, 0.05, 0, 0.5)
    put(np.sin(2 * np.pi * (55 + 25 * rise) * t) * rise, 0.10, 0, 0.2)

    # silêncio absoluto antes da revelação
    gate = lp(np.where((t > 7.95) & (t < 8.3), 0.0, 1.0), 80)[:, None]
    dry *= gate; send *= gate

    # revelação (8,3 s): um único impacto grave + placa metálica, cauda longa
    x = np.clip(t - 8.3, 0, None); on = t >= 8.3
    f = 62 * np.exp(-x / 0.3) + 34
    thump = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-x / 0.7) * on
    plate = sum(a * np.sin(2 * np.pi * fr * x + ph) * np.exp(-x / d) for fr, a, d, ph in
                ((293.7, 1.0, 2.6, 0), (440.0, 0.55, 2.1, 1), (587.3, 0.35, 1.6, 2), (880.9, 0.2, 1.1, 3),
                 (1318.5, 0.12, 0.8, 4), (1761.0, 0.06, 0.6, 5))) * on * np.clip(x / 0.003, 0, 1)
    air = bp(rng.standard_normal(n), 3000, 12000) * np.exp(-x / 0.25) * on
    put(thump, 0.75, 0, 0.25)
    put(plate, 0.10, 0, 1.0)
    put(air, 0.04, 0, 1.0)
    # brilho que passa na marca (8,3–9,9 s e 11,2–13,8 s)
    for t0, t1, g in ((8.4, 9.9, 0.004), (11.2, 13.8, 0.0025)):
        env = np.sin(np.pi * np.clip((t - t0) / (t1 - t0), 0, 1)) ** 2
        put(sum(np.sin(2 * np.pi * f * t + i) for i, f in enumerate((2349.3, 2793.8, 3520.0))) * env, g, 0.3, 1.0)

    # reverb: resposta ao impulso sintética, estéreo descorrelacionado
    irt = np.arange(int(3.8 * sr)) / sr
    wet = np.zeros_like(dry)
    for c in range(2):
        ir = rng.standard_normal(len(irt)) * np.exp(-irt / 0.9)
        ir = lp(ir, 6000); ir[: int((0.018 + 0.006 * c) * sr)] = 0
        wet[:, c] = fftconvolve(send[:, c], ir)[:n] * 0.018
    mix = dry + wet
    mix *= np.clip((15.6 - t) / 1.2, 0, 1)[:, None]
    mix = np.tanh(mix / np.abs(mix).max() * 1.3) / np.tanh(1.3) * 10 ** (-1.5 / 20)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())

# ------------------------------------------------------------------ main
ASSETS = None

def _init():
    global ASSETS
    ASSETS = load_assets()

def _job(i):
    return render_frame(i).tobytes()

def main():
    os.makedirs(OUT, exist_ok=True)
    if "--preview" in sys.argv:
        _init()
        ts = [float(x) for x in sys.argv[sys.argv.index("--preview") + 1:]] or \
             [0.6, 1.5, 2.6, 3.6, 4.6, 5.8, 6.6, 7.3, 8.1, 8.6, 9.4, 12.0, 15.9]
        for s in ts:
            fr = render_frame(int(round(s * FPS)))
            Image.fromarray(fr).resize((540, 960), Image.LANCZOS).save(f"{OUT}/preview_{s:05.2f}.png")
        return
    wav = os.path.join(OUT, "som.wav")
    render_audio(wav)
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    mp4 = os.path.join(OUT, "lancamento_identidade_2026.mp4")
    cmd = [ff, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", wav,
           "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
           "-c:v", "libx264", "-profile:v", "high", "-level:v", "5.2", "-preset", "slow",
           "-crf", "14", "-tune", "film", "-x264-params", "aq-mode=3",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
           "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart", mp4]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=_init) as pool:
        for i, buf in enumerate(pool.imap(_job, range(NFRAMES), chunksize=1)):
            p.stdin.write(buf)
            if i % 30 == 0:
                print(f"quadro {i}/{NFRAMES}", flush=True)
    p.stdin.close(); p.wait()
    _init()
    dbg = {}
    Image.fromarray(render_frame(NFRAMES - 1, debug=dbg)).save(os.path.join(OUT, "ultimo_quadro.png"))
    np.save(os.path.join(OUT, "ultimo_quadro_alfa.npy"), dbg["alpha"])
    print("ok", mp4, "região da marca:", dbg["region"])

if __name__ == "__main__":
    main()
