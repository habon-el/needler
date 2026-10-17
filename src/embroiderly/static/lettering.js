/* A new immutable artwork version per Create; no silent source replacement. */
(() => {
 'use strict';
 const $=id=>document.getElementById(id),dialog=$('letteringDialog');
 const button=document.createElement('button');button.type='button';button.id='textTool';button.title='Write words and choose a font';
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.classList.add('ui-icon');
 const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d','M4 6V3h16v3M12 3v18M8 21h8');svg.append(path);
 const label=document.createElement('span');label.textContent='Text';button.append(svg,label);$('undo').before(button);
 if(window.preparationConfig.nativeText){
  button.onclick=()=>{$('letteringWords').scrollIntoView({block:'center'});$('letteringWords').focus();};
  return; // Embroidery font settings are already in the workspace inspector.
 }
 let fonts=[],loaded=false,loading=false,timer,controller,revision=0,approved='',creating=false;
 const inputs=['letteringWords','letteringFont','letteringHeight','letteringSpacing','letteringAlign','letteringColour'];
 const status=s=>$('letteringStatus').textContent=s;
 const recipe=()=>({text:$('letteringWords').value,font:$('letteringFont').value,height_mm:Number($('letteringHeight').value),spacing:Number($('letteringSpacing').value),align:$('letteringAlign').value,colour:$('letteringColour').value});
 function fontList(selected){
  const query=$('letteringSearch').value.toLowerCase().trim(),matches=fonts.filter(f=>(f.family+' '+f.style).toLowerCase().includes(query));
  $('letteringFont').replaceChildren(...matches.map(f=>{const o=document.createElement('option');o.value=f.id;o.textContent=f.family+' · '+f.style;return o}));
  if(matches.some(f=>f.id===selected))$('letteringFont').value=selected;
  $('letteringCount').textContent=new Set(fonts.map(f=>f.family)).size+' font families · '+fonts.length+' styles installed · '+matches.length+' matching styles';
  $('letteringClearSearch').hidden=!query;
 }
 async function load(){
  if(loading)return;loading=true;status('Loading local fonts…');
  const loadRevision=revision;
  try{
   const [catalogue,saved]=await Promise.all([fetch('/lettering/fonts',{signal:AbortSignal.timeout(15000)}),fetch('/lettering/recipe/'+encodeURIComponent(window.preparationConfig.name),{signal:AbortSignal.timeout(15000)})]);
   if(!catalogue.ok||!saved.ok)throw Error('Fonts could not be loaded. Close and reopen Text to retry.');
   fonts=(await catalogue.json()).fonts;const initial=(await saved.json()).recipe;
   fontList(initial?.font||fonts.find(f=>f.family==='Lato'&&f.style==='Regular')?.id);
   if(initial&&loadRevision===revision){for(const [id,key]of [['letteringWords','text'],['letteringHeight','height_mm'],['letteringSpacing','spacing'],['letteringAlign','align'],['letteringColour','colour']])$(id).value=initial[key]}
   loaded=true;schedule();document.dispatchEvent(new Event('lettering:ready'));
  }catch(e){status(e.message)}finally{loading=false}
 }
 function schedule(){
  clearTimeout(timer);controller?.abort();revision++;approved='';$('letteringCreate').disabled=true;$('letteringPreview').hidden=true;$('letteringDimensions').textContent='';
  if(!dialog.open)return;
  status('Updating lettering preview…');timer=setTimeout(preview,350);
 }
 async function preview(){
  if(!loaded){load();return}if(creating)return;
  const version=revision,body=recipe();controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),15000);
  try{
   const res=await fetch('/lettering/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:controller.signal});
   const data=await res.json();if(version!==revision||!dialog.open)return;if(!res.ok)throw Error(data.error);
   $('letteringPreview').src=data.image;$('letteringPreview').hidden=false;
   const cap=data.size.reference_capital_mm;
   $('letteringDimensions').textContent=data.size.width_mm.toFixed(1)+' mm wide × '+data.size.height_mm.toFixed(1)+' mm high · whole text block, not each letter · '+(Number.isFinite(cap)?'reference capitals about '+cap.toFixed(1)+' mm. '+(cap<4?'Very small: picture-based fills may lose letter detail. Use Small embroidery text above.':''):'Letter height unavailable.');
   const font=fonts.find(f=>f.id===body.font);$('letteringLicense').href='/lettering/license/'+font.package;
   approved=JSON.stringify(body);$('letteringCreate').disabled=false;status('Preview ready for artwork only. Use an embroidery font above to build editable stitches.');
  }catch(e){if(version===revision&&dialog.open)status(e.name==='AbortError'?'Preview timed out. Refresh preview to retry.':e.message)}finally{clearTimeout(timeout)}
 }
 button.onclick=()=>{dialog.showModal();$('letteringWords').focus();if(!loaded)load();else {schedule();document.dispatchEvent(new Event('lettering:ready'));}};
 $('letteringClose').onclick=()=>dialog.close();
 dialog.addEventListener('close',()=>{clearTimeout(timer);controller?.abort();revision++;button.focus()});
 dialog.addEventListener('cancel',e=>{if(creating)e.preventDefault()});
 dialog.addEventListener('keydown',e=>{e.stopPropagation();if(e.key==='Escape'){e.preventDefault();if(!creating)dialog.close()}});
 for(const id of inputs)$(id).addEventListener('input',e=>{if(!e.isComposing)schedule()});
 $('letteringWords').addEventListener('compositionend',schedule);
 $('letteringSearch').oninput=e=>{if(e.isComposing)return;const selected=$('letteringFont').value;fontList(selected);schedule()};
 $('letteringSearch').addEventListener('compositionend',()=>{fontList($('letteringFont').value);schedule()});
 $('letteringClearSearch').onclick=()=>{$('letteringSearch').value='';fontList($('letteringFont').value);schedule();$('letteringSearch').focus()};
 $('letteringRetry').onclick=()=>{clearTimeout(timer);schedule()};
 $('letteringCreate').onclick=async()=>{
  if(creating||!approved||approved!==JSON.stringify(recipe()))return;
  if($('nativeCheck').getAttribute('aria-busy')==='true'){status('Wait for the embroidery-text check to finish before creating artwork.');return;}
  const disabledBefore=new Map([...dialog.querySelectorAll('input,textarea,select,button')].map(e=>[e,e.disabled]));
  creating=true;const body=approved;disabledBefore.forEach((_,e)=>e.disabled=true);status('Creating a separate lettering design…');
  try{
   const response=await fetch('/lettering/create',{method:'POST',headers:{'Content-Type':'application/json'},body,signal:AbortSignal.timeout(30000)});const data=await response.json();if(!response.ok)throw Error(data.error);
   $('letteringOpen').href=data.url;$('letteringOpen').hidden=false;status('Created artwork only. To make stitches, use an embroidery font above. Your chosen artwork font and original picture are unchanged.');
   approved='';
  }catch(e){status('Creation could not be confirmed: '+e.message+'. Check Recent designs before retrying.')}finally{
   creating=false;disabledBefore.forEach((disabled,e)=>e.disabled=disabled);$('letteringCreate').disabled=!approved;
  }
 };
})();
