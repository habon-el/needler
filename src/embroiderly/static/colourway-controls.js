/* Named colourways (colourways.py): colour versions of this design. A colourway is a name and
   the design's thread choices (merges, border thread); switching puts them back into the
   preparation options, so generated stitches and machine files follow the active colourway. */
document.addEventListener('DOMContentLoaded', async () => {
 'use strict';
 const $=id=>document.getElementById(id), studio=window.embroideryStudio, design=window.preparationConfig?.name;
 const hint=$('swatches')?.nextElementSibling;
 if(!studio||!design||!hint||window.nativeTextConfig)return;
 const url='/api/colourways/'+encodeURIComponent(design);
 let list;
 try{list=(await fetch(url,{cache:'no-store'}).then(r=>r.json())).saved}catch(_){return}
 if(!Array.isArray(list))return;
 const box=document.createElement('div');box.className='colourway-controls';
 box.innerHTML=`<label for="colourwayPick">Colourway</label>
  <select id="colourwayPick" title="Colour versions of this design. Pick one to use its thread colours."></select>
  <label>Name<input id="colourwayName" maxlength="40" placeholder="For example: Summer"></label>
  <div class="colourway-row"><button type="button" id="colourwayNew">Save as new</button><button type="button" id="colourwayRename">Rename</button><button type="button" id="colourwayDelete">Delete</button></div>
  <p class="muted" id="colourwayNote" role="status"></p>`;
 hint.after(box);
 const pick=$('colourwayPick'),name=$('colourwayName'),note=$('colourwayNote');
 // The design's thread choices now; the border thread only counts while a border is sewn.
 const current=()=>{const o=studio.snapshot(),t={merges:o.merges||{}};if(o.border_style&&o.border_style!=='off')t.border_colour=o.border_colour||'#202020';return t};
 const same=(a,b)=>{const keys=o=>JSON.stringify(Object.keys(o).sort().map(k=>[k.toLowerCase(),String(o[k]).toLowerCase()]));
  return keys(a.merges||{})===keys(b.merges||{})&&(!b.border_colour||!a.border_colour||a.border_colour.toLowerCase()===b.border_colour)};
 const active=()=>list.find(c=>same(current(),c.threads));
 const sync=()=>{
  const on=active();pick.replaceChildren();
  if(!on)pick.append(new Option(list.length?'Colours now (not saved)':'No colourways yet',''));
  for(const c of list)pick.append(new Option(c.name,c.id));
  pick.value=on?on.id:'';$('colourwayRename').disabled=$('colourwayDelete').disabled=!on;
 };
 const send=async(method,path,body)=>{
  const result=await fetch(url+path,{method,headers:{'Content-Type':'application/json'},body:body&&JSON.stringify(body)}).then(r=>r.json()).catch(()=>({error:'Not saved. Try again.'}));
  if(result.error){note.textContent=result.error;return false}
  list=result.saved;sync();return true;
 };
 pick.addEventListener('change',()=>{
  const c=list.find(x=>x.id===pick.value);if(!c)return;
  try{studio.apply({merges:{...c.threads.merges},...(c.threads.border_colour?{border_colour:c.threads.border_colour}:{})});
   note.textContent=`Now using “${c.name}”. Generate stitches to sew these colours.`}
  catch(error){note.textContent=error.message}
  sync();
 });
 $('colourwayNew').onclick=async()=>{
  const wanted=name.value.trim()||'Colourway '+(list.length+1);
  if(await send('POST','',{name:wanted,threads:current()})){name.value='';note.textContent=`Saved “${wanted}”.`}
 };
 $('colourwayRename').onclick=async()=>{
  const c=active();if(!c)return;
  if(!name.value.trim()){note.textContent='Type the new name first.';return}
  const wanted=name.value.trim();
  if(await send('PATCH','/'+encodeURIComponent(c.id),{name:wanted})){name.value='';note.textContent=`Renamed to “${wanted}”.`}
 };
 $('colourwayDelete').onclick=async()=>{
  const c=active();if(!c)return;
  if(await send('DELETE','/'+encodeURIComponent(c.id)))note.textContent=`Deleted “${c.name}”. The colours stay as they are.`;
 };
 window.addEventListener('studio:controls',sync);window.addEventListener('studio:preview',sync);sync();
});
