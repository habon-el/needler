"""Re-space only straight, forward machine-grid runs with undersized spans.

Keep every corner, reversal, coincident penetration and command boundary.
There is no simplification tolerance: replacement segments cover exactly the
same line, with integer 0.1 mm coordinates. Short corner legs remain unresolved.
"""
import math
import pyembroidery as emb


def repair(pattern, minimum_mm, maximum_mm):
    source=pattern.stitches
    output=[s[:] for s in source]
    counts={'straight_runs':0,'removed_penetrations':0,'repositioned_penetrations':0}
    runs=[];start=None;direction=None
    def flush(end):
        if start is not None and end>start+1:runs.append((start,end))
    for i in range(1,len(source)):
        a,b=source[i-1],source[i]
        # Only consecutive ordinary stitches; preserve flags and event points.
        if a[2]!=emb.STITCH or b[2]!=emb.STITCH:
            flush(i-1);start=None;direction=None;continue
        dx,dy=b[0]-a[0],b[1]-a[1]
        if not all(float(v).is_integer() for v in (*a[:2],*b[:2])):
            raise ValueError('Spacing repair requires decoded machine-grid coordinates.')
        divisor=math.gcd(int(abs(dx)),int(abs(dy)))
        if not divisor:
            flush(i-1);start=None;direction=None;continue
        unit=(int(dx)//divisor,int(dy)//divisor)
        if unit!=direction:
            flush(i-1);start=i-1;direction=unit
    flush(len(source)-1)
    # Reverse splice order keeps the original command indices stable.
    for first,last in reversed(runs):
        points=source[first:last+1]
        lengths=[math.dist(a[:2],b[:2])/10 for a,b in zip(points,points[1:])]
        if not any(0<d<minimum_mm-1e-8 for d in lengths):continue
        a,b=points[0],points[-1];dx,dy=int(b[0]-a[0]),int(b[1]-a[1])
        steps=math.gcd(abs(dx),abs(dy));ux,uy=dx//steps,dy//steps
        step_mm=math.hypot(ux,uy)/10
        low=math.ceil((minimum_mm-1e-8)/step_mm)
        high=math.floor((maximum_mm+1e-8)/step_mm)
        if high<low:continue
        least=math.ceil(steps/high);most=steps//low
        if least>most:continue
        segments=min(max(len(points)-1,least),most)
        quotient,remainder=divmod(steps,segments)
        new=[a[:]];offset=0
        for j in range(segments):
            offset+=quotient+(j<remainder)
            new.append([a[0]+ux*offset,a[1]+uy*offset,emb.STITCH])
        counts['straight_runs']+=1
        counts['removed_penetrations']+=max(0,len(points)-len(new))
        counts['repositioned_penetrations']+=sum(p[:2]!=q[:2] for p,q in zip(points[1:-1],new[1:-1]))
        output[first:last+1]=new
    pattern.stitches=output
    return counts
