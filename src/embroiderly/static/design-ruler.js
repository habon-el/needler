/* Read-only image-space measurement. Physical scale belongs to height_mm;
   zoom and pan never participate in the distance calculation. */
(() => {
  'use strict';
  const studio=window.embroideryStudio, $=id=>document.getElementById(id);
  const make=(tag,text)=>{const el=document.createElement(tag);if(text)el.textContent=text;return el};
  const button=make('button');button.type='button';button.dataset.tool='measure';
  button.title='Measure between two points';button.setAttribute('aria-label','Ruler');
  button.setAttribute('aria-pressed','false');
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.classList.add('ui-icon');
  const path=document.createElementNS(svg.namespaceURI,'path');
  path.setAttribute('d','m3 16 13-13 5 5-13 13zM7 12l3 3m1-7 3 3m1-7 3 3');
  svg.append(path);button.append(svg,make('span','Ruler'));
  $('undo').before(button);
  const option=make('option','Ruler');option.value='measure';$('tool').append(option);
  const bar=make('div');bar.id='rulerBar';bar.className='surface-toolbar';bar.hidden=true;
  const output=make('output','Click point A, then point B.');output.id='rulerDistance';
  output.setAttribute('role','status');output.setAttribute('aria-live','polite');
  const clear=make('button','Clear measurement'),size=make('button','Edit size');
  clear.type=size.type='button';clear.id='clearRuler';size.id='rulerEditSize';
  bar.append(output,clear,size);$('toolHint').after(bar);
  const targetLabel=make('label','Adjust with arrows '),target=make('select');
  target.id='rulerTarget';target.setAttribute('aria-label','Ruler keyboard target');
  for(const [value,label] of [['cursor','New point'],['0','Point A'],['1','Point B'],['all','Whole ruler']]){const opt=make('option',label);opt.value=value;target.append(opt)}
  targetLabel.append(target);bar.append(targetLabel);
  let points=[],cursor=null,drag=null;
  const copy=()=>points.map(p=>p.slice());
  function translate(base,dx,dy){
    const {width,height}=studio.imageSize();
    dx=Math.max(-Math.min(...base.map(p=>p[0])),Math.min(width-1-Math.max(...base.map(p=>p[0])),dx));
    dy=Math.max(-Math.min(...base.map(p=>p[1])),Math.min(height-1-Math.max(...base.map(p=>p[1])),dy));
    return base.map(p=>[p[0]+dx,p[1]+dy]);
  }
  function start(p,scale){
    const before=copy(),hit=points.findIndex(q=>Math.hypot(q[0]-p[0],q[1]-p[1])*scale<=12);
    let mode=hit;
    if(hit<0&&points.length===2){
      const [a,b]=points,dx=b[0]-a[0],dy=b[1]-a[1],length=dx*dx+dy*dy;
      const t=length?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length)):0;
      if(Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)*scale<=8)mode='all';
    }
    if(mode===-1){place(p);mode=points.length===1?'new':1}
    drag={before,base:copy(),at:p.slice(),mode,scale};
    target.value=mode==='all'?'all':mode==='new'?'cursor':String(mode);
  }
  function move(p){
    if(!drag)return;
    if(drag.mode==='new'){
      if(Math.hypot(p[0]-drag.at[0],p[1]-drag.at[1])*drag.scale<3)return;
      points=[drag.at.slice(),p.slice()];
    }else if(drag.mode==='all')points=translate(drag.base,p[0]-drag.at[0],p[1]-drag.at[1]);
    else points[drag.mode]=p.slice();
    cursor=null;
  }
  function cancel(){if(drag){points=drag.before;drag=null;cursor=null}}
  const active=()=>$('tool').value==='measure';
  const text=mm=>document.documentElement.dataset.units==='in'?(mm/25.4).toFixed(3)+' in':mm.toFixed(1)+' mm';
  function reset(){points=[];cursor=null;drag=null;target.value='cursor';studio.redraw()}
  function place(p){if(points.length!==1)points=[];points.push(p.slice());cursor=p.slice()}
  button.onclick=()=>{document.querySelector('[data-tool="pan"]').click();studio.selectTool('measure');const canvas=[...document.querySelectorAll('.panels canvas')].find(c=>c.parentElement.style.display!=='none');canvas?.focus({preventScroll:true})};
  clear.onclick=reset;
  size.onclick=()=>{
    document.querySelector('[data-topic="size"]').click();
    const field=document.querySelector('[data-option="height_mm"]');
    field.closest('details').open=true;field.focus();field.select();
  };
  window.DesignRuler={place,start,move,cancel,end:()=>{drag=null},paint(c,scale,height,heightMm,enabled){
    bar.hidden=!enabled;if(!enabled)return;
    clear.disabled=!points.length;
    for(const opt of target.options)opt.disabled=opt.value==='all'?points.length!==2:['0','1'].includes(opt.value)?!points[Number(opt.value)]:false;
    const label=points.length===2?'A → B: '+text(Math.hypot(points[1][0]-points[0][0],points[1][1]-points[0][1])*heightMm/height):points.length?'Point A set. Click point B.':'Click point A, then point B.';
    if(output.textContent!==label)output.textContent=label;
    c.save();c.lineCap='round';
    const stroke=()=>{c.strokeStyle='#ffffff';c.lineWidth=4/scale;c.stroke();c.strokeStyle='#243538';c.lineWidth=2/scale;c.stroke()};
    if(points.length===2){c.setLineDash([1/scale,6/scale]);c.beginPath();c.moveTo(...points[0]);c.lineTo(...points[1]);stroke();c.setLineDash([])}
    points.forEach((p,i)=>{c.beginPath();c.arc(...p,4/scale,0,Math.PI*2);stroke();c.font=12/scale+'px system-ui';c.lineWidth=3/scale;c.strokeStyle='#ffffff';c.strokeText(i?'B':'A',p[0]+7/scale,p[1]-7/scale);c.fillStyle='#243538';c.fillText(i?'B':'A',p[0]+7/scale,p[1]-7/scale)});
    if(cursor){c.beginPath();c.moveTo(cursor[0]-7/scale,cursor[1]);c.lineTo(cursor[0]+7/scale,cursor[1]);c.moveTo(cursor[0],cursor[1]-7/scale);c.lineTo(cursor[0],cursor[1]+7/scale);stroke()}
    c.restore();
  }};
  for(const canvas of document.querySelectorAll('.panels canvas'))canvas.addEventListener('keydown',e=>{
    if(!active()||e.isComposing||e.ctrlKey||e.metaKey||e.altKey||studio.isBusy())return;
    const moves={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
    if(!moves[e.key]&&!['Enter','Escape'].includes(e.key))return;
    e.preventDefault();e.stopImmediatePropagation();
    const {width,height}=studio.imageSize();
    if(e.key==='Escape'){if(drag){cancel();studio.redraw()}else reset();return}
    if(moves[e.key]&&target.value!=='cursor'){
      const step=e.shiftKey?10:1,dx=moves[e.key][0]*step,dy=moves[e.key][1]*step;
      if(target.value==='all'&&points.length===2)points=translate(points,dx,dy);
      else if(points[Number(target.value)]){const i=Number(target.value);points[i]=[Math.max(0,Math.min(width-1,points[i][0]+dx)),Math.max(0,Math.min(height-1,points[i][1]+dy))]}
      cursor=null;studio.redraw();return;
    }
    cursor??=[width/2,height/2];
    if(e.key==='Enter')place(cursor);
    else{const step=e.shiftKey?10:1;cursor=[Math.max(0,Math.min(width-1,cursor[0]+moves[e.key][0]*step)),Math.max(0,Math.min(height-1,cursor[1]+moves[e.key][1]*step))]}
    studio.redraw();
  },true);
  new MutationObserver(()=>studio.redraw()).observe(document.documentElement,{attributes:true,attributeFilter:['data-units']});
})();
