"""Confere o último quadro contra o arquivo oficial da nova marca.

1. Alfa (silhueta) usado no último quadro  x  alfa do arquivo oficial na mesma escala: deve ser idêntico.
2. Silhueta extraída do quadro final (do PNG e do MP4), reduzida à escala do arquivo, x arquivo oficial.
3. Imagem lado a lado para conferência visual.
"""
import numpy as np
from PIL import Image
from render import load_assets, W, H

A = load_assets()
nova = Image.open("assets/logo_nova_oficial.webp")
ox, oy = map(int, A["nova_off"]); nf = A["nova_final_f"]
ref = np.zeros((H, W), np.float32); ref[oy:oy + nf.shape[0], ox:ox + nf.shape[1]] = nf

alpha = np.load("saida/ultimo_quadro_alfa.npy")
import render
dbg = {}; render.ASSETS = A
render.render_frame(render.NFRAMES - 1, debug=dbg)
x0, y0, x1, y1 = dbg["region"]
full = np.zeros((H, W), np.float32); full[y0:y1, x0:x1] = dbg["alpha"]
print("1) alfa do último quadro x arquivo oficial: diferença máxima =", float(np.abs(full - ref).max()))

orig_a = np.asarray(nova)[..., 3].astype(np.float32) / 255
for name in ("saida/ultimo_quadro.png", "saida/ultimo_quadro_do_mp4.png"):
    fr = np.asarray(Image.open(name).convert("L"), np.float32)
    crop = fr[oy:oy + nf.shape[0], ox:ox + nf.shape[1]]
    bg = np.median(crop[nf < 0.01]); ink = np.percentile(crop[nf > 0.99], 5)
    est = np.clip((crop - bg) / (ink - bg), 0, 1)
    est_o = np.asarray(Image.fromarray(est).resize(nova.size, Image.LANCZOS))
    sil_f, sil_o = est_o > 0.5, orig_a > 0.5
    iou = (sil_f & sil_o).sum() / (sil_f | sil_o).sum()
    print(f"2) {name}: silhueta x arquivo oficial (escala original) IoU = {iou:.4f}; "
          f"pixels divergentes = {100 * (sil_f ^ sil_o).mean():.3f}% (borda do bisel, que o sombreamento escurece; a forma usada é a do item 1)")

final = Image.open("saida/ultimo_quadro.png").convert("RGB").crop((ox, oy, ox + nf.shape[1], oy + nf.shape[0])).resize(nova.size, Image.LANCZOS)
orig = Image.new("RGB", nova.size, (255, 255, 255)); orig.paste(nova, (0, 0), nova)
side = Image.new("RGB", (nova.width * 2 + 40, nova.height), (128, 128, 128))
side.paste(orig, (0, 0)); side.paste(final, (nova.width + 40, 0))
side.save("saida/comparacao_oficial_x_ultimo_quadro.png")
