"""Catalogue suggestions using CIEDE2000; never automatic recolouring.

Formula implementation: scikit-image, default kL=kC=kH=1.
Reference: Sharma, Wu & Dalal (2005), doi:10.1002/col.20070.
RGB catalogue values are not calibrated measurements of physical thread.
"""
from pathlib import Path
import numpy as np
from skimage.color import rgb2lab, deltaE_ciede2000

CATALOGUE=Path("/opt/inkstitch/palettes/InkStitch Madeira Rayon.gpl")

def colour_distance(lab1,lab2):
    return float(deltaE_ciede2000(np.asarray(lab1,dtype=float),np.asarray(lab2,dtype=float)))

def rank_threads(hexcode,path=CATALOGUE):
    if not isinstance(hexcode,str) or len(hexcode)!=7 or not hexcode.startswith("#"):
        raise ValueError("Use a six-digit RGB colour.")
    rgb=tuple(int(hexcode[i:i+2],16) for i in (1,3,5))
    path=Path(path)
    if not path.is_file(): return []
    entries=[]
    for line in path.read_text().splitlines():
        parts=line.split()
        if len(parts)<5 or not all(v.isdigit() and 0<=int(v)<=255 for v in parts[:3]):continue
        entries.append((tuple(map(int,parts[:3]))," ".join(parts[3:-1]),parts[-1]))
    if not entries:return []
    lab=rgb2lab(np.array([e[0] for e in entries],dtype=float)[None]/255)[0]
    target=rgb2lab(np.array(rgb,dtype=float)[None,None]/255)[0,0]
    differences=deltaE_ciede2000(lab,np.broadcast_to(target,lab.shape))
    indices=sorted(range(len(entries)),key=lambda i:(float(differences[i]),entries[i][2],i))[:3]
    return [dict(brand="Madeira Rayon" if path==CATALOGUE else path.stem,
        name=entries[i][1],code=entries[i][2],hex="#%02x%02x%02x"%entries[i][0],
        delta_e=round(float(differences[i]),2),method="CIEDE2000",
        source="Installed RGB catalogue; approximate physical match") for i in indices]
