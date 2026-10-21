/* Visual editors for existing settings. No new stitch algorithms or second state owner. */
(() => {
 'use strict';
 const studio=window.embroideryStudio;
 if(!studio)return;
 const NS='http://www.w3.org/2000/svg';
 function sample(kind){
  const svg=document.createElementNS(NS,'svg');
  svg.setAttribute('viewBox','0 0 120 64');svg.setAttribute('aria-hidden','true');
  function path(d,width=1.8,opacity=1){
   const p=document.createElementNS(NS,'path');
   for(const [k,v] of Object.entries({d,fill:'none',stroke:'currentColor','stroke-width':width,'stroke-linecap':'round',opacity}))p.setAttribute(k,v);
   svg.append(p);
  }
  if(['tatami','embossed'].includes(kind)){
   for(let y=10;y<58;y+=4){path('M12 '+y+'H108',2);for(let x=20+(y%8)*2;x<108;x+=24)path('M'+x+' '+(y-1)+'v2',1,.4)}
   if(kind==='embossed')for(let x=20;x<100;x+=24)path(`M${x} 32l12-14 12 14-12 14Z`,2.5,.55);
  }else if(kind==='motif'||kind==='cross'){
   for(let x=16;x<100;x+=22)for(let y=12;y<52;y+=22)path(kind==='cross'?`M${x} ${y}l16 16m0-16-16 16`:`M${x+8} ${y}l8 8-8 8-8-8Z`,1.6);
  }else if(kind==='contour'||kind==='ripple'){
   for(let i=0;i<5;i++){const x=12+i*9,y=7+i*5,w=96-i*18,h=50-i*10;if(kind==='contour')path(`M${x} ${y}h${w}v${h}h-${w}Z`);else path(`M${x} 32a${w/2} ${h/2} 0 1 0 ${w} 0a${w/2} ${h/2} 0 1 0 -${w} 0`)}
  }else if(kind==='stipple'){
   path('M12 12C44-2 28 28 14 26S8 52 30 52S52 36 38 26S50 3 68 12S62 32 60 40S84 62 94 46S70 22 100 12');
  }else if(kind==='puff'){
   path('M24 52C24 14 96 14 96 52',10,.18);
   for(let x=28;x<=92;x+=4)path(`M${x} 52C${x} ${30+Math.abs(x-60)*.45} ${x+2} 22 ${x+2} 22`,1.6);
   path('M18 52H102',1.2,.5);
  }else if(kind==='raised_satin'){
   for(let y=12;y<=52;y+=2.5){path(`M28 ${y} L92 ${y-3}`,4,.4);path(`M28 ${y-2} L92 ${y-5}`,2)}
  }else if(kind==='off'){path('M24 12H96V52H24Z',1,.25);path('M48 32H72',2)}
  else if(kind==='satin'){
   for(let y=12;y<=52;y+=2.5)path(`M28 ${y} L92 ${y-3}`,2);
   path('M28 12V52M92 9V49',1,.5);
  }else{
   const width=kind==='bean'?4.5:1.5;
   path('M14 46L32 22L50 40L68 20L86 40L106 18',width);
   if(kind==='bean')path('M14 46L32 22L50 40L68 20L86 40L106 18',1,.45);
   for(const [x,y] of [[14,46],[32,22],[50,40],[68,20],[86,40],[106,18]]){
    const c=document.createElementNS(NS,'circle');c.setAttribute('cx',x);c.setAttribute('cy',y);c.setAttribute('r','2.2');c.setAttribute('fill','currentColor');svg.append(c);
   }
  }
  return svg;
 }
 window.StitchSamples=sample;
 function gallery(selector,key,title,choices,eventType){
  const select=document.querySelector(selector);if(!select)return;
  const oldLabel=select.closest('label');
  const group=document.createElement('fieldset');group.className='stitch-chooser';
  const legend=document.createElement('legend');legend.textContent=title;group.append(legend);
  const grid=document.createElement('div');grid.className='stitch-choice-grid';group.append(grid);
  const entries=choices.map(([value,name,kind,description])=>{
   const label=document.createElement('label');label.className='stitch-choice';
   const radio=document.createElement('input');radio.type='radio';radio.name='stitch-choice-'+key;radio.value=value;
   const text=document.createElement('strong');text.textContent=name;
   const hint=document.createElement('small');hint.textContent=description;
   label.append(radio,sample(kind),text,hint);grid.append(label);
   radio.addEventListener('change',()=>{
    if(!radio.checked||radio.disabled)return;
    select.value=value;select.dispatchEvent(new Event(eventType,{bubbles:true}));sync();
   });
   return {radio,label,value};
  });
  const note=document.createElement('p');note.className='stitch-choice-note';
  note.textContent='Illustrated stitch samples, not a sew-out prediction. Generate stitches to inspect your design.';group.append(note);
  oldLabel.before(group);oldLabel.hidden=true;oldLabel.style.display='none';
  // The original select remains a hidden adapter to the established undo/save handler.
  // There is exactly one visible editor; options remain the source of truth.
  function sync(){
   const settings=studio.snapshot();
   note.textContent=key==='border_style'&&settings.ink_only===true?'Turn off Black lines only in Colours to add a subject border.':'Illustrated stitch samples, not a sew-out prediction. Generate stitches to inspect your design.';
   for(const {radio,label,value} of entries){
    radio.checked=String(settings[key]??select.value)===value;
    radio.disabled=select.disabled||!!select.closest('fieldset:disabled')||(key==='border_style'&&settings.ink_only===true&&value!=='off');
    label.dataset.selected=String(radio.checked);
   }
  }
  window.addEventListener('studio:changed',sync);window.addEventListener('studio:controls',sync);sync();
 }
 gallery('[data-option="ink_bean_repeats"]','ink_bean_repeats','Stitch type · black lines',[
  ['0','Running','running','One pass · fine line'],
  ['1','Reinforced','bean','Bean stitch · extra passes'],
 ],'input');
 gallery('[data-border="border_style"]','border_style','Stitch type · subject border',[
  ['off','None','off','No added outline'],
  ['running','Running','running','Fine edge line'],
  ['satin','Satin','satin','Wide stitched band'],
 ],'change');
})();
