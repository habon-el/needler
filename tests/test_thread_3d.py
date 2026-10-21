import subprocess
from pathlib import Path

def test_thread_3d_stacks_crossings_not_neighbours_and_reports_findings():
    static=Path('src/embroiderly/static').resolve()
    subprocess.run(['node','-e',"""
const assert=require('node:assert/strict'),path=require('node:path');
global.window={RouteReview:require(path.join(process.argv[1],'route-review.js'))};
const {build,findings}=require(path.join(process.argv[1],'thread-3d.js'));
const s=(x,y,t='stitch',color='#ff0000')=>({x,y,t,color});
// Centre-walk underlay, then a satin column over it, then a satin crossing both.
const steps=[s(0,0)];
for(let i=0;i<=40;i++)steps.push(s(i*.25,2));
for(let i=0;i<25;i++)steps.push(s(i*.4,0),s(i*.4+.2,4));
for(let i=0;i<20;i++)steps.push(s(3.5,i*.2,'stitch','#0000ff'),s(6.5,i*.2+.1,'stitch','#0000ff'));
steps.push(s(6.5,4,'trim'),s(30,10,'jump'),s(31,10),s(45,10));
const plan={steps,origin_mm:[0,0]},before=JSON.stringify(plan);
const g=build(plan,{},.1875),mid=i=>g.lifts[4*i+1];
assert.equal(JSON.stringify(plan),before);
assert.equal(g.count,steps.filter((t,i)=>t.t==='stitch'&&i&&Math.hypot(t.x-steps[i-1].x,t.y-steps[i-1].y)>=.01).length);
assert.ok(mid(10)<.2,'underlay lies on the fabric');
const satin=g.instanceStep.findIndex(k=>k>45);
assert.ok(mid(satin)>mid(10),'satin rests on the underlay it crosses');
assert.ok(Math.max(...g.layers)<=6,'side-by-side satin does not pile up');
assert.equal(g.trims.length/5,1);assert.ok(g.jumps.length>0);
const f=findings(plan,g,.1875);
assert.ok(f.some(x=>x.kind==='long'&&/14\\.0 mm/.test(x.title)),'long stitch is reported');
assert.ok(f.every(x=>x.where.every(Number.isFinite)));
// 3D puff: satin of a puff thread domes over the foam; flat threads do not.
const puffed=[s(0,0),s(4,0),s(0,.2),s(4,.2),{x:4,y:.2,t:'color_change'},s(0,3),s(4,3),s(0,3.2),s(4,3.2)];
const p=build({steps:puffed,origin_mm:[0,0],puff:{threads:[1],foam_mm:3}},{},.1875);
const dome=i=>p.lifts[4*i+3];
assert.equal(dome(0),0);assert.ok(dome(p.count-1)>2.4,'satin over 3 mm foam rises about 2.5 mm');
assert.ok(Math.max(...p.height)>2.4,'the fabric shadow sees the foam');
// An empty plan still builds.
assert.equal(build({steps:[]},{},.2).count,0);
""",str(static)],check=True)
