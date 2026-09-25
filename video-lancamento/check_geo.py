from PIL import Image, ImageDraw; import numpy as np; from geometry import *
def ov(img_alpha, polys, S, out):
    m=Image.new('L',(img_alpha.shape[1],img_alpha.shape[0]),0);d=ImageDraw.Draw(m)
    for q in polys: d.polygon([(x*S,y*S) for x,y in q],fill=255)
    o=img_alpha;v=np.asarray(m)>128
    rgb=np.full(o.shape+(3,),255,np.uint8);rgb[o&v]=(80,80,80);rgb[o&~v]=(255,0,0);rgb[~o&v]=(0,120,255)
    Image.fromarray(rgb).save(out);print(out,(o&~v).sum(),(~o&v).sum(),o.sum())
P='/tmp/claude-0/-home-user-sistema-jpsl/bdd4dea5-8328-58af-bf9d-8dfd690cdfea/scratchpad/'
o=Image.open('assets/logo_antiga.jpg').convert('L').crop((0,0,280,364));S=4
ov(np.asarray(o.resize((280*S,364*S),Image.LANCZOS))<146,OLD.values(),S,P+'ovo.png')
n=np.asarray(Image.open('assets/logo_nova_oficial.webp'))[:900,:,3]>128
ov(n,NEW.values(),1,P+'ovn.png')
