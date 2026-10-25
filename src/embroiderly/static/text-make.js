/* Text designs: make the stitches obvious. A large "Make stitches" button sits
   under the text settings and nothing is stitched until it is pressed (making
   stitches while typing delayed the next change). A short hint says when the
   words changed since the last stitches. The size note waits until there is a
   measured size. The button only presses the existing check (lettering-native.js). */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 if(!window.nativeTextConfig)return;
 const $=id=>document.getElementById(id);
 const words=$('letteringWords'),check=$('stitch');
 if(!words||!check)return;
 const panel=words.closest('aside')||document.body;
 const make=document.createElement('button');make.type='button';make.id='textMake';make.className='primary';
 make.textContent='Make stitches';
 const hint=document.createElement('p');hint.className='muted';hint.id='textMakeHint';
 hint.textContent='Press Make stitches when your words are ready.';
 // Under the alignment / colour row, above 3D puff and the details.
 const anchor=$('letteringAlign')?.closest('div')?.parentElement?.querySelector(':scope > .puff-controls')
  || panel.querySelector('#workflowEdit .puff-controls') || $('letteringAlign')?.closest('div');
 if(anchor?.classList?.contains('puff-controls'))anchor.before(make,hint);else (anchor||words).after(make,hint);
 let busy=false,made=false;
 // Always answer a press: an earlier refused size must not leave the button dead.
 const say=(text,error)=>{hint.textContent=text;hint.classList.toggle('text-make-error',!!error)};
 const press=()=>{if(busy)return;if(!words.value.trim()){say('Type your words first.',true);words.focus();return}
  document.querySelectorAll('#workflowEdit [aria-invalid="true"]').forEach(el=>el.removeAttribute('aria-invalid'));check.click()};
 make.addEventListener('click',press);
 document.addEventListener('lettering:busy',e=>{
  busy=!!e.detail;make.disabled=busy;make.textContent=busy?'Making stitches…':'Make stitches';
  // A new press clears the last error; finishing keeps an error shown by lettering:failed.
  if(busy)hint.classList.remove('text-make-error');
  else if(!made&&!hint.classList.contains('text-make-error'))hint.textContent='Press Make stitches when your words are ready.';
 });
 // Only a real result counts as up to date (a failed check leaves the old hint).
 document.addEventListener('lettering:result',()=>{made=true;say('Stitches are up to date.')});
 // Why no stitches were made, next to the button (it was only in the status bar).
 document.addEventListener('lettering:failed',e=>say(e.detail,true));
 // Changing the words or settings only marks the stitches as out of date.
 const later=()=>{hint.classList.remove('text-make-error');hint.textContent=made?'Words or settings changed · press Make stitches to update.':'Press Make stitches when your words are ready.'};
 for(const id of ['letteringWords','nativeFont','nativeHeight','nativeWidth','letteringAlign','letteringColour','puffOn','puffFoam','nativeBaseline','nativeCurve','nativeFabric','nativeLetterSpacing','nativeLineSpacing','nativeSequence'])
  $(id)?.addEventListener(id==='letteringWords'||id==='nativeHeight'||id==='nativeWidth'||id==='nativeCurve'?'input':'change',later);
 // The size note is only useful once there is a measured size.
 const size=$('workflowMeasuredSize');
 if(size){
  const note=size.nextElementSibling;
  const sync=()=>{const empty=/needs checking|check stitches to measure/i.test(size.textContent);size.hidden=empty;if(note)note.hidden=empty};
  new MutationObserver(sync).observe(size,{childList:true,characterData:true,subtree:true});sync();
 }
});

/* Instant letter preview while typing: the words drawn with the real embroidery
   font over the canvas, no stitching (so no delay). Hidden as soon as real
   stitches are made, shown again when the words or settings change. */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 if(!window.nativeTextConfig)return;
 const $=id=>document.getElementById(id);
 const words=$('letteringWords');if(!words)return;
 const fonts={};let peeked=null,overlay=null,host=null,stale=!words.value.trim()?false:true,frame=0;
 const fontFor=key=>{
  if(!fonts[key]){fonts[key]=new FontFace('needler-'+key,`url(/text-font/${encodeURIComponent(key)})`).load()
   .then(face=>{document.fonts.add(face);return face}).catch(()=>null)}
  return fonts[key];
 };
 const canvas=()=>[...document.querySelectorAll('main canvas')].find(c=>c.offsetParent&&c.clientWidth>200&&!c.classList.contains('remove-overlay')&&!c.closest('.thread-3d'));
 function place(){
  const c=canvas();if(!c)return null;
  if(!overlay){overlay=document.createElement('canvas');overlay.className='text-preview';}
  if(overlay.parentElement!==c.parentElement){host=c.parentElement;if(getComputedStyle(host).position==='static')host.style.position='relative';host.append(overlay)}
  overlay.width=c.clientWidth;overlay.height=c.clientHeight;
  overlay.style.left=c.offsetLeft+'px';overlay.style.top=c.offsetTop+'px';
  overlay.style.width=c.clientWidth+'px';overlay.style.height=c.clientHeight+'px';
  return overlay;
 }
 async function draw(){
  const text=words.value.replace(/\s+$/,'');
  if((!stale&&!peeked)||!text){if(overlay)overlay.hidden=true;return}
  const key=peeked||$('nativeFont')?.value||'small_font',size=Math.max(1,Number($('nativeHeight')?.value)||5);
  const face=await fontFor(key);
  const o=place();if(!o)return;o.hidden=false;
  const g=o.getContext('2d'),family=face?`needler-${key}`:'sans-serif';
  // The height entered is the height of the stitched words (all lines), as on
  // the server (small_lettering.scale_for): measure the block at 100 px.
  g.font=`100px "${family}"`;
  const lines=text.split('\n'),probe=g.measureText('Hg');
  const step=((probe.fontBoundingBoxAscent||80)+(probe.fontBoundingBoxDescent||20))*1.05;
  const m=lines.map(l=>g.measureText(l||' '));
  const top=Math.min(...m.map((x,i)=>i*step-(x.actualBoundingBoxAscent||0)));
  const bottom=Math.max(...m.map((x,i)=>i*step+(x.actualBoundingBoxDescent||0)));
  const mmPerPx=size/Math.max(1,bottom-top),widths=m.map(x=>x.width*mmPerPx);
  const widthMm=Math.max(...widths),heightMm=size;
  const scale=Math.min(o.width*.84/Math.max(widthMm,1),o.height*.62/Math.max(heightMm,1));
  g.clearRect(0,0,o.width,o.height);
  g.fillStyle='#ebe8e1';  // fixed opaque fabric tone: the theme's canvas colour is translucent
  g.fillRect(0,0,o.width,o.height);  // solid: old stitches must not show through
  const px=mmPerPx*scale;g.font=`${100*px}px "${family}"`;g.fillStyle=$('letteringColour')?.value||'#202020';
  const align=$('letteringAlign')?.value||'center',y0=(o.height-heightMm*scale)/2-top*px;
  const baseline=$('nativeBaseline')?.value||'straight',arc=baseline!=='straight'&&lines.length===1;
  let shownMm=widthMm;
  if(arc){
   // Same placement as the stitches (embroidery_fonts._arc_matrices): each letter's centre on the
   // circle, turned to follow it; the circle's size follows the words' length (Curve in degrees).
   const line=lines[0],w=widths[0]*scale,sweep=Math.max(10,Number($('nativeCurve')?.value)||90)*Math.PI/180,R=w/sweep;
   const sag=R*(1-Math.cos(sweep/2)),up=baseline==='arc_over'?1:-1;
   // Width across the curve (arch letters stand outward, smile letters inward), as the stitch check measures it.
   shownMm=2*(R/scale+(up>0?.8*heightMm:0))*(sweep<Math.PI?Math.sin(sweep/2):1);
   const by=o.height/2+heightMm*scale*.35-up*sag/2;let x=-w/2;
   for(const ch of line){
    const adv=g.measureText(ch).width,a=(x+adv/2)/R;
    g.save();g.translate(o.width/2+R*Math.sin(a),by+up*R*(1-Math.cos(a)));g.rotate(up*a);g.fillText(ch,-adv/2,0);g.restore();x+=adv;
   }
  }else lines.forEach((line,i)=>{
   const w=widths[i]*scale,left=(o.width-widthMm*scale)/2,x=align==='left'?left:align==='right'?left+widthMm*scale-w:(o.width-w)/2;
   g.fillText(line,x,y0+i*step*px);
  });
  g.font='12px system-ui, sans-serif';g.fillStyle='#555';
  g.fillText(peeked?`Preview of this font · about ${Math.round(shownMm)} mm wide · click it to choose`
   :`Preview · about ${Math.round(shownMm)} mm wide · press Make stitches for the real stitches`,12,o.height-12);
 }
 const later=()=>{stale=true;cancelAnimationFrame(frame);frame=requestAnimationFrame(draw)};
 // The font picker (font-picker.js) previews a font on hover without choosing it.
 window.NeedlerTextPreview={peek:key=>{peeked=key;cancelAnimationFrame(frame);frame=requestAnimationFrame(draw)}};
 for(const id of ['letteringWords','nativeFont','nativeHeight','letteringAlign','letteringColour','nativeBaseline','nativeCurve'])
  $(id)?.addEventListener(id==='letteringWords'||id==='nativeHeight'||id==='nativeCurve'?'input':'change',later);
 document.addEventListener('lettering:result',()=>{stale=false;if(overlay)overlay.hidden=true});
 window.addEventListener('resize',()=>{if(stale)later()});
 if(stale)setTimeout(later,600);
});

/* Every problem at once, under Make stitches, each with a one-click fix (the server's
   /lettering/native/advice: puff font, height range, curve on one line, width). Fixes set
   the same fields the customer would, so the usual checks and undo still apply. */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 if(!window.nativeTextConfig||!window.nativeLettering)return;
 const $=id=>document.getElementById(id);
 const hint=$('textMakeHint');if(!hint)return;
 const list=document.createElement('ul');list.id='textAdvice';list.setAttribute('aria-live','polite');list.hidden=true;
 hint.after(list);
 const targets={text:'letteringWords',font:'nativeFont',height_mm:'nativeHeight',available_width_mm:'nativeWidth',align:'letteringAlign',
  colour:'letteringColour',baseline:'nativeBaseline',arc_degrees:'nativeCurve',letter_spacing_mm:'nativeLetterSpacing',
  line_spacing_percent:'nativeLineSpacing',sequence:'nativeSequence',fabric_preset:'nativeFabric',puff_foam_mm:'puffFoam'};
 function apply(values){
  if('puff' in values&&window.NativePuff&&window.NativePuff.get()!==!!values.puff){
   window.NativePuff.set(!!values.puff,values.puff_foam_mm);$('puffOn').dispatchEvent(new Event('change',{bubbles:true}));
  }
  for(const [key,value] of Object.entries(values)){
   const el=$(targets[key]);if(!el||value===undefined||String(el.value)===String(value))continue;el.value=String(value);
   for(const type of ['input','change'])el.dispatchEvent(new Event(type,{bubbles:true}));
  }
 }
 window.NeedlerTextApply=apply;
 const fixButton=fix=>{const b=document.createElement('button');b.type='button';b.textContent=fix.label;b.onclick=()=>apply(fix.set);return b};
 let timer=0,asked=0;
 window.NeedlerPuffFonts=null;
 async function check(){
  const ask=++asked,body=window.nativeLettering.values();
  if(!body.text.trim()){list.hidden=true;return}
  try{
   const response=await fetch('/lettering/native/advice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});
   const data=await response.json();if(ask!==asked)return;
   const problems=response.ok?data.problems:[{message:data.error||'These settings could not be checked.'}];
   window.NeedlerPuffFonts=body.puff?new Set(data.puff_fonts||[]):null;
   list.replaceChildren(...problems.map(p=>{
    const item=document.createElement('li');item.append(p.message+' ');
    if(p.fix)item.append(fixButton(p.fix));if(p.also)item.append(' ',fixButton(p.also));return item;
   }));
   list.hidden=!problems.length;
  }catch{if(ask===asked)list.hidden=true}
 }
 const later=()=>{clearTimeout(timer);timer=setTimeout(check,350)};
 // Delegated: the puff controls are added by another script, possibly after this one.
 const watched=new Set(['letteringWords','nativeFont','nativeHeight','nativeWidth','nativeBaseline','nativeCurve','nativeLetterSpacing','nativeLineSpacing','puffOn','puffFoam','nativeFabric']);
 for(const type of ['input','change'])document.addEventListener(type,e=>{if(watched.has(e.target?.id))later()});
 document.addEventListener('lettering:layout',later);document.addEventListener('lettering:result',later);
 setTimeout(check,800);
});

/* Ask AI on the Text page: describe what you want, Claude sets the text settings
   (checked by Needler as it goes), then the stitches are made. Shown only when
   Claude is set up on this computer (/api/auto-digitize-claude). */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 if(!window.nativeTextConfig||!window.nativeLettering)return;
 const $=id=>document.getElementById(id),edit=$('workflowEdit');if(!edit)return;
 const box=document.createElement('div');box.id='textAsk';box.hidden=true;
 box.innerHTML=`<label for="textAskInput">Ask AI</label>
  <div class="text-ask-row"><input id="textAskInput" maxlength="500" placeholder="e.g. curve it down, 3D puff for a cap">
  <button type="button" id="textAskGo">Ask</button></div><p id="textAskStatus" class="muted" role="status" aria-live="polite"></p>`;
 edit.querySelector('h1')?.after(box);
 fetch('/api/auto-digitize-claude').then(r=>r.json()).then(info=>{box.hidden=!info.available}).catch(()=>{});
 const input=$('textAskInput'),go=$('textAskGo'),say=t=>{$('textAskStatus').textContent=t};
 async function ask(){
  const request=input.value.trim();if(!request){input.focus();return}
  go.disabled=true;say('Thinking… Claude is choosing and checking the settings (about 10–40 seconds).');
  try{
   const response=await fetch('/lettering/native/ask',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({request,values:window.nativeLettering.values()}),signal:AbortSignal.timeout(180000)});
   const data=await response.json();
   if(!response.ok)throw Error(data.error||'AI help could not finish.');
   window.NeedlerTextApply(data.values);
   say(data.note+(data.problems.length?' Still to check: '+data.problems.join(' '):'')+` (AI cost $${data.claude_usd.toFixed(2)})`);
   if(!data.problems.length)setTimeout(()=>$('textMake')?.click(),300);
  }catch(error){say(error.message+' Your settings are unchanged.')}
  finally{go.disabled=false}
 }
 go.addEventListener('click',ask);
 input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.isComposing){e.preventDefault();ask()}});
});

/* Thread names for the text colour: the closest machine threads, click one to use its colour. */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 if(!window.nativeTextConfig)return;
 const colour=document.getElementById('letteringColour');if(!colour)return;
 const names=document.createElement('div');names.id='textThreads';names.setAttribute('aria-live','polite');
 (colour.closest('label')||colour).after(names);
 let asked=0;
 async function show(){
  const ask=++asked;
  try{
   const response=await fetch('/lettering/native/thread?hex='+encodeURIComponent(colour.value));
   const data=await response.json();if(ask!==asked||!response.ok)return;
   names.replaceChildren(...data.threads.map(t=>{
    const b=document.createElement('button');b.type='button';b.className='text-thread';
    b.title=`${t.brand} ${t.code} · ${t.name} · approximate match (ΔE ${t.delta_e})`;
    const chip=document.createElement('span');chip.style.background=t.hex;
    b.append(chip,`${t.brand} ${t.code} ${t.name}`);
    b.onclick=()=>{colour.value=t.hex;for(const type of ['input','change'])colour.dispatchEvent(new Event(type,{bubbles:true}))};
    return b;
   }));
  }catch{}
 }
 colour.addEventListener('change',show);colour.addEventListener('input',()=>{clearTimeout(show.t);show.t=setTimeout(show,250)});
 setTimeout(show,600);
});
