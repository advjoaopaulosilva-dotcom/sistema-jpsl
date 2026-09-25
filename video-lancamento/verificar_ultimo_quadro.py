"""Confere o último quadro contra o arquivo oficial da nova marca."""
import numpy as np; from PIL import Image
from render import load_assets, PAPEL
A = load_assets()
nova = Image.open('assets/logo_nova_oficial.webp')
ox, oy = map(int, A['nova_off']); nf = A['nova_final']
ref_a = np.zeros((3840, 2160), np.float32); ref_a[oy:oy+nf.height, ox:ox+nf.width] = np.asarray(nf, np.float32)/255
for name in ('saida/ultimo_quadro.png', 'saida/ultimo_quadro_do_mp4.png'):
    fr = np.asarray(Image.open(name).convert('RGB'), np.float32)
    # alfa da tinta recuperado do quadro (fundo local estimado fora da tinta)
    bg = fr[oy-20, ox-20]
    est = 1 - fr.mean(2) / bg.mean()
    reg = (slice(oy, oy+nf.height), slice(ox, ox+nf.width))
    d = np.abs(est[reg] - ref_a[reg])
    print(name, 'erro médio de alfa %.4f  | pixels com erro >0.15: %.4f%%' % (d.mean(), 100*(d > .15).mean()),
          '| tinta 100%% no quadro: RGB', fr[reg][ref_a[reg] > .999].mean(0).round(1))
    # recorte do quadro reduzido à escala do arquivo, lado a lado com o original
    crop = Image.open(name).convert('RGB').crop((ox, oy, ox+nf.width, oy+nf.height)).resize(nova.size, Image.LANCZOS)
    orig = Image.new('RGB', nova.size, tuple(int(v) for v in PAPEL)); orig.paste(nova, (0, 0), nova)
    diff = np.abs(np.asarray(crop, np.float32) - np.asarray(orig, np.float32)).mean(2)
    print('   vs arquivo oficial na escala original: dif. média %.2f/255, máx. região >40: %.4f%%' % (diff.mean(), 100*(diff > 40).mean()))
side = Image.new('RGB', (2000*2+40, 1688), (255, 255, 255))
side.paste(orig, (0, 0)); side.paste(crop, (2040, 0)); side.save('saida/comparacao_oficial_x_ultimo_quadro.png')
