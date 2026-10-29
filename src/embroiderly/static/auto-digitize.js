/* "Digitize for me": one button that runs the rules-based auto-digitizer on
   the server, shows each step live, then opens the result for review.
   The server saves settings and stitches; nothing is downloaded here. */
document.addEventListener('DOMContentLoaded', () => {
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
 <p class="muted">It looks at your picture, chooses the settings, makes the stitches and checks them. If a check fails it adjusts and tries again. You review the result before downloading.</p>
 <label for="autoRequest">Anything it should know? <span class="muted">(optional)</span></label>
 <textarea id="autoRequest" maxlength="300" placeholder="For example: cap front, 6 cm wide, 3 colours"></textarea>
 <p class="muted">It understands sizes (mm, cm, inches; wide or tall), a number of colours, and “line art”, “black lines” or “logo”.</p>
 <label for="autoDetail">Detail</label>
 <div class="auto-detail"><span class="muted">Fewer</span><input type="range" id="autoDetail" min="1" max="5" step="1" value="3"><span class="muted">More</span></div>
 <label class="auto-claude"><input type="checkbox" id="autoOutline"> <span>Add a dark outline around each colour</span></label>
 <label class="auto-claude" id="autoClaudeRow" hidden><input type="checkbox" id="autoClaude"> <span><strong>Let Claude decide</strong> (AI). It looks at your picture and at each result, like a human digitizer. Costs about 5–40 cents per design from your Claude credit. <span id="autoClaudeSpend"></span></span></label>
 <div class="auto-actions"><button type="button" id="autoStart" class="primary">Start</button><button type="button" id="autoClose">Back</button></div>
 <ol id="autoSteps" aria-live="polite"></ol>
 <div id="autoResult" hidden></div>`;
 inspector.prepend(panel);
 const steps=$('autoSteps'),result=$('autoResult'),start=$('autoStart');
 const cover=node('div','','auto-cover');cover.hidden=true;cover.innerHTML='<div><strong>Digitizing…</strong><span></span></div>';
 document.querySelector('.panels')?.append(cover);
 const hideOthers=on=>{for(const child of inspector.children)if(child!==panel)child.classList.toggle('auto-hidden',on)};

 function show(){panel.hidden=false;hideOthers(true);inspector.scrollTop=0;$('autoRequest').focus()}
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
   ...((r.check||[]).map(t=>node('p','Check: '+t,'auto-note'))),
   ...(r.problem?[node('p',r.problem_detail||r.problem,'auto-problem')]:[]),
   ...((r.issues||[]).map(t=>node('p',t,'auto-problem'))),
   node('p','Check it in 3D, then use Save and download. A sample sew-out is still needed.'+(r.claude_usd!=null?` Claude cost for this design: $${Number(r.claude_usd).toFixed(2)}.`:''),'muted'));
  if(r.stitches){const b=node('button','Show the result');b.type='button';b.className='primary';b.onclick=()=>{location.href=location.pathname+'?view=stitched&auto=1'};result.append(b)}
 }
 async function poll(){
  try{
   const job=await fetch(api,{cache:'no-store'}).then(r=>r.json());
   render(job);
   if(job.state==='running'){timer=setTimeout(poll,1000);return}
  }catch{timer=setTimeout(poll,2500);return}
  running=false;start.disabled=false;$('autoClose').disabled=false;cover.hidden=true;start.textContent='Start again';
 }
 start.onclick=async()=>{
  if(running)return;
  if(studio.isBusy()){result.hidden=false;result.replaceChildren(node('p','Wait for the current preparation to finish, then start.','auto-problem'));return}
  running=true;start.disabled=true;$('autoClose').disabled=true;cover.hidden=false;steps.replaceChildren();result.hidden=true;
  const response=await fetch(api,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request:$('autoRequest').value,use_claude:$('autoClaude').checked,
   outlines:$('autoOutline').checked,detail:Number($('autoDetail').value)})}).catch(()=>null);
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
      if(found.length)result.insertBefore(node('p',`The 3D review marks ${found.length} place${found.length===1?'':'s'} worth a look (numbered on the model). They passed the file checks; check them on a sample sew-out.`,'auto-note'),result.querySelector('.muted'));
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
