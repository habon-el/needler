(() => {
const choices=window.threadChoices,host=document.getElementById('thread-editors'),note=document.getElementById('thread-edit-status');
let pending=0;
function redraw(){cancelAnimationFrame(pending);pending=requestAnimationFrame(()=>{playing=false;button.textContent='Play';ctx.clearRect(0,0,900,650);index=0;colour=0;last={x:0,y:0};advance(steps.length);note.textContent='Unsaved thread preview. Save a new design to update the actual stitch plan.'})}
function controls(){host.replaceChildren();for(const [hex,value] of Object.entries(choices)){
 const row=document.createElement('div'),label=document.createElement('label'),check=document.createElement('input'),picker=document.createElement('input');
 check.type='checkbox';check.checked=value.include;label.append(check,' Sew '+hex+' ');picker.type='color';picker.value=value.thread;picker.setAttribute('aria-label','Replace '+hex);
 check.onchange=()=>{value.include=check.checked;redraw()};picker.oninput=()=>{value.thread=picker.value;redraw()};row.append(label,picker);host.append(row);
}}
document.getElementById('thread-reset').onclick=()=>{for(const [hex,v] of Object.entries(choices)){v.include=true;v.thread=hex}controls();redraw()};
document.getElementById('thread-save').onclick=async()=>{
 const save=document.getElementById('thread-save');save.disabled=true;note.textContent='Writing updated stitches…';
 try{const response=await fetch('/thread-variant/'+encodeURIComponent(window.threadDesignName),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(choices)});const result=await response.json();if(!response.ok)throw Error(result.error||'Could not save thread changes');location.href=result.url}
 catch(error){note.textContent=error.message;save.disabled=false}
};controls();
})();
