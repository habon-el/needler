/* Fabric presets: one menu that sets density, pull compensation, underlay and
   tie-offs for the fabric (generation_policy.py). The value lives in the
   preparation options like every other setting. "My own fabric" saves a listed
   fabric with the user's own values (custom_fabrics.py); the chosen one is copied
   into the options as fabric_custom. */
document.addEventListener('DOMContentLoaded', async () => {
 'use strict';
 const $=id=>document.getElementById(id), studio=window.embroideryStudio;
 const anchor=$('workflowSizeFields');
 if(!studio||!anchor||window.nativeTextConfig)return;
 let data;
 try{data=await fetch('/api/fabrics',{cache:'no-store'}).then(r=>r.json())}catch(_){return}
 const box=document.createElement('div');box.className='fabric-controls';
 box.innerHTML=`<label for="fabricPreset">Fabric</label>
  <select id="fabricPreset">${data.fabrics.map(f=>`<option value="${f.id}">${f.label}</option>`).join('')}</select>
  <p class="muted" id="fabricAdvice"></p>
  <details id="fabricMine" class="fabric-mine"><summary>My own fabric</summary>
  <label>Name<input id="fabricName" maxlength="40" placeholder="For example: Thick hoodie"></label>
  <div class="fabric-row"><label title="Gap between fill rows">Fill spacing mm<input id="fabricRow" type="number" min="0.25" max="1" step="0.01"></label>
  <label title="Gap between satin stitches">Satin spacing mm<input id="fabricSatin" type="number" min="0.25" max="0.8" step="0.01"></label></div>
  <div class="fabric-row"><label title="How much wider satins are sewn, each side, so the fabric pulling in leaves them the right width">Pull mm<input id="fabricPull" type="number" min="0" max="0.6" step="0.01"></label>
  <label>Longest stitch mm<input id="fabricLong" type="number" min="2" max="7" step="0.1"></label></div>
  <label class="fabric-check"><input type="checkbox" id="fabricUnder"> Underlay under fills</label>
  <div class="fabric-row"><button type="button" id="fabricSave">Save fabric</button><button type="button" id="fabricDelete" hidden>Delete</button></div>
  <p class="muted" id="fabricNote" role="status"></p></details>
  <label for="stitchDensity">Density</label>
  <select id="stitchDensity"><option value="lighter">Lighter</option><option value="normal">Normal</option><option value="denser">Denser</option></select>
  <label for="sewOrder">Sewing order</label>
  <select id="sewOrder" title="Best look sews back to front: a part lying on another is sewn after it, even if that thread was used before. It can add colour changes."><option value="colours">Fewest colour changes</option><option value="layers">Best look (back to front)</option></select>
  <fieldset id="appliqueOptions" class="fabric-applique" hidden><legend>Appliqué</legend>
  <label class="fabric-check" title="The fabric runs on under the parts sewn on it; their stitches hide that edge, so it gets no satin"><input type="checkbox" data-key="applique_partial"> Tuck under parts on top</label>
  <label class="fabric-check" title="Pieces of one colour are placed, tacked down and covered together: two stops in all"><input type="checkbox" data-key="applique_combine"> Share stops</label>
  <label class="fabric-check" title="Where two pieces meet, only the top piece's satin covers the join"><input type="checkbox" data-key="applique_join"> Cover joins once</label></fieldset>
  <label for="bastingChoice">Basting</label>
  <select id="bastingChoice" title="Long stitches sewn first in their own thread, holding the fabric to the backing; pull them out afterwards"><option value="off">Off</option><option value="design">Around the design</option><option value="hoop">Around the hoop</option></select>
  <details id="buttonholes" class="buttonholes"><summary>Buttonholes</summary>
  <p class="muted">Sewn last. Position is from the design's centre, in mm.</p>
  <div id="buttonholeList"></div><button type="button" id="buttonholeAdd">Add buttonhole</button></details>`;
 anchor.after(box);
 // Hoop picker (hoop-controls.js) sits with the other design-wide choices.
 const hoop=await window.hoopControls?.(studio);if(hoop)box.append(hoop);
 const select=$('fabricPreset'),advice=$('fabricAdvice'),note=$('fabricNote');
 data.saved=data.saved||[];
 const fill=()=>{
  select.replaceChildren(...data.fabrics.map(f=>new Option(f.label,f.id)));
  const mine=[...data.saved],used=studio.snapshot().fabric_custom;
  // A design keeps its own fabric after the saved one is deleted.
  if(used&&!mine.some(f=>f.id===used.id))mine.push(used);
  if(mine.length){const g=document.createElement('optgroup');g.label='My fabrics';g.append(...mine.map(f=>new Option(f.name,f.id)));select.append(g)}
 };
 const base=id=>data.fabrics.find(x=>x.id===id);
 const mineFor=id=>data.saved.find(f=>f.id===id)||(studio.snapshot().fabric_custom?.id===id?studio.snapshot().fabric_custom:null);
 const field={row_spacing_mm:'fabricRow',satin_spacing_mm:'fabricSatin',satin_pull_mm:'fabricPull',max_stitch_length_mm:'fabricLong'};
 // The form starts from the chosen fabric; a saved fabric is edited in place.
 let filledFor=null;
 const prefill=()=>{filledFor=select.value;const mine=mineFor(select.value),f=mine||base(select.value)||base(data.default);
  $('fabricName').value=mine?mine.name:'';for(const [k,id] of Object.entries(field))$(id).value=f[k];$('fabricUnder').checked=f.fill_underlay!==false;
  $('fabricSave').textContent=mine?'Save changes':'Save fabric';$('fabricDelete').hidden=!data.saved.some(x=>x.id===select.value)};
 // Short hint; the full advice is on hover.
 const describe=()=>{const mine=mineFor(select.value),f=mine?base(mine.base):data.fabrics.find(x=>x.id===select.value);
  advice.textContent=!f?'':f.backing?'Backing: '+f.backing+(f.topping?' · Topping: '+f.topping:''):'Stabilizer: '+f.stabilizer.split(/[;.]/)[0].trim();
  advice.title=f?f.stabilizer:''};
 const density=$('stitchDensity');
 const order=$('sewOrder');
 const sync=()=>{const o=studio.snapshot();fill();select.value=o.fabric_custom?.id||o.fabric_preset||data.default;if(select.value!==filledFor)prefill();density.value=studio.snapshot().density||'normal';order.value=studio.snapshot().sew_order||'colours';describe()};
 order.addEventListener('change',()=>{try{studio.apply({sew_order:order.value})}catch(error){sync();(window.studioStatus||console.warn)(error.message)}});
 // Adjust stitch spacing for the whole design (generation_policy.DENSITY).
 density.addEventListener('change',()=>{try{studio.apply({density:density.value})}catch(error){sync();(window.studioStatus||console.warn)(error.message)}});
 const choose=()=>{const mine=mineFor(select.value);
  try{studio.apply(mine?{fabric_preset:mine.base,fabric_custom:mine}:{fabric_preset:select.value,fabric_custom:undefined})}catch(error){(window.studioStatus||console.warn)(error.message)}sync()};
 select.addEventListener('change',()=>{note.textContent='';choose()});
 $('fabricMine').addEventListener('toggle',()=>{if($('fabricMine').open)prefill()});
 $('fabricSave').onclick=async()=>{
  const mine=mineFor(select.value),body={name:$('fabricName').value,base:mine?mine.base:select.value,fill_underlay:$('fabricUnder').checked,...(mine?{id:mine.id}:{})};
  for(const [k,id] of Object.entries(field))body[k]=Number($(id).value);
  const result=await fetch('/api/fabrics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()).catch(()=>({error:'Fabric not saved. Try again.'}));
  if(result.error){note.textContent=result.error;return}
  data.saved=result.saved;fill();select.value=result.fabric.id;note.textContent=`Saved “${result.fabric.name}”.`;choose();prefill();
 };
 $('fabricDelete').onclick=async()=>{
  const result=await fetch('/api/fabrics/'+encodeURIComponent(select.value),{method:'DELETE'}).then(r=>r.json()).catch(()=>({error:'Fabric not deleted. Try again.'}));
  if(result.error){note.textContent=result.error;return}
  // The design keeps the deleted fabric's values until another fabric is chosen.
  data.saved=result.saved;note.textContent='Fabric deleted.';sync();
 };
 // Appliqué options (applique_layout.py): shown once the design has appliqué pieces.
 const applique=$('appliqueOptions'),switches=[...applique.querySelectorAll('input')];
 let hasApplique=false;
 const syncApplique=()=>{const o=studio.snapshot();for(const box of switches)box.checked=o[box.dataset.key]===true;
  applique.hidden=!hasApplique&&!switches.some(box=>box.checked)};
 for(const box of switches)box.addEventListener('change',()=>{try{studio.apply({[box.dataset.key]:box.checked})}catch(error){(window.studioStatus||console.warn)(error.message)}syncApplique()});
 window.addEventListener('studio:preview',e=>{hasApplique=!!e.detail?.applique;syncApplique()});
 window.addEventListener('studio:controls',syncApplique);syncApplique();
 // Basting and buttonholes (basting_buttonholes.py).
 const basting=$('bastingChoice'),holeList=$('buttonholeList');
 const tell=error=>(window.studioStatus||console.warn)(error.message);
 const holes=()=>(studio.snapshot().buttonholes||[]).map(h=>({...h}));
 const saveHoles=list=>{try{studio.apply({buttonholes:list})}catch(error){tell(error)}syncExtras()};
 const fields=[['x','X',-1000,1000,.5],['y','Y',-1000,1000,.5],['length_mm','Length',8,40,.5],['angle','Angle',-180,180,15]];
 const syncExtras=()=>{const o=studio.snapshot();basting.value=o.basting||'off';
  basting.querySelector('[value=hoop]').disabled=!o.piece_hoop_mm&&o.basting!=='hoop';
  const list=holes();if(list.length)$('buttonholes').open=true;
  const head=document.createElement('div');head.className='buttonhole-row buttonhole-head';
  head.append(...['X mm','Y mm','Length','Angle °'].map(t=>Object.assign(document.createElement('span'),{textContent:t})));
  holeList.replaceChildren(...(list.length?[head]:[]),...list.map((hole,i)=>{const row=document.createElement('div');row.className='buttonhole-row';
   for(const [key,label,min,max,step] of fields){const input=Object.assign(document.createElement('input'),{type:'number',min,max,step,value:hole[key]});
    input.setAttribute('aria-label',label+(key==='angle'?' °':' mm'));input.title=label;
    input.onchange=()=>{const next=holes();next[i][key]=Number(input.value);saveHoles(next)};row.append(input)}
   const colour=Object.assign(document.createElement('input'),{type:'color',value:hole.colour,title:'Thread'});
   colour.onchange=()=>{const next=holes();next[i].colour=colour.value;saveHoles(next)};
   const remove=Object.assign(document.createElement('button'),{type:'button',textContent:'✕',title:'Remove'});
   remove.onclick=()=>{const next=holes();next.splice(i,1);saveHoles(next)};
   row.append(colour,remove);return row}))};
 basting.addEventListener('change',()=>{try{studio.apply({basting:basting.value})}catch(error){tell(error)}syncExtras()});
 $('buttonholeAdd').onclick=()=>saveHoles([...holes(),{x:0,y:0,length_mm:15,width_mm:4,angle:90,colour:'#202020'}]);
 window.addEventListener('studio:controls',syncExtras);window.addEventListener('studio:preview',syncExtras);syncExtras();
 window.addEventListener('studio:controls',sync);window.addEventListener('studio:preview',sync);sync();
 // Clean Edit panel: size, its ±10% buttons and notes together, then the design options.
 const resize=$('canvasResize');
 if(resize){
  let at=anchor;
  for(const el of [resize,$('canvasSizeStatus'),resize.parentElement.querySelector(':scope > details')]){if(el&&el.parentElement===anchor.parentElement){at.after(el);at=el}}
  const options=document.createElement('div');options.className='design-options';at.after(options);
  options.append(box,...['.photo-controls','.puff-controls:not(.photo-controls)'].map(q=>anchor.parentElement.querySelector(':scope > '+q)).filter(Boolean));
 }
});
