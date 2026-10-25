/* Team names on the Text page: one name per line, the font, height, shape and colour
   above shared by all, one checked machine file per name (team_names.py). Names are
   made one after another, so the page shows progress and the computer does one at a
   time. A name wider than Max width is listed with the height that would fit; it is
   never resized unless the customer picks that height for all names. */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 if(!window.nativeTextConfig||!window.nativeLettering)return;
 const $=id=>document.getElementById(id),edit=$('workflowEdit');if(!edit)return;
 const box=document.createElement('details');box.id='textTeamNames';
 box.innerHTML=`<summary>Team names</summary>
  <label for="teamNamesList">One name per line</label>
  <textarea id="teamNamesList" rows="5" maxlength="2100" placeholder="ALEX 7&#10;SAM 12&#10;JORDAN"></textarea>
  <p class="muted">Every name uses the font, height, shape and colour above. Up to 50 names, 40 letters each.</p>
  <button type="button" id="teamNamesMake">Make all names</button>
  <p id="teamNamesStatus" class="muted" role="status" aria-live="polite"></p>
  <ul id="teamNamesSummary"></ul>
  <p id="teamNamesFix" hidden></p>
  <button type="button" id="teamNamesZip" class="primary" hidden>Download all (zip)</button>`;
 const anchor=$('workflowTextDetails');if(anchor?.parentElement===edit)edit.insertBefore(box,anchor);else edit.append(box);
 const list=$('teamNamesList'),make=$('teamNamesMake'),zip=$('teamNamesZip'),fix=$('teamNamesFix'),out=$('teamNamesSummary');
 const say=(text,error)=>{$('teamNamesStatus').textContent=text;$('teamNamesStatus').classList.toggle('text-make-error',!!error)};
 const post=(url,body)=>fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(180000)});
 const setup=()=>{const v={...window.nativeLettering.values()};delete v.text;return JSON.stringify(v)};
 const format=()=>$('workflowFormat')?.value||'dst';
 const label=()=>{zip.textContent=`Download all (zip, ${format().toUpperCase()})`};
 $('workflowFormat')?.addEventListener('change',label);
 let running=false,stop=false,rows=[],madeWith=null;
 function show(){
  const ready=rows.filter(r=>r.ready),wide=rows.filter(r=>r.fit_height_mm);
  out.replaceChildren(...rows.map(r=>{
   const li=document.createElement('li');li.className=r.ready?'team-ok':'team-bad';
   li.textContent=r.ready?`✓ ${r.name} · ${r.width_mm} mm wide · ${r.stitches} stitches`:`✗ ${r.name} · ${r.reason}`;
   return li;
  }));
  fix.hidden=!wide.length||running;fix.replaceChildren();
  if(wide.length&&!running){
   // One height for every name, so they all still match: the smallest that fits.
   const height=Math.min(...wide.map(r=>r.fit_height_mm));
   const use=document.createElement('button');use.type='button';use.textContent=`Use ${height} mm for all names`;
   use.onclick=()=>{window.NeedlerTextApply?.({height_mm:height});run()};
   fix.append(`${wide.length} ${wide.length===1?'name is':'names are'} wider than your max width. Make Max width larger, or `,use);
  }
  label();zip.hidden=running||!ready.length;
 }
 async function one(body){
  // Another lettering check may be running: wait for it, a few times.
  for(let i=0;i<20;i++){
   const response=await post('/lettering/native/team/name',body);
   if(response.status!==409){const data=await response.json();if(!response.ok)throw Error(data.error||'This name could not be made.');return data}
   await new Promise(r=>setTimeout(r,1500));
  }
  throw Error('Another lettering check is still running. Try again shortly.');
 }
 async function run(){
  if(running){stop=true;make.textContent='Stopping…';return}
  rows=[];show();
  try{
   const response=await post('/lettering/native/team/list',{names:list.value});
   const data=await response.json();if(!response.ok)throw Error(data.error||'Check your list of names.');
   running=true;stop=false;make.textContent='Stop';madeWith=setup();
   for(const [i,item] of data.names.entries()){
    if(stop)break;
    say(`Making ${i+1} of ${data.names.length}: ${item.name}…`);
    rows.push(await one({...window.nativeLettering.values(),text:item.name}));show();
   }
   const ready=rows.filter(r=>r.ready).length;
   say((stop?'Stopped. ':'')+`${ready} of ${data.names.length} names ready.`+(ready<rows.length?' Names with ✗ are left out of the zip.':''));
  }catch(error){say(error.message,true)}
  finally{running=false;make.textContent='Make all names';show()}
 }
 make.addEventListener('click',run);
 zip.addEventListener('click',async ()=>{
  if(setup()!==madeWith){say('The settings changed since the names were made. Press Make all names again.',true);return}
  const fmt=format(),names=rows.filter(r=>r.ready).map(r=>({name:r.name,id:r.id}));
  zip.disabled=true;say('Preparing the zip…');
  try{
   const response=await post('/lettering/native/team/zip',{format:fmt,names});
   if(!response.ok){const data=await response.json().catch(()=>({}));throw Error(data.error||'The zip could not be made. Try again.')}
   const link=document.createElement('a');link.href=URL.createObjectURL(await response.blob());link.download=`team-names-${fmt}.zip`;
   document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
   say(`${names.length} ${fmt.toUpperCase()} files downloaded. Sew a sample first.`);
  }catch(error){say(error.message,true)}
  finally{zip.disabled=false}
 });
});
