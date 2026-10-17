(() => {
'use strict';
const studio=window.embroideryStudio, config=window.preparationConfig;
const section=document.createElement('details');section.open=true;
section.innerHTML=`<summary>Suggested changes</summary>
<p class="muted">Nothing applies until you confirm. Local suggestions work without AI. Stitch previews always use real generated paths.</p>
<button id="assistSubject" aria-pressed="false">Click to select a subject</button>
<p id="assistHint" class="muted">Click the subject, Shift-click to add, Alt-click to subtract; or drag a box. Review the proposed mask below.</p>
<button id="assistRecommend">Suggest artwork settings</button><button id="assistScale">Check minimum size</button>
<label>Describe a change<input id="assistText" type="text" maxlength="1000" placeholder="Remove the white, or fit a cap"></label>
<label><input id="assistCloud" type="checkbox"> Allow this request to send artwork to OpenAI (paid API; optional)</label>
<button id="assistEdit">Preview requested change</button><button id="assistReview">Ask AI to review real stitches</button>
<p id="assistStatus" role="status" aria-live="polite">Local suggestions available. Checking model configuration…</p>
<div id="assistResult"></div>`;
document.querySelector('.inspector h1').after(section);
const $=id=>document.getElementById(id), out=$('assistResult');
let current=null, generation=0, busy=false, controller=null, selecting=false, prompts=[], subjectBox=null, startPoint=null, originalOptions=null, autoRequested=false,activeAutomatic=false;
function node(tag,text){const e=document.createElement(tag);e.textContent=text;return e}
function clear(){generation++;controller?.abort();current=null;out.replaceChildren();}
function message(text){$('assistStatus').textContent=text}
function image(url,label){const figure=document.createElement('figure');figure.style.margin='8px 0';const img=document.createElement('img');img.src=url;img.alt=label;img.style.cssText='width:100%;max-height:220px;object-fit:contain;background:repeating-conic-gradient(#ddd 0% 25%,#fff 0% 50%) 0 / 16px 16px';figure.append(img,node('figcaption',label));return figure}
function show(result,snapshot,args){
 if(result.operation==='colour-knockout'&&window.colourKnockout){window.colourKnockout.show(result,snapshot,args);return}
 out.replaceChildren();out.append(node('p',result.method));
 const alternatives=result.alternatives?.length?result.alternatives:(args.maskAlternatives||[]);
 if(alternatives.length>1){const next=node('button','Next subject candidate');next.id='nextMaskCandidate';next.onclick=()=>{const index=((args.maskIndex||0)+1)%alternatives.length;request({action:'preview',patch:alternatives[index],maskAlternatives:alternatives,maskIndex:index})};out.append(node('p',`Subject candidate ${(args.maskIndex||0)+1} of ${alternatives.length} — not applied`),next);}
 if(result.detection)out.append(node('p','Likely '+result.detection.kind+' · '+result.detection.method));
 (result.reasons||[]).forEach(r=>out.append(node('p',r)));
 if(result.before_image)out.append(image(result.before_image,'Current artwork—unchanged'));
 if(result.image)out.append(image(result.image,args.action==='review'?'Actual stitch render sent for review':'Proposed artwork—not yet applied'));
 if(result.stitch_image)out.append(image(result.stitch_image,'Proposed real stitches—not applied'));
 if(result.after?.detail_loss?.boundary?.length)out.append(node('p',`${result.after.detail_loss.boundary.length} proposed mask-edge warnings. Inspect the subject outline; try another candidate or add/subtract clicks before applying.`));
 if(result.before&&result.after)out.append(node('p',`Regions: ${result.before.regions_after} → ${result.after.regions_after}. Small-area flags: ${result.before.below_floor_after} → ${result.after.below_floor_after}. Colours: ${result.before.colours_after} → ${result.after.colours_after}. Canvas: ${result.before.height_mm} → ${result.after.height_mm} mm.`));
 if(result.audit)out.append(node('p',`Measured candidate PES: ${result.audit.stitch_count} stitches · ${result.audit.trim_count} trims · stitch lengths ${result.audit.shortest_stitch_mm.toFixed(2)}–${result.audit.longest_stitch_mm.toFixed(2)} mm. Not a complete machine-limit audit.`));
 for(const finding of result.findings||[])out.append(node('p','Second opinion · priority '+finding.priority+': '+finding.text));
 if(result.patch&&Object.keys(result.patch).length){
  const keys=Object.entries(result.patch).filter(([key])=>!['mask_runs','hints'].includes(key));
  out.append(node('p','Changes: '+keys.map(([k,v])=>k.replaceAll('_',' ')+' → '+v).join('; ')));
  const apply=node('button','Apply proposal');apply.id='assistApply';apply.className='primary';
  apply.onclick=()=>{
   if(JSON.stringify(studio.snapshot())!==snapshot){clear();message('Artwork changed; request a fresh suggestion.');return}
   try{studio.apply(result.patch);selecting=false;$('assistSubject').setAttribute('aria-pressed','false');clear();message('Proposal applied. Undo restores your previous settings. Your saved design is unchanged until you save.')}catch(e){message(e.message)}
  };
  const render=node('button','Preview real stitches');render.id='assistRender';render.onclick=()=>request({action:'preview',patch:result.patch,stitches:true});
  const dismiss=node('button','Dismiss');dismiss.onclick=()=>{clear();message('Dismissed. No settings changed.')};
  out.append(apply,render,dismiss);current={result,snapshot};
 }
}
async function request(args,automatic=false){
 if(automatic&&studio.hasPlayback())return;
 if(busy||studio.isBusy()){message('Wait for the current preview to finish.');return}
 activeAutomatic=automatic;busy=true;window.dispatchEvent(new CustomEvent('assist:state',{detail:{busy:true,action:args.action,colourRemoval:args.action==='remove_colour'||!!args.patch?.colour_knockouts||(args.action==='edit'&&/^(remove( the)? white|keep only( the)? black)[.!?]*$/i.test(args.text?.trim()||''))}}));const version=++generation,snapshot=JSON.stringify(studio.snapshot());
 out.replaceChildren();message(args.action==='review'?'Generating real stitches, then requesting a cloud second opinion…':'Calculating a proposal; your design is unchanged…');
 let timeout;
 try{
  controller=new AbortController();const signal=controller.signal;
  timeout=setTimeout(()=>controller?.abort(),args.action==='remove_colour'||args.patch?.colour_knockouts?30000:240000);
  const response=await fetch('/assist/'+encodeURIComponent(config.name),{method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({options:JSON.parse(snapshot),...args})});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Suggestion unavailable.');
  if(version!==generation||snapshot!==JSON.stringify(studio.snapshot())){message('Artwork changed; outdated suggestion discarded.');return}
  show(result,snapshot,args);message((result.elapsed_ms!==undefined?'Proposal ready in '+(result.elapsed_ms/1000).toFixed(2)+' s. ':'')+(result.cloud_available?'Cloud model configured; consent required for each cloud action.':'Cloud model not configured. Local tools remain available.'));
 }catch(e){if(version===generation){const text=e.name==='AbortError'?'Preview timed out. Your design is unchanged; retry the preview.':e.message;message(text);window.dispatchEvent(new CustomEvent('assist:error',{detail:text}))}}finally{clearTimeout(timeout);controller=null;busy=false;activeAutomatic=false;window.dispatchEvent(new CustomEvent('assist:state',{detail:{busy:false}}))}
}
$('assistRecommend').onclick=()=>request({action:'recommend'});
$('assistScale').onclick=()=>request({action:'scale'});
$('assistEdit').onclick=()=>{const consent=$('assistCloud').checked;$('assistCloud').checked=false;request({action:'edit',text:$('assistText').value,cloud_consent:consent})};
$('assistReview').onclick=()=>{if(!$('assistCloud').checked){message('Tick the consent box to send this artwork, a real stitch render, and measurements to OpenAI.');return}$('assistCloud').checked=false;request({action:'review',cloud_consent:true})};
$('assistSubject').onclick=()=>{selecting=!selecting;prompts=[];subjectBox=null;$('assistSubject').setAttribute('aria-pressed',String(selecting));if(selecting){studio.selectOriginal();message('Click the subject or drag a box. Selection is proposed, not applied.')}};
document.querySelectorAll('[data-tool],#outlineSubject,#inspectDetail').forEach(button=>button.addEventListener('click',()=>{selecting=false;$('assistSubject').setAttribute('aria-pressed','false')}));
const canvas=$('original');
canvas.addEventListener('pointerdown',e=>{if(!selecting||studio.navigationGesture(e))return;e.stopImmediatePropagation();if(busy||studio.isBusy())return;canvas.setPointerCapture(e.pointerId);startPoint={point:studio.point(e),shift:e.shiftKey,alt:e.altKey};},true);
canvas.addEventListener('pointermove',e=>{if(selecting&&!studio.navigationGesture(e))e.stopImmediatePropagation()},true);
canvas.addEventListener('pointerup',e=>{
 if(!selecting||studio.navigationGesture(e))return;e.stopImmediatePropagation();if(!startPoint)return;
 const end=studio.point(e),start=startPoint;startPoint=null;
 if(Math.hypot(end[0]-start.point[0],end[1]-start.point[1])>5){
  prompts=[];subjectBox=[Math.min(end[0],start.point[0]),Math.min(end[1],start.point[1]),Math.max(end[0],start.point[0]),Math.max(end[1],start.point[1])];request({action:'segment',points:[],box:subjectBox});
 }else{
  if(!start.shift&&!start.alt){prompts=[];subjectBox=null}
  prompts.push({point:end,label:start.alt?0:1});request({action:'segment',points:prompts,box:subjectBox});
 }
},true);
canvas.addEventListener('pointercancel',()=>startPoint=null,true);
window.addEventListener('studio:changed',()=>{clear();message('Artwork changed. Suggestions will not overwrite your edits.')});
// An automatic artwork proposal must never replace a generated result,
 // even if its response arrives late with identical settings.
 window.addEventListener('studio:stitch-state',e=>{
  if(activeAutomatic&&['generating','ready'].includes(e.detail.state)){
   clear();message('Automatic suggestion dismissed so you can review your stitches.');
  }
 });
window.addEventListener('studio:preview',e=>{
 const {options,report}=e.detail;
 if(originalOptions){
  const changes={};for(const [key,value] of Object.entries(options))if(typeof value==='number'&&typeof originalOptions[key]==='number'&&value!==originalOptions[key])changes[key]=[originalOptions[key],value];
  if(Object.keys(changes).length)fetch('/assist-events/'+encodeURIComponent(config.name),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({changes,measurements:report})}).catch(()=>{});
 }
 originalOptions=structuredClone(options);
 if(!autoRequested){autoRequested=true;if(e.detail.hasPlayback||studio.hasPlayback()||new URLSearchParams(location.search).get('view')==='stitched')return;const fresh=!Object.keys(config.options||{}).length;const w=report.width_px,h=report.height_px;setTimeout(()=>request(report.background_proposal?{action:'remove_colour',operation:report.background_proposal}:fresh&&w>20&&h>20?{action:'segment',points:[],box:[Math.max(1,Math.floor(w*.05)),Math.max(1,Math.floor(h*.05)),Math.min(w-2,Math.floor(w*.95)),Math.min(h-2,Math.floor(h*.95))]}:{action:'recommend'},true),0)}
});
window.embroideryAssistance={request,cancel:clear,isBusy:()=>busy};
})();
