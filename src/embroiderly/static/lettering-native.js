/* Native satin text owns one explicit check/approval, bound to its recipe. */
(() => {
 'use strict';
 const $=id=>document.getElementById(id), dialog=$('letteringDialog');
 const fields=['letteringWords','letteringAlign','letteringColour','nativeFont','nativeHeight','nativeWidth','nativeFabric',
  'nativeBaseline','nativeCurve','nativeLetterSpacing','nativeLineSpacing','nativeSequence'];
 // Layout controls and the recipe keys they set; a control left at its default sends nothing.
 const layoutFields=[['nativeBaseline','baseline','straight'],['nativeLetterSpacing','letter_spacing_mm','0'],
  ['nativeLineSpacing','line_spacing_percent','100'],['nativeSequence','sequence','left']];
 function layout(){const out={};
  for(const [id,key,plain] of layoutFields){const v=$(id).value;if(v!==plain)out[key]=$(id).type==='number'?Number(v):v;}
  // Curve in degrees (the circle follows the words' length). Lettering saved with a radius
  // keeps it until the Curve slider is moved.
  if(out.baseline){if(savedRadius)out.arc_radius_mm=savedRadius;else out.arc_degrees=Number($('nativeCurve').value);}return out;}
 let savedRadius=null;
 const showRadius=()=>{$('nativeCurveField').hidden=$('nativeBaseline').value==='straight';$('nativeCurveValue').textContent=$('nativeCurve').value+'°';};
 $('nativeBaseline').addEventListener('input',showRadius);$('nativeBaseline').addEventListener('change',showRadius);
 $('nativeCurve').addEventListener('input',()=>{savedRadius=null;showRadius();});
 // Fabric preset: the satin edge follows the fabric, as in the main studio.
 // A saved recipe can arrive before the list; keep its fabric until the options exist.
 let fabricWanted=null;const setFabric=value=>{fabricWanted=value;$('nativeFabric').value=value;};
 fetch('/api/fabrics').then(r=>r.json()).then(data=>{const select=$('nativeFabric'),kept=fabricWanted??select.value;
  select.replaceChildren(...data.fabrics.map(f=>new Option(f.label,f.id===data.default?'':f.id)));select.value=kept;}).catch(()=>{});
 const active=()=>!!window.nativeTextConfig||dialog.open;
 const emit=(name,data)=>document.dispatchEvent(new CustomEvent('lettering:'+name,{detail:data}));
 // Fabric, shape, curve and spacing of a saved recipe (the words, font and size are set by the caller).
 function applyLayout(recipe){
  setFabric(recipe.fabric_preset||'');
  for(const [id,key,plain] of layoutFields)$(id).value=recipe[key]??plain;
  savedRadius=recipe.arc_degrees?null:recipe.arc_radius_mm||null;
  $('nativeCurve').value=recipe.arc_degrees||90;
  showRadius();$('nativeLayout').open=layoutFields.some(([,key])=>key in recipe);
  emit('layout',recipe);
 }
 window.nativeLettering={values:()=>values(),load:data=>render(data),applyLayout};
 let revision=0, controller, result=null, busy=false;
 const status=text=>{$('nativeStatus').textContent=text;emit('status',text);};
 function invalidate(){
  revision++;controller?.abort();result=null;emit('invalidated');
  $('nativeApprove').disabled=true;$('nativeDownloads').hidden=true;$('nativePreview').hidden=true;
  $('nativeResult').textContent='';$('nativeChanges').textContent='';$('nativeProblems').hidden=true;
  $('nativeFit').textContent='Width not checked for these settings. Nothing will be resized automatically.';
 }
 function values(){return {text:$('letteringWords').value,font:$('nativeFont').value,height_mm:Number($('nativeHeight').value),
  available_width_mm:Number($('nativeWidth').value),align:$('letteringAlign').value,colour:$('letteringColour').value,
  ...layout(),
  ...(window.NativePuff?.get()?{puff:true,puff_foam_mm:window.NativePuff.foam()}:
      $('nativeFabric').value?{fabric_preset:$('nativeFabric').value}:{})};}
 function render(data){
  result=data;const r=data.reports.dst,p=data.reports.pes;
  $('nativePreview').src=data.image;$('nativePreview').hidden=false;
  $('nativeResult').textContent=`${r.width_mm} mm wide × ${r.height_mm} mm high · ${r.stitches} stitches · ${r.trims} cuts. `+
   (data.checks_passed?'Both machine files passed the file checks. ':`Download blocked — DST: ${r.short} stitches too short, ${r.long} too long, ${r.crossings} across empty areas, ${r.missing_columns} missing letter parts; PES: ${p.short} too short, ${p.long} too long, ${p.crossings} across empty areas, ${p.missing_columns} missing letter parts. `)+
   `Stitch lengths: DST ${r.minimum_mm}–${r.maximum_mm} mm; PES ${p.minimum_mm}–${p.maximum_mm} mm.`;
  if(data.lock_adjustment)$('nativeResult').textContent+=` Adjusted the securing stitches: ${data.lock_adjustment.before_short} too-short stitches → 0. Words, font and size are unchanged; review before saving.`;
  $('nativeFit').textContent=data.fit.fits?`Width fits: ${r.width_mm} mm within your ${data.fit.available_width_mm} mm space. No resizing.`:
   `Too wide: ${r.width_mm} mm, but Max width is ${data.fit.available_width_mm} mm. Use the fix under Make stitches, or add a line break. Nothing is shrunk automatically.`;
  $('nativeChanges').textContent=`Kept ${data.source_glyphs} letters and punctuation marks. Added ${data.extra_component_cuts} cuts between separate font pieces, including dots. Tie-off stitches (stop the thread coming loose) are 0.6 mm; spacing and supporting stitches follow the font. ${data.cached?'Reused the checked files.':`Built in ${data.seconds} seconds.`}`;
  $('nativeProblemList').replaceChildren();
  for(const fmt of ['dst','pes'])for(const issue of data.issues[fmt]){const li=document.createElement('li'),p=issue.location;
   li.textContent=fmt.toUpperCase()+': '+issue.reason+(p?` — x ${p.x_mm}, y ${p.y_mm} mm`:'');$('nativeProblemList').append(li);}
  $('nativeProblems').hidden=!data.issues.dst.length&&!data.issues.pes.length;
  $('nativeApprove').disabled=!data.checks_passed||data.approved;
  $('nativeDownloads').hidden=!data.approved;
  $('nativeBookmark').href=$('nativeWorkspaceLink').href='/text/'+data.id;
  emit('result',data);
  status(data.approved?'Saved locally. Download the checked files below, or edit the words to make a new version.':data.message);
 }
 async function json(url, options){
  const response=await fetch(url,options);const data=await response.json();if(!response.ok)throw Error(data.error||'The check could not finish. Please retry.');return data;
 }
 for(const id of fields)$(id).addEventListener('input',()=>{invalidate();status('Settings changed. Check stitches again before saving.');});
 document.addEventListener('lettering:busy',e=>{
  $('nativeSmaller').disabled=$('nativeLarger').disabled=e.detail;
 });
 function sizeRange(){
  const option=$('nativeFont').selectedOptions[0];
  // Puff letters may be larger: their strokes must be as wide as the foam is thick.
  // The height is the height of the stitched words, which depends on the words:
  // the server gives the exact range for them (small_lettering.scale_for).
  $('nativeHeight').min=1;$('nativeHeight').max=400;
 }
 sizeRange();$('nativeFont').addEventListener('input',sizeRange);
 for(const [id,factor] of [['nativeSmaller',.9],['nativeLarger',1.1]])$(id).addEventListener('click',()=>{
  if(busy)return;
  sizeRange();const input=$('nativeHeight'),next=Math.round(Number(input.value)*factor*10)/10;
  if(!input.value.trim()||!Number.isFinite(next)||next<Number(input.min)||next>Number(input.max)){
   input.setAttribute('aria-invalid','true');status(`This font offers ${input.min}–${input.max} mm sizes. Enter a size in that range; nothing was resized.`);input.focus();return;
  }
  input.value=next;input.removeAttribute('aria-invalid');input.dispatchEvent(new Event('input',{bubbles:true}));
  status(`Font size ${next} mm. Check stitches to rebuild the letters; old stitches are not stretched.`);
 });
 // Escape restores the last committed field value, not a half-entered size.
 let sizeBefore=$('nativeHeight').value;
 $('nativeHeight').addEventListener('focus',()=>{sizeBefore=$('nativeHeight').value;});
 $('nativeHeight').addEventListener('keydown',e=>{
  if(e.isComposing||e.key!=='Escape')return;
  e.preventDefault();e.stopPropagation();$('nativeHeight').value=sizeBefore;$('nativeHeight').dispatchEvent(new Event('input',{bubbles:true}));
 });
 dialog.addEventListener('close',invalidate);
 $('nativeCheck').addEventListener('click',async()=>{
  if(busy)return;
  const body=values();
  for(const [id,valid,message] of [
   ['letteringWords',!!body.text.trim(),'Enter your words above.'],
   ['nativeHeight',Number.isFinite(body.height_mm)&&body.height_mm>=Number($('nativeHeight').min)&&body.height_mm<=Number($('nativeHeight').max),'Enter the height of your stitched words in mm.'],
   ['nativeWidth',Number.isFinite(body.available_width_mm)&&body.available_width_mm>=5&&body.available_width_mm<=400,'Enter an available width from 5 to 400 mm.']]){
   $(id).setAttribute('aria-invalid',String(!valid));if(!valid){status(message);emit('failed',message);$(id).focus();return;}
  }
  invalidate();const version=revision;busy=true;controller=new AbortController();
  $('nativeCheck').disabled=true;$('nativeCheck').setAttribute('aria-busy','true');emit('busy',true);
  status('Building satin letters and checking the written DST and PES. You can keep editing; changed settings will need a fresh check.');
  const timeout=setTimeout(()=>controller.abort(),260000);
  try{
   const data=await json('/lettering/native/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:controller.signal});
   if(version===revision&&active()&&JSON.stringify(values())===JSON.stringify(body))render(data);
   else if(version===revision&&active()){invalidate();status('The words changed while loading. Build and check again.');}
  }catch(e){if(version===revision&&active()){const message=e.name==='AbortError'?'The check timed out. Your picture is unchanged. Retry shortly.':e.message;status(message);emit('failed',message);}}
  finally{clearTimeout(timeout);busy=false;$('nativeCheck').disabled=false;$('nativeCheck').removeAttribute('aria-busy');emit('busy',false);}
 });
 $('nativeApprove').addEventListener('click',async()=>{
  if(!result?.checks_passed||$('nativeApprove').disabled)return;
  const current=result,version=revision;$('nativeApprove').disabled=true;
  try{
   await json(`/lettering/native/${current.id}/approve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approve:true}),signal:AbortSignal.timeout(15000)});
   if(version===revision&&active())render({...current,approved:true});
  }catch(e){if(version===revision&&active()){status('Could not confirm saving. Retry Save; it will not create a duplicate. '+e.message);$('nativeApprove').disabled=false;}}
 });
 for(const fmt of ['dst','pes'])$('native'+fmt[0].toUpperCase()+fmt.slice(1)).addEventListener('click',async function(){
  if(!result?.approved||this.disabled)return;
  const version=revision,id=result.id;this.disabled=true;status('Checking the saved files before download…');
  try{
   const response=await fetch(`/lettering/native/${id}/download/${fmt}`,{signal:AbortSignal.timeout(30000)});
   if(!response.ok){const data=await response.json();throw Error(data.error);}
   const blob=await response.blob();if(version!==revision||!active())return;
   const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='embroiderly-lettering.'+fmt;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);
   status(fmt.toUpperCase()+' file checked and sent to your browser’s downloads. Physical sew-out still required.');
  }catch(e){if(version===revision&&active())status('Download not released. '+e.message);}
  finally{this.disabled=false;}
 });
 // Bookmark hydration waits for the existing dialog's source-recipe loader,
 // preventing a late legacy response from replacing the saved native words.
 document.addEventListener('lettering:ready',async()=>{
  const id=new URL(location.href).searchParams.get('native_text');
  if(!active())return;
  if(!id){
   if(result||busy){invalidate();status('Loaded your saved words. Build and check them before saving.');}
   return;
  }
  const version=revision;
  try{
   const data=await json('/lettering/native/'+encodeURIComponent(id),{signal:AbortSignal.timeout(15000)});
   if(version!==revision||!active())return;
   window.NativePuff?.set(data.recipe.puff,data.recipe.puff_foam_mm);
   for(const [field,key] of [['letteringWords','text'],['letteringAlign','align'],['letteringColour','colour'],['nativeFont','font'],['nativeHeight','height_mm'],['nativeWidth','available_width_mm']])$(field).value=data.recipe[key];
   applyLayout(data.recipe);
   render(data);
  }catch(e){status('Saved lettering could not be loaded. '+e.message);}
 });
 if(new URL(location.href).searchParams.has('native_text'))window.addEventListener('load',()=>$('textTool').click());
})();
