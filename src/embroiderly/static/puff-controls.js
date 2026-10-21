/* 3D puff controls and sewing instructions. Values live in the existing
   owners: preparation options for pictures, the text recipe for lettering. */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 const $=id=>document.getElementById(id), studio=window.embroideryStudio;
 if(!studio)return;
 const node=(tag,cls,html)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(html)e.innerHTML=html;return e;};
 const native=!!window.nativeTextConfig;
 const box=node('div','puff-controls');
 box.innerHTML=`<label class="puff-toggle" title="Raised satin over foam"><input type="checkbox" id="puffOn"> <span>3D puff</span></label>
  <div class="puff-more" hidden><label for="puffFoam">Foam thickness</label>
  <select id="puffFoam"><option value="2">2 mm · subtle</option><option value="3" selected>3 mm · classic cap puff</option></select>
  <p class="muted">${native?'Use a bold font: strokes 3–6 mm wide (2–6 mm on 2 mm foam).':
   'Parts 3–6 mm wide puff (2–6 mm on 2 mm foam).'}</p></div>`;
 const anchor=native?$('workflowTextExtras'):$('workflowSizeFields');
 if(!anchor)return;
 anchor.after(box);
 const more=box.querySelector('.puff-more'),on=$('puffOn');
 if(native){
  // The text recipe reads this checkbox (lettering-native.js values()).
  const changed=()=>{more.hidden=!on.checked;$('nativeFont').dispatchEvent(new Event('input',{bubbles:true}));
   $('letteringWords').dispatchEvent(new Event('input',{bubbles:true}))};
  on.addEventListener('change',changed);$('puffFoam').addEventListener('change',changed);
  window.NativePuff={get:()=>on.checked,foam:()=>Number($('puffFoam').value),
   set:(v,foam)=>{on.checked=!!v;more.hidden=!on.checked;if(foam)$('puffFoam').value=String(foam)}};
 }else{
  const sync=()=>{const o=studio.snapshot();on.checked=o.puff===true;more.hidden=!on.checked;$('puffFoam').value=String(o.puff_foam_mm||3)};
  const apply=patch=>{try{studio.apply(patch)}catch(error){sync();(window.studioStatus||console.warn)(error.message)}};
  on.addEventListener('change',()=>{more.hidden=!on.checked;apply({puff:on.checked,puff_foam_mm:Number($('puffFoam').value)})});
  $('puffFoam').addEventListener('change',()=>apply({puff_foam_mm:Number($('puffFoam').value)}));
  window.addEventListener('studio:controls',sync);window.addEventListener('studio:preview',sync);sync();
 }

 // How to sew it: shown on Check stitches whenever the stitches contain puff.
 const help=node('section','puff-sewing');help.hidden=true;
 ($('workflowCheck')||document.querySelector('.inspector')).prepend(help);
 let shown='';
 setInterval(()=>{
  const view=studio.playbackView?.(),puff=view?.plan?.puff;
  const key=puff?JSON.stringify([puff,view.plan.colors]):'';
  if(key===shown)return;shown=key;help.hidden=!puff;if(!puff)return;
  const first=puff.threads[0]+1,colour=view.plan.colors[puff.threads[0]];
  help.innerHTML=`<h2>Sewing 3D puff</h2><ol>
   <li>Hoop the fabric drum-tight with a firm backing. A loose hoop is the most common reason puff lifts.</li>
   <li>${first===1?'Before you start':`The machine sews the outline where the foam goes, then stops before thread ${first}. Now`} lay <strong>${puff.foam_mm} mm puff foam</strong> in the thread colour (<span class="puff-swatch" style="background:${colour}"></span>) over the outline, a little larger than it. A light spray adhesive or tape at the edges keeps it from shifting.</li>
   <li>Slow the machine to about 600–700 stitches per minute and loosen the top thread tension slightly, so the thread wraps over the foam without crushing it.</li>
   <li>Continue sewing. A short running stitch tacks the foam down, caps close the column ends, and dense satin covers it all and cuts the foam along its edges.</li>
   <li>Tear the extra foam away gently, pulling away from the stitches. A little steam or a hair-dryer shrinks small fibres that poke out.</li></ol>
   <p class="muted">Use the 3D view to check the raised parts. Puff needs a sample sew-out: foam brands and machines differ.</p>`;
 },1000);
});
