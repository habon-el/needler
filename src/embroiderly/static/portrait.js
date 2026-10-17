(() => {
'use strict';
const studio=window.embroideryStudio,config=window.preparationConfig,$=id=>document.getElementById(id);
const section=document.createElement('details');section.open=true;
section.innerHTML=`<summary>Portrait &amp; photographic detail</summary>
<p id="portraitMode" class="muted"></p><p id="portraitDetection" class="muted">Checking for a possible face locally…</p>
<button id="portraitPropose">Preview portrait mode</button><button id="portraitLogo">Use logo mode</button>
<div id="portraitProposal"></div>
<div id="portraitControls" hidden>
<p class="muted">Experimental photo-stitch · 8–12 colours. Exported stitch lengths checked at 0.3–7 mm. No automatic underlay or tie-off; physical sew-out is essential.</p>
<label>Colour order<select id="photoOrder"><option value="light_to_dark">Light to dark</option><option value="dark_to_light">Dark to light</option></select></label>
<label>Default direction (degrees)<input id="photoAngle" type="number" min="-180" max="180" value="0"></label>
<label>Boundary blend (mm)<input id="photoBlend" type="number" min="0" max="1" step=".1" value=".6"></label>
<label>Row spacing (mm)<input id="photoSpacing" type="number" min=".4" max="1.5" step=".1" value=".4"></label>
<label>Feature label<select id="featureKind"><option value="mouth">Mouth</option><option value="eyes">Eyes</option><option value="teeth">Teeth or gap</option><option value="detail">Other detail</option></select></label>
<button id="markFeature">Draw feature box</button><button id="drawDirection">Draw region direction</button><button id="clearPortraitMarks">Clear portrait marks</button>
<p id="portraitHint" class="muted">Mark features to measure them. Direction lines start inside a prepared colour region and set one angle for that connected region—not automatic facial flow.</p>
<div id="portraitReport"></div></div>`;
document.querySelector('.inspector h1').after(section);
let mode=null,gesture=null,revision=0,first=true,download=null,proposalBusy=false;
const node=(tag,text)=>{const e=document.createElement(tag);e.textContent=text;return e};
function sync(){const options=studio.snapshot(),portrait=options.artwork_type==='portrait';$('portraitMode').textContent=portrait?'Active: Portrait / photo-stitch':'Active: Logo / existing fill engine';$('portraitControls').hidden=!portrait;
 $('photoOrder').value=options.photo_order||'light_to_dark';$('photoAngle').value=options.photo_angle??0;$('photoBlend').value=options.photo_blend_mm??.6;$('photoSpacing').value=options.photo_spacing_mm??.4;
}
function apply(patch){try{studio.apply(patch);sync()}catch(e){$('portraitHint').textContent=e.message}}
$('portraitLogo').onclick=()=>apply({artwork_type:'logo',fill_style:'auto_fill',count:Math.min(8,studio.snapshot().count),floor_mm2:1,smooth:1,simplify:0,mask_holes_mm2:1,mask_smooth:0});
$('photoOrder').onchange=()=>apply({photo_order:$('photoOrder').value});
for(const [id,key] of [['photoAngle','photo_angle'],['photoBlend','photo_blend_mm'],['photoSpacing','photo_spacing_mm']])$(id).onchange=()=>{if($(id).reportValidity())apply({[key]:+$(id).value})};
$('portraitPropose').onclick=async()=>{
 if(proposalBusy||studio.isBusy())return;proposalBusy=true;const version=revision,snapshot=JSON.stringify(studio.snapshot());$('portraitProposal').replaceChildren(node('p','Preparing a portrait proposal. Your current settings are unchanged.'));
 try{
  const response=await fetch('/portrait/'+encodeURIComponent(config.name),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'propose',options:JSON.parse(snapshot)})});
  const result=await response.json();if(!response.ok)throw Error(result.error);
  if(version!==revision)return;
  const img=document.createElement('img');img.src=result.image;img.alt='Proposed portrait artwork—not yet applied';img.style.cssText='width:100%;max-height:240px;object-fit:contain;background:#eee';
  const button=node('button','Apply portrait mode');button.id='applyPortrait';button.className='primary';
  button.onclick=()=>{if(snapshot!==JSON.stringify(studio.snapshot()))return;apply(result.patch);$('portraitProposal').replaceChildren()};
  $('portraitProposal').replaceChildren(img,node('p',`${result.report.colours_after} colours · ${result.report.regions_after} regions. Preserves smaller colour regions with a 0.16 mm² area floor and reduced cleanup. This is not a stitchability guarantee.`),button);
 }catch(e){$('portraitProposal').replaceChildren(node('p',e.message))}finally{proposalBusy=false}
};
function mark(tool){if($('assistSubject')?.getAttribute('aria-pressed')==='true')$('assistSubject').click();mode=mode===tool?null:tool;studio.selectOriginal();$('portraitHint').textContent=mode==='feature'?'Drag around the feature. The label and box are your annotation—not automatic anatomy detection.':mode==='direction'?'Drag a line starting inside the colour region. Use Artwork view to identify a region, then draw here.':'Selection tools restored.'}
$('markFeature').onclick=()=>mark('feature');$('drawDirection').onclick=()=>mark('direction');
$('clearPortraitMarks').onclick=()=>{mode=null;apply({portrait_features:[],direction_lines:[]})};
document.querySelectorAll('[data-tool],#assistSubject').forEach(e=>e.addEventListener('click',()=>mode=null));
const canvas=$('original');
canvas.addEventListener('pointerdown',e=>{if(!mode)return;e.stopImmediatePropagation();if(studio.isBusy())return;canvas.setPointerCapture(e.pointerId);gesture={start:studio.point(e),tool:mode};},true);
canvas.addEventListener('pointermove',e=>{if(mode)e.stopImmediatePropagation()},true);
canvas.addEventListener('pointerup',e=>{
 if(!mode)return;e.stopImmediatePropagation();if(!gesture)return;
 const a=gesture.start,b=studio.point(e),tool=gesture.tool;gesture=null;
 if(Math.hypot(a[0]-b[0],a[1]-b[1])<3){$('portraitHint').textContent='Draw a larger box or line.';return}
 const options=studio.snapshot();
 if(tool==='feature'){
  const bounds=[Math.floor(Math.min(a[0],b[0])),Math.floor(Math.min(a[1],b[1])),Math.ceil(Math.max(a[0],b[0])),Math.ceil(Math.max(a[1],b[1]))];
  apply({portrait_features:[...(options.portrait_features||[]),{kind:$('featureKind').value,bounds}]});
 }else apply({direction_lines:[...(options.direction_lines||[]),[a,b]]});
 studio.selectOriginal();
},true);
canvas.addEventListener('pointercancel',()=>gesture=null,true);
window.addEventListener('studio:changed',()=>{revision++;$('portraitProposal').replaceChildren();sync()});
window.addEventListener('studio:preview',async e=>{
 sync();const {report,portraitAudit}=e.detail;
 if(first){first=false;
  try{const response=await fetch('/portrait/'+encodeURIComponent(config.name),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'detect',options:studio.snapshot()})});const detection=await response.json();$('portraitDetection').textContent=detection.likely?'Possible face detected. Preview portrait mode to compare; nothing changes automatically.':'No confident face candidate found. You can still choose portrait mode manually.'}catch{$('portraitDetection').textContent='Face detection unavailable. Manual portrait mode is still available.'}
 }
 if(report.artwork_type!=='portrait')return;
 const area=$('portraitReport');area.replaceChildren();
 const removals=[...(report.portrait_removals||[]),...(report.portrait_mask_removals||[])];
 area.append(node('p',`${removals.length} regions affected by cleanup; ${(report.portrait_merges||[]).length} close palette colours merged.`));
 for(const feature of report.portrait_features||[]){
  area.append(node('p',`${feature.kind}: marked area ${feature.box_width_mm} × ${feature.box_height_mm} mm; ${feature.prepared_colours} prepared colours. ${feature.status}. Shape-width recommendation: ${feature.canvas_height_for_shape_mm} mm canvas or larger.`));
  if(feature.alternative)area.append(node('p',feature.alternative));
  const table=document.createElement('table');const header=document.createElement('tr');['Canvas mm','Marked area mm','Width screen'].forEach(s=>header.append(node('th',s)));table.append(header);
  for(const size of [80,150,250]){const scale=size/report.height_mm,w=feature.box_width_mm*scale,h=feature.box_height_mm*scale,row=document.createElement('tr');[size,w.toFixed(2)+' × '+h.toFixed(2),Math.min(w,h)>=1.2?'Passes area-box width screen':'Below 1.2 mm'].forEach(s=>row.append(node('td',s)));table.append(row)}
  area.append(table,node('p','Size comparison is a box-width estimate, not proof of recognizable eyes or individual teeth.'));
 }
 if(!(report.portrait_features||[]).length)area.append(node('p','Draw feature boxes to measure the mouth, eyes or a tooth gap. The app does not automatically identify individual teeth.'));
 if(portraitAudit){const a=portraitAudit.length_audits;area.append(node('p',`Written PES: ${a.pes.stitch_count} stitches, ${a.pes.shortest_stitch_mm.toFixed(2)}–${a.pes.longest_stitch_mm.toFixed(2)} mm. PES and DST length violations: ${a.pes.violations+a.dst.violations}. ${portraitAudit.omissions.length} short or unsafe row fragments not sewn. ${portraitAudit.selected_pixels_without_thread_coverage} selected pixels without estimated thread coverage. Maximum planned boundary penetration: ${portraitAudit.max_planned_penetration_mm} mm.`),node('p',portraitAudit.note));}
 if(download)URL.revokeObjectURL(download);
 download=URL.createObjectURL(new Blob([JSON.stringify({preparation:report,stitches:portraitAudit||null},null,2)],{type:'application/json'}));
 const link=document.createElement('a');link.href=download;link.download='portrait-feature-report.json';link.textContent='Download every removal, feature and overlap measurement';area.append(link);
 });
sync();
})();
