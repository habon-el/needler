/* Proposal UI only. Preparation options/history remain the sole design owner. */
(() => {
'use strict';
const $=id=>document.getElementById(id),studio=window.embroideryStudio,assistant=window.embroideryAssistance;
let draft=null,applied=null,pick=null,selecting=false,pressed=null,editIndex=null,imageReady=false;
const status=text=>$('knockoutStatus').textContent=text;
const inputs=['knockoutColour','knockoutScope','knockoutTolerance','knockoutCleanup','knockoutArea','knockoutRadius'];
function fill(op){
 $('knockoutColour').value=op.colour;$('knockoutScope').value=op.scope;
 $('knockoutTolerance').value=op.tolerance;$('knockoutCleanup').checked=op.cleanup;
 $('knockoutArea').value=op.minimum_area_mm2;$('knockoutRadius').value=op.close_radius_mm;
 if(op.point)pick=op.point;
}
function operation(){
 const number=(id,min,max)=>{
  const field=$(id),value=Number(field.value);
  const valid=field.value.trim()!==''&&Number.isFinite(value)&&value>=min&&value<=max;
  field.setAttribute('aria-invalid',String(!valid));
  if(!valid){field.focus();throw Error('Enter a value from '+min+' to '+max+' for '+field.closest('label').firstChild.textContent.trim()+'.')}
  return value;
 };
 const op={colour:$('knockoutColour').value,scope:$('knockoutScope').value,tolerance:number('knockoutTolerance',0,100),
  cleanup:$('knockoutCleanup').checked,minimum_area_mm2:number('knockoutArea',0,25),close_radius_mm:number('knockoutRadius',0,Number($('knockoutRadius').max)),restore_parts:[]};
 if(op.scope==='this area'){if(!pick)throw Error('Use Remove colour to click the area on the original first.');op.point=pick}
 return op;
}
function propose(op){
 if(studio.isBusy()||assistant.isBusy()){status('Wait for the current preview to finish.');return}
 const operations=structuredClone(studio.snapshot().colour_knockouts||[]);
 if(editIndex!==null&&editIndex<operations.length)operations[editIndex]=op;
 else operations.push(op);
 assistant.request({action:'preview',patch:{colour_knockouts:operations}});
}
function preview(){try{propose(operation())}catch(error){status(error.message)}}
function updateCurrent(update){
 if(studio.isBusy()||assistant.isBusy())return;
 if(draft){
  if(draft.snapshot!==JSON.stringify(studio.snapshot())){cancel();status('Artwork changed. Preview removal again.');return}
  const patch=structuredClone(draft.result.patch);update(patch.colour_knockouts.at(-1));
  assistant.request({action:'preview',patch});
 }else if(applied){
  const operations=structuredClone(studio.snapshot().colour_knockouts||[]);
  if(!operations.length)return;update(operations.at(-1));
  studio.apply({colour_knockouts:operations});
 }
}
function showParts(report){
 const container=$('knockoutParts');container.replaceChildren();
 const heading=document.createElement('h4');heading.textContent='Enclosed parts · tick to keep';container.append(heading);
 const hint=document.createElement('p');hint.className='muted';hint.textContent=report.parts.length?'Check eyes, badge text and other intentional details. Unticked parts are transparent.':'No larger enclosed parts were found.';container.append(hint);
 const list=document.createElement('div');list.className='knockout-parts-list';container.append(list);
 for(const part of report.parts){
  const label=document.createElement('label');label.className='knockout-part';
  const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=part.keep;checkbox.dataset.partId=part.id;
  const image=document.createElement('img');image.alt='';image.width=46;image.height=46;
  if(part.thumbnail)image.src=part.thumbnail;
  else{
   // Existing applied report has no thumbnails; crop a context view from source.
   const source=new Image();source.onload=()=>{if(!label.isConnected)return;const [x,y,r,b]=part.bounds,c=document.createElement('canvas');c.width=Math.max(1,r-x+8);c.height=Math.max(1,b-y+8);c.getContext('2d').drawImage(source,x-4,y-4,c.width,c.height,0,0,c.width,c.height);image.src=c.toDataURL()};source.src=window.preparationConfig.original;
  }
  const text=document.createElement('span');text.textContent=part.label+' · '+part.area_mm2.toFixed(2)+' mm²';
  checkbox.addEventListener('change',()=>{const keep=checkbox.checked;updateCurrent(op=>{op.restore_parts=(op.restore_parts||[]).filter(id=>id!==part.id);if(keep){op.restore_parts.push(part.id);op.fill_parts=(op.fill_parts||[]).filter(id=>id!==part.id)}})});
  label.append(checkbox,image,text);list.append(label);
  if(part.review_hole){
   const explanation=document.createElement('p');explanation.textContent=part.filled?'Filled by your choice.':'Left open. This may be a letter hole; size and shape alone cannot prove it is texture.';list.append(explanation);
   const button=document.createElement('button');button.type='button';button.textContent=part.filled?'Keep hole open':'Fill this speck';button.setAttribute('aria-pressed',String(part.filled));
   button.addEventListener('click',()=>updateCurrent(op=>{
    op.fill_parts=(op.fill_parts||[]).filter(id=>id!==part.id);
    if(!part.filled){op.fill_parts.push(part.id);op.restore_parts=(op.restore_parts||[]).filter(id=>id!==part.id);op.cleanup=true}
   }));list.append(button);
  }
 }
}
function measurements(report,proposed){
 $('knockoutResult').hidden=false;$('knockoutDraftActions').hidden=!proposed;
 $('knockoutMeasurements').textContent=(proposed?'Proposed':'Applied')+' · matching colour remaining: '+report.remaining_colour_area_mm2.toFixed(4)+' mm²'+(report.restored_pixels?' (includes parts you kept).':'.');
 $('knockoutBrushReport').textContent=report.cleanup_note+' Edge close: '+report.effective_close_radius_mm.toFixed(3)+' mm.';
 $('knockoutUndoCleanup').hidden=!report.operation.cleanup;
 showParts(report);
}
function cancel(){draft=null;imageReady=false;assistant.cancel();studio.clearProposal();$('knockoutDraftActions').hidden=true;if(applied)measurements(applied,false);else $('knockoutResult').hidden=true;status('Proposal cancelled. Your artwork is unchanged.')}
window.colourKnockout={async show(result,snapshot){
 draft={result,snapshot};imageReady=false;$('knockoutApply').disabled=true;fill(result.knockout.operation);measurements(result.knockout,true);
 window.embroideryWorkspace?.showTopic('selection');
 try{await studio.showProposal(result);if(draft?.result===result){imageReady=true;$('knockoutApply').disabled=assistant.isBusy();status('Before / after proposal. Check the holes and parts, then Apply removal.')}}
 catch(error){status(error.message);draft=null;$('knockoutApply').disabled=true}
}};
$('knockoutPreview').addEventListener('click',preview);
for(const id of inputs)$(id).addEventListener('change',()=>{if(draft)preview()});
$('knockoutApply').addEventListener('click',()=>{
 if(!draft||!imageReady||studio.isBusy()||assistant.isBusy())return;
 if(draft.snapshot!==JSON.stringify(studio.snapshot())){cancel();status('Artwork changed. Preview removal again.');return}
 const patch=draft.result.patch;draft=null;selecting=false;studio.clearProposal();studio.apply(patch);
 status('Removal applied. Undo restores it; Save design keeps it between sessions.');
});
$('knockoutCancel').addEventListener('click',cancel);
$('knockoutUndoCleanup').addEventListener('click',()=>updateCurrent(op=>op.cleanup=false));
document.querySelectorAll('[data-tool]').forEach(button=>button.addEventListener('click',()=>{selecting=button.dataset.tool==='colour-remove';if(selecting){studio.clearProposal();status('Click a colour on the original. Space-drag still moves the image.')}}));
const canvas=$('original');
canvas.addEventListener('pointerdown',event=>{
 if(!selecting||studio.navigationGesture(event)||event.button!==0)return;
 event.preventDefault();event.stopImmediatePropagation();
 if(studio.isBusy()||assistant.isBusy())return;
 pressed=event.pointerId;canvas.setPointerCapture(pressed);
},true);
canvas.addEventListener('pointerup',event=>{
 if(pressed!==event.pointerId)return;event.stopImmediatePropagation();pressed=null;
 if(canvas.hasPointerCapture(event.pointerId))canvas.releasePointerCapture(event.pointerId);
 pick=studio.point(event);$('knockoutColour').value=studio.sampleColour(pick);draft=null;editIndex=null;preview();
},true);
canvas.addEventListener('pointercancel',()=>pressed=null,true);
window.addEventListener('assist:state',event=>{
 const busy=event.detail.busy;if(busy)imageReady=false;$('knockoutControls').setAttribute('aria-busy',String(busy));
 $('knockoutPreview').disabled=busy;$('knockoutApply').disabled=busy||!imageReady;
 for(const id of inputs)$(id).disabled=busy;
 $('knockoutUndoCleanup').disabled=busy;
 $('knockoutParts').querySelectorAll('input,button').forEach(input=>input.disabled=busy);
 if(busy&&event.detail.colourRemoval)status('Calculating a colour-removal proposal. Your design is unchanged…');
});
window.addEventListener('studio:controls',()=>{
 const busy=studio.isBusy()||assistant.isBusy();
 $('knockoutPreview').disabled=busy;$('knockoutApply').disabled=busy||!draft||!imageReady;
 $('knockoutUndoCleanup').disabled=busy;
 for(const id of inputs)$(id).disabled=busy;
 $('knockoutParts').querySelectorAll('input,button').forEach(input=>input.disabled=busy);
});
window.addEventListener('assist:error',event=>{imageReady=false;status('Could not preview removal: '+event.detail+'. Your design is unchanged; retry Preview removal.');$('knockoutApply').disabled=true});
window.addEventListener('studio:changed',()=>{draft=null;applied=null;imageReady=false;editIndex=null;studio.clearProposal();$('knockoutResult').hidden=true});
window.addEventListener('studio:preview',event=>{
 const report=event.detail.report.colour_knockouts?.at(-1);
 if(report&&!draft){applied=report;editIndex=event.detail.options.colour_knockouts.length-1;fill(report.operation);measurements(report,false);status('Applied removal. Tick a part to restore it in one click, or Undo brush cleanup only.')}
});
})();
