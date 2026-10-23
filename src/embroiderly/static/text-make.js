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
 for(const id of ['letteringWords','nativeFont','nativeHeight','nativeWidth','letteringAlign','letteringColour','puffOn','puffFoam'])
  $(id)?.addEventListener(id==='letteringWords'||id==='nativeHeight'||id==='nativeWidth'?'input':'change',later);
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
  lines.forEach((line,i)=>{
   const w=widths[i]*scale,left=(o.width-widthMm*scale)/2,x=align==='left'?left:align==='right'?left+widthMm*scale-w:(o.width-w)/2;
   g.fillText(line,x,y0+i*step*px);
  });
  g.font='12px system-ui, sans-serif';g.fillStyle='#555';
  g.fillText(peeked?`Preview of this font · about ${Math.round(widthMm)} mm wide · click it to choose`
   :`Preview · about ${Math.round(widthMm)} mm wide · press Make stitches for the real stitches`,12,o.height-12);
 }
 const later=()=>{stale=true;cancelAnimationFrame(frame);frame=requestAnimationFrame(draw)};
 // The font picker (font-picker.js) previews a font on hover without choosing it.
 window.NeedlerTextPreview={peek:key=>{peeked=key;cancelAnimationFrame(frame);frame=requestAnimationFrame(draw)}};
 for(const id of ['letteringWords','nativeFont','nativeHeight','letteringAlign','letteringColour'])
  $(id)?.addEventListener(id==='letteringWords'||id==='nativeHeight'?'input':'change',later);
 document.addEventListener('lettering:result',()=>{stale=false;if(overlay)overlay.hidden=true});
 window.addEventListener('resize',()=>{if(stale)later()});
 if(stale)setTimeout(later,600);
});
