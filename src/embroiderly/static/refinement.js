(() => {
'use strict';
const studio=window.embroideryStudio,config=window.preparationConfig,$=id=>document.getElementById(id);
const panel=document.createElement('details');panel.open=true;
panel.innerHTML='<summary>Review & repair stitches</summary><p>Compare the original with the actual stitch plan. Corrections stay inside the selected patch.</p><button id="reviewSide">Source | stitches</button><button id="reviewWipeButton">Wipe comparison</button><label>Source / stitches wipe<input id="reviewWipe" type="range" min="0" max="100" value="50"></label><button id="refreshWorklist">Check stitch detail</button><p id="refineTiming" role="status">Checking local selection cache…</p><p id="refineStatus" role="status" aria-live="polite">Generate a current stitch plan to build the worklist.</p><div id="refineWorklist"></div><div id="refineProposal"></div><details><summary>Accepted correction history</summary><ol id="refineHistory"></ol></details>';
document.querySelector('.inspector h1').after(panel);
let busy=false,revision=0,previousCount=null,previousArea=null,selected=null,pointMode=null,latest=null;
function node(tag,text){const el=document.createElement(tag);el.textContent=text;return el}
function picture(url,label){const figure=document.createElement('figure');figure.style.margin='8px 0';const im=new Image();im.src=url;im.alt=label;im.style.cssText='max-width:100%;max-height:200px;object-fit:contain';figure.append(im,node('figcaption',label));return figure}
function timing(result){
 if(!result)return;
 if(result.method==='SAM2'){$('refineTiming').textContent=`SAM encoder: ${(result.initial_encoder_ms||0).toFixed(2)} ms once; decoder: ${(result.decoder_ms||0).toFixed(2)} ms. Embedding reused: ${result.embedding_reused?'yes':'no'}. Encoder/decoder ratio: ${(result.encoder_to_decoder_ratio||0).toFixed(1)}×. ${result.encoder_to_decoder_ratio<10?'Below the requested 10× target; investigate before claiming the performance requirement is met.':''}`}
 else if(result.available===true)$('refineTiming').textContent=`Image embedding cached. Encoder: ${(result.initial_encoder_ms||0).toFixed(2)} ms. Decoder timing will appear after a refinement click.`;
 else $('refineTiming').textContent='SAM timing unavailable: '+(result.reason||result.fallback_reason||'model not configured')+'. Local fallback is not an encoder/decoder benchmark.';
}
if(!config.nativeText)fetch('/refine-warm/'+encodeURIComponent(config.name),{method:'POST'}).then(r=>r.json()).then(timing).catch(()=>{$('refineTiming').textContent='Selection cache unavailable; local editing remains available.'});
$('reviewSide').onclick=()=>studio.review('review');$('reviewWipeButton').onclick=()=>studio.review('wipe');$('reviewWipe').oninput=()=>{studio.review('wipe');studio.redraw()};
function history(){const list=$('refineHistory');list.replaceChildren();for(const op of studio.snapshot().refinement_ops||[])list.append(node('li',`${op.type} at (${op.point.join(', ')}), patch [${op.bounds.join(', ')}]`));if(!list.children.length)list.append(node('li','No accepted local corrections.'))}
async function request(action='check',patch=null,remedy=null,point=null){
 if(busy||studio.isBusy())return;
 busy=true;const version=revision,snapshot=JSON.stringify(studio.snapshot());$('refineStatus').textContent=action==='check'?'Comparing source against the current sewn paths…':'Calculating a bounded correction; nothing is applied…';
 try{
  const response=await fetch('/refine/'+encodeURIComponent(config.name),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,options:JSON.parse(snapshot),id:patch?.id,remedy,point})});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Comparison unavailable.');
  if(version!==revision||snapshot!==JSON.stringify(studio.snapshot()))return;
  if(action==='check'){
   latest=result;const count=result.audit.patches.length;const change=previousCount===null?'':` Previous stitch worklist: ${previousCount} → ${count}; lost-contrast area ${previousArea} → ${result.audit.total_lost_area_mm2} mm². Counts may split as detail returns.`;previousCount=count;previousArea=result.audit.total_lost_area_mm2;
   $('refineStatus').textContent=`${count} ranked patches.${change} ${result.audit.discarded_noise_patches} noise patches below ${result.audit.minimum_area_mm2} mm² excluded. Window: ${result.audit.window_mm} mm.`;
   const list=$('refineWorklist');list.replaceChildren();
   result.audit.patches.slice(0,30).forEach((p,index)=>{
    const item=document.createElement('article'),locate=node('button',`Patch ${index+1} · ${p.position} · ${p.width_mm} mm`);locate.onclick=()=>{selected=p;studio.focusReview(p.bounds)};item.append(locate,node('p',p.reason));
    if(p.diagnosis==='colour-merge')item.append(node('p',`Representative source/result ΔE76: ${p.delta_e76}. Recorded merges: ${p.recorded_merge_pairs.map(c=>c.source+' → '+c.target).join(', ')}. A local split does not alter the global threshold.`));
    if(p.diagnosis==='physical-limit')item.append(node('p',`Shape-width estimate: ${p.canvas_height_for_shape_mm} mm canvas height. No automatic running-stitch conversion is offered.`));
    for(const type of p.remedies){const button=node('button','Preview '+type.replaceAll('-',' '));button.onclick=()=>{selected=p;request('propose',p,type)};item.append(button);
     {const click=node('button','Choose point to '+(type==='add-region'?'add':type==='subtract-region'?'remove':'preserve'));click.onclick=()=>{selected=p;pointMode=type;if($('assistSubject')?.getAttribute('aria-pressed')==='true')$('assistSubject').click();studio.focusReview(p.bounds);$('refineStatus').textContent='Click inside this patch on the source image.'};item.append(click)}}
    list.append(item);
   });
   if(count>30)list.append(node('p','Showing the 30 highest-ranked patches.'));
  }else{
   timing(result.timing);const out=$('refineProposal');out.replaceChildren(picture(result.before_image,'Before — prepared artwork'),picture(result.after_image,'After — local artwork proposal'),node('p',result.note),node('p',`Colours ${result.colours} → ${result.after_colours}; ${result.proof.changed_pixels} pixels changed. Outside-patch RGBA and mask hashes match.`));
   if(result.operation.type==='split-region')out.append(node('p',`Measured ΔE76 ${result.operation.measured_delta_e76}; local separation threshold ${result.operation.local_threshold_delta_e76}. Global settings are unchanged.`));
   out.append(node('p','Accepting approves this corrected subject, saves the operation and regenerates stitches.'));
   const apply=node('button','Accept & regenerate stitches');apply.id='acceptRefinement';apply.onclick=()=>{if(snapshot!==JSON.stringify(studio.snapshot()))return;studio.acceptRefinement(result.patch);out.replaceChildren();$('refineStatus').textContent='Correction accepted. Regenerating stitches and the worklist…';history()};
   const cancel=node('button','Dismiss');cancel.onclick=()=>out.replaceChildren();out.append(apply,cancel);$('refineStatus').textContent='Proposal ready. Current stitch plan is unchanged until you accept and regenerate.';
  }
 }catch(error){if(version===revision)$('refineStatus').textContent=error.message}finally{busy=false}
}
$('refreshWorklist').onclick=()=>request();
$('original').addEventListener('pointerdown',e=>{if(!pointMode)return;e.stopImmediatePropagation();e.preventDefault();const point=studio.point(e).map(Math.round),kind=pointMode;pointMode=null;request('propose',selected,kind,point)},true);
window.addEventListener('studio:changed',()=>{revision++;pointMode=null;$('refineProposal').replaceChildren();$('refineWorklist').replaceChildren();$('refineStatus').textContent='Settings changed. Update stitches before comparing again.';history()});
window.addEventListener('studio:preview',event=>{history();if(event.detail.hasPlayback)setTimeout(()=>request(),0)});
history();
})();
