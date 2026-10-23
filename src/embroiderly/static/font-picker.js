/* Font picker for text designs, like a word processor's: every font shows the
   customer's own words written in that font, hovering one previews it on the
   canvas (text-make.js), clicking chooses it. The real <select> stays the
   source of truth; choosing sets it and sends its usual events. */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 if(!window.nativeTextConfig)return;
 const $=id=>document.getElementById(id);
 const select=$('nativeFont'),words=$('letteringWords');
 if(!select||!words)return;
 const faces={};
 const face=key=>faces[key]||(faces[key]=new FontFace('needler-'+key,`url(/text-font/${encodeURIComponent(key)})`).load()
  .then(f=>{document.fonts.add(f);return true}).catch(()=>false));
 const name=o=>o.textContent.split('·')[0].replace(/\(.*\)/,'').trim();
 const style=o=>(o.textContent.split('·')[1]||'').trim();
 const button=document.createElement('button');button.type='button';button.id='fontPick';
 button.setAttribute('aria-haspopup','listbox');button.setAttribute('aria-expanded','false');
 const list=document.createElement('div');list.id='fontList';list.setAttribute('role','listbox');list.hidden=true;
 list.setAttribute('aria-label','Embroidery fonts');
 select.hidden=true;select.after(button,list);
 const sample=()=>(words.value.split('\n').find(l=>l.trim())||'').trim().slice(0,28);
 function show(){
  const o=select.selectedOptions[0];if(!o)return;
  button.textContent=name(o);button.dataset.key=o.value;button.style.fontFamily=`"needler-${o.value}", sans-serif`;
  face(o.value);
 }
 function fill(){
  const text=sample();
  list.replaceChildren(...[...select.options].map(o=>{
   const row=document.createElement('div');row.className='font-row';row.setAttribute('role','option');
   row.dataset.key=o.value;row.tabIndex=-1;row.setAttribute('aria-selected',String(o.selected));
   const big=document.createElement('span');big.className='font-sample';big.textContent=text||name(o);
   big.style.fontFamily=`"needler-${o.value}", sans-serif`;
   const small=document.createElement('span');small.className='font-name';
   small.textContent=name(o)+(style(o)?' · '+style(o):'');
   row.append(big,small);face(o.value);return row;
  }));
 }
 function open(){fill();list.hidden=false;button.setAttribute('aria-expanded','true');
  (list.querySelector('[aria-selected=true]')||list.firstChild)?.focus();}
 function close(back){list.hidden=true;button.setAttribute('aria-expanded','false');window.NeedlerTextPreview?.peek(null);if(back)button.focus();}
 function choose(key){
  if(select.value!==key){select.value=key;for(const type of ['input','change'])select.dispatchEvent(new Event(type,{bubbles:true}));}
  show();close(true);
 }
 button.addEventListener('click',()=>list.hidden?open():close(true));
 list.addEventListener('click',e=>{const row=e.target.closest('.font-row');if(row)choose(row.dataset.key)});
 // Hover or arrow keys: see the words in that font on the canvas before choosing.
 list.addEventListener('mouseover',e=>{const row=e.target.closest('.font-row');if(row)window.NeedlerTextPreview?.peek(row.dataset.key)});
 list.addEventListener('mouseleave',()=>window.NeedlerTextPreview?.peek(null));
 list.addEventListener('focusin',e=>{const row=e.target.closest('.font-row');if(row)window.NeedlerTextPreview?.peek(row.dataset.key)});
 list.addEventListener('keydown',e=>{
  const rows=[...list.children],i=rows.indexOf(document.activeElement);
  if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();rows[Math.max(0,Math.min(rows.length-1,i+(e.key==='ArrowDown'?1:-1)))]?.focus()}
  else if(e.key==='Enter'||e.key===' '){e.preventDefault();if(rows[i])choose(rows[i].dataset.key)}
  else if(e.key==='Escape'){e.preventDefault();close(true)}
 });
 document.addEventListener('pointerdown',e=>{if(!list.hidden&&!list.contains(e.target)&&e.target!==button)close(false)});
 select.addEventListener('change',show);
 words.addEventListener('input',()=>{if(!list.hidden)fill()});
 // Loading a saved design sets the select without an event: keep the button in step.
 setInterval(()=>{if(button.dataset.key!==select.value)show()},500);
 show();
});
