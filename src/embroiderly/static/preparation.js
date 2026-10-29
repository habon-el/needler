(() => {
'use strict';
const $=id=>document.getElementById(id), config=window.preparationConfig;
config.nativeText=window.nativeTextConfig;
const nativeMode=!!config.nativeText;
const workspaceStitches='/artwork/'+encodeURIComponent(config.name)+'?view=stitched';
const openStitches=new URLSearchParams(location.search).get('view')==='stitched';
let options={ink_length_mm:2,ink_bean_repeats:0,selection:'full',count:4,brightness:1,contrast:1,height_mm:100,floor_mm2:1,simplify:0,smooth:1,mask_holes_mm2:1,mask_smooth:0,edge:0,hints:[],edits:[],locks:[],merges:{},interactions:0,...config.options};
let proposalBefore=null,proposalAfter=null,proposalVersion=0;
const canvases=['original','prepared','stitched'].map($), original=new Image(), prepared=new Image(), isolated=new Image();
let width=1,height=1, zoom=1,panX=0,panY=0,space=false,gesture=null,history=[],redoHistory=[],activeControl=null,selectedBounds=null,timer,revision=0,busy=false,queued=false,playback=null,latest=null;
const stitchLayer=new window.StitchLayer();let threadAt=new Uint32Array(1),stitchBounds=null;
const sample=document.createElement('canvas'), sampleCtx=sample.getContext('2d'),tint=document.createElement('canvas');

let routeReport=null,routeFlag=-1;
let colourPreviewPlan=null,colourPreviewMap={},colourPreviewImage=null,colourFrame=0;
let outlineDraft=[],draftMoving=-1,outlinePurpose='keep',brushCursor=null;
const outlineTool=tool=>['polygon','erase-outline'].includes(tool);
let currentView='original',cursor=0,running=false,lastFrame=0,stitchError='',queuedAction=null,preparingAction=null,resultStateKey='';
// Read-only presentation of this controller's result; artwork is not a stitch plan.
function resultInfo(){
 const report=latest?.report,blockers=report?.generation_blockers?.length||0;
 const pending=(report?.cleanup_review||[]).filter(item=>item.decision==='pending').length;
 return {state:busy&&preparingAction==='digitize'?'generating':stitchError?'error':playback?'ready':busy?'preparing':blockers||pending?'blocked':'empty',
  error:stitchError,blockers,pending,stitches:playback?.stitch_count||0,trims:playback?.trim_count||0};
}
function updateStitchState(){
 const info=resultInfo(),key=JSON.stringify(info);
 if(key!==resultStateKey){resultStateKey=key;window.dispatchEvent(new CustomEvent('studio:stitch-state',{detail:info}));}
 $('stitchEmpty').hidden=currentView!=='stitched'||!!playback;
 $('stitchEmptyTitle').textContent=busy?'Preparing stitch view…':stitchError?'Stitch preview could not be prepared':'No current stitch plan';
 $('stitchEmptyMessage').textContent=busy?'Please wait. The controls will become available when preparation finishes.':stitchError||'No current stitches. Return to Edit to approve your subject, then choose Check stitches.';
 $('stitchEmptyConfirm').checked=$('confirmed').checked;
 $('stitchEmptyConfirm').disabled=busy;
 $('stitchEmptyGenerate').disabled=busy||!$('confirmed').checked;
 $('stitchEmptyGenerate').textContent=stitchError?'Retry generating stitches':'Generate stitches';
}
const panels=canvases.map(c=>c.parentElement);
function setView(view){
 if(view==='stitched'&&currentView!=='stitched'&&playback){zoom=1;panX=panY=0}
 currentView=view;
 $('middleView').value=view==='isolated'?'isolated':'prepared';
 panels.forEach((p,i)=>p.style.display=(view==='review'?(i===0||i===2):view==='compare'?(i<2):(view==='original'?i===0:['isolated','prepared','proposal'].includes(view)?i===1:i===2))?'block':'none');
 document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));
 if(view!=='stitched'){running=false;$('run').textContent='▶ Play'}
 draw();updateStitchState();window.dispatchEvent(new CustomEvent('studio:view',{detail:view}));
}
function transport(){
 updateHealth();updateStitchState();
 const available=!!playback;
 $('routeFinished').disabled=!available;$('routeNext').disabled=!available||!routeReport?.flags.length;
 if(!available){$('routeSummary').textContent='Generate current stitches to inspect their route.';$('routeBorder').textContent='No current border stitch plan.';$('routeWarning').textContent=''}
 for(const id of ['run','rewind','timeline','stepBack','stepNext','finish','fitStitches'])$(id).disabled=!available;
 $('timeline').max=available?playback.steps.length:0;$('timeline').value=cursor;
 $('progress').textContent=available?cursor.toLocaleString()+' / '+playback.steps.length.toLocaleString():'No current stitch plan';
 if(available){
  let s=playback.steps[Math.max(0,cursor-1)],block=threadAt[cursor]||0;
  const baseHex=s?.color||playback.colors[0],hex=colourPreviewMap[baseHex]||baseHex;
  $('activeThread').textContent='Thread '+(block+1)+' of '+playback.colors.length+' · '+hex+(playback.colors[block+1]?' · Next '+(colourPreviewMap[playback.colors[block+1]]||playback.colors[block+1]):' · Last colour');
  $('activeThread').style.borderLeft='12px solid '+hex;$('activeThread').style.paddingLeft='8px';
 }else{$('activeThread').textContent='Update stitches to preview thread order.';$('activeThread').style.borderLeft='none'}
}
function configurePlayback(result){
 stitchLayer.reset();threadAt=new Uint32Array(playback.steps.length+1);stitchBounds=null;
 routeReport=window.RouteReview.analyze(playback);routeFlag=-1;$('routeWarning').textContent='';
 $('routeSummary').textContent=routeReport.flags.length+' route warnings · '+routeReport.jumps+' jump commands. No warning is not a guarantee of stitch quality.';
 const border=playback.border;
 $('routeBorder').textContent=border?border.style+' border · '+border.colour+' · '+(border.style==='satin'?border.width_mm+' mm · '+border.placement:'running outline')+' · sewn after fills in the actual playback.':'This saved plan has no border metadata. Add a border and regenerate to include it.';
 let prior={x:0,y:0};
 playback.steps.forEach((step,i)=>{
  threadAt[i+1]=threadAt[i]+(step.t==='color_change'?1:0);
  if(step.t==='stitch'){
   for(const p of [prior,step]){
    if(!stitchBounds)stitchBounds=[p.x,p.y,p.x,p.y];
    else{stitchBounds[0]=Math.min(stitchBounds[0],p.x);stitchBounds[1]=Math.min(stitchBounds[1],p.y);stitchBounds[2]=Math.max(stitchBounds[2],p.x);stitchBounds[3]=Math.max(stitchBounds[3],p.y)}
   }
  }prior=step;
 });
 buildColourStops();
 cursor=playback.steps.length;running=false;$('run').textContent='▶ Play';transport();
 const name=new URL(result.simulation,location.origin).pathname.split('/').pop();
 if(nativeMode)return; // Native controller owns checked-file approval/downloads.
 for(const [id,format] of [['exportPes','pes'],['exportDst','dst']]){$(id).href='/studio-export/'+encodeURIComponent(name)+'/'+format;$(id).hidden=false}
}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>setView(b.dataset.view));
$('stitchLink').addEventListener('click',e=>{if(e.button||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();setView('stitched')});
const hints={'colour-remove':'Click a colour to preview removal everywhere or in this area. Nothing changes until Apply.',polygon:'Click around the subject. Drag points to adjust. Space-drag or middle-drag to pan; wheel to zoom. Apply outline when ready.',box:'Draw a rectangle around your subject, leaving a small background margin.',lasso:'Draw a closed outline around the part to embroider.',keep:'Brush over missing subject areas. Works with outlines and assisted selections.',remove:'Brush over background that should be excluded.','erase-outline':'Click around the area to remove. Review the red area, then Erase area. Esc cancels. Nothing changes until applied.',erase:'Brush erase removes inside the visible circle. Drag to erase; Undo restores the previous edit.',paint:'Paint with the selected colour.',pan:'Drag to pan. Mouse wheel zooms. Your position stays when you change views.',inspect:'Click a small detail to zoom into the original and artwork together.',split:'Click the original to preserve an additional colour.'};
function selectTool(tool){
 if(nativeMode&&!['pan','measure'].includes(tool)){status('Edit native letters with the Text controls; picture tools are not applied.');return;}
 hints.measure='Drag to measure. Drag A or B to adjust; drag the dotted line to move it. Arrow keys adjust the chosen target. Esc cancels a drag or clears. Space-drag pans.';
 const purpose=tool==='erase-outline'?'erase':'keep';
 if(outlineTool(tool)&&purpose!==outlinePurpose){outlineDraft=[];draftMoving=-1}
 if(outlineTool(tool))outlinePurpose=purpose;
 $('tool').value=tool;brushCursor=null;
 $('outlineActions').hidden=!outlineTool(tool)&&!outlineDraft.length;
 $('outlineActions').dataset.purpose=outlinePurpose;
 $('applyOutline').textContent=outlinePurpose==='erase'?'Erase area':'Keep outline';
 $('editOutline').hidden=outlinePurpose==='erase';
 $('toolHint').textContent=hints[tool];
 document.querySelectorAll('[data-tool]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tool===tool)));
 if(!['pan','measure'].includes(tool))setView('original');
 draw();
}
document.querySelectorAll('[data-tool]').forEach(b=>b.onclick=()=>selectTool(b.dataset.tool));
$('splitTool').onclick=()=>selectTool('split');
$('run').onclick=()=>{if(!playback)return;setView('stitched');if(cursor>=playback.steps.length)cursor=0;running=!running;$('run').textContent=running?'Ⅱ Pause':'▶ Play';transport();draw()};
$('rewind').onclick=()=>{running=false;cursor=0;$('run').textContent='▶ Play';setView('stitched');transport()};
$('timeline').oninput=()=>{running=false;cursor=+$('timeline').value;$('run').textContent='▶ Play';setView('stitched');transport()};
function seek(position){if(!playback)return;running=false;cursor=Math.max(0,Math.min(playback.steps.length,position));$('run').textContent='▶ Play';setView('stitched');transport()}
$('routeArrows').onchange=$('routeJumps').onchange=()=>draw();
$('routeFinished').onclick=()=>seek(playback?.steps.length||0);
$('routeNext').onclick=()=>{
 if(!playback||!routeReport?.flags.length)return;
 routeFlag=(routeFlag+1)%routeReport.flags.length;const flag=routeReport.flags[routeFlag];
 seek(flag.index+1);$('routeArrows').checked=true;$('routeJumps').checked=true;
 $('routeWarning').textContent='Warning '+(routeFlag+1)+' / '+routeReport.flags.length+' · command '+(flag.index+1)+' · '+flag.length.toFixed(2)+' mm. '+flag.reason;
 draw();
};
$('stepBack').onclick=()=>seek(cursor-1);$('stepNext').onclick=()=>seek(cursor+1);$('finish').onclick=()=>seek(playback?.steps.length||0);
$('fitStitches').onclick=()=>{
 if(!playback||!stitchBounds)return;setView('stitched');
 const canvas=canvases[2],factor=height/options.height_mm,[left,top,right,bottom]=stitchBounds;
 const base=Math.min(canvas.width/width,canvas.height/height)*.92;
 zoom=Math.max(.1,Math.min(16,canvas.width*.82/(Math.max(right-left,.5)*factor*base),canvas.height*.82/(Math.max(bottom-top,.5)*factor*base)));
 const centerX=((left+right)/2+playback.origin_mm[0])*factor,centerY=((top+bottom)/2+playback.origin_mm[1])*factor;
 panX=(width/2-centerX)*base*zoom/canvas.width;panY=(height/2-centerY)*base*zoom/canvas.height;draw();
};
function frame(t){if(running&&playback&&t-lastFrame>=33){cursor=Math.min(playback.steps.length,cursor+Math.max(1,Math.round(Math.min(t-lastFrame,100)*Number($('rate').value)/1000)));lastFrame=t;draw();transport();if(cursor===playback.steps.length){running=false;$('run').textContent='▶ Play'}}if(!running)lastFrame=t;requestAnimationFrame(frame)}
requestAnimationFrame(frame);

function updateHistory(){ $('undo').disabled=!history.length; $('redo').disabled=!redoHistory.length; }
function remember(){history.push(JSON.stringify(options));if(history.length>20)history.shift();redoHistory=[];updateHistory()}
function status(text){$('status').textContent=text}
function syncInkControls(){$('inkStitchSettings').disabled=options.ink_only!==true;document.querySelectorAll('#swatches input,#paintColour,[data-option=count],[data-option=smooth],[data-option=simplify],[data-option=floor_mm2],[data-option=mask_holes_mm2],[data-option=mask_smooth]').forEach(e=>e.disabled=options.ink_only===true);const removed=!!options.colour_knockouts?.length;
 document.querySelectorAll('[data-option=smooth],[data-option=simplify],[data-option=floor_mm2],[data-option=mask_holes_mm2],[data-option=mask_smooth],[data-option=edge]').forEach(e=>e.disabled=options.ink_only===true||removed);
 $('protectSubject').disabled=$('unprotectSubject').disabled=removed;
 window.dispatchEvent(new Event('studio:controls'))}
function syncControls(){syncInkControls();$('inkOnly').checked=options.ink_only===true;$('lineArt').checked=options.line_art===true;document.querySelectorAll('[data-border]').forEach(e=>{const defaults={border_style:'off',border_width:2,border_colour:'#202020',border_placement:'center',border_spacing:.4,border_inner:'off',border_motif:'diamond',border_pattern:'wave'};e.value=options[e.dataset.border]??defaults[e.dataset.border]});$('borderMotif').style.display=options.border_style==='motif'?'':'none';$('borderPattern').style.display=options.border_style==='pattern'?'':'none';$('protectSubject').setAttribute('aria-pressed',String(options.protect_selection===true));$('protectSubject').textContent=options.protect_selection?'Fine details protected':'Protect fine details';const colourBudget=document.querySelector('[data-option=count]');colourBudget.min=options.artwork_type==='portrait'?8:2;colourBudget.max=options.artwork_type==='portrait'?12:8;document.querySelectorAll('[data-option]').forEach(el=>el.value=options[el.dataset.option]);$('countValue').value=options.count}
function focusDetail(bounds){
 selectedBounds=bounds.slice();setView('compare');
 const c=canvases[0],base=Math.min(c.width/width,c.height/height)*.92;
 zoom=Math.max(1,Math.min(16,.7*Math.min(c.width/(Math.max(8,bounds[2]-bounds[0])*base),c.height/(Math.max(8,bounds[3]-bounds[1])*base))));
 panX=(width/2-(bounds[0]+bounds[2])/2)*base*zoom/c.width;
 panY=(height/2-(bounds[1]+bounds[3])/2)*base*zoom/c.height;
 draw();status('Detail close-up: original left, simplified artwork right. Zoom does not add missing pixels. Use detail recovery or preserve a source colour.');
}
function transform(canvas){const s=Math.min(canvas.width/width,canvas.height/height)*.92*zoom;return {s,x:(canvas.width-width*s)/2+panX*canvas.width,y:(canvas.height-height*s)/2+panY*canvas.height}}
function draw(){
 $('toolHint').textContent=currentView==='proposal'?'Compare the colour-removal proposal. Move the Before / After slider, review the enclosed parts, then Apply removal.':hints[$('tool').value];
 $('knockoutWipeBar').hidden=currentView!=='proposal';
 $('surfaceToolbar').hidden=!['stitched','review','wipe'].includes(currentView);
 $('downloadMockup').disabled=!playback;
 canvases.forEach((canvas,i)=>{
  if(canvas.parentElement.style.display==='none')return;
  const rect=canvas.getBoundingClientRect(),cw=Math.max(1,Math.round(rect.width)),ch=Math.max(1,Math.round(rect.height));if(canvas.width!==cw)canvas.width=cw;if(canvas.height!==ch)canvas.height=ch;
  const c=canvas.getContext('2d'),t=transform(canvas);
  c.clearRect(0,0,canvas.width,canvas.height);c.save();c.translate(t.x,t.y);c.scale(t.s,t.s);
  if(i===0&&original.naturalWidth)c.drawImage(original,0,0,width,height);
  if(i===1){const im=$('middleView').value==='isolated'?isolated:prepared;if(im.naturalWidth)c.drawImage($('middleView').value!=='isolated'&&colourPreviewImage?colourPreviewImage:im,0,0,width,height)}
  if(i===1&&currentView==='proposal'&&proposalAfter&&proposalBefore){
    c.clearRect(0,0,width,height);c.drawImage(proposalAfter,0,0,width,height);
    const split=width*Number($('knockoutWipe').value)/100;
    c.save();c.beginPath();c.rect(0,0,split,height);c.clip();c.clearRect(0,0,width,height);c.drawImage(proposalBefore,0,0,width,height);c.restore();
    c.strokeStyle='#126957';c.lineWidth=2/t.s;c.beginPath();c.moveTo(split,0);c.lineTo(split,height);c.stroke();
  }
  if(i===1&&currentView!=='proposal')window.PiecePanel?.paint(c,t.s);
  if(i===1&&currentView!=='proposal')window.CanvasGuides?.paint(c,t.s);
  if(i===1&&currentView!=='proposal'&&window.stitchRegionSelection){
    c.save();c.beginPath();
    for(const ring of window.stitchRegionSelection.rings){ring.forEach(([x,y],j)=>j?c.lineTo(x,y):c.moveTo(x,y));c.closePath()}
    c.fillStyle='rgba(0,180,160,.18)';c.fill('evenodd');c.strokeStyle='#008d79';c.lineWidth=2/t.s;c.stroke();c.restore();
  }
  if(i===0&&prepared.naturalWidth&&options.selection!=='full'){
    tint.width=width;tint.height=height;const mask=tint.getContext('2d');mask.drawImage(prepared,0,0);mask.globalCompositeOperation='source-in';mask.fillStyle='#00c999';mask.fillRect(0,0,width,height);c.globalAlpha=+$('overlay').value/100;c.drawImage(tint,0,0);c.globalAlpha=1;
  }
  if(i===2){
    c.fillStyle=$('fabric').value;c.fillRect(0,0,width,height);
    const displayPlan=playback||colourPreviewPlan;
    if(!displayPlan){
     c.save();c.setTransform(1,0,0,1,0,0);
     const theme=getComputedStyle(document.documentElement),availableWidth=Math.max(1,canvas.width-48);
     c.fillStyle=theme.getPropertyValue('--ui-background').trim()||'#eef2f3';c.fillRect(0,0,canvas.width,canvas.height);
     c.fillStyle=theme.getPropertyValue('--ui-ink').trim()||'#24383e';c.font='bold 18px system-ui';
     c.fillText(busy&&preparingAction==='digitize'?'Making stitches…':'No stitches yet',24,52,availableWidth);
     c.font='14px system-ui';c.fillText('See the status above.',24,80,availableWidth);c.restore();
    }
    if(displayPlan){
      const factor=height/options.height_mm;
      stitchLayer.paint(c,displayPlan,playback?cursor:displayPlan.steps.length,{width:canvas.width,height:canvas.height,...t,factor,threadWidth:Number($('threadVisualWidth').value),relief:$('threadRelief').checked,colourMap:colourPreviewMap,fabric:$('fabric').value,texture:$('fabricTexture').value,lightAngle:Number($('lightAngle').value),neutralLight:$('neutralLight').checked});
      window.threadPreviewUI?.sync(stitchLayer,!!playback);
      if(playback)window.RouteReview.paint(c,playback,cursor,{s:t.s,factor},$('routeArrows').checked,$('routeJumps').checked);
      window.MultiHooping?.paint(c,t.s,factor);
      if(currentView==='wipe'){const edge=width*Number(document.getElementById('reviewWipe').value)/100;c.save();c.beginPath();c.rect(0,0,edge,height);c.clip();c.drawImage(original,0,0,width,height);c.restore();c.save();c.strokeStyle='#007fca';c.lineWidth=2/t.s;c.beginPath();c.moveTo(edge,0);c.lineTo(edge,height);c.stroke();c.restore();}
      // Needle marker is a screen overlay, not an extra stitch.
      if(playback&&cursor>0&&cursor<playback.steps.length){
       const step=playback.steps[cursor-1],x=(step.x+playback.origin_mm[0])*factor,y=(step.y+playback.origin_mm[1])*factor;
       c.save();c.lineWidth=1.5/t.s;c.strokeStyle='#0879bc';c.beginPath();c.arc(x,y,5/t.s,0,Math.PI*2);c.moveTo(x-8/t.s,y);c.lineTo(x+8/t.s,y);c.moveTo(x,y-8/t.s);c.lineTo(x,y+8/t.s);c.stroke();c.restore();
      }
    }
  }
  if(i===0){
    c.lineWidth=2/t.s;c.strokeStyle='#008d79';
    const box=gesture?.tool==='box'?gesture.rect:options.selection==='grabcut'?options.rect:null;
    if(box){const [x,y,r,b]=box;c.strokeRect(x,y,r-x,b-y)}
    if(options.outline&&options.selection==='lasso'){
      c.beginPath();options.outline.forEach(([x,y],j)=>j?c.lineTo(x,y):c.moveTo(x,y));c.closePath();c.stroke();
    }
    for(const hint of options.hints||[]){
      c.strokeStyle=hint.kind==='keep'?'#20da90':'#ff4550';c.lineWidth=hint.radius*2;c.globalAlpha=.6;c.lineCap='round';
      c.beginPath();hint.points.forEach(([x,y],j)=>j?c.lineTo(x,y):c.moveTo(x,y));c.stroke();c.globalAlpha=1;
    }
  }
  if(i===0||i===1){
   c.lineWidth=2/t.s;c.strokeStyle='#236dc7';
   for(const line of options.direction_lines||[]){c.beginPath();line.forEach(([x,y],j)=>j?c.lineTo(x,y):c.moveTo(x,y));c.stroke()}
   c.strokeStyle='#b54e96';
   for(const feature of options.portrait_features||[]){const [x,y,r,b]=feature.bounds;c.strokeRect(x,y,r-x,b-y)}
  }
  if(i===0&&outlineDraft.length){c.strokeStyle=outlinePurpose==='erase'?'#a53545':'#ff8a00';c.lineWidth=2/t.s;c.beginPath();outlineDraft.forEach(([x,y],j)=>j?c.lineTo(x,y):c.moveTo(x,y));c.closePath();if(outlinePurpose==='erase'){c.fillStyle='rgba(165,53,69,.22)';c.fill()}c.stroke();for(const [x,y] of outlineDraft){c.beginPath();c.arc(x,y,5/t.s,0,Math.PI*2);c.fillStyle='#fff';c.fill();c.stroke()}}
  if(i===1&&$('middleView').value==='prepared'&&latest?.report?.border){const border=latest.report.border;c.save();c.strokeStyle=border.colour;c.globalAlpha=.7;c.lineWidth=(border.style==='satin'?border.width_mm:.2)/border.scale;c.lineJoin='miter';c.miterLimit=6;for(const path of border.paths){c.beginPath();path.forEach(([x,y],j)=>j?c.lineTo(x,y):c.moveTo(x,y));c.closePath();c.stroke()}c.restore()}
  if(i===0&&gesture?.tool==='erase'){
   c.save();c.strokeStyle='rgba(165,53,69,.5)';c.fillStyle=c.strokeStyle;
   c.lineWidth=Number($('radius').value)*2;c.lineCap='round';c.lineJoin='round';
   c.beginPath();gesture.points.forEach(([x,y],j)=>j?c.lineTo(x,y):c.moveTo(x,y));c.stroke();
   for(const [x,y] of [gesture.points[0],gesture.points[gesture.points.length-1]]){c.beginPath();c.arc(x,y,Number($('radius').value),0,Math.PI*2);c.fill()}c.restore();
  }
  if(i===0&&brushCursor&&['erase','paint','keep','remove'].includes($('tool').value)){
   c.save();c.strokeStyle=$('tool').value==='erase'?'#a53545':'#126957';c.lineWidth=1.5/t.s;
   c.beginPath();c.arc(...brushCursor,Number($('radius').value),0,Math.PI*2);c.stroke();c.restore();
  }
  if(selectedBounds){const [x,y,r,b]=selectedBounds;c.strokeStyle='#dd7600';c.lineWidth=2/t.s;c.setLineDash([5/t.s,3/t.s]);c.strokeRect(x,y,r-x,b-y);c.setLineDash([])}
  window.DesignRuler?.paint(c,t.s,height,options.height_mm,$('tool').value==='measure');
  c.restore();
  const mm=height/options.height_mm*t.s,unit=10*mm>canvas.width*.4?1:10;c.fillStyle='#234536';c.fillRect(16,canvas.height-22,unit*mm,2);c.font='11px system-ui';c.fillText(unit+' mm',16,canvas.height-28);
 });$('zoomValue').textContent=Math.round(zoom*100)+'%';
}
function point(e,canvas){const r=canvas.getBoundingClientRect(),t=transform(canvas);return [Math.max(0,Math.min(width-1,(e.clientX-r.left-t.x)/t.s)),Math.max(0,Math.min(height-1,(e.clientY-r.top-t.y)/t.s))]}
function invalidate(keepApproval=false){proposalVersion++;proposalBefore=proposalAfter=null;if(currentView==='proposal')currentView='prepared';colourPreviewPlan=null;colourPreviewMap={};colourPreviewImage=null;cancelAnimationFrame(colourFrame);colourFrame=0;stitchLayer.reset();queuedAction=null;stitchError='';window.dispatchEvent(new Event('studio:changed'));latest=null;selectedBounds=null;running=false;cursor=0;$('run').textContent='▶ Play';$('exportPes').hidden=$('exportDst').hidden=true;if(!keepApproval)$('confirmed').checked=false;$('stitch').disabled=true;revision++;playback=null;$('colourStops').replaceChildren();transport();$('stitchLink').hidden=true;$('stitchStatus').textContent='Artwork changed. Generate again to update the stitched result.';draw()}
function schedule(keepApproval=false){invalidate(keepApproval);clearTimeout(timer);status('Preview updating…');timer=setTimeout(()=>requestPreview(),250)}
function colourName(hex){const a=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)),v=a.reduce((s,n)=>s+n)/3;
 if(Math.max(...a)-Math.min(...a)<25)return v<30?'Black':v<100?'Charcoal':v<190?'Grey':v<240?'Light grey':'White';
 return 'Custom thread';}
function renderPalette(palette){
 $('swatches').replaceChildren();
 palette.forEach(p=>{
  const el=document.createElement('div');el.className='chip';el.draggable=options.ink_only!==true;
  const input=document.createElement('input');input.type='color';input.value=p.hex;input.title='Replace '+p.hex;
  let sourcePixels=null,baseMap=null;
  const liveColour=()=>{
   if(!sourcePixels){const c=document.createElement('canvas');c.width=width;c.height=height;const ink=c.getContext('2d');ink.drawImage(prepared,0,0,width,height);sourcePixels=ink.getImageData(0,0,width,height);baseMap={...colourPreviewMap}}
   $('exportPes').hidden=$('exportDst').hidden=true;$('stitchLink').hidden=true;
   colourPreviewPlan=playback||colourPreviewPlan;
   colourPreviewMap={...baseMap};
   for(const [key,value] of Object.entries(baseMap))if(value===p.hex)colourPreviewMap[key]=input.value;
   colourPreviewMap[p.hex]=input.value;
   const c=document.createElement('canvas');c.width=width;c.height=height;
   const pixels=new ImageData(new Uint8ClampedArray(sourcePixels.data),width,height);
   const from=[1,3,5].map(i=>parseInt(p.hex.slice(i,i+2),16)),to=[1,3,5].map(i=>parseInt(input.value.slice(i,i+2),16));
   for(let i=0;i<pixels.data.length;i+=4)if(pixels.data[i+3]&&from.every((v,j)=>pixels.data[i+j]===v))to.forEach((v,j)=>pixels.data[i+j]=v);
   c.getContext('2d').putImageData(pixels,0,0);colourPreviewImage=c;if(playback){buildColourStops();transport()}draw();
   $('stitchStatus').textContent='Live colour preview on existing paths — not regenerated. Update stitches before exporting.';
  };
  input.oninput=()=>{cancelAnimationFrame(colourFrame);colourFrame=requestAnimationFrame(()=>{colourFrame=0;liveColour()})};
  input.onchange=()=>{
   cancelAnimationFrame(colourFrame);colourFrame=0;liveColour();
   const previewPlan=colourPreviewPlan,previewMap=colourPreviewMap,previewImage=colourPreviewImage;
   remember();
   let mapped=false;for(const key of Object.keys(options.merges))if(options.merges[key]===p.hex){options.merges[key]=input.value;mapped=true}
   if(!mapped)options.merges[p.hex]=input.value;
   options.locks=options.locks.filter(c=>c!==p.hex);
   // A new thread colour keeps the subject and its shapes, so "I approve" stays; picking another
   // swatch's colour merges two areas (new shapes) and needs approving again.
   const merged=palette.some(c=>c.hex!==p.hex&&c.hex.toLowerCase()===input.value.toLowerCase());
   options.interactions++;schedule(!merged);
   colourPreviewPlan=previewPlan;colourPreviewMap=previewMap;colourPreviewImage=previewImage;draw();
   $('stitchStatus').textContent='Colour preview only — previous paths retained. '+(merged?'Approve and update':'Update')+' stitches to regenerate/export.';
  };
  const text=document.createElement('div');text.textContent=colourName(p.hex)+' '+p.hex;
  const label=document.createElement('label'),lock=document.createElement('input');lock.type='checkbox';lock.checked=options.locks.includes(p.hex);
  lock.onchange=()=>{remember();options.locks=options.locks.filter(c=>c!==p.hex);if(lock.checked)options.locks.push(p.hex);options.interactions++;schedule()};
  label.append(lock,' Preserve colour');el.append(input,text,label);if(p.match){
   const match=document.createElement('p');match.className='muted';match.textContent='Nearest '+p.match.brand+' '+p.match.code+' · '+p.match.name+' (ΔE00 '+p.match.delta_e+')';el.append(match);
   const choices=document.createElement('details');choices.style.gridColumn='1 / -1';const title=document.createElement('summary');title.textContent='Compare thread suggestions';choices.append(title);
   // The chart menu limits the suggestions to one thread chart; remembered on this computer, shared with the Text page.
   const rows=document.createElement('div'),picker=document.createElement('select');picker.title='Thread chart';picker.setAttribute('aria-label','Thread chart');
   const listed=list=>rows.replaceChildren(...list.map(candidate=>{const row=document.createElement('p'),swatch=document.createElement('span');swatch.style.cssText='display:inline-block;width:16px;height:16px;margin-right:6px;border:1px solid #888;vertical-align:middle';swatch.style.background=candidate.hex;row.append(swatch,candidate.brand+' '+candidate.code+' · '+candidate.name+' · '+candidate.hex+' · ΔE00 '+candidate.delta_e);return row}));
   const suggest=async()=>{let chart='';try{chart=picker.options.length?picker.value:localStorage.getItem('needler.threadChart')||''}catch{}
    try{const response=await fetch('/lettering/native/thread?hex='+encodeURIComponent(p.hex)+(chart?'&chart='+encodeURIComponent(chart):''));const data=await response.json();if(!response.ok)return;
     if(!picker.options.length){picker.append(new Option('All charts',''),...data.charts.map(c=>new Option(c,c)));picker.value=data.charts.includes(chart)?chart:''}
     listed(data.threads)}catch{}};
   picker.onchange=()=>{try{localStorage.setItem('needler.threadChart',picker.value)}catch{};suggest()};
   choices.ontoggle=()=>{if(choices.open)suggest()};
   listed(p.match.alternatives||[]);choices.append(picker,rows);
   const note=document.createElement('p');note.textContent='CIEDE2000 compares catalogue RGB values. Lower is closer digitally; check a physical thread chart. Suggestions do not change your artwork.';choices.append(note);el.append(choices)}
  el.ondragstart=e=>e.dataTransfer.setData('text/plain',p.hex);el.ondragover=e=>e.preventDefault();
  el.ondrop=e=>{e.preventDefault();const from=e.dataTransfer.getData('text/plain');if(!palette.some(c=>c.hex===from)||from===p.hex)return;if(options.locks.includes(from)){status('Turn off Preserve colour for the source before merging.');return}remember();options.merges[from]=p.hex;options.interactions++;schedule()};
  el.onclick=e=>{if(e.target===el||e.target===text)$('paintColour').value=p.hex};
  $('swatches').append(el);
 });
}
function metrics(r){$('borderStatus').textContent=r.border?`${r.border.style} border · ${r.border.paths.length} outer outlines · sews after fills. Artwork is a width guide, not stitches. ${r.border.warnings.join(' ')}`:'No border. Choose Running or Satin to add an outer outline.';
 updateHealth();
 $('designSize').textContent=(r.width_px/r.height_px*r.height_mm).toFixed(1)+' mm wide × '+Number(r.height_mm).toFixed(1)+' mm high · '+r.colours_after+' colours';
 $('metrics').replaceChildren();
 for(const [title,a,b] of [['Colours',r.colours_before,r.colours_after],['Connected regions',r.regions_before,r.regions_after],['Regions below '+r.floor_mm2+' mm²',r.below_floor_before,r.below_floor_after]]){
  const tr=document.createElement('tr');for(const value of [title,a,b]){const td=document.createElement('td');td.textContent=value;tr.append(td)}$('metrics').append(tr);
 }
 $('maskMetrics').textContent=r.colour_knockouts?.length?'Colour removal protects the holes. General smoothing, small-area removal and mask cleanup are paused; your stored settings are unchanged.':r.mask_specks_removed+' mask specks removed; '+r.mask_holes_filled+' small holes filled; '+r.mask_boundary_pixels_changed+' boundary pixels adjusted; '+r.mask_below_floor_after+' mask regions still below the area floor. Explicit keep/drop strokes take priority.';
 $('cleanup').textContent=r.boundary_pixels_changed+' boundary pixels adjusted; '+r.isolated_subject_islands_removed+' disconnected subject islands removed; '+r.specks_reassigned+' small regions processed under '+r.cleanup_floor_mm2.toFixed(2)+' mm². '+r.interactions+' recorded editing actions. '+r.width_px+' × '+r.height_px+' working pixels at '+r.height_mm+' mm canvas height. '+r.note;
}
let pieceRevision=null,acceptedOptions=JSON.stringify(options),pieceNotice='';
async function requestPreview(action,pieceCommand=null,restoreOptions=null){
 if(nativeMode)return window.NativeWorkspace?.action(action);
 if(action==='digitize'&&window.letteringSizeMetrics){
  status('This saved text is picture-based. Choose an embroidery font in Text to rebuild it. Your original font and picture stay unchanged.');
  $('textTool')?.click();return false;
 }
 if(busy){if(action){queuedAction={action,revision};if(action==='digitize')setView('stitched')}else queued=true;return}
 busy=true;preparingAction=action;queued=false;stitchError='';if(action==='digitize'){proposalVersion++;proposalBefore=proposalAfter=null}updateStitchState();const version=revision;
 const generationStart=performance.now();
 const progressTimer=action==='digitize'?setInterval(()=>{status('Generating stitch plan · '+Math.floor((performance.now()-generationStart)/1000)+' seconds elapsed. Complex designs may take several minutes.');draw()},1000):null;
 if(action==='digitize')setView('stitched');
 $('save').disabled=$('stitch').disabled=true;
 if(action)document.querySelectorAll('aside input,aside select,aside button:not([data-topic]):not([data-tool="pan"])').forEach(e=>e.disabled=true);
 status(action==='digitize'?'Preparing and generating real stitches locally…':'Preparing artwork…');
 try{
  const response=await fetch('/artwork/'+encodeURIComponent(config.name),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({options:restoreOptions||options,piece_revision:pieceRevision,piece_command:pieceCommand,piece_undo:!!restoreOptions,save:action==='save',digitize:action==='digitize',subject_confirmed:$('confirmed').checked})});
  const result=await response.json();
  if(version!==revision){queued=true;return}
  const reviewRequired=result.code==='cleanup_review_required';
  if(!response.ok&&!reviewRequired)throw new Error(result.error||'Preparation failed.');
  if(!reviewRequired){
   pieceRevision=result.piece_revision;
   acceptedOptions=JSON.stringify(result.options||options);
  }
  if(result.options){if(pieceCommand)remember();options=result.options;syncControls()}
  pieceNotice=pieceCommand&&result.piece_notice||'';
  if(result.piece_blocked){playback=null;running=false;cursor=0;stitchLayer.reset();$('exportPes').hidden=$('exportDst').hidden=$('stitchLink').hidden=true;$('colourStops').replaceChildren();setView('prepared');$('stitchStatus').textContent='Check the red pieces or show a piece. Nothing removed; no current stitches.'}
  latest=result;colourPreviewImage=null;await new Promise((resolve,reject)=>{prepared.onload=resolve;prepared.onerror=reject;prepared.src=result.image});
  await new Promise((resolve,reject)=>{isolated.onload=resolve;isolated.onerror=reject;isolated.src=result.isolated});
  if(version!==revision){queued=true;return}
  renderPalette(result.palette);metrics(result.report);
  window.dispatchEvent(new CustomEvent('studio:preview',{detail:{options:JSON.parse(JSON.stringify(options)),report:result.report,stitchCount:result.playback?.stitch_count??playback?.stitch_count??0,portraitAudit:result.playback?.portrait_audit,applique:result.playback?.applique,sewParts:result.playback?.sew_parts??playback?.sew_parts??[],hasPlayback:!!result.playback||!!playback}}));
  if(reviewRequired){
   setView('prepared');draw();status(result.error);
   window.dispatchEvent(new Event('studio:cleanup-needed'));
   return false;
  }
  if(result.playback){colourPreviewPlan=null;colourPreviewMap={};playback=result.playback;playback.origin_mm=playback.origin_mm||[0,0];$('stitchLink').href=workspaceStitches;$('stitchLink').hidden=false;$('stitchStatus').textContent=playback.stitch_count+' stitches · '+playback.trim_count+' trims · '+playback.colors.length+' thread blocks. Actual written paths; sew-out still required.';configurePlayback(result);if(action==='digitize')$('fitStitches').onclick()}
  draw();status((result.piece_blocked?'Piece saved; check its warning before generating stitches. ':action==='save'?'Settings and prepared artwork saved. ':action==='digitize'?'Stitches generated from this prepared artwork. ':'Preview ready. ')+(result.report.below_floor_after?'Some small details need checking.':'Review your subject before making stitches.'));
  const styleCount=(result.report.stitch_regions?.areas||[]).filter(a=>a.style_notice).length;if(styleCount)status($('status').textContent+' '+styleCount+' stitch-style notices below the canvas.');
  if(action==='save')window.dispatchEvent(new Event('studio:saved'));
  return true;
 }catch(error){if(error.message.includes('locked')){options=JSON.parse(acceptedOptions);syncControls()}stitchError=error.message;status('Could not prepare: '+error.message);if(options.border_style&&options.border_style!=='off')$('borderStatus').textContent='Border not generated: '+error.message;return false}
 finally{if(progressTimer!==null)clearInterval(progressTimer);busy=false;preparingAction=null;$('save').disabled=false;$('stitch').disabled=!$('confirmed').checked;document.querySelectorAll('aside input,aside select,aside button').forEach(e=>e.disabled=false);syncInkControls();updateHistory();updateStitchState();draw();const pending=queuedAction;queuedAction=null;if(pending&&pending.revision===revision)requestPreview(pending.action);else if(queued)requestPreview()}
}
document.querySelectorAll('[data-option]').forEach(el=>el.oninput=()=>{if(activeControl!==el){remember();activeControl=el}options[el.dataset.option]=+el.value;options.interactions++;if(['count','brightness','contrast','simplify'].includes(el.dataset.option))options.merges={};syncControls();schedule()});
document.querySelectorAll('[data-border]').forEach(el=>el.onchange=()=>{remember();options[el.dataset.border]=el.type==='number'?Number(el.value):el.value;$('borderMotif').style.display=options.border_style==='motif'?'':'none';$('borderPattern').style.display=options.border_style==='pattern'?'':'none';options.interactions++;schedule()});
$('lineArt').onchange=()=>{remember();options.line_art=$('lineArt').checked;if(options.line_art){options.ink_only=false;$('inkOnly').checked=false;delete options.colour_knockouts}syncInkControls();options.interactions++;schedule();setView('prepared')};
$('inkOnly').onchange=()=>{remember();options.ink_only=$('inkOnly').checked;if(options.ink_only){options.line_art=false;$('lineArt').checked=false}syncInkControls();options.interactions++;schedule();setView('prepared')};
$('save').onclick=()=>{clearTimeout(timer);requestPreview('save')};
$('stitch').onclick=()=>{clearTimeout(timer);requestPreview('digitize')};
$('protectSubject').onclick=()=>{remember();options.protect_selection=true;options.edge=0;options.interactions++;syncControls();schedule();setView('isolated');status('Selection protected from mask cleanup. Subject view preserves original colours; Artwork and Stitches still use separate colour reduction.')};
$('unprotectSubject').onclick=()=>{remember();options.protect_selection=false;options.interactions++;syncControls();schedule();status('Automatic mask cleanup enabled. Review the subject boundary.')};
$('outlineSubject').onclick=()=>{selectTool('polygon');status('Click outline points, adjust them, then Apply outline. Your existing selection is unchanged until applied.')};
function finishOutline(){
 if(busy){status('Wait for the preview to finish.');return}
 if(outlineDraft.length<3){status('Add at least three outline points.');return}
 const area=Math.abs(outlineDraft.reduce((sum,p,i)=>{const q=outlineDraft[(i+1)%outlineDraft.length];return sum+p[0]*q[1]-q[0]*p[1]},0))/2;
 if(area<1){status('Draw an enclosed area, not a straight line.');return}
 remember();
 if(outlinePurpose==='erase'){
  options.edits.push({kind:'erase',shape:'polygon',points:outlineDraft.map(p=>p.slice()),radius:1});
 }else{options.selection='lasso';options.outline=outlineDraft.map(p=>p.slice());options.hints=[];options.edge=0;options.protect_selection=true}
 options.interactions++;const erased=outlinePurpose==='erase';
 outlineDraft=[];draftMoving=-1;syncControls();schedule();selectTool(erased?'erase-outline':'polygon');
 if(erased)setView('isolated');
}
function discardOutline(){outlineDraft=[];draftMoving=-1;draw();status('Draft canceled. Your artwork is unchanged.')}
$('applyOutline').onclick=finishOutline;$('cancelOutline').onclick=discardOutline;
$('undoOutlinePoint').onclick=()=>{outlineDraft.pop();draw()};
$('editOutline').onclick=()=>{if(options.selection!=='lasso'||!options.outline?.length){status('Draw and apply an outline first.');return}outlineDraft=options.outline.map(p=>p.slice());selectTool('polygon');draw()};
$('full').onclick=()=>{remember();options.selection='full';options.hints=[];options.outline=[];options.rect=null;options.interactions++;schedule()};
async function restoreHistory(redo=false){
 if(busy)return;
 const from=redo?redoHistory:history,to=redo?history:redoHistory;if(!from.length)return;
 const candidate=JSON.parse(from[from.length-1]),before=JSON.stringify(options);
 if(options.piece_edits||candidate.piece_edits){
  if(await requestPreview('digitize',null,candidate)){from.pop();to.push(before);updateHistory()}
 }else{to.push(before);options=JSON.parse(from.pop());syncControls();updateHistory();schedule()}
}
$('undo').onclick=()=>restoreHistory();
$('overlay').oninput=$('fabric').oninput=$('knockoutWipe').oninput=draw;
$('threadVisualWidth').oninput=()=>{$('threadWidthValue').value=Number($('threadVisualWidth').value).toFixed(3)+' mm';draw()};
$('threadRelief').onchange=draw;
$('middleView').onchange=draw;$('confirmed').onchange=()=>{$('stitch').disabled=busy||!$('confirmed').checked;updateStitchState()};
$('stitchEmptyConfirm').onchange=()=>{$('confirmed').checked=$('stitchEmptyConfirm').checked;$('confirmed').onchange()};
$('stitchEmptyGenerate').onclick=()=>{if(!$('confirmed').checked)return;clearTimeout(timer);requestPreview('digitize')};
$('inspectDetail').onclick=()=>{selectTool('inspect');status('Click an eye, nose or other detail on the original to compare it close up. This does not change your selection.')};
$('zoomIn').onclick=()=>{zoom=Math.min(16,zoom*1.25);draw()};$('zoomOut').onclick=()=>{zoom=Math.max(.1,zoom/1.25);draw()};$('fit').onclick=()=>{zoom=1;panX=panY=0;draw()};
function textEntry(){return ['INPUT','SELECT','TEXTAREA','BUTTON','A','SUMMARY'].includes(document.activeElement.tagName)||document.activeElement.isContentEditable}
document.addEventListener('keydown',e=>{
 if(textEntry()||e.isComposing)return;
 if(e.code==='Space'){space=true;e.preventDefault()}
 if(e.key==='Escape'&&gesture?.tool==='box'){e.preventDefault();cancelGesture();status('Rectangle canceled. Your selection is unchanged.');return}
 if(outlineTool($('tool').value)){
  if(e.key==='Enter'){e.preventDefault();finishOutline()}
  if(e.key==='Escape'){e.preventDefault();discardOutline()}
  if(e.key==='Backspace'){e.preventDefault();outlineDraft.pop();draw()}
 }
});
document.addEventListener('keyup',e=>{if(e.code==='Space')space=false});
function cancelGesture(){
 if(gesture?.tool==='measure')window.DesignRuler?.cancel();
 if(gesture?.before){options=JSON.parse(gesture.before);history=gesture.history;redoHistory=gesture.redo;syncControls();updateHistory()}
 if(gesture?.draftBefore)outlineDraft=gesture.draftBefore;
 gesture=null;draftMoving=-1;brushCursor=null;draw();
}
window.addEventListener('blur',()=>{space=false;cancelGesture()});
canvases.forEach((canvas,i)=>{
 canvas.tabIndex=0;
 canvas.onwheel=e=>{
  e.preventDefault();const before=transform(canvas),rect=canvas.getBoundingClientRect();
  const x=(e.clientX-rect.left)*canvas.width/rect.width,y=(e.clientY-rect.top)*canvas.height/rect.height;
  const sourceX=(x-before.x)/before.s,sourceY=(y-before.y)/before.s;
  const delta=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?canvas.height:1);
  zoom=Math.max(.1,Math.min(16,zoom*Math.exp(-Math.max(-100,Math.min(100,delta))*.002)));
  const after=transform(canvas);
  panX+=(x-(sourceX*after.s+after.x))/canvas.width;
  panY+=(y-(sourceY*after.s+after.y))/canvas.height;draw();
 };
 canvas.onpointerdown=e=>{
  if(e.button!==0&&e.button!==1)return;
  let tool=space||e.button===1?'pan':$('tool').value==='measure'?'measure':i>0||currentView==='review'?'pan':e.altKey?'remove':e.shiftKey?'keep':$('tool').value;
  if(busy&&tool!=='pan')return;
  canvas.setPointerCapture(e.pointerId);e.preventDefault();canvas.focus({preventScroll:true});
  if(tool!=='pan'){const t=transform(canvas),r=canvas.getBoundingClientRect(),x=(e.clientX-r.left-t.x)/t.s,y=(e.clientY-r.top-t.y)/t.s;if(x<0||y<0||x>=width||y>=height){status('Start your edit inside the image.');return}}
  if(tool==='pan'){gesture={tool,x:e.clientX,y:e.clientY,panX,panY};return}
  if(tool==='measure'){window.DesignRuler?.start(point(e,canvas),transform(canvas).s);gesture={tool};draw();return}
  if(outlineTool(tool)){
   const draftBefore=outlineDraft.map(p=>p.slice());
   const p=point(e,canvas),t=transform(canvas);
   draftMoving=outlineDraft.findIndex(q=>Math.hypot(q[0]-p[0],q[1]-p[1])*t.s<10);
   if(draftMoving<0){if(outlineDraft.length>=10000){status('Outline point limit reached.');return}outlineDraft.push(p);draftMoving=outlineDraft.length-1}
   gesture={tool,draftBefore};draw();return;
  }
  if(tool==='inspect'){const p=point(e,canvas),r=20;focusDetail([Math.max(0,p[0]-r),Math.max(0,p[1]-r),Math.min(width,p[0]+r),Math.min(height,p[1]+r)]);return}
  // Auto select is a draft until pointer-up. A click must not overwrite a
  // working mask, invalidate playback, or leak a partial box into a request.
  if(tool==='box'){
   const p=point(e,canvas);
   gesture={tool,points:[p],rect:[...p,...p]};
   draw();return;
  }
  const before=JSON.stringify(options),priorHistory=history.slice(),priorRedo=redoHistory.slice();
  remember();options.interactions++;const p=point(e,canvas);
  if(tool==='split'){
    if(options.count>=(options.artwork_type==='portrait'?12:8)){status('Colour budget reached. Merge colours or turn off Preserve colour first.');return}
    const rgb=sampleCtx.getImageData(Math.floor(p[0]),Math.floor(p[1]),1,1).data;
    const hex='#'+[...rgb].slice(0,3).map(x=>x.toString(16).padStart(2,'0')).join('');
    if(!options.locks.includes(hex))options.locks.push(hex);options.count++;options.merges={};syncControls();schedule();return;
  }
  // Explicit selection corrections work for every mask type.
  gesture={tool,points:[p],before,history:priorHistory,redo:priorRedo};
  if(tool==='lasso'){options.selection='lasso';options.hints=[];options.outline=gesture.points}
  else{const stroke={kind:tool,points:gesture.points,radius:+$('radius').value,colour:options.ink_only?'#000000':$('paintColour').value};if(['keep','remove'].includes(tool))options.hints.push(stroke);else options.edits.push(stroke)}
  draw();
 };
 canvas.onpointermove=e=>{
  if(i===0)brushCursor=point(e,canvas);
  if(!gesture){draw();return}
  if(gesture.tool==='pan'){panX=gesture.panX+(e.clientX-gesture.x)/canvas.width;panY=gesture.panY+(e.clientY-gesture.y)/canvas.height;draw();return}
  const p=point(e,canvas);
  if(gesture.tool==='measure'){window.DesignRuler?.move(p);draw();return}
  if(outlineTool(gesture.tool)){if(draftMoving>=0)outlineDraft[draftMoving]=p;draw();return}
  gesture.points.push(p);
  if(gesture.tool==='box'){const a=gesture.points[0];gesture.rect=[Math.min(a[0],p[0]),Math.min(a[1],p[1]),Math.max(a[0],p[0]),Math.max(a[1],p[1])].map(Math.round)}
  draw();
 };
 canvas.onpointerup=()=>{
  if(gesture?.tool==='box'){
   const [x,y,r,b]=gesture.rect.map(Math.round);
   if(x>=r||y>=b){cancelGesture();status('Click and drag a rectangle around the subject. Your selection is unchanged.');return}
   if(busy){cancelGesture();status('Preview is updating. Your selection is unchanged; draw the rectangle again when it finishes.');return}
   remember();options.selection='grabcut';options.rect=[x,y,r,b];options.hints=[];options.interactions++;
   schedule();
  }
  else if(gesture?.tool==='measure')window.DesignRuler?.end();
  else if(gesture&&gesture.tool!=='pan'&&!outlineTool(gesture.tool))schedule();
  gesture=null;draftMoving=-1;draw();
 };
 canvas.onpointercancel=cancelGesture;
 canvas.onlostpointercapture=()=>{if(gesture)cancelGesture()};
 canvas.onpointerleave=()=>{if(!gesture){brushCursor=null;draw()}};
 canvas.addEventListener('auxclick',e=>{if(e.button===1)e.preventDefault()});
});
new ResizeObserver(draw).observe(document.querySelector('.panels'));
selectTool('box');setView('original');
original.onload=()=>{width=original.naturalWidth;height=original.naturalHeight;sample.width=width;sample.height=height;sampleCtx.drawImage(original,0,0);syncControls();if(config.previous){playback=config.previous;configurePlayback({simulation:config.simulation});$('stitchLink').href=workspaceStitches;$('stitchLink').hidden=false;$('stitchStatus').textContent=playback.stitch_count+' saved stitches · '+playback.trim_count+' trims. Actual written paths; sew-out still required.'}if(openStitches||playback)setView('stitched');draw();requestPreview()};

function updateHealth(){
 if(nativeMode)return; // Native checks have different, explicit coverage limits.
 const report=latest?.report,summary=$('healthSummary'),list=$('healthIssues');
 if(!summary)return;
 const key=JSON.stringify([report,playback?.stitch_count,playback?.trim_count]);
 if(summary.dataset.state===key)return;
 summary.dataset.state=key;
 list.replaceChildren();
 if(!report){summary.textContent='Design health · waiting for artwork';return}
 const styleNotices=(report.stitch_regions?.areas||[]).filter(a=>a.style_notice);
 const noticeCounts=new Map();
 for(const area of styleNotices){const key=area.colour+' · '+area.style_notice;noticeCounts.set(key,(noticeCounts.get(key)||0)+1)}
 for(const [message,count] of noticeCounts){const p=document.createElement('p');p.textContent=count+' area'+(count===1?'':'s')+' · '+message;list.append(p)}
 if(styleNotices.length)summary.closest('details').open=true;
 const blockers=report.generation_blockers||[];
 for(const detail of blockers){
  const p=document.createElement('p');p.textContent=`Cannot stitch ${detail.colour} detail: ${detail.width_mm} × ${detail.height_mm} mm. ${detail.reason}`;list.append(p);
  const locate=document.createElement('button');locate.type='button';locate.textContent='Show this detail';
  locate.onclick=()=>window.embroideryStudio.focusBounds(detail.bounds);list.append(locate);
 }
 const pendingCleanup=(report.cleanup_review||[]).filter(item=>item.decision==='pending');
 if(pendingCleanup.length){
  const p=document.createElement('p');p.textContent=`Cleanup proposes changing ${pendingCleanup.length} small areas. Keep them together or review each one.`;list.prepend(p);
  const review=document.createElement('button');review.type='button';review.textContent='Choose what to keep';
  review.onclick=()=>window.dispatchEvent(new Event('studio:cleanup-needed'));p.after(review);
 }
 if(blockers.length||pendingCleanup.length)summary.closest('details').open=true;
 const detailLoss=report.detail_loss?.findings?.length||0;
 const n=blockers.length+detailLoss+(report.below_floor_after||0)+(report.cleanup_review||[]).filter(item=>item.removed||item.decision==='pending').length;
 const lettering=window.letteringSizeMetrics;
 const cap=lettering?.capital_per_canvas_mm*report.height_mm;
 const letteringNotice=lettering?(Number.isFinite(cap)?'Lettering review · reference capitals about '+cap.toFixed(1)+' mm':'Lettering size needs review'):'';
 summary.textContent=(blockers.length?blockers.length+' selected details cannot be stitched yet':letteringNotice|| (n?'⚠ '+n+' detail warnings to review':'No tiny-area warnings'))+' · '+(playback?playback.stitch_count.toLocaleString()+' stitches · '+playback.trim_count+' trims':'Stitches need updating');
 if(lettering){
  const p=document.createElement('p');
  p.textContent='Typed words are using picture-based fills, not embroidery-font stitches. Canvas height is the whole design, not each letter. Review the width and letter estimate in Size & fabric or try embroidery fonts in Text. '+(n?n+' tiny details also need review.':'No tiny-area flags does not prove readable lettering.');
  list.append(p);
 }
 const note=document.createElement('p');note.textContent='A test sew-out is still required. These checks cover small areas—not density, tension, puckering or every machine limit.';list.append(note);
 for(const feature of report.small_features||[]){
  const button=document.createElement('button');
  button.textContent='Locate '+feature.colour+' region · '+feature.area_mm2.toFixed(3)+' mm²';
  button.onclick=()=>{
   selectedBounds=feature.bounds;
   const [x,y,r,b]=selectedBounds,c=canvases.find(c=>c.parentElement.style.display!=='none')||canvases[0];
   zoom=Math.min(16,Math.max(1,Math.min(width/Math.max(r-x,1),height/Math.max(b-y,1))*.35));
   const t=transform(c);panX=(width/2-(x+r)/2)*t.s/c.width;panY=(height/2-(y+b)/2)*t.s/c.height;draw();
  };list.append(button);
 }
 if((report.below_floor_after||0)>(report.small_features||[]).length){const p=document.createElement('p');p.textContent='Showing the first '+(report.small_features||[]).length+' remaining small-area warnings.';list.append(p)}
}
function buildColourStops(){
 const strip=$('colourStops');strip.replaceChildren();
 if(!playback)return;
 const blocks=[];let start=0;
 playback.steps.forEach((s,i)=>{if(s.t==='color_change'){blocks.push({start,end:i,colour:playback.steps[start]?.color});start=i+1}});
 blocks.push({start,end:playback.steps.length,colour:playback.steps[start]?.color});
 blocks.forEach((b,i)=>{const button=document.createElement('button');button.style.background=colourPreviewMap[b.colour]||b.colour;button.style.flexGrow=Math.max(1,b.end-b.start);button.title=(i&&b.colour===blocks[i-1].colour?'Machine stop · ':'')+'Thread '+(i+1)+' · '+(colourPreviewMap[b.colour]||b.colour);button.setAttribute('aria-label',button.title);
 button.onclick=()=>{cursor=b.start;running=false;$('run').textContent='▶ Play';setView('stitched');transport()};strip.append(button)});
}
$('redo').onclick=()=>restoreHistory(true);
document.querySelectorAll('[data-option]').forEach(el=>{el.addEventListener('change',()=>activeControl=null);el.addEventListener('blur',()=>activeControl=null)});
document.addEventListener('keydown',e=>{
 if(['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName))return;
 if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();$(e.shiftKey?'redo':'undo').click()}
 if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='y'){e.preventDefault();$('redo').click()}
});
updateHistory();


const sizePresets=[{label:'Left chest',axis:'width',mm:80},{label:'Cap front',axis:'height',mm:55},{label:'Sleeve',axis:'width',mm:60},{label:'Jacket back',axis:'width',mm:280}];
let sizeSetBusy=false;
$('generateSizes').onclick=async()=>{
 if(sizeSetBusy)return;
 if(!$('confirmed').checked){$('sizeStatus').textContent='Confirm your selected subject before generating size variants.';return}
 const sizes=[...document.querySelectorAll('.sizePreset:checked')].map(e=>sizePresets[+e.value]);
 if($('customSizeEnabled').checked)sizes.push({label:'Custom',axis:$('customAxis').value,mm:+$('customMm').value});
 if(!sizes.length){$('sizeStatus').textContent='Choose at least one size.';return}
 sizeSetBusy=true;$('generateSizes').disabled=true;$('sizeStatus').textContent='Regenerating '+sizes.length+' sizes from artwork. Larger designs may take longer; you can keep inspecting the canvas.';
 const snapshot=JSON.parse(JSON.stringify(options));
 try{
  const response=await fetch('/size-set/'+encodeURIComponent(config.name),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({options:snapshot,sizes,subject_confirmed:true})});
  const result=await response.json();if(!response.ok)throw new Error(result.error||'Size regeneration failed.');
  const table=document.createElement('table'),head=document.createElement('tr');
  for(const name of ['Placement','Written size mm','Stitches','Trims','Travel mm','Longest jump mm','Est. minutes','Thread path m','Below floor: before → after','Files']){
   const th=document.createElement('th');th.textContent=name;head.append(th)
  }table.append(head);
  for(const row of result.results){
   const tr=document.createElement('tr'),first=document.createElement('td');first.textContent=row.label+' · '+row.mm+' mm '+row.axis;
   if(row.preview){const img=document.createElement('img');img.src=row.preview;img.alt=row.label+' regenerated stitch preview';img.width=80;first.append(document.createElement('br'),img)}
   tr.append(first);
   if(row.status!=='generated'){const td=document.createElement('td');td.colSpan=9;td.textContent='Not generated: '+row.error+(row.remedy?' '+row.remedy:'');tr.append(td)}
   else{
    const a=row.audit;
    for(const value of [a.written_width_mm.toFixed(1)+' × '+a.written_height_mm.toFixed(1),a.stitch_count,a.trim_count,a.total_travel_mm.toFixed(1),a.longest_jump_mm.toFixed(1),(a.runtime_seconds/60).toFixed(1),(a.thread_length_mm/1000).toFixed(2),row.features_below_floor+' → '+row.features_remaining_below_floor]){
     const td=document.createElement('td');td.textContent=value;tr.append(td)
    }
    const td=document.createElement('td');
    for(const format of ['pes','dst']){const link=document.createElement('a');link.href=row[format];link.textContent=format.toUpperCase();link.style.marginRight='8px';td.append(link)}
    if(row.remedy){const p=document.createElement('p');p.textContent=row.remedy;td.append(p)}
    tr.append(td);
   }table.append(tr);
  }
  $('sizeTable').replaceChildren(table);$('sizeComparison').hidden=false;$('sizeComparison').open=true;
  $('sizeStatus').textContent=result.results.filter(r=>r.status==='generated').length+' of '+result.results.length+' sizes generated. Results belong to the settings snapshot when you clicked, not later edits.';
 }catch(e){$('sizeStatus').textContent=e.message}
 finally{sizeSetBusy=false;$('generateSizes').disabled=false}
};

window.embroideryStudio={
 nativeClear:()=>{
  if(!nativeMode)return;
  revision++;playback=null;running=false;cursor=0;stitchLayer.reset();stitchError='';
  $('exportPes').hidden=$('exportDst').hidden=$('stitchLink').hidden=true;
  $('colourStops').replaceChildren();transport();draw();
 },
 nativeAccept:async data=>{
  if(!nativeMode)throw Error('Not a native lettering workspace.');
  const version=++revision;
  await Promise.all([original,prepared,isolated].map(im=>new Promise((resolve,reject)=>{
   im.onload=()=>resolve();im.onerror=()=>reject(Error('Letter outlines could not be displayed. Retry Update stitches.'));
   im.src=data.image;
  })));
  if(version!==revision)return false;
  width=data.canvas_width_mm*10;height=data.canvas_height_mm*10;
  options.height_mm=data.canvas_height_mm;options.selection='full';
  latest=null;selectedBounds=null;colourPreviewImage=null;colourPreviewPlan=null;colourPreviewMap={};
  playback=data.playback;configurePlayback({simulation:location.href});
  $('stitchLink').href=location.pathname+'?view=stitched';$('stitchLink').hidden=false;
  $('designSize').textContent=data.result.reports.dst.width_mm+' mm wide × '+data.result.reports.dst.height_mm+' mm high · stitched text';
  $('stitchStatus').textContent='Actual DST needle paths · '+playback.stitch_count+' stitches · '+playback.trim_count+' cuts. Font outlines are kept separately; sew-out required.';
  $('routeBorder').textContent='Font-authored satin columns; no picture tracing or artwork cleanup.';
  window.dispatchEvent(new Event('studio:controls'));
  setView('stitched');$('fitStitches').onclick();return true;
 },
 selectTool,
 imageSize:()=>({width,height}),
 snapshot:()=>JSON.parse(JSON.stringify(options)),
 sampleColour:p=>{const d=sampleCtx.getImageData(Math.floor(p[0]),Math.floor(p[1]),1,1).data;return '#'+[...d].slice(0,3).map(x=>x.toString(16).padStart(2,'0')).join('')},
 showProposal:async result=>{const version=++proposalVersion;const images=await Promise.all([result.before_image,result.image].map(src=>new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('Proposal image unavailable; retry.'));im.src=src})));if(version!==proposalVersion)return;[proposalBefore,proposalAfter]=images;setView('proposal')},
 clearProposal:()=>{proposalVersion++;proposalBefore=proposalAfter=null;if(currentView==='proposal')setView('prepared')},
 navigationGesture:e=>space||e.button===1||gesture?.tool==='pan',
 focusBounds:bounds=>{focusDetail(bounds)},
 review:mode=>{if(playback){cursor=playback.steps.length;transport()}setView(mode)},
 redraw:()=>draw(),
 retrySurface:()=>{stitchLayer.retry();draw()},
 previewInfo:()=>({status:stitchLayer.status,frameMs:stitchLayer.surface?.lastFrameMs,builds:stitchLayer.surface?.builds}),
 focusReview:bounds=>{selectedBounds=bounds.slice();setView('review');const c=canvases[0],base=Math.min(c.width/width,c.height/height)*.92;zoom=Math.max(.5,Math.min(12,.75*Math.min(c.width/(Math.max(1,bounds[2]-bounds[0])*base),c.height/(Math.max(1,bounds[3]-bounds[1])*base))));panX=(width/2-(bounds[0]+bounds[2])/2)*base*zoom/c.width;panY=(height/2-(bounds[1]+bounds[3])/2)*base*zoom/c.height;if(playback)cursor=playback.steps.length;draw()},
 resultInfo,
 hasPlayback:()=>!!playback,pieceNotice:()=>pieceNotice,sewParts:()=>playback?.sew_parts||[],
 // Read-only view of the exported needle path for the 3D viewer.
 playbackView:()=>playback?{plan:playback,cursor,colourMap:colourPreviewMap,fabric:$('fabric').value,threadWidth:Number($('threadVisualWidth').value),lightAngle:Number($('lightAngle').value)}:null,
 seek,
 acceptRefinement:patch=>{if(nativeMode)throw Error('Picture recovery is not applied to embroidery letters.');if(busy)throw Error('Wait for preparation to finish.');remember();Object.assign(options,patch);options.interactions++;syncControls();schedule();clearTimeout(timer);$('confirmed').checked=true;requestPreview('digitize')},
 apply:patch=>{if(nativeMode)throw Error('Use the Text controls to edit embroidery letters. Picture edits cannot change this design.');if(busy)throw new Error('Wait for the current preparation to finish.');remember();Object.assign(options,patch);options.interactions++;syncControls();schedule();setView('prepared')},
 point:e=>point(e,canvases[0]),
 piecePoint:(e,canvas)=>{const r=canvas.getBoundingClientRect(),t=transform(canvas);return [(e.clientX-r.left-t.x)/t.s,(e.clientY-r.top-t.y)/t.s]},
 pieceEdit:async command=>{if(nativeMode)throw Error('Edit the embroidery font with Text; picture-piece transforms do not apply.');if(busy)throw Error('Wait for the current operation to finish.');clearTimeout(timer);const generate=['position','x_mm','y_mm','width_mm','height_mm','rotation','style','visible','outline','sew_order','align','distribute','match_size','mirror_copy','circle','array','weld','smooth','morph','auto_trace'].includes(command.field);if(generate&&!$('confirmed').checked)throw Error('Approve the selected subject before editing stitches.');return requestPreview(generate?'digitize':'save',command)},
 pieceReport:()=>latest?.report?.piece_layout,
 // Canvas guides (canvas-guides.js) are drawing aids: saved on their own route, with no new preview,
 // so the current stitch plan and machine files stay. False while busy: the caller retries afterwards.
 keepGuides:async guides=>{
  if(nativeMode||busy)return false;
  const response=await fetch('/api/guides/'+encodeURIComponent(config.name),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({guides})});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Guides not saved. Try again.');
  const accepted=JSON.parse(acceptedOptions);
  for(const kept of [options,accepted]){if(result.guides.length)kept.canvas_guides=result.guides;else delete kept.canvas_guides}
  acceptedOptions=JSON.stringify(accepted);pieceRevision=result.piece_revision;return true;
 },
 pieceView:()=>setView('prepared'),
 selectOriginal:()=>setView('original'),
 isBusy:()=>busy
};
if(!nativeMode)original.src=config.original;
})();
