/* Problems panel on Check stitches: one line per problem, Show and Fix.
   Fixes are preparation edits (problems.py); the stitches are then rebuilt
   and checked again. Nothing technical is shown. */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 const $=id=>document.getElementById(id), studio=window.embroideryStudio;
 if(!studio||window.nativeTextConfig)return;
 const panel=document.createElement('section');panel.className='problems-panel';panel.hidden=true;
 ($('workflowCheck')||document.querySelector('.inspector')).prepend(panel);
 let shown='',problems=[];
 const prepared=()=>{const href=$('exportPes')?.getAttribute('href')||'';const m=href.match(/^\/studio-export\/([^/]+)\//);return m?decodeURIComponent(m[1]):null};
 const node=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text)e.textContent=text;return e};
 function patchFor(list){
  const o=studio.snapshot(),edits=[...(o.edits||[])],set={};
  for(const p of list){if(!p.fix)continue;edits.push(...(p.fix.edits||[]));Object.assign(set,p.fix.set||{})}
  return {...set,...(edits.length!==(o.edits||[]).length?{edits}:{})};
 }
 function fix(list){
  try{studio.acceptRefinement(patchFor(list));panel.replaceChildren(node('p','muted','Fixing and checking again…'))}
  catch(error){(window.studioStatus||console.warn)(error.message)}
 }
 function render(){
  // Directly under the "Check your stitches" heading.
  const heading=panel.parentElement?.querySelector(':scope > h1');
  if(heading&&heading.nextElementSibling!==panel)heading.after(panel);
  panel.classList.toggle('problems-ok',!problems.length);
  if(!problems.length){panel.hidden=!prepared();panel.replaceChildren(node('p',null,'All checks passed. Sew a test before the real item.'));return}
  panel.hidden=false;
  const fixable=problems.filter(p=>p.fix);
  const head=node('div','problems-head');head.append(node('h2',null,problems.length===1?'1 problem to fix':`${problems.length} problems to fix`));
  if(fixable.length>1){const all=node('button','primary','Fix all');all.type='button';all.onclick=()=>fix(fixable);head.append(all)}
  const list=node('ul');
  for(const p of problems.slice(0,8)){
   const li=node('li');li.append(node('span',null,p.title+(p.count>1&&p.code!=='cuts'?` (${p.count})`:'')));
   const buttons=node('span','problems-actions');
   if(p.bounds){const s=node('button',null,'Show');s.type='button';s.onclick=()=>studio.focusReview(p.bounds);buttons.append(s)}
   if(p.fix){const f=node('button',null,'Fix');f.type='button';f.title=p.fix.label;f.onclick=()=>fix([p]);buttons.append(f)}
   li.append(buttons);list.append(li);
  }
  panel.replaceChildren(head,list);
  if(problems.length>8)panel.append(node('p','muted',`${problems.length-8} more after these are fixed.`));
 }
 async function refresh(){
  const name=prepared();if(!name){problems=[];render();return}
  if(name===shown)return;shown=name;
  try{
   const data=await fetch('/api/problems/'+encodeURIComponent(name),{cache:'no-store'}).then(r=>r.ok?r.json():{problems:[],note:'unavailable'});
   problems=data.problems||[];
   // The checks could not run: never claim they passed.
   if(data.note)problems=[{id:'stale',code:'stale',title:'Stitches need to be made again',count:1,bounds:null,fix:null}];
  }catch(_){problems=[{id:'stale',code:'stale',title:'Stitches could not be checked',count:1,bounds:null,fix:null}]}
  render();
 }
 window.addEventListener('studio:preview',()=>setTimeout(refresh,300));
 setInterval(refresh,1500);
});
