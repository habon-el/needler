import subprocess
from pathlib import Path

def test_route_review_preserves_commands_and_distinguishes_travel():
    script=Path('src/embroiderly/static/route-review.js').resolve()
    subprocess.run(['node','-e',"""
const assert=require('node:assert/strict'),{analyze}=require(process.argv[1]);
const p={steps:[{x:20,y:0,t:'jump',color:'#000000'},
 {x:22,y:0,t:'stitch',color:'#000000'},
 {x:20,y:0,t:'stitch',color:'#000000'},
 {x:22,y:0,t:'stitch',color:'#000000'},
 {x:40,y:0,t:'stitch',color:'#000000'}]};
const before=JSON.stringify(p),r=analyze(p);
assert.equal(r.jumps,1);assert.equal(r.flags.length,2);
assert.equal(r.flags[0].index,3);assert.equal(r.flags[1].index,4);
assert.equal(JSON.stringify(p),before);
assert.equal(analyze({steps:[]}).flags.length,0);
const ties={steps:Array.from({length:10},(_,i)=>({x:i%2*.1,y:0,t:'stitch',color:'#000000'}))};
assert.equal(analyze(ties).flags.length,0);
""",str(script)],check=True)
