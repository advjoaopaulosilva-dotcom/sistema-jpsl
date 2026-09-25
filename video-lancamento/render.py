"""Filme de lançamento — nova identidade visual de João Paulo Silva Lopes.

Renderiza video-lancamento/saida/lancamento_identidade_2026.mp4
(9:16, 2160x3840, 30 fps, H.264 + AAC).

Uso:  python3 render.py            (render completo)
      python3 render.py --preview   (quadros-chave em PNG, sem vídeo)

Dependências: pillow, numpy, imageio-ffmpeg (fornece o binário do ffmpeg).
"""
import os, sys, subprocess, wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from geometry import OLD, NEW, OLD_COLLAPSE, OLD_INK

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "saida")
W, H, FPS, DUR = 2160, 3840, 30, 16.0
NFRAMES = int(DUR * FPS)
F0 = np.array([W / 2, H / 2])

PAPEL = np.array([245, 244, 240], np.float32)
GRAFITE = np.array([59, 64, 72], np.float32)
LATAO = np.array([164, 142, 106], np.float32)
NOVA_INK = np.array([0, 0, 0], np.float32)  # cor do arquivo oficial (preto 100%)

# ------------------------------------------------------------------ util
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))

def seg(t, t0, t1):
    return clamp((t - t0) / (t1 - t0))

def ease(x):  # easeInOutCubic
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2

def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3

def ease_sine(x):
    x = clamp(x)
    return 0.5 - 0.5 * np.cos(np.pi * x)

# ------------------------------------------------------------------ assets
def load_assets():
    A = {}
    # Nova marca oficial: usada sem qualquer alteração, apenas escala uniforme.
    nova = Image.open(os.path.join(HERE, "assets/logo_nova_oficial.webp"))
    assert nova.mode == "RGBA"
    rgb = np.asarray(nova)[..., :3]
    al = np.asarray(nova)[..., 3]
    assert (rgb[al > 0] == 0).all(), "a nova marca deveria ser tinta preta"
    A["nova_alpha"] = nova.getchannel("A")
    ys, xs = np.where(al > 0)
    bbox_c = ((xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2)
    A["sn"] = 0.75                                   # 2000 px -> 1500 px (margem > 1/3 do símbolo)
    nw, nh = round(nova.width * A["sn"]), round(nova.height * A["sn"])
    A["nova_final"] = A["nova_alpha"].resize((nw, nh), Image.LANCZOS)
    A["nova_off"] = np.array([round(F0[0] - bbox_c[0] * A["sn"]), round(F0[1] - bbox_c[1] * A["sn"])], float)
    A["nova_split"] = 900                              # linha (px do arquivo) entre símbolo e texto

    # Marca antiga: o próprio JPEG, ampliado por reamostragem + limiar suave
    # (isola a tinta do fundo sem redesenhar nenhuma forma).
    old = Image.open(os.path.join(HERE, "assets/logo_antiga.jpg")).convert("L")
    A["so"] = 2.65
    ys, xs = np.where(np.asarray(old) < 146)
    ob = ((xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2)
    A["old_off"] = F0 - np.array(ob) * A["so"]
    A["old_split"] = 280                               # coluna (px do arquivo) entre símbolo e texto
    big = old.filter(ImageFilter.GaussianBlur(0.45)).resize((old.width * 8, old.height * 8), Image.LANCZOS)
    L = np.asarray(big, np.float32)
    a = np.clip((243 - L) / (243 - 46), 0, 1)
    a = np.clip((a - 0.5) * 3.0 + 0.5, 0, 1)
    a = a * a * (3 - 2 * a)
    old_a = Image.fromarray((a * 255).astype(np.uint8))
    A["old_levels"] = {8: old_a, 4: old_a.resize((old.width * 4, old.height * 4), Image.LANCZOS),
                       2: old_a.resize((old.width * 2, old.height * 2), Image.LANCZOS)}

    yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32) * 4
    A["r2"] = ((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2
    A["xx"], A["yy"] = xx, yy
    rng = np.random.default_rng(2026)
    A["dither"] = (rng.random((H, W), np.float32) + rng.random((H, W), np.float32) - 1.0) * 1.2
    return A

# ------------------------------------------------------------------ timeline
def camera(t):
    """(centro no mundo, zoom). Identidade exata a partir de 14 s."""
    macro_c = np.array([655.0, 1640.0])           # cruzamento das diagonais com a haste (marca antiga)
    if t < 2.0:
        k = seg(t, 0, 2.0)
        c = macro_c + np.array([-70 + 120 * ease_sine(k), 40 * ease_sine(k)])
        return c, 3.0 - 0.25 * ease_sine(k)
    if t < 4.0:
        k = ease(seg(t, 2.0, 3.85))
        c0 = macro_c + np.array([50, 40])
        return c0 + (F0 - c0) * k, 2.75 + (1.0 - 2.75) * k
    if t < 14.0:
        cx = F0[0] + 16 * np.sin(np.pi * seg(t, 4.0, 11.0))
        z = 1.0 - 0.025 * ease(seg(t, 4.0, 8.0))
        z += 0.025 * ease_out(seg(t, 11.0, 14.0))
        return np.array([cx, F0[1]]), z
    return F0.copy(), 1.0

MOVES = {  # traço: (início, fim) do movimento
    "L": (5.3, 6.2), "V1": (5.5, 6.6),
    "D1": (6.15, 7.7), "V2": (6.25, 7.78), "D2": (6.35, 7.85), "R": (6.55, 7.95),
}

OLD_SYM_C, OLD_SYM_H = np.array([137.0, 183.0]), 346.0
NEW_SYM_C, NEW_SYM_H = np.array([1017.0, 441.5]), 721.0

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

# ------------------------------------------------------------------ drawing
def to_frame(pts, cam):
    c, z = cam
    return (np.asarray(pts) - c) * z + F0

def raster_layer(img, s, off, cam, k=1.0):
    """Coloca uma imagem de alfa (em px do arquivo * k) no quadro via câmera."""
    c, z = cam
    a = k / (s * z)
    cx = k * ((-F0[0]) / z + c[0] - off[0]) / s
    cy = k * ((-F0[1]) / z + c[1] - off[1]) / s
    return img.transform((W, H), Image.AFFINE, (a, 0, cx, 0, a, cy), Image.BICUBIC)

def old_layer(A, cam, part):
    s, z = A["so"], cam[1]
    lvl = min((l for l in (2, 4, 8) if l / (s * z) >= 0.75), default=8)
    img = A["old_levels"][lvl]
    split = A["old_split"] * lvl
    if part == "sym":
        img = img.crop((0, 0, split, img.height))
    else:
        img = Image.composite(img, Image.new("L", img.size, 0), _right_mask(img.size, split))
    return raster_layer(img, s, A["old_off"], cam, lvl)

_masks = {}
def _right_mask(size, split):
    key = (size, split)
    if key not in _masks:
        m = Image.new("L", size, 0)
        ImageDraw.Draw(m).rectangle((split, 0, size[0], size[1]), fill=255)
        _masks[key] = m
    return _masks[key]

def draw_quads(quads, cam, SS=3):
    out = np.zeros((H, W), np.float32)
    if not quads:
        return out
    fr = [(to_frame(q, cam), a) for q, a in quads]
    allp = np.concatenate([q for q, _ in fr])
    x0, y0 = np.floor(allp.min(0)).astype(int) - 4
    x1, y1 = np.ceil(allp.max(0)).astype(int) + 4
    x0, y0 = max(x0, 0), max(y0, 0)
    x1, y1 = min(x1, W), min(y1, H)
    if x1 <= x0 or y1 <= y0:
        return out
    for q, a in fr:  # cada traço é opaco; alfas diferentes só nos que estão saindo
        m = Image.new("L", ((x1 - x0) * SS, (y1 - y0) * SS), 0)
        ImageDraw.Draw(m).polygon([((x - x0) * SS, (y - y0) * SS) for x, y in q], fill=255)
        m = np.asarray(m.resize((x1 - x0, y1 - y0), Image.BOX), np.float32) / 255 * a
        sub = out[y0:y1, x0:x1]
        out[y0:y1, x0:x1] = sub + m * (1 - sub)
    return out

def lowres_up(arr):
    return np.asarray(Image.fromarray(arr.astype(np.float32), "F").resize((W, H), Image.BILINEAR))

def band(A, t, t0, t1, angle=-0.35, width=260.0):
    """Faixa de luz diagonal que atravessa o quadro entre t0 e t1 (baixa resolução)."""
    k = seg(t, t0, t1)
    if k <= 0 or k >= 1:
        return None
    ca, sa = np.cos(angle), np.sin(angle)
    s = A["xx"] * ca + A["yy"] * sa
    smin, smax = -H * abs(sa) - 400, W * ca + 400
    pos = smin + (smax - smin) * ease_sine(k)
    return np.exp(-((s - pos) / width) ** 2) * np.sin(np.pi * k)

# ------------------------------------------------------------------ frame
def render_frame(i, A=None):
    A = A or ASSETS
    t = i / FPS
    cam = camera(t)
    final = t >= 14.0

    # fundo: Papel com vinheta muito suave; a luz "abre" na revelação (8,3 s)
    vig = 0.085 - 0.055 * ease(seg(t, 8.3, 9.8))
    light = 1.0 - vig * A["r2"]
    lb = band(A, t, 0.4, 2.8, width=380) if t < 3 else band(A, t, 8.3, 10.2, width=420)
    if lb is not None:
        light = light + 0.018 * lb
    bg = lowres_up(light)[..., None] * PAPEL

    layers = []  # (alfa HxW, cor rgb, se recebe a faixa de luz)
    # marca antiga (raster)
    old_op = ease_sine(seg(t, 0.5, 1.9)) * (1 - seg(t, 4.3, 4.7))
    if old_op > 0:
        a = np.asarray(old_layer(A, cam, "sym"), np.float32) / 255
        txt_op = ease_sine(seg(t, 0.5, 1.9)) * (1 - ease_sine(seg(t, 3.95, 4.7)))
        if txt_op > 0:
            a = a * old_op + np.asarray(old_layer(A, cam, "txt"), np.float32) / 255 * txt_op
        else:
            a = a * old_op
        # profundidade de campo: faixa de foco na macro, que se abre no recuo
        blur_amt = 1 - ease(seg(t, 2.2, 3.6))
        if blur_amt > 0:
            small = Image.fromarray((a * 255).astype(np.uint8)).resize((W // 4, H // 4), Image.BOX)
            bl = np.asarray(small.filter(ImageFilter.GaussianBlur(3 + 5 * blur_amt)), np.float32) / 255
            bl = lowres_up(bl)
            fy = 1560 + 260 * ease_sine(seg(t, 0, 2.2))
            d = (A["yy"] - (fy - 0.35 * (A["xx"] - W / 2))) / (H * 0.10)
            focus = np.exp(-d ** 2)
            m = lowres_up(1 - blur_amt * (1 - focus)) * (1 - 0.6 * blur_amt * (1 - seg(t, 0, 1.2)))
            a = a * m + bl * (1 - m)
        layers.append((a, np.array(OLD_INK, np.float32), True))

    # traços vetoriais (transformação)
    vec_op = seg(t, 4.3, 4.7) * (1 - seg(t, 8.35, 8.8))
    if vec_op > 0:
        a = draw_quads(vector_quads(t, A), cam) * vec_op
        col = np.array(OLD_INK, np.float32) * (1 - ease(seg(t, 6.2, 8.0)))
        layers.append((a, col, True))

    # nova marca — arquivo oficial
    if t >= 8.35:
        if final:
            a = np.zeros((H, W), np.float32)
            nf = A["nova_final"]
            ox, oy = map(int, A["nova_off"])
            a[oy:oy + nf.height, ox:ox + nf.width] = np.asarray(nf, np.float32) / 255
        else:
            if abs(cam[1] - 1) < 1e-9 and np.allclose(cam[0], F0):
                a = np.zeros((H, W), np.float32)
                nf = A["nova_final"]; ox, oy = map(int, A["nova_off"])
                a[oy:oy + nf.height, ox:ox + nf.width] = np.asarray(nf, np.float32) / 255
            else:
                a = np.asarray(raster_layer(A["nova_final"], 1.0, A["nova_off"], cam), np.float32) / 255
            sym_op = ease_sine(seg(t, 8.35, 8.8))
            # texto revelado por máscara suave (esquerda -> direita)
            k = ease(seg(t, 8.8, 10.4))
            split_y = to_frame([[0, A["nova_off"][1] + A["nova_split"] * A["sn"]]], cam)[0][1]
            xs = A["xx"][0]
            lx0, lx1 = to_frame([[A["nova_off"][0], 0], [A["nova_off"][0] + 2000 * A["sn"], 0]], cam)[:, 0]
            front = lx0 - 300 + (lx1 - lx0 + 600) * k
            row = np.clip((front - xs) / 300, 0, 1)
            mtxt = np.repeat(row[None, :], H // 4, 0)
            is_txt = (A["yy"] > split_y).astype(np.float32)
            m = lowres_up(is_txt * mtxt + (1 - is_txt) * sym_op)
            a = a * m
        layers.append((a, NOVA_INK, not final))

    # sombra muito suave (estrutura física), some depois da revelação
    sh_amt = 0.11 * (1 - ease(seg(t, 8.3, 10.0)))
    img = bg
    if layers and sh_amt > 0:
        u = np.zeros((H, W), np.float32)
        for a, _, _ in layers:
            u = u + a * (1 - u)
        small = Image.fromarray((u * 255).astype(np.uint8)).resize((W // 4, H // 4), Image.BOX)
        small = small.transform(small.size, Image.AFFINE, (1, 0, 0, 0, 1, -4 * cam[1]), Image.BILINEAR)
        sh = lowres_up(np.asarray(small.filter(ImageFilter.GaussianBlur(9)), np.float32) / 255)
        img = img * (1 - sh_amt * sh)[..., None]

    # faixa de luz sobre a tinta (latão só na revelação, muito discreto)
    ib = None
    if 0.4 < t < 2.8:
        ib, lift, amt = band(A, t, 0.4, 2.8, width=300), GRAFITE + 50, 0.45
    elif 8.3 < t < 10.2:
        ib, lift, amt = band(A, t, 8.3, 10.2, width=320), LATAO, 0.22
    elif 11.2 < t < 13.8:
        ib, lift, amt = band(A, t, 11.2, 13.8, width=340), GRAFITE + 40, 0.16
    ibf = lowres_up(ib)[..., None] if ib is not None else None

    for a, col, lit in layers:
        c = np.broadcast_to(col, (H, W, 3))
        if lit and ibf is not None:
            c = c + (lift - col) * (amt * ibf)
        img = img * (1 - a[..., None]) + c * a[..., None]

    # dithering finíssimo: evita faixas na vinheta após a compressão 8 bits.
    # Proporcional ao brilho, então a tinta preta da marca não é afetada.
    # Padrão fixo (o fundo não se move na tela), para não custar taxa de bits.
    img = img + (A["dither"] * (img.mean(2) / 245.0))[..., None]
    return np.clip(img + 0.5, 0, 255).astype(np.uint8)

# ------------------------------------------------------------------ audio
def render_audio(path, sr=48000):
    n = int(DUR * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(7)
    L = np.zeros(n); R = np.zeros(n)

    def env(t0, a, d):
        x = t - t0
        return np.where(x < 0, 0, np.where(x < a, x / a, np.exp(-(x - a) / d)))

    def lp(x, fc):
        k = int(sr / fc)
        return np.convolve(x, np.ones(k) / k, "same")

    def add(sig, g=1.0, pan=0.0):
        L[:] += sig * g * (1 - pan) ** 0.5
        R[:] += sig * g * (1 + pan) ** 0.5

    # grave muito discreto quando a marca antiga aparece
    e = np.clip((t - 0.9) / 1.4, 0, 1) ** 2 * np.exp(-np.clip(t - 2.3, 0, None) / 1.1)
    add((np.sin(2 * np.pi * 41 * t) + 0.35 * np.sin(2 * np.pi * 82.3 * t)) * e, 0.22)

    # sons precisos: início e pouso de cada traço
    def tick(t0, pitch, g, pan):
        x = t - t0
        on = x >= 0
        nz = rng.standard_normal(n)
        click = (nz - lp(nz, 2500)) * np.exp(-np.clip(x, 0, None) / 0.006) * on
        ring = np.sin(2 * np.pi * pitch * x) * np.exp(-np.clip(x, 0, None) / 0.07) * on
        add(click * 0.25 + ring * 0.35, g, pan)

    for k, (t0, t1) in MOVES.items():
        pan = {"L": -0.5, "V1": -0.2, "D1": -0.3, "V2": 0.0, "D2": 0.25, "R": 0.45}[k]
        tick(t0, 1850, 0.05, pan)
        tick(t1, 1240 if k in ("L", "V1") else 1480, 0.08, pan)

    # movimento: ar filtrado seguindo a velocidade das linhas
    sp = np.zeros(n)
    for k, (t0, t1) in MOVES.items():
        x = np.clip((t - t0) / (t1 - t0), 0, 1)
        sp += np.sin(np.pi * x) ** 2
    nz = rng.standard_normal(n)
    air = lp(nz, 900) - lp(nz, 180)
    add(air * sp * 0.5, 0.35)

    # silêncio absoluto antes da revelação
    gate = np.where((t > 7.95) & (t < 8.3), 0.0, 1.0)
    gate = lp(gate, 60)
    L *= gate; R *= gate

    # impacto único na revelação (8,3 s)
    x = np.clip(t - 8.3, 0, None); on = t >= 8.3
    f = 58 * np.exp(-x / 0.35) + 38
    thump = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-x / 0.45) * on
    bell = sum(g * np.sin(2 * np.pi * fr * x) * np.exp(-x / d) for fr, g, d in
               ((392.0, 1.0, 1.8), (784.6, 0.45, 1.2), (1176.0, 0.22, 0.8), (1569.5, 0.12, 0.6))) * on
    bell *= np.clip(x / 0.004, 0, 1)
    hit = thump * 0.55 + bell * 0.12
    ir_t = np.arange(int(2.6 * sr)) / sr
    irL = rng.standard_normal(len(ir_t)) * np.exp(-ir_t / 0.55); irR = rng.standard_normal(len(ir_t)) * np.exp(-ir_t / 0.55)
    irL[: int(0.02 * sr)] = 0; irR[: int(0.025 * sr)] = 0
    src = bell * 0.12 + thump * 0.1
    i0 = int(8.3 * sr)
    wetL = np.convolve(src[i0:], irL)[: n - i0] * 0.012
    wetR = np.convolve(src[i0:], irR)[: n - i0] * 0.012
    L += hit; R += hit
    L[i0:] += wetL; R[i0:] += wetR

    # depois, silêncio
    fade = np.clip((13.5 - t) / 2.0, 0, 1)
    L *= fade; R *= fade
    peak = max(np.abs(L).max(), np.abs(R).max())
    st = np.stack([L, R], 1) / peak * 10 ** (-3 / 20)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((st * 32767).astype(np.int16).tobytes())

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
        for ts in (0.3, 1.2, 2.0, 3.0, 4.0, 5.0, 5.9, 6.4, 6.9, 7.4, 8.1, 8.6, 9.6, 15.9):
            fr = render_frame(int(round(ts * FPS)))
            Image.fromarray(fr).resize((540, 960), Image.LANCZOS).save(f"{OUT}/preview_{ts:05.2f}.png")
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
        for i, buf in enumerate(pool.imap(_job, range(NFRAMES), chunksize=2)):
            p.stdin.write(buf)
            if i % 30 == 0:
                print(f"quadro {i}/{NFRAMES}", flush=True)
    p.stdin.close(); p.wait()
    # último quadro, sem compressão, para conferência
    _init()
    Image.fromarray(render_frame(NFRAMES - 1)).save(os.path.join(OUT, "ultimo_quadro.png"))
    print("ok", mp4)

if __name__ == "__main__":
    main()
