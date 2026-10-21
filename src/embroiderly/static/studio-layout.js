/* Studio layout: docks, splitter and focus mode around the one canvas.
   Placement only. Nodes are moved, never copied; their owners keep handlers. */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 const $=id=>document.getElementById(id), q=s=>document.querySelector(s);
 const main=q('main'), header=q('main > header'), bench=q('.workbench'), inspector=q('.inspector');
 if(!main||!header||!bench||!inspector)return;
 const store={
  get(key,fallback){try{const v=localStorage.getItem('needler.layout.'+key);return v===null?fallback:JSON.parse(v);}catch{return fallback;}},
  set(key,value){try{localStorage.setItem('needler.layout.'+key,JSON.stringify(value));}catch{}},
 };
 const node=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text)e.textContent=text;return e;};
 const icon=d=>`<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${d}"/></svg>`;
 const toggle=(label,title,d,fn)=>{const b=node('button','dock-toggle');b.type='button';b.title=title;b.setAttribute('aria-pressed','true');b.innerHTML=icon(d)+'<span>'+label+'</span>';b.onclick=fn;return b;};
 main.classList.add('studio-layout');

 // One top bar: steps sit between the brand and the actions.
 const steps=$('workflowSteps');
 if(steps)header.firstElementChild.after(steps);
 // Status, design size and thread order share one bottom bar, like a desktop digitizer.
 const status=q('.statusbar');
 if(status){
  bench.after(status);
  const info=q('.thread-info');if(info)status.insertBefore(info,$('designSize'));
 }

 // Canvas column: view bar, canvas, then one compact info line and the player.
 const area=q('.canvas-area'), panels=q('.panels');
 if(area&&panels){
  const line=node('div','canvas-info');line.setAttribute('aria-label','Canvas information');
  for(const id of ['toolHint','workflowCanvasSize'])if($(id))line.append($(id));
  panels.after(line);
  const heading=$('workflowPlaybackHeading');if(heading)heading.classList.add('sr-only');
 }

 // Docks: Pieces on the left, properties on the right. Both collapse; the right one resizes.
 const pieces=q('.piece-layers');
 const viewbar=q('.viewbar');
 const dockBar=node('div','dock-bar');dockBar.setAttribute('role','group');dockBar.setAttribute('aria-label','Panels');
 const state={pieces:store.get('pieces',innerWidth>=1500),inspector:store.get('inspector',true),focus:false,width:store.get('inspectorWidth',316)};
 const piecesButton=pieces?toggle('Pieces','Show or hide the Pieces list','M4 5h16M4 12h16M4 19h16',()=>{state.pieces=!state.pieces;store.set('pieces',state.pieces);state.focus=false;apply();}):null;
 const propsButton=toggle('Properties','Show or hide the properties panel','M15 4v16M4 4h16v16H4z',()=>{state.inspector=!state.inspector;store.set('inspector',state.inspector);state.focus=false;apply();});
 const focusButton=toggle('Focus','Canvas only: hide both panels (F)','M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5',()=>{state.focus=!state.focus;apply();});
 if(piecesButton)dockBar.append(piecesButton);
 dockBar.append(propsButton,focusButton);
 if(viewbar)viewbar.append(dockBar);

 const splitter=node('div','dock-splitter');
 splitter.setAttribute('role','separator');splitter.setAttribute('aria-orientation','vertical');
 splitter.setAttribute('aria-label','Resize properties panel');splitter.tabIndex=0;
 splitter.setAttribute('aria-valuemin','260');splitter.setAttribute('aria-valuemax','560');
 inspector.before(splitter);
 const clamp=w=>Math.round(Math.max(260,Math.min(560,Math.min(w,innerWidth*.45))));
 const setWidth=(w,save)=>{state.width=clamp(w);bench.style.setProperty('--inspector-w',state.width+'px');splitter.setAttribute('aria-valuenow',state.width);if(save)store.set('inspectorWidth',state.width);};
 splitter.addEventListener('pointerdown',e=>{
  if(e.button!==0)return;
  e.preventDefault();splitter.setPointerCapture(e.pointerId);bench.classList.add('is-resizing');
  const right=bench.getBoundingClientRect().right;
  const move=ev=>setWidth(right-ev.clientX,false);
  const up=()=>{splitter.removeEventListener('pointermove',move);bench.classList.remove('is-resizing');store.set('inspectorWidth',state.width);};
  splitter.addEventListener('pointermove',move);splitter.addEventListener('pointerup',up,{once:true});splitter.addEventListener('pointercancel',up,{once:true});
 });
 splitter.addEventListener('keydown',e=>{
  const step=e.shiftKey?40:10;
  if(e.key==='ArrowLeft'){setWidth(state.width+step,true);e.preventDefault();}
  else if(e.key==='ArrowRight'){setWidth(state.width-step,true);e.preventDefault();}
 });
 splitter.addEventListener('dblclick',()=>setWidth(316,true));

 function apply(){
  // Text designs have no pieces list; its owner hides it there.
  const hasPieces=!!pieces&&!pieces.hidden&&bench.classList.contains('with-pieces');
  const showPieces=hasPieces&&state.pieces&&!state.focus, showProps=state.inspector&&!state.focus;
  bench.classList.toggle('pieces-collapsed',!showPieces);
  bench.classList.toggle('inspector-collapsed',!showProps);
  if(piecesButton){piecesButton.hidden=!hasPieces;piecesButton.setAttribute('aria-pressed',String(showPieces));}
  propsButton.setAttribute('aria-pressed',String(showProps));
  focusButton.setAttribute('aria-pressed',String(state.focus));
 }
 setWidth(state.width,false);apply();
 if(pieces)new MutationObserver(apply).observe(pieces,{attributes:true,attributeFilter:['hidden']});
 document.addEventListener('keydown',e=>{
  if(e.key!=='f'&&e.key!=='F')return;
  if(e.ctrlKey||e.metaKey||e.altKey||e.repeat)return;
  if(e.target.closest('input,textarea,select,[contenteditable=true]'))return;
  state.focus=!state.focus;apply();e.preventDefault();
 });
});
