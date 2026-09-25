"""Geometria das duas marcas, medida diretamente nos arquivos oficiais.
Cada traço é um quadrilátero [inicioA, fimA, fimB, inicioB] (A e B = bordas longas),
em coordenadas de pixel do próprio arquivo. Serve apenas para a animação de transição;
os quadros finais usam o arquivo oficial da nova marca, sem alteração."""

# Marca antiga — assets/logo_antiga.jpg (640x364)
OLD = {
    "D1": [(39, 177), (168, 306), (168, 330), (15, 176)],   # diagonal inferior esquerda
    "V2": [(152, 314), (152, 10), (168, 25), (168, 330)],   # haste vertical direita
    "D2": [(106, 33), (259, 186), (236, 186), (106, 56)],   # diagonal superior direita
    "R":  [(259, 186), (183, 262), (183, 240), (236, 186)], # braço inferior do vértice direito
    "L":  [(92, 100), (15, 176), (39, 177), (92, 122)],     # braço superior do vértice esquerdo
    "V1": [(106, 340), (106, 33), (122, 49), (122, 356)],   # haste vertical esquerda
}
OLD_INK = (45, 55, 70)

# Nova marca — assets/logo_nova_oficial.webp (2000x1688)
NEW = {
    "D1": [(703, 429), (979.5, 705.5), (1020.5, 804.5), (674, 458)],
    "V2": [(979.5, 705.5), (979.5, 80.5), (1020.5, 180.5), (1020.5, 804.5)],
    "D2": [(979.5, 80.5), (1362, 463), (1262, 422), (1020.5, 180.5)],
    "R":  [(1362, 463), (1054, 463), (1054, 422), (1262, 422)],
}
# Traços que saem: L recolhe até o vértice esquerdo; V1 desliza e funde-se em V2.
OLD_COLLAPSE = {
    "L":  [(15, 176), (15, 176), (39, 177), (39, 177)],
    "V1": OLD["V2"],
}
