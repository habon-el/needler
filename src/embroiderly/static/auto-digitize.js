/* "Digitize for me": one button that runs the rules-based auto-digitizer on
   the server, shows each step live, then opens the result for review.
   The server saves settings and stitches; nothing is downloaded here. */
// Longest request the server reads (REQUEST_LIMIT in auto_digitize.py); longer is warned, not cut silently.
const AUTO_REQUEST_LIMIT=1000;
/* The note under the 3D review, worded from the real export result: the places the 3D
   review marks, and whether the file checks passed or the download is blocked. */
function autoReviewNote(found,result){
 if(!found||!result?.stitches)return '';
 const places=`${found} place${found===1?'':'s'}`;
 return `3D preview ready. Look at the ${places} it marks (numbered on the model). `+(result.problem||result.ok===false?
  'The download is blocked until the problem above is fixed.':
  `The file checks passed; check ${found===1?'it':'them'} on a sample sew-out.`);
}
/* Taps instead of a blank box: what it goes on, size, look. Same keys as GOES_ON and SIZES
   in auto_digitize.py; typed words win over a tap. */
const AUTO_ICON=d=>`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${d}"/></svg>`;
const AUTO_GOES_ON=[
 ['t_shirt','T-shirt','M8 3 3 6l2 4 2-1v12h10V9l2 1 2-4-5-3c0 2-1.5 3-4 3S8 5 8 3z'],
 ['polo','Polo','M8 3 3 6l2 4 2-1v12h10V9l2 1 2-4-5-3-4 3zM12 6v5'],
 ['hoodie','Hoodie','M8 4c0-1 8-1 8 0l4 3-2 4-2-1v11H8V10l-2 1-2-4zM9 4c0 3 1.5 5 3 5s3-2 3-5'],
 ['cap','Cap','M4 15c0-5 3.5-8 8-8s8 3 8 8zM4 15h17l-1 2H5zM12 7V5'],
 ['jacket','Jacket','M8 3 4 6v15h7V8l1-3 1 3v13h7V6l-4-3M12 8v13'],
 ['bag','Bag','M5 8h14l-1 13H6zM9 8V6a3 3 0 0 1 6 0v2'],
 ['towel','Towel','M6 4h12v16H6zM6 8h12M6 16h12'],
 ['','Not sure','M9 9a3 3 0 1 1 4 2.8c-.7.3-1 .8-1 1.5V14M12 17.5v.5']];
const AUTO_SIZES=[['small','Small','chest, cap · 70 mm'],['medium','Medium','front · 100 mm'],['large','Large','back · 200 mm']];
const AUTO_LOOKS=[['simple','Simple','fewer colours'],['balanced','Balanced',''],['detailed','Detailed','small parts kept']];
const AUTO_EXAMPLES=['Keep the background','Only 3 colours','Black lines only','Make the text bold'];
if(typeof document!=='undefined')document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 const $=id=>document.getElementById(id), studio=window.embroideryStudio;
 const choices=$('workflowChoices'), inspector=document.querySelector('.inspector');
 if(!studio||!choices||window.nativeTextConfig)return;
 const name=window.preparationConfig.name, api='/api/auto-digitize/'+encodeURIComponent(name);
 const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text)e.textContent=text;if(cls)e.className=cls;return e;};
 const wand='<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20 15 9M14 4v3M19 9h-3M17.5 5.5l-2 2M9 4l.6 1.4L11 6l-1.4.6L9 8l-.6-1.4L7 6l1.4-.6zM19 13l.5 1 1 .5-1 .5-.5 1-.5-1-1-.5 1-.5z"/></svg>';

 const open=document.createElement('button');open.type='button';open.id='autoDigitizeOpen';
 open.innerHTML=wand+'<span>Digitize for me</span>';open.title='Choose the settings, make the stitches and check them automatically';
 choices.prepend(open);

 const panel=node('section','','auto-panel');panel.id='autoDigitize';panel.hidden=true;panel.setAttribute('aria-labelledby','autoTitle');
 panel.innerHTML=`<h1 id="autoTitle">Digitize for me</h1>
 <p class="muted">Three taps and it does the rest: settings, stitches and checks. You see the result before downloading.</p>
 <fieldset class="auto-q"><legend><b>1</b> What is it going on?</legend><div class="auto-cards" id="autoGoesOn">${AUTO_GOES_ON.map(([v,t,d],i)=>
  `<label><input type="radio" name="autoGoesOn" value="${v}"${i===AUTO_GOES_ON.length-1?' checked':''}>${AUTO_ICON(d)}<span>${t}</span></label>`).join('')}</div></fieldset>
 <fieldset class="auto-q"><legend><b>2</b> How big?</legend><div class="auto-seg" id="autoSize">${AUTO_SIZES.map(([v,t,n])=>
  `<label><input type="radio" name="autoSize" value="${v}"><span>${t}<small>${n}</small></span></label>`).join('')}</div></fieldset>
 <fieldset class="auto-q"><legend><b>3</b> Which look?</legend><div class="auto-seg" id="autoLook">${AUTO_LOOKS.map(([v,t,n])=>
  `<label><input type="radio" name="autoLook" value="${v}"${v==='balanced'?' checked':''}><span>${t}${n?`<small>${n}</small>`:''}</span></label>`).join('')}</div>
  <div class="auto-chips"><label><input type="checkbox" id="autoOutline"><span>Dark outline</span></label><label><input type="checkbox" id="autoPuff"><span>3D puff</span></label></div></fieldset>
 <div class="auto-brief" aria-live="polite"><small>What you will get</small><p id="autoBrief">Reading your picture…</p></div>
 <details class="auto-more"><summary>Anything else? <span class="muted">(optional)</span></summary>
 <div class="auto-chips" id="autoExamples">${AUTO_EXAMPLES.map(t=>`<button type="button">${t}</button>`).join('')}</div>
 <textarea id="autoRequest" aria-label="Anything else" placeholder="In your own words, for example: 6 cm wide, keep the white star"></textarea>
 <p id="autoRequestLong" class="auto-problem" hidden></p></details>
 <label class="auto-claude" id="autoClaudeRow" hidden><input type="checkbox" id="autoClaude"> <span><strong>Let Claude decide</strong> (AI). It looks at your picture and at each result, like a human digitizer. Costs about 5–40 cents per design from your Claude credit. <span id="autoClaudeSpend"></span></span></label>
 <div class="auto-actions"><button type="button" id="autoStart" class="primary">Start</button><button type="button" id="autoClose">Back</button></div>
 <ol id="autoSteps" aria-live="polite"></ol>
 <div id="autoResult" hidden></div>`;
 inspector.prepend(panel);
 const steps=$('autoSteps'),result=$('autoResult'),start=$('autoStart');
 const picked=group=>panel.querySelector(`input[name=${group}]:checked`)?.value||'';
 const choicesNow=()=>({request:$('autoRequest').value,goes_on:picked('autoGoesOn'),size:picked('autoSize'),
  look:picked('autoLook'),outlines:$('autoOutline').checked,puff:$('autoPuff').checked});
 // The brief follows every tap; the server reads the picture, so it costs nothing.
 let briefTimer=0;
 const updateBrief=()=>{clearTimeout(briefTimer);briefTimer=setTimeout(()=>fetch(api+'/brief',{method:'POST',
  headers:{'Content-Type':'application/json'},body:JSON.stringify(choicesNow())}).then(r=>r.json())
  .then(b=>{if(b.brief)$('autoBrief').textContent=b.brief}).catch(()=>{}),250)};
 panel.addEventListener('change',updateBrief);
 $('autoRequest').oninput=()=>{
  const n=$('autoRequest').value.length,warn=$('autoRequestLong');warn.hidden=n<=AUTO_REQUEST_LIMIT;
  warn.textContent=`Too long: ${n.toLocaleString()} characters. Only the first ${AUTO_REQUEST_LIMIT.toLocaleString()} are read; shorten it.`;
  updateBrief();
 };
 for(const b of $('autoExamples').children)b.onclick=()=>{
  const box=$('autoRequest'),text=box.value.trim();
  if(!text.toLowerCase().includes(b.textContent.toLowerCase()))box.value=(text?text.replace(/[.\s]*$/,'. '):'')+b.textContent+'.';
  box.oninput();box.focus();
 };
 const cover=node('div','','auto-cover');cover.hidden=true;cover.innerHTML='<div><strong>Digitizing…</strong><span></span></div>';
 document.querySelector('.panels')?.append(cover);
 const hideOthers=on=>{for(const child of inspector.children)if(child!==panel)child.classList.toggle('auto-hidden',on)};

 function show(){panel.hidden=false;hideOthers(true);inspector.scrollTop=0;updateBrief();panel.querySelector('input[name=autoGoesOn]:checked')?.focus()}
 function close(){if(running)return;panel.hidden=true;hideOthers(false);open.focus()}
 open.onclick=show;$('autoClose').onclick=close;

 let running=false,timer=0;
 function render(job){
  steps.replaceChildren(...(job.steps||[]).map(s=>{const li=node('li');li.append(node('span',s.text),node('small',s.at.toFixed(0)+' s'));return li}));
  const last=job.steps?.[job.steps.length-1];cover.querySelector('span').textContent=last?last.text:'Starting…';
  if(job.state==='running'){result.hidden=true;return}
  const r=job.result||{};result.hidden=false;result.dataset.state=job.state;
  const facts=r.stitches?`${r.width_mm} × ${r.height_mm} mm · ${Number(r.stitches).toLocaleString()} stitches · ${r.trims} cut${r.trims===1?'':'s'} · ${r.colours} colour${r.colours===1?'':'s'}`:'';
  result.replaceChildren(
   node('strong',job.state==='done'?'Ready to review':job.state==='needs_review'?'Made, but needs your review':'Could not finish'),
   ...(facts?[node('p',facts)]:[]),
   ...(r.summary?[node('p',r.summary,'auto-summary')]:[]),
   ...(r.request?[node('p','Your request: '+r.request,'auto-summary')]:[]),
   ...(r.plan?.length?[(()=>{const ul=node('ul',null,'auto-plan');ul.append(...r.plan.map(t=>node('li',t)));return ul})()]:[]),
   ...(r.tools_used?.length?[node('p','Tools used: '+r.tools_used.join(', '),'muted')]:[]),
   ...(r.decided_by?[node('p','Settings chosen by '+r.decided_by+'.','muted')]:[]),
   ...((r.check||[]).map(t=>node('p','Check: '+t,'auto-note'))),
   ...(r.problem?[node('p',r.problem_detail||r.problem,'auto-problem')]:[]),
   ...((r.issues||[]).map(t=>node('p',t,'auto-problem'))),
   node('p',(r.problem?'Check it in 3D. The download is blocked until the problem above is fixed.':'Check it in 3D, then use Save and download.')+' A sample sew-out is still needed.'+(r.claude_usd!=null?` Claude cost for this design: $${Number(r.claude_usd).toFixed(2)}.`:''),'muted'));
  if(r.stitches){const b=node('button','Show the result');b.type='button';b.className='primary';b.onclick=()=>{location.href=location.pathname+'?view=stitched&auto=1'};result.append(b)}
 }
 async function poll(){
  let job;
  try{job=await fetch(api,{cache:'no-store'}).then(r=>r.json())}catch{timer=setTimeout(poll,2500);return}
  // A result it cannot show must not leave Start stuck as if a run were still going.
  try{render(job)}catch(error){console.error(error)}
  if(job.state==='running'){timer=setTimeout(poll,1000);return}
  running=false;start.disabled=false;$('autoClose').disabled=false;cover.hidden=true;start.textContent='Start again';
 }
 const pause=ms=>new Promise(done=>setTimeout(done,ms));
 // The studio enables every inspector button when its own preview ends; not these during a run.
 for(const b of [start,$('autoClose')])new MutationObserver(()=>{if(running&&!b.disabled)b.disabled=true}).observe(b,{attributes:true,attributeFilter:['disabled']});
 start.onclick=async()=>{
  if(running)return;
  running=true;start.disabled=true;$('autoClose').disabled=true;cover.hidden=false;
  // An earlier result goes at once, so Start always visibly starts.
  steps.replaceChildren();result.hidden=true;result.replaceChildren();cover.querySelector('span').textContent='Starting…';
  // After opening a result the page is still preparing it: wait for that instead of refusing.
  for(let waited=0;studio.isBusy()&&waited<600000;waited+=500){
   cover.querySelector('span').textContent='Waiting for the current preparation to finish…';await pause(500);
  }
  const response=await fetch(api,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...choicesNow(),use_claude:$('autoClaude').checked})}).catch(()=>null);
  if(!response||!response.ok&&response.status!==202){
   const body=await response?.json().catch(()=>({}))||{};
   running=false;start.disabled=false;$('autoClose').disabled=false;cover.hidden=true;
   result.hidden=false;result.replaceChildren(node('p',body.error||'Could not start. Is Needler still running?','auto-problem'));return;
  }
  clearTimeout(timer);poll();
 };
 // Offer Claude only when a key is set on this computer; remember the choice.
 fetch('/api/auto-digitize-claude',{cache:'no-store'}).then(r=>r.json()).then(info=>{
  if(!info.available)return;
  $('autoClaudeRow').hidden=false;
  $('autoClaudeSpend').textContent=`Used so far: $${info.spent_usd.toFixed(2)} of Needler's $${info.total_limit_usd.toFixed(2)} limit.`;
  try{$('autoClaude').checked=localStorage.getItem('needler.autoClaude')==='true'}catch{}
  $('autoClaude').onchange=()=>{try{localStorage.setItem('needler.autoClaude',String($('autoClaude').checked))}catch{}};
 }).catch(()=>{});

 // After "Show the result": the page reloads with the new stitches; reopen the report and the 3D view.
 if(new URLSearchParams(location.search).get('auto')==='1'){
  fetch(api,{cache:'no-store'}).then(r=>r.json()).then(job=>{
   if(!job.steps)return;
   show();render(job);start.textContent='Start again';
   if(job.result?.stitches&&!$('confirmed').checked)$('confirmed').click();
   let tries=0;const wait=setInterval(()=>{
    if(studio.hasPlayback()&&window.Thread3D){
     clearInterval(wait);document.querySelector('#workflowSteps [data-workflow=check]')?.click();window.Thread3D.open();
     // The 3D review checks build-up the file checks do not; report it here too.
     setTimeout(()=>{
      const found=(window.Thread3D.findings()||[]).filter(f=>f.kind!=='repeat');
      const show3d=result.querySelector('button');if(show3d){show3d.textContent='Open 3D view';show3d.onclick=()=>window.Thread3D.open()}
      const note=autoReviewNote(found.length,job.result);
      if(note)result.insertBefore(node('p',note,'auto-note'),result.querySelector('.muted'));
     },1200);
    }
    else if(++tries>40)clearInterval(wait);
   },250);
  }).catch(()=>{});
 }else{
  // A job still running from before a reload continues to report here.
  fetch(api,{cache:'no-store'}).then(r=>r.json()).then(job=>{if(job.state==='running'){show();running=true;start.disabled=true;cover.hidden=false;poll()}}).catch(()=>{});
 }
});
if(typeof module!=='undefined')module.exports={autoReviewNote,AUTO_REQUEST_LIMIT};
