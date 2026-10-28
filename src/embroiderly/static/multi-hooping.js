/* Multi-hooping (multi_hooping.py): a stitched design bigger than the hoop is split into
   hoopings. The hoop box says how many, "Show hoopings" draws each hoop on the stitched view,
   and Save and download lists one machine file per hooping. Called by hoop-controls.js. */
window.MultiHooping={paint(){}};
window.multiHooping=(box,studio)=>{
 'use strict';
 const fit=box.querySelector('#hoopFit');if(!fit)return;
 const line=document.createElement('div');line.className='hoop-split';line.hidden=true;
 line.innerHTML=`<p id="hoopSplitText"></p><label class="hoop-show"><input type="checkbox" id="hoopSplitShow"> Show hoopings</label>`;
 fit.after(line);
 const text=line.querySelector('#hoopSplitText'),show=line.querySelector('#hoopSplitShow');
 const files=document.createElement('div');files.id='workflowHoopings';files.hidden=true;
 const $=id=>document.getElementById(id);
 let plan=null,asked='',request=0;
 // The current stitches only: the link is hidden while changed settings wait for Update stitches.
 const source=()=>{const link=$('exportDst');return link&&!link.hidden?link.getAttribute('href')?.match(/\/studio-export\/([^/]+)\//)?.[1]:null};
 const node=(tag,words)=>{const n=document.createElement(tag);if(words)n.textContent=words;return n};
 // One link per hooping, in the machine format chosen above.
 const renderFiles=()=>{
  const sheet=$('workflowWorksheet');if(sheet&&!files.isConnected)sheet.after(files);
  files.hidden=!plan;if(!plan)return;
  const fmt=$('workflowFormat')?.value||'dst',count=plan.hoopings.length,list=node('ol');
  for(const h of plan.hoopings){const a=node('a',`Hooping ${h.n} (${fmt.toUpperCase()})`);a.href=`/hooping/${plan.key}/${h.n}/${fmt}`;a.download=`hooping-${h.n}-of-${count}.${fmt}`;const li=node('li');li.append(a);list.append(li)}
  const tip=node('p','Pink crosses are alignment marks. After re-hooping, move the design until the needle meets the crosses from the hooping before, then skip the pink colour.');tip.className='muted';
  files.replaceChildren(node('p',`Sew in ${count} hoopings, in this order:`),list,tip);
 };
 const update=async()=>{
  const name=source(),field=studio.snapshot().piece_hoop_mm||[100,100];
  if(!name||fit.dataset.level!=='red'){if(plan||asked){plan=null;asked='';studio.redraw()}line.hidden=true;renderFiles();return}
  const want=`${name}/${field[0]}x${field[1]}`;if(want===asked)return;asked=want;const mine=++request;
  let body;try{body=await fetch('/api/hoopings/'+want,{cache:'no-store'}).then(r=>r.json())}catch(_){body={error:'Hoopings could not be worked out. Try again.'}}
  if(mine!==request)return;
  plan=body.hoopings?.length?{...body,key:want}:null;
  text.textContent=plan?`Or sew it in ${plan.hoopings.length} hoopings. The files are under Save and download.`:body.error||'';
  line.hidden=!plan&&!body.error;show.parentElement.hidden=!plan;
  renderFiles();studio.redraw();
 };
 try{show.checked=localStorage.getItem('needler.showHoopings')!=='off'}catch(_){show.checked=true}
 show.addEventListener('change',()=>{try{localStorage.setItem('needler.showHoopings',show.checked?'on':'off')}catch(_){}studio.redraw()});
 document.addEventListener('change',e=>{if(e.target?.id==='workflowFormat')renderFiles()});
 window.addEventListener('studio:preview',update);window.addEventListener('studio:controls',update);
 // Each hooping's hoop, dashed and numbered, on the stitched view (mm around the design origin).
 window.MultiHooping.paint=(c,s,factor)=>{
  if(!plan||!show.checked)return;
  const [ox,oy]=plan.origin_mm||[0,0],[w,h]=plan.field_mm;
  c.save();c.lineWidth=1.5/s;c.setLineDash([6/s,4/s]);c.font=`bold ${13/s}px system-ui`;
  plan.hoopings.forEach((hooping,i)=>{
   const colour=['#e5007e','#0072b2','#d55e00','#009e73'][i%4],[cx,cy]=hooping.centre_mm;
   const x=(cx-w/2+ox)*factor,y=(cy-h/2+oy)*factor;
   c.strokeStyle=c.fillStyle=colour;c.strokeRect(x,y,w*factor,h*factor);c.fillText(String(hooping.n),x+5/s,y+16/s);
  });
  c.restore();
 };
 update();
};
