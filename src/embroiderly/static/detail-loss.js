(() => {
'use strict';
const studio=window.embroideryStudio,config=window.preparationConfig;
const section=document.createElement('details');section.open=true;
section.innerHTML='<summary>Detail & mask checks</summary><p>Pink: interior contrast lost. Blue: a mask edge to inspect. These are measurements, not automatic identification of eyes or hair.</p><p id="detailStatus" role="status" aria-live="polite">Checking the next artwork preview…</p><canvas id="detailMap" aria-label="Source image with detail-loss and mask-boundary highlights" style="width:100%;height:auto"></canvas><div id="detailFindings"></div><div id="detailProposal"></div><button id="downloadDetails">Download all measurements</button>';
document.querySelector('.inspector h1').after(section);
const cleanup=document.createElement('div');cleanup.id='cleanupChoices';
section.querySelector('#detailFindings').before(cleanup);
const $=id=>document.getElementById(id),list=$('detailFindings'),proposal=$('detailProposal');
let audit=null,busy=false,revision=0,download=null;
function node(tag,text){const el=document.createElement(tag);el.textContent=text;return el}
function picture(src,label){const figure=document.createElement('figure');figure.style.margin='8px 0';const img=new Image();img.src=src;img.alt=label;img.style.cssText='max-width:100%;max-height:220px;object-fit:contain';figure.append(img,node('figcaption',label));return figure}
function draw(){const image=new Image(),version=revision;image.onload=()=>{if(version!==revision)return;const c=$('detailMap');c.width=image.width;c.height=image.height;const ink=c.getContext('2d');ink.drawImage(image,0,0);for(const [items,colour] of [[audit.findings,'#d7006f'],[audit.boundary,'#007fca']]){ink.strokeStyle=colour;ink.lineWidth=2;for(const item of items){const [x,y,r,b]=item.bounds;ink.strokeRect(x,y,r-x,b-y)}}};image.src=config.original}
async function recover(finding,strategy='local'){
 if(busy||studio.isBusy())return;
 busy=true;const snapshot=JSON.stringify(studio.snapshot()),version=revision;
 proposal.replaceChildren(node('p','Calculating before and after. Nothing has changed.'));
 try{
  const response=await fetch('/details/'+encodeURIComponent(config.name),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'recover',strategy,id:finding.id,options:JSON.parse(snapshot)})});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Recovery unavailable.');
  if(version!==revision||snapshot!==JSON.stringify(studio.snapshot()))return;
  proposal.replaceChildren(picture(result.image,'Before — current reduced artwork'),picture(result.after_image,'After — proposed recovery'),node('p',result.explanation),node('p',`Colours: ${result.colours} → ${result.after_colours}. Contrast warnings: ${result.audit.findings.length} → ${result.after_audit.findings.length}.`));
  const apply=node('button','Apply detail recovery');apply.id='applyDetailRecovery';apply.onclick=()=>{if(snapshot!==JSON.stringify(studio.snapshot())){proposal.replaceChildren(node('p','Artwork changed. Request a fresh preview.'));return}studio.apply(result.patch);proposal.replaceChildren()};
  const dismiss=node('button','Ignore proposal');dismiss.onclick=()=>proposal.replaceChildren();proposal.append(apply,dismiss);
 }catch(error){if(version===revision)proposal.replaceChildren(node('p',error.message))}finally{busy=false}
}
window.addEventListener('studio:changed',()=>{revision++;proposal.replaceChildren();$('detailStatus').textContent='Artwork changed; recalculating checks…';});
window.addEventListener('studio:preview',event=>{
 const report=event.detail.report;
 audit=report.detail_loss;if(!audit)return;revision++;proposal.replaceChildren();list.replaceChildren();cleanup.replaceChildren();draw();
 const changes=report.automatic_changes||(report.cleanup_review||[]).some(item=>item.removed)||(audit.pipeline_changes||[]).length||report.mask_cleanup_changes;
 $('detailStatus').textContent=`${audit.findings.length} possible interior detail-loss areas; ${audit.boundary.length} mask-edge warnings. ${changes?'Cleanup or colour changes are present; review the details below.':'Nothing was changed automatically.'}`;
 const snapshot=JSON.stringify(studio.snapshot());
 const records=report.cleanup_review||[],pending=records.filter(item=>item.decision==='pending');
 if(pending.length){
  cleanup.append(node('p',`${pending.length} small areas are awaiting your choice. Keep them as they were before cleanup, or review each below.`));
  const keep=node('button','Keep all pending details');keep.id='keepPendingDetails';keep.type='button';
  keep.onclick=()=>{
   if(studio.isBusy()||snapshot!==JSON.stringify(studio.snapshot()))return;
   const decisions={...(studio.snapshot().cleanup_decisions||{})};
   for(const item of pending)decisions[item.id]='keep';
   studio.apply({cleanup_decisions:decisions});
  };
  cleanup.append(keep,node('p','Keeps only the pending areas. Your earlier choices stay unchanged. Undo reverses this action.'));
 }else if(records.length)cleanup.append(node('p','All cleanup choices made. Check stitches when ready.'));
 // Bound the DOM for large reviews; every record stays available.
 let shown=0;
 const more=node('button','Show more cleanup details');more.type='button';
 const items=document.createElement('div');cleanup.append(items);
 function page(){
 for(const detail of records.slice(shown,shown+30)){
  const item=document.createElement('article');
  item.append(node('p',`Cleanup detail: ${detail.width_mm} × ${detail.height_mm} mm; ${detail.area_mm2} mm². Image bounds: ${detail.bounds.join(', ')}. Decision: ${detail.decision}.`));
  const locate=node('button','Locate cleanup detail');locate.type='button';locate.onclick=()=>studio.focusBounds(detail.bounds);item.append(locate);
  for(const [value,label] of [['keep','Keep it'],['drop','Let it go']]){
   const button=node('button',label);button.type='button';button.setAttribute('aria-pressed',String(detail.decision===value));
   button.onclick=()=>{
    if(studio.isBusy()||snapshot!==JSON.stringify(studio.snapshot()))return;
    studio.apply({cleanup_decisions:{...(studio.snapshot().cleanup_decisions||{}),[detail.id]:value}});
   };item.append(button);
  }
  items.append(item);
 }
 shown=Math.min(records.length,shown+30);
 more.hidden=shown>=records.length;more.textContent=`Show more cleanup details (${shown} of ${records.length})`;
 }
 more.onclick=page;cleanup.append(more);page();
 if(audit.findings.length>100)list.append(node('p','Texture-heavy artwork: select the subject first. Not every flagged patch is a detail you should stitch.'));
 for(const f of audit.findings.slice(0,20)){
  const item=document.createElement('article');item.append(node('p',`${f.position}: ${f.width_mm} × ${f.height_mm} mm. Contrast ${f.source_contrast} → ${f.result_contrast}. Cause: ${f.cause}.`));
  const locate=node('button','Locate on main image');locate.onclick=()=>studio.focusBounds(f.bounds);item.append(locate);
  if(f.merged_colours.length)item.append(node('p','Recorded colour changes: '+f.merged_colours.map(v=>v.source+' → '+v.target).join(', ')));
  else item.append(node('p',`Representative source tone ${f.source_tone} became ${f.result_tone}; no exact merge pair is proven.`));
  if(f.below_thread_width)item.append(node('p',`Below the nominal 0.4 mm thread-width screen. Estimated canvas height: ${f.canvas_height_for_thread_width_mm} mm. This is not a sewability guarantee.`));
  else {const button=node('button','Preview recovery here');button.onclick=()=>recover(f);item.append(button);if(f.cause==='recorded palette merge'&&event.detail.options.artwork_type==='portrait'){const merge=node('button','Preview lower merge threshold');merge.onclick=()=>recover(f,'merge_threshold');item.append(merge)}}
  if(f.canvas_height_for_area_mm>event.detail.report.height_mm)item.append(node('p',`Area-floor estimate: ${f.canvas_height_for_area_mm} mm canvas height.`));
  list.append(item);
 }
 if(audit.findings.length>20)list.append(node('p','Showing the 20 largest areas. Download includes every finding.'));
 for(const f of audit.boundary.slice(0,5))list.append(node('p',`Mask edge, ${f.position}, ${f.span_mm} mm: ${f.note}`));
 if(audit.boundary.length)list.append(node('p','Use “Click to select a subject”, then cycle candidates if available; Shift-click adds and Alt-click subtracts. Lasso and correction brushes remain available.'));
 if(download)URL.revokeObjectURL(download);download=URL.createObjectURL(new Blob([JSON.stringify({...audit,cleanup_review:records},null,2)],{type:'application/json'}));
});
$('detailMap').title='Click a highlighted area to inspect it close up, including findings outside the first 20.';
$('detailMap').onclick=event=>{
 if(!audit)return;
 const canvas=$('detailMap'),rect=canvas.getBoundingClientRect();
 const x=(event.clientX-rect.left)*canvas.width/rect.width,y=(event.clientY-rect.top)*canvas.height/rect.height;
 const hits=[...audit.findings,...audit.boundary].filter(f=>x>=f.bounds[0]&&x<=f.bounds[2]&&y>=f.bounds[1]&&y<=f.bounds[3]);
 hits.sort((a,b)=>(a.bounds[2]-a.bounds[0])*(a.bounds[3]-a.bounds[1])-(b.bounds[2]-b.bounds[0])*(b.bounds[3]-b.bounds[1]));
 const f=hits[0];if(!f)return;studio.focusBounds(f.bounds);
 proposal.replaceChildren(node('p','Selected detail: inspect original versus artwork at the same zoom.'));
 if(audit.findings.includes(f)&&!f.below_thread_width){const button=node('button','Preview recovery for selected detail');button.onclick=()=>recover(f);proposal.append(button)}
 else proposal.append(node('p','Use Keep/Drop for a mask error; details below the width screen may require a larger design.'));
};
$('downloadDetails').onclick=()=>{if(!download)return;const link=document.createElement('a');link.href=download;link.download='detail-loss-audit.json';link.click()};
})();
