"""Catalogue suggestions using CIEDE2000; never automatic recolouring.

Formula implementation: scikit-image, default kL=kC=kH=1.
Reference: Sharma, Wu & Dalal (2005), doi:10.1002/col.20070.
Built-in charts are the machine thread palettes shipped with pyembroidery
(MIT). RGB catalogue values are not calibrated measurements of physical thread.
"""
from functools import lru_cache
from importlib import import_module
from pathlib import Path
import numpy as np
from skimage.color import rgb2lab, deltaE_ciede2000

CATALOGUE=None
CHARTS={
    'Brother':'pyembroidery.EmbThreadPec',
    'Janome':'pyembroidery.EmbThreadJef',
    'Janome SEW':'pyembroidery.EmbThreadSew',
    'Husqvarna Viking':'pyembroidery.EmbThreadHus',
    'Pfaff':'pyembroidery.EmbThreadShv',
}

def colour_distance(lab1,lab2):
    return float(deltaE_ciede2000(np.asarray(lab1,dtype=float),np.asarray(lab2,dtype=float)))

@lru_cache(maxsize=None)
def chart(brand):
    """(rgb, name, code) entries of one built-in machine thread chart."""
    entries=[]
    for thread in import_module(CHARTS[brand]).get_thread_set():
        if thread is None:continue
        value=thread.color&0xFFFFFF
        entries.append(((value>>16&255,value>>8&255,value&255),thread.description or '',str(thread.catalog_number or '')))
    return tuple(entries)

def palette_file(path):
    entries=[]
    for line in Path(path).read_text().splitlines():
        parts=line.split()
        if len(parts)<5 or not all(v.isdigit() and 0<=int(v)<=255 for v in parts[:3]):continue
        entries.append((tuple(map(int,parts[:3]))," ".join(parts[3:-1]),parts[-1]))
    return entries

def rank_threads(hexcode,path=CATALOGUE,brands=None,limit=3):
    """Closest catalogue threads. A GIMP palette path, or the built-in charts."""
    if not isinstance(hexcode,str) or len(hexcode)!=7 or not hexcode.startswith("#"):
        raise ValueError("Use a six-digit RGB colour.")
    rgb=tuple(int(hexcode[i:i+2],16) for i in (1,3,5))
    if path is not None:
        path=Path(path)
        if not path.is_file(): return []
        entries=[(*entry,path.stem) for entry in palette_file(path)]
        source="Installed RGB catalogue; approximate physical match"
    else:
        entries=[(*entry,brand) for brand in (brands or CHARTS) if brand in CHARTS for entry in chart(brand)]
        source="Built-in machine thread chart (pyembroidery); approximate physical match"
    if not entries:return []
    lab=rgb2lab(np.array([e[0] for e in entries],dtype=float)[None]/255)[0]
    target=rgb2lab(np.array(rgb,dtype=float)[None,None]/255)[0,0]
    differences=deltaE_ciede2000(lab,np.broadcast_to(target,lab.shape))
    indices=sorted(range(len(entries)),key=lambda i:(float(differences[i]),entries[i][3],entries[i][2],i))[:limit]
    return [dict(brand=entries[i][3],name=entries[i][1],code=entries[i][2],hex="#%02x%02x%02x"%entries[i][0],
        delta_e=round(float(differences[i]),2),method="CIEDE2000",source=source) for i in indices]
