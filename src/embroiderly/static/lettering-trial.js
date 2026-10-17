/* Read-only trial uses the canonical Text dialog and its words/alignment. */
(() => {
 'use strict';
 const $=id=>document.getElementById(id), run=$('smallLetteringRun'),dialog=$('letteringDialog');
 let busy=false,revision=0,controller;
 const status=text=>{$('smallLetteringStatus').textContent=text;};
 function invalidate(){revision++;controller?.abort();$('smallLetteringImage').hidden=true;$('smallLetteringResult').textContent='';$('smallLetteringFit').textContent='Width not checked for these settings. Rebuild the trial; no automatic shrinking.';status('Settings changed. Rebuild the trial to check them.');}
 for(const id of ['letteringWords','letteringAlign','smallLetteringFont','smallLetteringHeight','smallLetteringWidth'])$(id).addEventListener('input',invalidate);
 dialog.addEventListener('close',invalidate);
 run.addEventListener('click',async()=>{
  if(busy)return;
  const height=$('smallLetteringHeight'),words=$('letteringWords'),width=$('smallLetteringWidth');
  const valid=Number.isFinite(Number(height.value))&&Number(height.value)>=4&&Number(height.value)<=6;
  height.setAttribute('aria-invalid',String(!valid));
  if(!valid){status('Use a nominal font height from 4 to 6 mm.');height.focus();return;}
  if(!words.value.trim()){status('Enter your words above.');words.focus();return;}
  const widthValid=Number.isFinite(Number(width.value))&&Number(width.value)>=5&&Number(width.value)<=400;
  width.setAttribute('aria-invalid',String(!widthValid));
  if(!widthValid){status('Enter an available width from 5 to 400 mm.');width.focus();return;}
  invalidate();const version=revision;busy=true;run.disabled=true;run.setAttribute('aria-busy','true');controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),260000);
  status('Rebuilding font vectors and checking saved DST/PES lengths. This may take a few minutes.');
  try{
   const response=await fetch('/lettering/small-trial',{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,
    body:JSON.stringify({text:words.value,font:$('smallLetteringFont').value,height_mm:Number(height.value),available_width_mm:Number(width.value),align:$('letteringAlign').value})});
   const data=await response.json();if(version!==revision||!dialog.open)return;
   if(!response.ok)throw Error(data.error);
   const r=data.reports.dst;
   $('smallLetteringImage').src=data.image;$('smallLetteringImage').hidden=false;
   $('smallLetteringResult').textContent=`Actual stitches: ${r.width_mm} × ${r.height_mm} mm · ${r.stitches} stitches · ${r.trims} cuts · length ${r.minimum_mm}–${r.maximum_mm} mm. DST: ${r.short} too short, ${r.long} too long. PES: ${data.reports.pes.short} too short, ${data.reports.pes.long} too long.`;
   const fit=data.fit;
   $('smallLetteringFit').textContent=fit.fits?`Width fits: ${fit.actual_width_mm} mm within your ${fit.available_width_mm} mm space. The words were not resized.`:
    `Too wide: ${fit.actual_width_mm} mm for your ${fit.available_width_mm} mm space at nominal ${data.nominal_height_mm.toFixed(2)} mm font height. Edit the words or line breaks, or use a wider space. No words were shrunk or removed.`;
   status('Trial complete — not approved for export. Width fit and stitch lengths do not establish readability or needle safety.');
  }catch(e){if(version===revision&&dialog.open)status(e.name==='AbortError'?'Trial timed out. Your design is unchanged. Retry shortly.':e.message);}
  finally{clearTimeout(timeout);busy=false;run.disabled=false;run.removeAttribute('aria-busy');}
 });
})();
