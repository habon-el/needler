/* Sole editor of transient surface appearance; never changes preparation options. */
(() => {
'use strict';
const $=id=>document.getElementById(id),canvas=$('stitched');
let drag=null,download=null,weight='40';
const widths=new Map([['40',Number($('threadVisualWidth').value)]]);
$('threadWeight').addEventListener('change',()=>{
 const value=Number($('threadWeight').value);
 if(!Number.isInteger(value)||value<1||value>200){$('threadWeight').setAttribute('aria-invalid','true');$('threadWeightNote').textContent='Enter a whole-number weight from 1 to 200; this is a visual profile label, not a machine setting.';return;}
 $('threadWeight').removeAttribute('aria-invalid');weight=String(value);
 if(widths.has(weight)){$('threadVisualWidth').value=widths.get(weight);$('threadVisualWidth').dispatchEvent(new Event('input'));}
 $('threadWeightNote').textContent=widths.has(weight)?'Using this session’s '+weight+'-weight visual width for all threads. Not a catalogue measurement.':'No calibrated width for '+weight+' weight. Adjust Visible strand width to set this session’s profile.';
 redraw();
});
$('threadVisualWidth').addEventListener('input',()=>{widths.set(weight,Number($('threadVisualWidth').value));$('threadWeightNote').textContent='Using this session’s '+weight+'-weight visual width for all threads. Not a catalogue measurement.';});
const redraw=()=>window.embroideryStudio.redraw();
for(const id of ['fabricTexture','lightAngle','neutralLight'])$(id).addEventListener('input',()=>{
 $('lightAngleValue').value=$('lightAngle').value+'°';redraw();
});
$('retrySurface').addEventListener('click',()=>window.embroideryStudio.retrySurface());
function lightAt(e){
 const r=canvas.getBoundingClientRect();
 const angle=(Math.atan2(e.clientY-r.top-r.height/2,e.clientX-r.left-r.width/2)*180/Math.PI+360)%360;
 $('neutralLight').checked=false;$('lightAngle').value=Math.round(angle);$('lightAngleValue').value=$('lightAngle').value+'°';redraw();
}
canvas.addEventListener('pointerdown',e=>{
 if(!$('dragLight').checked||!$('threadRelief').checked||e.button!==0||window.embroideryStudio.navigationGesture(e))return;
 e.preventDefault();e.stopImmediatePropagation();drag=e.pointerId;canvas.setPointerCapture(drag);lightAt(e);
},true);
canvas.addEventListener('pointermove',e=>{if(e.pointerId!==drag)return;e.preventDefault();e.stopImmediatePropagation();lightAt(e)},true);
for(const event of ['pointerup','pointercancel'])canvas.addEventListener(event,e=>{
 if(e.pointerId!==drag)return;e.stopImmediatePropagation();if(canvas.hasPointerCapture(drag))canvas.releasePointerCapture(drag);drag=null;
},true);
window.threadPreviewUI={sync(layer,available){
 if(!download)$('surfaceStatus').textContent=layer.status||'Preparing thread surface…';
 $('retrySurface').hidden=!layer.surfaceError;
 $('downloadMockup').disabled=!available||!!download;
}};
const placements=new Map();
fetch('/api/products').then(r=>r.json()).then(data=>{
 for(const product of data.products){placements.set(product.id,product.placements);$('mockupProduct').append(new Option(product.label,product.id));}
}).catch(()=>{});
$('mockupProduct').addEventListener('change',()=>{
 const list=placements.get($('mockupProduct').value)||[];
 $('mockupPlacement').replaceChildren(...list.map(p=>new Option(p.label,p.id)));$('mockupPlacement').hidden=!list.length;
});
$('downloadMockup').addEventListener('click',async()=>{
 if(download||!window.embroideryStudio.hasPlayback())return;
 const path=new URL($('exportPes').href,location.origin).pathname;
 const name=path.split('/').at(-2);
 if(!name)return;
 const options=new URLSearchParams({strand:$('threadVisualWidth').value,fabric:$('fabric').value,texture:$('fabricTexture').value,angle:$('lightAngle').value,neutral:String($('neutralLight').checked)});
 if($('mockupProduct').value){options.set('product',$('mockupProduct').value);options.set('placement',$('mockupPlacement').value);}
 download=new AbortController();const timeout=setTimeout(()=>download?.abort(),45000);
 $('downloadMockup').disabled=true;$('surfaceStatus').textContent='Rendering a full-design PNG from the exported PES file…';
 try{
  const response=await fetch('/thread-mockup/'+name+'?'+options,{signal:download.signal});
  if(!response.ok){const data=await response.json();throw Error(data.error||'Mockup unavailable.');}
  const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');
  a.href=url;a.download='embroiderly-thread-mockup.png';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  const note=response.headers.get('X-Mockup-Note');
  $('surfaceStatus').textContent=$('mockupProduct').value?'PNG saved: the design at real size on the product.'+(note?' '+note:''):'PNG saved from the exported PES. Full design fitted; no physical sew-out claimed.';
 }catch(error){$('surfaceStatus').textContent=error.name==='AbortError'?'Mockup timed out. Your design is unchanged; you can retry.':error.message;}
 finally{clearTimeout(timeout);download=null;$('downloadMockup').disabled=!window.embroideryStudio.hasPlayback();}
});
})();
