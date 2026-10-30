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
// Ready-made changes under a result; the person may also say or type their own.
const AUTO_CHANGES=['Remove the background','Fewer colours','Make it bigger','Add a dark outline','More detail'];
const AUTO_MIC='M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0M12 18v3';
const AUTO_SEND='M12 19V5M5 12l7-7 7 7';
/* A prompt box: the words, and a microphone underneath when the browser can listen. Speech lands
   in the box to read and correct; nothing is sent until the panel's own button is pressed. */
function autoComposer(id,label,placeholder,send){
 const box=document.createElement('div');box.className='auto-composer';
 box.innerHTML=`<textarea id="${id}" rows="2" aria-label="${label}" placeholder="${placeholder}"></textarea>
 <div class="auto-composer-bar"><span class="auto-listening" hidden aria-live="polite"><i></i><i></i><i></i> Listening… speak now</span>
 ${send?`<button type="button" class="auto-send" aria-label="${send}" title="${send}">${AUTO_ICON(AUTO_SEND)}</button>`:''}</div>`;
 const field=box.querySelector('textarea'),bar=box.querySelector('.auto-composer-bar');
 const Listen=typeof window!=='undefined'&&(window.SpeechRecognition||window.webkitSpeechRecognition);
 if(!Listen)return box;
 const mic=document.createElement('button');mic.type='button';mic.className='auto-mic';mic.setAttribute('aria-pressed','false');
 mic.innerHTML=AUTO_ICON(AUTO_MIC)+'<span>Speak</span>';mic.title='Say it instead of typing';bar.prepend(mic);
 const listening=box.querySelector('.auto-listening');
 const why=document.createElement('p');why.className='auto-voice-problem';why.hidden=true;why.setAttribute('role','status');box.append(why);
 const tell=text=>{why.textContent=text||'';why.hidden=!text};
 // Every reason the browser gives for stopping is said in words; none is silent.
 const REASONS={'not-allowed':'The microphone is blocked for this page. Click the microphone or lock icon at the left of the address bar, allow it, then press Speak again.',
  'service-not-allowed':'This browser does not allow speech typing here. Use Chrome or Edge, or type instead.',
  'audio-capture':'No microphone was found. Plug one in, or pick it in Windows sound settings, then press Speak again.',
  'network':'The browser’s speech service could not be reached. Speech typing needs the internet; check the connection or type instead.',
  'language-not-supported':'Speech typing does not support this language here. Type instead.',
  'no-speech':'Nothing was heard. Press Speak and talk a little closer to the microphone.'};
 // Chrome ends listening by itself after a pause; keep going until Stop is pressed.
 let recognition=null,wanted=false,starting=false,quickEnds=0,said='',since=0,heardAudio=0;
 const off=()=>{wanted=false;starting=false;recognition=null;clearTimeout(heardAudio);mic.classList.remove('on');
  mic.setAttribute('aria-pressed','false');listening.hidden=true;mic.querySelector('span').textContent='Speak'};
 function listen(){
  const started=Date.now(),before=said;
  recognition=new Listen();recognition.lang=navigator.language||'en-US';
  recognition.continuous=true;recognition.interimResults=true;
  recognition.onaudiostart=()=>clearTimeout(heardAudio);
  recognition.onresult=e=>{
   const heard=[...e.results].map(r=>r[0].transcript).join('').trim();
   said=(before&&heard?before+' ':before)+heard;field.value=said;field.dispatchEvent(new Event('input'));quickEnds=0;
  };
  recognition.onerror=e=>{if(e.error==='aborted')return;
   if(e.error!=='no-speech'||!field.value.trim())tell(REASONS[e.error]||`Speech typing stopped (${e.error}). Press Speak to try again, or type instead.`);
   if(e.error!=='no-speech')off()};
  recognition.onend=()=>{
   if(!wanted){off();return}
   // Ending at once again and again means the browser cannot listen here.
   quickEnds=Date.now()-started<1500?quickEnds+1:0;
   if(quickEnds>=3){off();tell('Listening stops as soon as it starts. Check that the microphone works in Windows sound settings and that no other app is using it.');return}
   try{listen()}catch{off();tell('Listening stopped and could not start again. Press Speak to go on, or type instead.')}
  };
  recognition.start();
 }
 mic.onclick=async()=>{
  // A second click while starting, or a double click, must not stop it at once.
  if(starting||wanted&&Date.now()-since<700)return;
  if(wanted){wanted=false;recognition?.stop();off();field.focus();return}
  tell('');
  // The browser gives the microphone only to pages opened at localhost or 127.0.0.1 (or https).
  if(window.isSecureContext===false){
   tell(`Speech typing needs Needler opened at http://127.0.0.1:${location.port||80} or http://localhost:${location.port||80} on this computer; at ${location.host} the browser keeps the microphone off. Type instead, or open that address.`);
   return;
  }
  starting=true;mic.querySelector('span').textContent='Starting…';
  // Ask for the microphone first: this shows the browser's permission prompt and finds a missing microphone.
  if(navigator.mediaDevices?.getUserMedia){
   try{(await navigator.mediaDevices.getUserMedia({audio:true})).getTracks().forEach(t=>t.stop())}
   catch(error){off();tell(REASONS[error.name==='NotFoundError'?'audio-capture':error.name==='NotAllowedError'?'not-allowed':'']||
    `The microphone could not be opened (${error.name}). Check it in Windows sound settings, or type instead.`);return}
  }
  starting=false;wanted=true;quickEnds=0;said=field.value.trim();since=Date.now();
  try{listen()}catch{off();tell('Speech typing could not start. Reload the page and press Speak again, or type instead.');return}
  // Listening that never reaches the microphone is said too, not left looking busy.
  heardAudio=setTimeout(()=>{if(wanted){recognition?.abort?.();off();
   tell('The microphone did not start. Check that it is switched on and chosen in Windows sound settings, and that no other app is using it.')}},5000);
  mic.classList.add('on');mic.setAttribute('aria-pressed','true');mic.querySelector('span').textContent='Stop';listening.hidden=false;
 };
 return box;
}
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
 <div class="auto-say"><h2>Or say it in your own words <span class="muted">(optional)</span></h2>
 <div class="auto-chips" id="autoExamples">${AUTO_EXAMPLES.map(t=>`<button type="button">${t}</button>`).join('')}</div>
 <div id="autoRequestBox"></div>
 <p id="autoRequestLong" class="auto-problem" hidden></p></div>
 <label class="auto-claude" id="autoClaudeRow" hidden><input type="checkbox" id="autoClaude"> <span><strong>Let Claude decide</strong> (AI). It looks at your picture and at each result, like a human digitizer. Costs about 5–40 cents per design from your Claude credit. <span id="autoClaudeSpend"></span></span></label>
 <div class="auto-actions"><button type="button" id="autoStart" class="primary">Start</button><button type="button" id="autoClose">Back</button></div>
 <ol id="autoSteps" aria-live="polite"></ol>
 <div id="autoResult" hidden></div>`;
 inspector.prepend(panel);
 $('autoRequestBox').replaceWith(autoComposer('autoRequest','Your own words',
  'Type or speak: “6 cm wide, remove the white background, keep only the ball on fire”'));
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
   ...(r.cleaned?[node('p',r.cleaned,'auto-note')]:[]),
   ...(r.problem?[node('p',r.problem_detail||r.problem,'auto-problem')]:[]),
   ...((r.issues||[]).map(t=>node('p',t,'auto-problem'))),
   node('p',(r.problem?'Check it in 3D. The download is blocked until the problem above is fixed.':'Check it in 3D, then use Save and download.')+' A sample sew-out is still needed.'+(r.claude_usd!=null?` Claude cost for this design: $${Number(r.claude_usd).toFixed(2)}.`:''),'muted'));
  if(r.stitches){const b=node('button','Show the result');b.type='button';b.className='primary';b.onclick=()=>{location.href=location.pathname+'?view=stitched&auto=1'};result.append(b)}
  if(r.stitches&&job.state!=='running')result.after(changeSection(job));
 }
 /* Change it: say or type what to change; Needler says what it understood and shows it,
    and only after "Do it" makes that change, keeping the rest. */
 function changeSection(job){
  document.getElementById('autoChangeSection')?.remove();
  const section=node('section','','auto-change');section.id='autoChangeSection';
  section.innerHTML=`<h2>Change it</h2><p class="muted">Say or type what to change. Only that changes; the rest stays.</p>
   <div class="auto-chips">${AUTO_CHANGES.map(t=>`<button type="button">${t}</button>`).join('')}</div>`;
  const composer=autoComposer('autoChange','What to change','For example: remove the white background, keep only the ball on fire','See the change');
  section.append(composer);
  const answer=node('div','','auto-understood');answer.hidden=true;section.append(answer);
  const field=composer.querySelector('textarea'),send=composer.querySelector('.auto-send');
  if(job.changes?.length)section.querySelector('p').textContent=`Changes so far: ${job.changes.join(' · ')}. Say what else to change.`;
  for(const b of section.querySelectorAll('.auto-chips button'))b.onclick=()=>{field.value=b.textContent;ask()};
  field.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask()}});
  send.onclick=ask;
  async function ask(){
   const text=field.value.trim();if(!text){field.focus();return}
   send.disabled=true;answer.hidden=false;answer.replaceChildren(node('p','Reading what you asked…','muted'));
   const reply=await fetch(api+'/change',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})})
    .then(r=>r.ok?r.json():null).catch(()=>null);
   send.disabled=false;
   if(!reply){answer.replaceChildren(node('p','Could not read that. Is Needler still running?','auto-problem'));return}
   const claude=$('autoClaude').checked&&!$('autoClaudeRow').hidden;
   const parts=[];
   if(reply.understood.length){
    parts.push(node('strong','Here is what I will change'));
    const ul=node('ul');ul.append(...reply.understood.map(t=>node('li',t)));parts.push(ul);
   }else parts.push(node('p',claude?'Needler’s own rules do not cover this, so Claude will read it and decide when you press Do it.':
    'I did not find a change I can make from that. Try words like “remove the white background”, “5 colours”, “bigger” or “add an outline”, or turn on Let Claude decide.','auto-note'));
   if(reply.preview){
    const figure=node('figure');const img=document.createElement('img');img.src=reply.preview;img.alt='The picture with the part to leave out shown as a checkerboard';
    figure.append(img,node('figcaption','Checkerboard: left out, not sewn. Everything else is stitched.'));parts.push(figure);
   }
   if(reply.understood.length||claude){
    const row=node('div','','auto-actions');
    const go=node('button','Do it','primary');go.type='button';
    const no=node('button','Not that');no.type='button';
    no.onclick=()=>{answer.hidden=true;field.focus();field.select()};
    go.onclick=()=>apply(text,go);
    row.append(go,no);parts.push(row);
   }
   answer.replaceChildren(...parts);
  }
  async function apply(text,go){
   if(running)return;
   go.disabled=true;running=true;start.disabled=true;$('autoClose').disabled=true;cover.hidden=false;
   cover.querySelector('span').textContent='Making your change…';
   const response=await fetch(api+'/change/apply',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text,use_claude:$('autoClaude').checked})}).catch(()=>null);
   if(!response||response.status!==202){
    const body=await response?.json().catch(()=>({}))||{};
    running=false;start.disabled=false;$('autoClose').disabled=false;cover.hidden=true;go.disabled=false;
    answer.append(node('p',body.error||'Could not start the change. Is Needler still running?','auto-problem'));return;
   }
   section.remove();steps.replaceChildren();result.hidden=true;clearTimeout(timer);poll();
  }
  return section;
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
  steps.replaceChildren();result.hidden=true;result.replaceChildren();document.getElementById('autoChangeSection')?.remove();
  cover.querySelector('span').textContent='Starting…';
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
if(typeof module!=='undefined')module.exports={autoReviewNote,autoComposer,AUTO_REQUEST_LIMIT};
