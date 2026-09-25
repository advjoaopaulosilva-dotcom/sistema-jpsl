# Filme de lançamento — Identidade Visual 2026

`saida/lancamento_identidade_2026.mp4` — 16 s, 9:16, 2160×3840, 30 fps, H.264 High + AAC.

| Arquivo | Função |
|---|---|
| `assets/logo_antiga.jpg` | marca antiga (arquivo fornecido) |
| `assets/logo_nova_oficial.webp` | nova marca oficial (arquivo fornecido, usado sem alteração) |
| `geometry.py` | traços das duas marcas medidos nos arquivos, usados só na transformação |
| `render.py` | animação, câmera, luz, som e codificação |
| `check_geo.py` | sobrepõe a geometria medida aos arquivos originais |
| `verificar_ultimo_quadro.py` | compara o último quadro com o arquivo oficial |

```
pip install pillow numpy imageio-ffmpeg
python3 render.py --preview   # quadros-chave em PNG
python3 render.py             # vídeo completo (~4 min em 4 núcleos)
python3 verificar_ultimo_quadro.py
```
