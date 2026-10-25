/* Hoop picker (hoops.py): hoops by machine brand and the user's own, turn 90°, a fit note,
   and the hoop drawn on the canvas. The chosen hoop lives in the preparation options
   (hoop_id, piece_hoop_mm as placed); "Show on canvas" is a per-browser preference. */
window.hoopControls = async studio => {
 'use strict';
 let data;
 try{data=await fetch('/api/hoops',{cache:'no-store'}).then(r=>r.json())}catch(_){return null}
 const box=document.createElement('div');box.className='hoop-controls';
 box.innerHTML=`<label for="hoopPick">Hoop</label>
  <div class="hoop-row"><select id="hoopPick" title="The usable sewing area. Machines differ: check your manual."></select>
  <button type="button" id="hoopTurn" title="Turn the hoop 90°">⟳ Turn</button></div>
  <p class="muted" id="hoopFit" role="status"></p>
  <label class="hoop-show"><input type="checkbox" id="hoopShow"> Show on canvas</label>
  <details id="hoopMine"><summary>My own hoop</summary>
  <label>Name<input id="hoopName" maxlength="40" placeholder="For example: Big frame"></label>
  <div class="hoop-row"><label>Width mm<input id="hoopW" type="number" min="10" max="1000" step="1"></label>
  <label>Height mm<input id="hoopH" type="number" min="10" max="1000" step="1"></label></div>
  <div class="hoop-row"><button type="button" id="hoopSave">Save hoop</button><button type="button" id="hoopDelete" hidden>Delete this hoop</button></div>
  <p class="muted" id="hoopNote" role="status"></p></details>`;
 const $=id=>box.querySelector('#'+id);
 const pick=$('hoopPick'),fit=$('hoopFit'),show=$('hoopShow'),note=$('hoopNote');
 const all=()=>[...data.brands.flatMap(g=>g.hoops.map(h=>({...h,brand:g.brand}))),...data.saved.map(h=>({...h,brand:'My hoops'}))];
 const fill=()=>{
  pick.replaceChildren(new Option('Choose your hoop',''));
  for(const group of [...data.brands,{brand:'My hoops',hoops:data.saved}]){
   if(!group.hoops.length)continue;
   const g=document.createElement('optgroup');g.label=group.brand;
   for(const h of group.hoops)g.append(new Option(`${h.name} · ${h.width_mm} × ${h.height_mm} mm`,h.id));
   pick.append(g);
  }
 };
 const status=message=>(window.studioStatus||console.warn)(message);
 // The design's size: the outlines of its visible parts, or the canvas when there are none.
 const designSize=()=>{
  const pieces=(studio.pieceReport()?.pieces||[]).filter(p=>p.visible);
  if(pieces.length){
   const l=Math.min(...pieces.map(p=>p.x_mm-p.width_mm/2)),r=Math.max(...pieces.map(p=>p.x_mm+p.width_mm/2));
   const t=Math.min(...pieces.map(p=>p.y_mm-p.height_mm/2)),b=Math.max(...pieces.map(p=>p.y_mm+p.height_mm/2));
   return [r-l,b-t];
  }
  const o=studio.snapshot(),s=studio.imageSize();return [o.height_mm*s.width/s.height,o.height_mm];
 };
 const sync=()=>{
  const o=studio.snapshot(),field=o.piece_hoop_mm||[100,100],hoop=all().find(h=>h.id===o.hoop_id);
  pick.value=hoop?hoop.id:'';
  const [w,h]=designSize(),turned=hoop&&field[0]!==hoop.width_mm;
  const name=hoop?`${hoop.brand==='My hoops'?'':hoop.brand+' '}${hoop.name}${turned?' (turned)':''}`:'Reference hoop';
  window.hoopLabel=`${name} · ${field[0]} × ${field[1]} mm`;
  const spareX=(field[0]-w)/2,spareY=(field[1]-h)/2,fits=spareX>=0&&spareY>=0;
  fit.textContent=`${field[0]} × ${field[1]} mm. `+(fits?`The design fits: ${spareX.toFixed(0)} mm spare left and right, ${spareY.toFixed(0)} mm top and bottom.`:
   `Too big: ${[spareX<0?`${(-2*spareX).toFixed(0)} mm too wide`:'',spareY<0?`${(-2*spareY).toFixed(0)} mm too tall`:''].filter(Boolean).join(', ')}. Turn the hoop or choose a bigger one.`);
  fit.dataset.level=fits?'green':'red';
  $('hoopDelete').hidden=!(hoop&&hoop.brand==='My hoops');
  try{show.checked=localStorage.getItem('needler.showHoop')!=='off'}catch(_){show.checked=true}
  window.hoopShown=show.checked;
 };
 const choose=patch=>{try{studio.apply(patch)}catch(error){status(error.message)}sync();studio.redraw()};
 pick.addEventListener('change',()=>{
  const hoop=all().find(h=>h.id===pick.value);
  choose(hoop?{hoop_id:hoop.id,piece_hoop_mm:[hoop.width_mm,hoop.height_mm]}:{hoop_id:undefined,piece_hoop_mm:[100,100]});
 });
 $('hoopTurn').onclick=()=>{const f=studio.snapshot().piece_hoop_mm||[100,100];choose({piece_hoop_mm:[f[1],f[0]]})};
 show.addEventListener('change',()=>{try{localStorage.setItem('needler.showHoop',show.checked?'on':'off')}catch(_){}window.hoopShown=show.checked;studio.redraw()});
 $('hoopSave').onclick=async()=>{
  const body={name:$('hoopName').value,width_mm:Number($('hoopW').value),height_mm:Number($('hoopH').value)};
  const result=await fetch('/api/hoops',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()).catch(()=>({error:'Hoop not saved. Try again.'}));
  if(result.error){note.textContent=result.error;return}
  data.saved=result.saved;fill();const mine=data.saved[data.saved.length-1];note.textContent=`Saved “${mine.name}”.`;
  $('hoopName').value=$('hoopW').value=$('hoopH').value='';
  choose({hoop_id:mine.id,piece_hoop_mm:[mine.width_mm,mine.height_mm]});
 };
 $('hoopDelete').onclick=async()=>{
  const id=studio.snapshot().hoop_id;
  const result=await fetch('/api/hoops/'+encodeURIComponent(id),{method:'DELETE'}).then(r=>r.json()).catch(()=>({error:'Hoop not deleted. Try again.'}));
  if(result.error){note.textContent=result.error;return}
  data.saved=result.saved;fill();note.textContent='Hoop deleted.';sync();
 };
 fill();
 window.addEventListener('studio:controls',sync);window.addEventListener('studio:preview',sync);sync();
 return box;
};
