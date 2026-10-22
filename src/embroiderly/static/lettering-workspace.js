/* The existing text controller owns the recipe/check/save. This adapter only
   connects it to the shared canvas and toolbar. Never POST to /artwork here. */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 const initial=window.nativeTextConfig;if(!initial)return;
 const $=id=>document.getElementById(id),studio=window.embroideryStudio;
 const fields={letteringWords:'text',letteringAlign:'align',letteringColour:'colour',nativeFont:'font',nativeHeight:'height_mm',nativeWidth:'available_width_mm'};
 const inspector=document.querySelector('.inspector');
 document.body.classList.add('native-text-workspace');
 document.title='Editable embroidery text · Embroiderly';
 for(const child of inspector.children)child.hidden=true;
 const section=document.createElement('section');section.id='workspaceText';
 const heading=document.createElement('h1');heading.textContent='Edit embroidery text';
 const note=document.createElement('p');note.textContent='Edit your words, then check the stitches.';
 section.append(heading,note);
 for(const id of ['letteringWords','letteringAlign','letteringColour']){
  const el=$(id),label=document.querySelector('label[for="'+id+'"]');
  if(label)section.append(label,el);else section.append(el.closest('label'));
 }
 section.append($('nativeLettering'));inspector.append(section);
 $('nativeCheck').textContent='Update stitches';$('nativeApprove').textContent='Save design';
 $('nativeHeight').closest('section').querySelector('h2').textContent='Font & size';
 $('nativeWorkspaceLink').hidden=true;
 $('letteringWords').setAttribute('aria-describedby','nativeStatus');
 $('nativeLettering').querySelector('p').textContent='Edit your words, then check the stitches. Your saved version stays unchanged.';
 $('confirmed').checked=true;
 $('stitchEmptyConfirm').closest('label').hidden=true;
 $('stitchEmptyGenerate').onclick=()=>$('nativeCheck').click();
 $('save').onclick=()=>$('nativeApprove').click();$('stitch').onclick=()=>$('nativeCheck').click();
 $('textTool').setAttribute('aria-pressed','true');
 for(const button of document.querySelectorAll('[data-tool]')){
  if(!['pan','measure'].includes(button.dataset.tool)){button.hidden=true;button.disabled=true;}
 }
 for(const view of ['isolated','prepared'])document.querySelector('[data-view="'+view+'"]').hidden=true;
 document.querySelector('[data-view="original"]').textContent='Letter shapes';
 document.querySelector('[data-view="compare"]').onclick=()=>studio.review('review');
 $('inspectDetail').hidden=true;
 document.querySelector('.piece-layers')?.setAttribute('hidden','');
 document.querySelector('.workbench').classList.remove('with-pieces');
 studio.selectTool('pan');
 $('rulerEditSize').onclick=()=>{$('nativeHeight').scrollIntoView({block:'center'});$('nativeHeight').focus();};
 let current=null,version=0,loading=false,checking=false,dirty=false,history=[],future=[],snapshot;
 const values=()=>window.nativeLettering.values();
 function assign(recipe){
  for(const [id,key] of Object.entries(fields))$(id).value=recipe[key];snapshot=JSON.stringify(values());
  // 3D puff lives in puff-controls.js, which may start after this file.
  // Only the size range follows; no input event, so the loaded check stays valid.
  const puff=()=>{window.NativePuff.set(recipe.puff,recipe.puff_foam_mm);const option=$('nativeFont').selectedOptions[0];
   if(recipe.puff&&option?.dataset.puffMax)$('nativeHeight').max=option.dataset.puffMax;snapshot=JSON.stringify(values());};
  if(window.NativePuff)puff();else setTimeout(()=>window.NativePuff&&puff(),0);
 }
 function status(message){$('status').textContent=message;}
 function buttons(){
  $('stitch').disabled=checking||loading;
  $('save').disabled=checking||loading||!current?.checks_passed||current.approved;
  $('nativeApprove').disabled=$('save').disabled;
  $('undo').disabled=!history.length||checking||loading;$('redo').disabled=!future.length||checking||loading;
  for(const [id,fmt] of [['exportDst','dst'],['exportPes','pes']]){
   $(id).hidden=!current?.approved||loading||checking;
   if(current?.approved)$(id).href='/lettering/native/'+current.id+'/download/'+fmt;
  }
 }
 function invalidate(){
  version++;loading=false;current=null;dirty=true;studio.nativeClear();buttons();
  $('healthSummary').textContent='Text changed · Update stitches to check';
  $('designSize').textContent='Size needs updating';
  if($('pieceStitchTotal'))$('pieceStitchTotal').textContent='No current stitches';
  $('stitchStatus').textContent='Previous letter shapes only. Update stitches for the edited words and size.';
 }
 document.addEventListener('lettering:invalidated',invalidate);
 document.addEventListener('lettering:status',e=>status(e.detail));
 document.addEventListener('lettering:busy',e=>{checking=e.detail;buttons();});
 document.addEventListener('lettering:result',async e=>{
  const data=e.detail,token=++version;current=null;loading=true;buttons();
  try{
   const response=await fetch('/lettering/native/'+data.id+'/workspace-data',{signal:AbortSignal.timeout(30000)});
   const payload=await response.json();if(token!==version)return;
   if(!response.ok)throw Error(payload.error||'The checked stitch plan could not be loaded. Retry Update stitches.');
   if(!await studio.nativeAccept(payload)||token!==version)return;
   // Checked stitches are stored at /text/<id>, so a reload keeps them.
   current=data;dirty=false;
   const r=data.reports.dst;
   if($('pieceStitchTotal'))$('pieceStitchTotal').textContent=r.stitches+' total stitches';
   $('healthSummary').textContent=(data.checks_passed?'File checks passed':'Check these stitches')+' · '+r.stitches+' stitches · '+r.trims+' cuts';
   $('healthIssues').replaceChildren();
   const warning=document.createElement('p');warning.textContent='No picture cleanup was used. These checks do not prove density, readability or needle safety. Sew a sample on your fabric.';$('healthIssues').append(warning);
   window.history.replaceState(null,'','/text/'+data.id);
   status(data.approved?'Saved. The canvas and both downloads use this checked plan. Test sew-out required.':data.message);
  }catch(error){if(token===version){current=null;studio.nativeClear();status('Stitch view unavailable. '+error.message);}}
  finally{if(token===version)loading=false;buttons();}
 });
 for(const [id,fmt] of [['exportDst','dst'],['exportPes','pes']])$(id).addEventListener('click',e=>{
  // Keep all errors inside the workspace rather than opening raw JSON tabs.
  e.preventDefault();if(!current?.approved||loading||checking)return;
  $('native'+fmt[0].toUpperCase()+fmt.slice(1)).click();
 });
 for(const id of Object.keys(fields))$(id).addEventListener('input',()=>{
  const next=JSON.stringify(values());if(next!==snapshot){history.push(snapshot);if(history.length>30)history.shift();future=[];snapshot=next;buttons();}
 });
 function undo(redo){
  const from=redo?future:history,to=redo?history:future;if(!from.length)return;
  to.push(snapshot);assign(JSON.parse(from.pop()));
  // Dispatch through the canonical controller so stale approval cannot survive.
  $('nativeHeight').dispatchEvent(new Event('input',{bubbles:true}));buttons();
 }
 $('undo').onclick=()=>undo(false);$('redo').onclick=()=>undo(true);
 // Warn only when words were edited and not stitched yet; a reload loses only those edits.
 window.addEventListener('beforeunload',e=>{if(dirty&&$('letteringWords').value.trim()){e.preventDefault();e.returnValue='';}});
 window.NativeWorkspace={action:action=>{if(action==='save')$('nativeApprove').click();else if(action==='digitize')$('nativeCheck').click();}};
 assign(initial.recipe);buttons();
 // Immutable saved recipe is authoritative; never load an old image's recipe.
 if(!initial.id){status('Type your words, then Check stitches.');return;}
 const bootVersion=version;
 fetch('/lettering/native/'+initial.id,{signal:AbortSignal.timeout(15000)}).then(async response=>{
  const data=await response.json();if(dirty||bootVersion!==version)return;
  if(!response.ok)throw Error(data.error||'Saved lettering could not be loaded.');
  window.nativeLettering.load(data);
 }).catch(error=>{if(bootVersion===version){status(error.message+' Your words are still here. Press Update stitches to rebuild.');buttons();}});
});
