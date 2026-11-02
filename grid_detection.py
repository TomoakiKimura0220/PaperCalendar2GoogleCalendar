"""Find long calendar rules with Hough lines, then fit an evenly spaced grid."""
import itertools
import cv2
import numpy as np
from PIL import ImageOps


def _groups(lines, vertical, width, height):
    candidates = []
    for x1,y1,x2,y2 in lines:
        dx,dy=x2-x1,y2-y1
        if vertical:
            if abs(dy)<height*.2 or abs(dx)>abs(dy)*.25: continue
            a=dx/dy; b=x1-a*y1; mid=a*height/2+b; length=abs(dy)
        else:
            if abs(dx)<width*.2 or abs(dy)>abs(dx)*.25: continue
            a=dy/dx; b=y1-a*x1; mid=a*width/2+b; length=abs(dx)
        candidates.append((mid,a,b,length))
    groups=[]
    for c in sorted(candidates):
        if groups and abs(c[0]-np.mean([p[0] for p in groups[-1]]))<min(width,height)*.006:
            groups[-1].append(c)
        else: groups.append([c])
    result=[]
    for group in groups:
        weights=np.array([c[3] for c in group])
        result.append(tuple(np.average(np.array(group),axis=0,weights=weights)))
    return result


def _sequence(groups, count, extent):
    if len(groups)<count: raise ValueError('カレンダーの罫線が十分に見つかりません')
    # Limit noisy images to the strongest rules before the bounded search.
    groups=sorted(sorted(groups,key=lambda g:g[3],reverse=True)[:16])
    best=None
    for chosen in itertools.combinations(groups,count):
        positions=np.array([c[0] for c in chosen]); gaps=np.diff(positions)
        if positions[-1]-positions[0]<extent*.5: continue
        variation=float(np.std(gaps)/np.mean(gaps))
        if variation>.12: continue
        score=variation - .02*sum(c[3] for c in chosen)/(extent*count)
        if best is None or score<best[0]: best=(score,chosen)
    if best is None: raise ValueError('等間隔のマスを確認できません。手動で四隅を指定してください')
    return best[1]


def detect_grid(image, rows):
    if rows not in (4,5,6): raise ValueError('週の行数は4〜6です')
    image=ImageOps.exif_transpose(image).convert('RGB')
    image.thumbnail((1600,1600))
    width,height=image.size
    gray=cv2.cvtColor(np.array(image),cv2.COLOR_RGB2GRAY)
    edges=cv2.Canny(gray,20,60)
    segments=cv2.HoughLinesP(edges,1,np.pi/180,threshold=50,minLineLength=int(min(width,height)*.18),maxLineGap=50)
    if segments is None: raise ValueError('罫線が見つかりません。明るく鮮明な写真で試してください')
    segments=segments.reshape(-1, 4)
    horizontal=_sequence(_groups(segments,False,width,height),rows+1,height)
    vertical=_sequence(_groups(segments,True,width,height),8,width)
    def intersect(h,v):
        _,ha,hb,_=h; _,va,vb,_=v
        x=(va*hb+vb)/(1-va*ha);y=ha*x+hb
        return [float(x/(width-1)),float(y/(height-1))]
    corners=[intersect(horizontal[0],vertical[0]),intersect(horizontal[0],vertical[-1]),intersect(horizontal[-1],vertical[-1]),intersect(horizontal[-1],vertical[0])]
    from perspective import validate_corners
    validate_corners(corners)
    return corners
