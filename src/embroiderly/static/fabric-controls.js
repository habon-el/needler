/* Fabric presets: one menu that sets density, pull compensation, underlay and
   tie-offs for the fabric (generation_policy.py). The value lives in the
   preparation options like every other setting. */
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
  <p class="muted" id="fabricAdvice"></p>`;
 anchor.after(box);
 const select=$('fabricPreset'),advice=$('fabricAdvice');
 // Short hint; the full advice is on hover.
 const describe=()=>{const f=data.fabrics.find(x=>x.id===select.value);
  advice.textContent=!f?'':f.backing?'Backing: '+f.backing+(f.topping?' · Topping: '+f.topping:''):'Stabilizer: '+f.stabilizer.split(/[;.]/)[0].trim();
  advice.title=f?f.stabilizer:''};
 const sync=()=>{select.value=studio.snapshot().fabric_preset||data.default;describe()};
 select.addEventListener('change',()=>{describe();try{studio.apply({fabric_preset:select.value})}catch(error){sync();(window.studioStatus||console.warn)(error.message)}});
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
