/* Stitch edits, under the playback controls: at the stitch playback has reached,
   add a machine stop or a thread cut, delete that stitch or move it a little
   (stitch_edits.py). Saved with the design like Remove stitches, and undoable. */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 const studio=window.embroideryStudio,transport=document.querySelector('.transport');
 if(!studio||!transport||window.nativeTextConfig)return;
 const NAMES={stop:'Stop',trim:'Cut',delete:'Deleted stitch',move:'Moved stitch'},MAX_MOVE_MM=3;
 const box=document.createElement('div');box.className='stitch-edits';box.hidden=true;
 box.innerHTML=`<div class="stitch-edit-actions"><span class="muted">At this stitch:</span>
  <button type="button" data-kind="stop" title="The machine pauses here, for example to lay appliqué fabric or foam">Add stop here</button>
  <button type="button" data-kind="trim" title="The thread is tied off and cut here">Add cut here</button>
  <button type="button" data-kind="delete">Delete this stitch</button>
  <button type="button" data-kind="move" title="Then click where it should go, up to 3 mm away">Move this stitch</button></div>
  <ul class="stitch-edit-list"></ul><p class="muted stitch-edit-note" hidden></p>`;
 transport.after(box);
 const list=box.querySelector('.stitch-edit-list'),note=box.querySelector('.stitch-edit-note');
 const say=text=>(window.studioStatus||(()=>{}))(text);
 const saved=()=>studio.snapshot().stitch_edits||[];
 // The last sewn stitch at the playback position, with its place in the sewing order.
 function current(){
  const view=studio.playbackView();if(!view)return null;
  const steps=view.plan.steps;let k=Math.min(view.cursor,steps.length)-1;
  while(k>=0&&steps[k].t!=='stitch')k--;
  if(k<0)return null;
  let n=0;for(let i=0;i<=k;i++)if(steps[i].t==='stitch')n++;
  return {x:steps[k].x,y:steps[k].y,n};
 }
 function save(list,message){
  try{studio.acceptRefinement({stitch_edits:list});say(message)}catch(error){say(error.message)}
 }
 function add(edit,message){save([...saved(),edit],message)}
 let picking=null;
 function stopPicking(){if(picking){window.removeEventListener('pointerdown',picking.handler,true);document.removeEventListener('keydown',picking.key);picking=null}}
 function move(at){
  const view=studio.playbackView(),size=studio.imageSize();
  const canvas=[...document.querySelectorAll('canvas')].find(c=>c.offsetParent&&c.width>200&&!c.closest('.thread-3d'));
  if(!view||!size.height||!canvas){say('Show the stitches first.');return}
  stopPicking();
  const scale=(view.plan.height_mm||1)/size.height,origin=view.plan.origin_mm||[0,0];
  // Caught before the canvas's own pan and edit handlers see the click.
  const handler=e=>{
   if(e.target!==canvas)return;
   e.preventDefault();e.stopImmediatePropagation();stopPicking();
   const p=studio.piecePoint(e,canvas),to=[Math.round((p[0]*scale-origin[0])*100)/100,Math.round((p[1]*scale-origin[1])*100)/100];
   const far=Math.hypot(to[0]-at.x,to[1]-at.y);
   if(far>MAX_MOVE_MM){say(`That is ${far.toFixed(1)} mm away. A stitch can move at most ${MAX_MOVE_MM} mm.`);return}
   add({kind:'move',...at,to},'Moving the stitch and checking again…');
  };
  const key=e=>{if(e.key==='Escape'){stopPicking();say('Move cancelled.')}};
  picking={handler,key};window.addEventListener('pointerdown',handler,true);document.addEventListener('keydown',key);
  say('Click where the stitch should go (up to 3 mm away). Esc cancels.');
 }
 box.querySelector('.stitch-edit-actions').addEventListener('click',e=>{
  const kind=e.target.closest('button')?.dataset.kind;if(!kind)return;
  const at=current();
  if(!at){say('Play or step to a stitch first.');return}
  if(kind==='move'){move(at);return}
  add({kind,...at},{stop:'Adding a stop and checking again…',trim:'Adding a cut and checking again…',delete:'Deleting the stitch and checking again…'}[kind]);
 });
 // Seek to an edit's stitch in playback.
 function seek(n){
  const view=studio.playbackView();if(!view)return;
  let count=0;const i=view.plan.steps.findIndex(s=>s.t==='stitch'&&++count>=n);
  if(i>=0)studio.seek(i+1);
 }
 let shown='';
 function sync(){
  const edits=saved(),report=studio.playbackView()?.plan.stitch_edits,dropped=report?.dropped||[];
  box.hidden=!studio.hasPlayback()&&!edits.length;
  const state=JSON.stringify([edits,dropped]);if(state===shown)return;shown=state;
  list.replaceChildren(...edits.map((edit,i)=>{
   const li=document.createElement('li'),go=document.createElement('button'),remove=document.createElement('button');
   go.type=remove.type='button';go.className='link';
   go.textContent=`${NAMES[edit.kind]} · stitch ${edit.n.toLocaleString()}`;go.title='Show it in playback';go.onclick=()=>seek(edit.n);
   remove.textContent='×';remove.title='Remove this edit';remove.setAttribute('aria-label','Remove '+go.textContent);
   remove.onclick=()=>save(edits.filter((_,j)=>j!==i),'Removing the edit and checking again…');
   li.append(go,remove);return li;
  }));
  note.textContent=dropped.join(' ');note.hidden=!dropped.length;
 }
 window.addEventListener('studio:preview',sync);setInterval(sync,1500);sync();
});
