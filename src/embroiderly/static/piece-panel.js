/* Saved values belong to preparation options; selection and disclosure are UI-only. */
(() => {
 'use strict';
 const studio=window.embroideryStudio,$=id=>document.getElementById(id);
 if(!studio||!$('topic-styles'))return;
 const workbench=document.querySelector('.workbench'),panel=$('topic-styles');
 const layers=document.createElement('aside');layers.className='piece-layers';layers.setAttribute('aria-label','Pieces');
 layers.innerHTML='<h2>Pieces</h2><p class="muted">Select a part. Ctrl/⌘-click to select several.</p><div id="pieceList"></div>';
 document.querySelector('.tools').after(layers);workbench.classList.add('with-pieces');
 const properties=document.createElement('section');properties.className='piece-properties';
 properties.innerHTML=`<div class="piece-header"><span id="pieceSwatch" class="piece-swatch"></span><label class="sr-only" for="pieceName">Piece name</label><input id="pieceName" maxlength="100" placeholder="Select a piece"><button id="pieceEye" type="button" title="Show or hide piece" aria-label="Show or hide piece"></button><button id="pieceLock" type="button" title="Lock piece" aria-label="Lock piece"></button></div>
 <div class="piece-modes"><button type="button" id="pieceSimple" aria-pressed="true">Simple</button><button type="button" id="pieceAdvanced" aria-pressed="false">Advanced</button></div>
 <p id="pieceSize"></p><p id="pieceAudit" role="status"></p>
 <fieldset id="pieceTransform"><legend>Transform</legend><div class="piece-fields">
 <label class="piece-advanced">X <span class="piece-unit"></span><input id="pieceX" inputmode="decimal" data-field="x_mm" title="Centre relative to hoop centre; positive X is right."></label>
 <label class="piece-advanced">Y <span class="piece-unit"></span><input id="pieceY" inputmode="decimal" data-field="y_mm" title="Centre relative to hoop centre; positive Y is down, like the canvas ruler."></label>
 <label>Width <span class="piece-unit"></span><input id="pieceW" inputmode="decimal" data-field="width_mm" title="Actual outline bounding-box width. Enter applies; Esc cancels."></label>
 <label>Height <span class="piece-unit"></span><input id="pieceH" inputmode="decimal" data-field="height_mm" title="Actual outline bounding-box height. Enter applies; Esc cancels."></label>
 </div><button id="pieceLink" type="button" aria-pressed="true">Keep proportions</button>
 <label class="piece-advanced">Rotation °<input id="pieceRotation" inputmode="decimal" data-field="rotation" title="Clockwise around the selected piece centre. A multi-selection rotates as a group."></label>
 <label class="piece-advanced">Skew °<input id="pieceSkew" inputmode="decimal" placeholder="0" title="Lean the piece sideways, −60 to 60. Enter applies."></label>
 <p id="pieceNodes" class="piece-advanced"></p>
 <div class="piece-arrange" role="group" aria-label="Arrange">
 <button type="button" data-arrange="mirror:x" title="Mirror left–right">⇋ Mirror</button><button type="button" data-arrange="mirror:y" title="Mirror top–bottom">⇅ Mirror</button>
 <button type="button" data-arrange="rotate_by:-15" title="Rotate 15° to the left">↺ 15°</button><button type="button" data-arrange="rotate_by:15" title="Rotate 15° to the right">↻ 15°</button><button type="button" data-arrange="rotate_by:45" title="Rotate 45° to the right">↻ 45°</button>
 <button type="button" id="pieceDuplicate" title="Copy the piece, 5 mm to the right and down">Duplicate</button><button type="button" id="pieceKnife" aria-pressed="false" title="Drag a line across the selected piece to cut it in two">✂ Knife</button><button type="button" id="piecePoints" aria-pressed="false" title="Drag an outline point to move it; click an edge to add a point; click a point and press Delete to remove it">◇ Points</button><button type="button" id="pieceSatinHere" aria-pressed="false" title="Drag a line where a thin part starts: that side becomes satin, the rest keeps its fill">〰 Satin here</button><button type="button" id="pieceWeld" title="Join the selected pieces of one thread into one piece. They must touch or overlap.">⊕ Weld</button><button type="button" id="pieceSmooth" title="Smooth the outline: removes jagged pixel steps, keeps sharp corners and the size">Smooth</button><select id="pieceSmoothStrength" aria-label="How much to smooth" title="How much to smooth"><option value="light">Light</option><option value="more">More</option></select><select id="pieceMorphKind" aria-label="Morph" title="Morph the outline around its centre"><option value="pinch">Pinch</option><option value="punch">Punch</option><option value="twirl">Twirl</option><option value="wave">Wave</option></select><label title="How strong the morph is, 10–100%">Strength %<input id="pieceMorphStrength" type="number" min="10" max="100" step="5" value="40"></label><button type="button" id="pieceMorph" title="Pinch draws the sides in, Punch bulges them out, Twirl turns the middle, Wave makes it rise and fall">Morph</button><button type="button" id="pieceDelete" hidden title="Delete this copy or part">Delete</button>
 </div>
 </fieldset>
 <fieldset id="pieceLineUp"><legend>Line up</legend><div class="piece-arrange" role="group" aria-label="Line up several pieces">
 <button type="button" data-lineup="align:left" title="Line up the left edges">⇤ Left</button><button type="button" data-lineup="align:centre" title="Line up the centres, left to right">Centre</button><button type="button" data-lineup="align:right" title="Line up the right edges">Right ⇥</button>
 <button type="button" data-lineup="align:top" title="Line up the top edges">⤒ Top</button><button type="button" data-lineup="align:middle" title="Line up the middles, top to bottom">Middle</button><button type="button" data-lineup="align:bottom" title="Line up the bottom edges">⤓ Bottom</button>
 <button type="button" data-lineup="distribute:across" title="Same gap between each piece, left to right. Pick 3 or more.">Space across</button><button type="button" data-lineup="distribute:down" title="Same gap between each piece, top to bottom. Pick 3 or more.">Space down</button>
 <button type="button" data-lineup="match_size:width" title="Make each piece as wide as the first one you picked, keeping its shape">Same width</button><button type="button" data-lineup="match_size:height" title="Make each piece as tall as the first one you picked, keeping its shape">Same height</button><button type="button" data-lineup="match_size:both" title="Give each piece the width and height of the first one you picked">Same size</button>
 </div></fieldset>
 <fieldset id="pieceOutline"><legend>Outline</legend><div class="piece-fields">
 <label>Stitch<select id="pieceOutlineStitch"><option value="">None</option><option value="running">Running</option><option value="triple">Triple</option><option value="satin">Satin</option></select></label>
 <label title="0 sews on the edge; more moves the outline outward">Gap mm<input id="pieceOutlineGap" type="number" min="0" max="6" step=".5" value="0"></label>
 <label class="piece-outline-satin">Satin width mm<input id="pieceOutlineWidth" type="number" min="1.2" max="5" step=".1" value="2"></label>
 <label>Thread<input id="pieceOutlineColour" type="color" value="#202020"></label></div></fieldset>
 <fieldset id="pieceSewOrder"><legend>Sewing order</legend><div class="piece-arrange" role="group" aria-label="Sewing order">
 <button type="button" data-sew="earlier" title="Sew the selected part one step sooner">↑ Sew earlier</button><button type="button" data-sew="later" title="Sew the selected part one step later">↓ Sew later</button>
 <button type="button" data-sew="picked" title="Sew the selected parts one after another, in the order you clicked them">Sew in the order I picked</button><button type="button" data-sew="auto" title="Let Needler choose the order again">Automatic order</button></div>
 <p id="pieceSewNote" class="muted"></p></fieldset>
 <fieldset id="pieceDraw"><legend>Draw a shape</legend><div class="piece-arrange" role="group" aria-label="Draw">
 <button type="button" data-draw="rectangle" aria-pressed="false" title="Drag from one corner to the opposite corner">▭ Rectangle</button><button type="button" data-draw="ellipse" aria-pressed="false" title="Drag from one corner to the opposite corner">◯ Ellipse</button>
 <button type="button" data-draw="polygon" aria-pressed="false" title="Click each corner; double-click, Enter or click the first point to finish. Esc cancels.">⬠ Polygon</button><button type="button" data-draw="freehand" aria-pressed="false" title="Hold and draw the outline; release to close it">✎ Freehand</button>
 <button type="button" data-draw="line" aria-pressed="false" title="Click each point of a stitched line; double-click or Enter to finish. Esc cancels.">〰 Line</button><button type="button" data-draw="freehand_line" aria-pressed="false" title="Hold and draw a stitched line">✎ Freehand line</button>
 <label title="Running: a fine single line. Triple: each stitch sewn three times, bold.">Line <select id="pieceLineStitch"><option value="running">Running</option><option value="triple">Triple</option></select></label>
 <button type="button" data-draw="fill" aria-pressed="false" title="Click an empty space closed by lines to fill it. The fill is sewn first, under the lines.">🪣 Click to fill</button>
 <label title="Leave the parts inside the space open; off fills under them too"><input id="pieceFillHoles" type="checkbox" checked> Keep holes</label>
 <label>Thread <input id="pieceDrawColour" type="color" value="#202020"></label></div></fieldset>
 <fieldset id="pieceTrace"><legend>Trace</legend><div class="piece-arrange" role="group" aria-label="Trace">
 <button type="button" data-draw="wand" aria-pressed="false" title="Click a colour in the artwork: the area of similar colour around it becomes a new piece">🪄 Magic wand</button>
 <label title="How different a colour may be and still be selected, 1–60">Tolerance<input id="pieceWandTolerance" type="number" min="1" max="60" step="1" value="12"></label>
 <select id="pieceTraceWhich" aria-label="What to trace"><option value="">Selected pieces</option><option value="all">All threads</option></select>
 <button type="button" id="pieceTrace" title="Turn the outlines into clean curves with sharp corners">Auto trace</button></div></fieldset>
 <div class="piece-modes"><button id="pieceMove" type="button" aria-pressed="true">Drag to move</button><button id="pieceRotate" type="button" aria-pressed="false">Drag to rotate</button></div>
 <label class="piece-advanced">Group / subgroup<input id="pieceGroup" maxlength="100" placeholder="For example: Head / Eyes"></label>
 <p id="pieceFeedback" role="status" aria-live="polite">Select a piece to edit its measurements.</p>
 <details class="piece-advanced"><summary>Stitch settings and limitations</summary><p>Stitches rebuild from the outline after a transform. Fill angle follows rotation. Density and underlay retain the existing style preset.</p><p>Individual row spacing, stitch length, staggers, underlay, pull compensation, entry/exit and tie-in/tie-off editors are not available here.</p></details>`;
 panel.insertBefore(properties,$('stitchStyles'));$('stitchStyles').querySelector('summary').textContent='Stitch type';
 $('stitchRegion').closest('label').hidden=true;$('regionStyleStatus').hidden=true;
 const total=document.createElement('output');total.id='pieceStitchTotal';total.textContent='0 total stitches';document.querySelector('.thread-info').append(total);
 let report={pieces:[]},sewn=[],custom=false,selected=new Set(),advanced=false,linked=true,active=false,pending=false,drag=null,rotate=false,knife=null,drawing=null;
 const icon=(kind)=>{const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.classList.add('ui-icon');const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',kind==='lock'?'M6 10h12v11H6zM8 10V6a4 4 0 0 1 8 0v4':kind==='unlock'?'M6 10h12v11H6zM8 10V6a4 4 0 0 1 8 0':kind==='eye'?'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Zm10-3a3 3 0 1 0 0 6 3 3 0 0 0 0-6':'M3 3l18 18M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z');svg.append(path);return svg};
 function targets(){return report.pieces.filter(p=>selected.has(p.id))}
 function aggregate(items=targets()){
  if(!items.length)return null;
  const left=Math.min(...items.map(p=>p.x_mm-p.width_mm/2)),right=Math.max(...items.map(p=>p.x_mm+p.width_mm/2)),top=Math.min(...items.map(p=>p.y_mm-p.height_mm/2)),bottom=Math.max(...items.map(p=>p.y_mm+p.height_mm/2));
  return {x_mm:(left+right)/2,y_mm:(top+bottom)/2,width_mm:right-left,height_mm:bottom-top,rotation:items.every(p=>p.rotation===items[0].rotation)?items[0].rotation:null};
 }
 function units(){return document.documentElement.dataset.units==='in'?'in':'mm'}
 function format(value,angle=false){return value===null?'—':(value/(units()==='in'&&!angle?25.4:1)).toFixed(units()==='in'&&!angle?3:1)}
 function feedback(message){$('pieceFeedback').textContent=message}
 async function commit(field,value,ids=[...selected]){
  if(pending||(!ids.length&&field!=='draw'&&field!=='click_fill'&&field!=='magic_wand'))return;
  pending=true;sync();feedback('Saving piece and rebuilding stitches when needed…');
  try{const ok=await studio.pieceEdit({ids,field,value,linked:advanced?linked:true});feedback(ok?(studio.hasPlayback()?(field==='sew_order'?'Saved. Stitches follow the new sewing order.':'Saved. Stitches use the updated outline.'):'Piece saved. No current stitch plan; review the design before generating.'):'Not applied. See the workspace message; the previous piece is unchanged.')}
  catch(error){feedback(error.message)}finally{pending=false;sync()}
 }
 function choose(ids,toggle=false){if(points)points.picked=null;if(!toggle)selected.clear();for(const id of ids){if(toggle&&selected.has(id))selected.delete(id);else selected.add(id)}studio.pieceView();document.querySelector('[data-topic="styles"]').click();sync();renderRows()}
 function sync(){
  const items=targets(),box=aggregate(items),locked=items.some(p=>p.locked),disabled=!box||locked||pending||studio.isBusy();
  properties.dataset.mode=advanced?'advanced':'simple';
  $('pieceSimple').setAttribute('aria-pressed',String(!advanced));$('pieceAdvanced').setAttribute('aria-pressed',String(advanced));
  $('pieceName').value=items.length===1?items[0].name:items.length?`${items.length} pieces`:'';
  $('pieceName').disabled=disabled||items.length!==1;
  $('pieceGroup').value=items.length&&items.every(p=>p.group===items[0].group)?items[0].group:'';$('pieceGroup').disabled=disabled;
  $('pieceSwatch').style.background=items.length===1?items[0].colour:'transparent';
  $('pieceEye').replaceChildren(icon(items.length&&items.every(p=>p.visible)?'eye':'hidden'));
  $('pieceEye').disabled=disabled;
  $('pieceLock').replaceChildren(icon(locked?'lock':'unlock'));$('pieceLock').disabled=!box||pending||studio.isBusy();$('pieceLock').setAttribute('aria-label',locked?'Unlock piece':'Lock piece');$('pieceLock').title=locked?'Unlock before editing':'Lock against manual and automatic changes';
  $('pieceSize').textContent=box?`Size ${format(box.width_mm)} × ${format(box.height_mm)} ${units()}`:'No piece selected';
  $('pieceNodes').textContent=items.length?`Nodes ${items.reduce((n,p)=>n+p.nodes,0)} · outline points`:'';
  $('pieceTransform').title=(window.hoopLabel||'Reference hoop '+(report.hoop_mm||[]).join(' × ')+' mm')+'. Positions are measured from the hoop centre.';
  $('pieceAudit').textContent=items.length?`${items.some(p=>p.audit.level==='red')?'RED — check size':items.some(p=>p.audit.level==='yellow')?'YELLOW — check thin span':'GREEN — area check'} · ${[...new Set(items.flatMap(p=>p.audit.messages))].join(' ')}`:'';
  $('pieceAudit').dataset.level=items.some(p=>p.audit.level==='red')?'red':items.some(p=>p.audit.level==='yellow')?'yellow':'green';
  properties.querySelectorAll('[data-arrange],#pieceDuplicate,#pieceDelete,#pieceSkew,#pieceKnife,#pieceSatinHere').forEach(control=>{control.disabled=disabled;});
  $('pieceWeld').disabled=disabled||items.length<2||items.some(p=>p.line);$('pieceSmooth').disabled=$('pieceSmoothStrength').disabled=disabled||items.some(p=>p.line);
  ['pieceMorph','pieceMorphKind','pieceMorphStrength'].forEach(id=>{$(id).disabled=disabled||items.some(p=>p.line)});
  const which=$('pieceTraceWhich').value;$('pieceTrace').disabled=pending||studio.isBusy()||!traceTargets().length||(!which&&disabled);
  $('pieceKnife').disabled=$('pieceSatinHere').disabled=disabled||items.length!==1||items.some(p=>p.line);
  $('piecePoints').disabled=disabled||items.length!==1;
  properties.querySelectorAll('[data-lineup]').forEach(b=>{b.disabled=disabled||items.length<(b.dataset.lineup.startsWith('distribute')?3:2)});
  const outline=items.length&&items.every(p=>JSON.stringify(p.outline)===JSON.stringify(items[0].outline))?items[0].outline:null;
  if(!properties.contains(document.activeElement)||!document.activeElement.id.startsWith('pieceOutline')){
   $('pieceOutlineStitch').value=outline?.stitch||'';if(outline){$('pieceOutlineGap').value=outline.offset_mm;$('pieceOutlineWidth').value=outline.width_mm;$('pieceOutlineColour').value=outline.colour}}
  $('pieceOutline').querySelectorAll('select,input').forEach(c=>{c.disabled=disabled||items.some(p=>p.line)});
  $('pieceOutline').querySelector('.piece-outline-satin').hidden=$('pieceOutlineStitch').value!=='satin';
  $('pieceDelete').hidden=!items.length||!items.every(p=>p.copy);
 $('pieceRepeat').disabled=disabled;
  properties.querySelectorAll('[data-field]').forEach(input=>{input.setAttribute('aria-describedby','pieceFeedback');input.disabled=disabled;input.value=box?format(box[input.dataset.field],input.dataset.field==='rotation'):'';input.removeAttribute('aria-invalid')});
  properties.querySelectorAll('.piece-unit').forEach(node=>node.textContent=units());
  $('pieceLink').disabled=disabled||!advanced;$('pieceLink').setAttribute('aria-pressed',String(!advanced||linked));
  $('pieceMove').disabled=$('pieceRotate').disabled=disabled;
  const sewBlocked=!items.length||pending||studio.isBusy()||!sewn.length;
  properties.querySelectorAll('[data-sew]').forEach(b=>{b.disabled=sewBlocked});
  properties.querySelector('[data-sew="picked"]').disabled=sewBlocked||items.length<2;properties.querySelector('[data-sew="auto"]').disabled=!custom||pending||studio.isBusy();
  $('pieceSewNote').textContent=!sewn.length?'Generate the stitches to change the sewing order.':items.length===1&&sewn.includes(items[0].id)?`Sewn ${sewn.indexOf(items[0].id)+1} of ${sewn.length}.`:custom?'Your own sewing order.':'Automatic sewing order.';
  properties.querySelectorAll('[data-draw],#pieceDrawColour,#pieceFillHoles,#pieceLineStitch,#pieceWandTolerance,#pieceTraceWhich').forEach(control=>{control.disabled=pending||studio.isBusy()||!report.pieces.length;});
  properties.querySelectorAll('[data-draw]').forEach(b=>b.setAttribute('aria-pressed',String(drawing?.shape===b.dataset.draw)));
  window.stitchRegionSelection=active&&items.length?{rings:items.flatMap(p=>p.rings)}:null;
  const target=$('stitchRegion');target.value=items.length===1?items[0].id:'';target.dispatchEvent(new Event('change'));
  studio.redraw();
 }
 function groupActions(items,label){
  const actions=document.createElement('div');actions.className='piece-group-actions';
  const select=document.createElement('button');select.type='button';select.textContent='Select group';select.onclick=()=>choose(items.map(p=>p.id));
  const eye=document.createElement('button');eye.type='button';eye.replaceChildren(icon(items.some(p=>p.visible)?'eye':'hidden'));eye.setAttribute('aria-label','Show or hide '+label);eye.disabled=pending||items.some(p=>p.locked);eye.onclick=()=>commit('visible',!items.some(p=>p.visible),items.map(p=>p.id));
  actions.append(select,eye);return actions;
 }
 function traceChoices(){
  const list=$('pieceTraceWhich'),was=list.value,threads=[...new Set(report.pieces.filter(p=>!p.line).map(p=>p.colour))];
  list.replaceChildren(new Option('Selected pieces',''),new Option('All threads','all'),...threads.map(c=>new Option(report.pieces.find(p=>p.colour===c).thread_name||c,c)));
  list.value=[...list.options].some(o=>o.value===was)?was:'';
 }
 function renderRows(){
  const list=$('pieceList'),open=new Set([...list.querySelectorAll('details[open]')].map(d=>d.dataset.group));list.replaceChildren();
  if(!report.pieces.length){const p=document.createElement('p');p.textContent=report.unavailable||'Prepare a colour artwork to see its pieces.';list.append(p);return}
  const groups=new Map();
  for(const p of report.pieces){const fallback=p.y_mm< -report.origin_mm[1]/3?'Upper parts':p.y_mm>report.origin_mm[1]/3?'Lower parts':'Middle parts';const group=p.group||fallback;if(!groups.has(group))groups.set(group,[]);groups.get(group).push(p)}
  const containers=new Map();
  for(const [group,items] of groups){
   let parent=list,path='';
   for(const token of group.split('/').map(s=>s.trim()).filter(Boolean)){
    path+=(path?'/':'')+token;
    if(!containers.has(path)){const d=document.createElement('details');d.dataset.group=path;d.open=open.has(path);const summary=document.createElement('summary');summary.textContent=token;d.append(summary);parent.append(d);containers.set(path,d)}parent=containers.get(path);
   }
   parent.append(groupActions(items,group));
   for(const p of items){const row=document.createElement('div');row.className='piece-row';row.dataset.id=p.id;const select=document.createElement('button');select.type='button';select.className='piece-select';select.setAttribute('aria-pressed',String(selected.has(p.id)));select.title=p.name;const order=document.createElement('span');order.textContent=sewn.includes(p.id)?sewn.indexOf(p.id)+1:p.order;order.className='piece-order';const thumb=document.createElementNS('http://www.w3.org/2000/svg','svg');thumb.setAttribute('viewBox',`${p.x_mm-p.width_mm/2} ${p.y_mm-p.height_mm/2} ${Math.max(p.width_mm,.1)} ${Math.max(p.height_mm,.1)}`);thumb.setAttribute('aria-hidden','true');const path=document.createElementNS(thumb.namespaceURI,'path');path.setAttribute('d',p.rings_mm.map(r=>'M '+r.map(x=>x.join(',')).join(' L ')+(p.line?'':' Z')).join(' '));if(p.line){path.setAttribute('fill','none');path.setAttribute('stroke',p.colour);path.setAttribute('stroke-width',String(Math.max(p.width_mm,p.height_mm)/12))}else path.setAttribute('fill',p.colour);path.setAttribute('fill-rule','evenodd');thumb.append(path);const name=document.createElement('span');name.className='piece-label';name.textContent=p.name;select.append(order,thumb,name);select.onclick=e=>choose([p.id],e.ctrlKey||e.metaKey);const swatch=document.createElement('span');swatch.className='piece-swatch';swatch.style.background=p.colour;swatch.title=(p.thread_name||p.colour)+' · '+p.colour;swatch.setAttribute('aria-label','Thread '+(p.thread_name||p.colour));const eye=document.createElement('button');eye.type='button';eye.replaceChildren(icon(p.visible?'eye':'hidden'));eye.setAttribute('aria-label',(p.visible?'Hide ':'Show ')+p.name);eye.disabled=pending||p.locked;eye.onclick=()=>commit('visible',!p.visible,[p.id]);row.append(select,swatch,eye);parent.append(row)}
  }
  for(const [path,container] of containers){
   if(container.querySelector(':scope > .piece-group-actions'))continue;
   const items=report.pieces.filter(p=>p.group.split('/').map(s=>s.trim()).filter(Boolean).join('/').startsWith(path+'/'));
   if(items.length)container.insertBefore(groupActions(items,path),container.children[1]);
  }
 }
 properties.querySelectorAll('[data-field]').forEach(input=>input.addEventListener('keydown',e=>{
  if(e.isComposing)return;
  if(e.key==='Escape'){e.preventDefault();sync();return}
  if(e.key==='ArrowUp'||e.key==='ArrowDown'){e.preventDefault();const sign=e.key==='ArrowUp'?1:-1;const increment=(e.shiftKey?1:.1)/(units()==='in'&&input.dataset.field!=='rotation'?25.4:1);const current=Number(input.value);if(Number.isFinite(current))input.value=(current+sign*increment).toFixed(units()==='in'?4:1);return}
  if(e.key==='Enter'){e.preventDefault();const raw=input.value.trim(),value=Number(raw)*(units()==='in'&&input.dataset.field!=='rotation'?25.4:1);if(!raw||!Number.isFinite(value)){sync();input.setAttribute('aria-invalid','true');feedback('Enter a valid number. The previous value was restored.');return}commit(input.dataset.field,value)}
 }));
 for(const [id,field] of [['pieceName','name'],['pieceGroup','group']])$(id).addEventListener('keydown',e=>{if(e.isComposing)return;if(e.key==='Escape'){e.preventDefault();sync()}if(e.key==='Enter'){e.preventDefault();commit(field,e.target.value.trim())}});
 properties.querySelectorAll('[data-arrange]').forEach(button=>button.onclick=()=>{
  const [field,value]=button.dataset.arrange.split(':');commit(field,field==='mirror'?value:Number(value));});
 // Line up: the selection is kept in click order, so the first piece picked sets the size.
 properties.querySelectorAll('[data-lineup]').forEach(button=>button.onclick=()=>commit(...button.dataset.lineup.split(':')));
 $('pieceDuplicate').onclick=()=>commit('duplicate',[5,5]);
 // Weld: the pieces in the order picked (the first keeps its style); Smooth: each selected outline.
 $('pieceWeld').onclick=()=>commit('weld',null);
 $('pieceSmooth').onclick=()=>commit('smooth',$('pieceSmoothStrength').value);
 $('pieceMorph').onclick=()=>commit('morph',{kind:$('pieceMorphKind').value,strength:Number($('pieceMorphStrength').value)});
 // Auto trace: the selected pieces, every filled piece, or one thread's pieces (locked and hidden ones stay).
 function traceTargets(){const which=$('pieceTraceWhich').value;return which?report.pieces.filter(p=>!p.line&&!p.locked&&p.visible&&(which==='all'||p.colour===which)):targets()}
 $('pieceTraceWhich').onchange=()=>sync();
 $('pieceTrace').onclick=()=>commit('auto_trace',null,traceTargets().map(p=>p.id));
 // Sewing order by hand: send every part in its new place; the first selected part decides the spot.
 properties.querySelectorAll('[data-sew]').forEach(button=>button.onclick=()=>{
  if(button.dataset.sew==='auto'){commit('sew_order',null,report.pieces.map(p=>p.id));return}
  const order=[...new Set(sewn)].filter(id=>report.pieces.some(p=>p.id===id));
  for(const p of report.pieces)if(!order.includes(p.id))order.push(p.id);
  const ids=[...selected];
  if(button.dataset.sew==='picked'){const at=Math.min(...ids.map(id=>order.indexOf(id))),rest=order.filter(id=>!selected.has(id));rest.splice(at,0,...ids);commit('sew_order',rest);return}
  const step=button.dataset.sew==='earlier'?-1:1;
  for(let i=step<0?1:order.length-2;step<0?i<order.length:i>=0;i-=step)
   if(selected.has(order[i])&&!selected.has(order[i+step])&&order[i+step]!==undefined)[order[i],order[i+step]]=[order[i+step],order[i]];
  commit('sew_order',order);
 });
 // Outline per part: any change applies to the selected parts; None removes it.
 const outlineSpec=()=>$('pieceOutlineStitch').value?{stitch:$('pieceOutlineStitch').value,offset_mm:Number($('pieceOutlineGap').value)||0,
  width_mm:Number($('pieceOutlineWidth').value)||2,colour:$('pieceOutlineColour').value}:null;
 for(const id of ['pieceOutlineStitch','pieceOutlineGap','pieceOutlineWidth','pieceOutlineColour'])
  $(id).addEventListener('change',()=>{if(targets().length)commit('outline',outlineSpec())});
 $('pieceDelete').onclick=()=>commit('delete',true);
 $('pieceSkew').addEventListener('keydown',e=>{if(e.key!=='Enter')return;e.preventDefault();
  const v=Number($('pieceSkew').value);if(Number.isFinite(v)&&v){commit('skew',v);$('pieceSkew').value='';}});
 $('pieceEye').onclick=()=>commit('visible',!targets().every(p=>p.visible));$('pieceLock').onclick=()=>commit('locked',!targets().some(p=>p.locked));
 $('pieceLink').onclick=()=>{linked=!linked;sync()};$('pieceSimple').onclick=()=>{advanced=false;sync()};$('pieceAdvanced').onclick=()=>{advanced=true;sync()};
 $('pieceMove').onclick=()=>{rotate=false;$('pieceMove').setAttribute('aria-pressed','true');$('pieceRotate').setAttribute('aria-pressed','false')};$('pieceRotate').onclick=()=>{rotate=true;$('pieceMove').setAttribute('aria-pressed','false');$('pieceRotate').setAttribute('aria-pressed','true')};
 // Repeat: a mirrored copy touching the selection, copies around a circle, or rows and columns (piece_patterns.py).
 const repeatSet=document.createElement('fieldset');repeatSet.id='pieceRepeat';
 repeatSet.innerHTML=`<legend>Repeat</legend><div class="piece-arrange" role="group" aria-label="Mirror copy">
 <button type="button" data-repeat="x" title="Add a mirrored copy on the right, touching this one">⇋ Mirror copy</button><button type="button" data-repeat="y" title="Add a mirrored copy below, touching this one">⇅ Mirror copy</button></div>
 <div class="piece-repeat-row" role="group" aria-label="Circle"><label title="How many around the circle, this one included">Around<input id="pieceCircleCount" type="number" min="2" max="36" step="1" value="6"></label><label title="From the circle's centre to this piece">Radius mm<input id="pieceCircleRadius" type="number" min="1" max="500" step="1" value="30"></label><label class="piece-repeat-check" title="Turn each copy to follow the circle, like a wreath"><input id="pieceCircleTurn" type="checkbox" checked> Turn</label><button type="button" id="pieceCircle" title="Place copies around a circle; this piece stays at the top">◌ Circle</button></div>
 <div class="piece-repeat-row" role="group" aria-label="Array"><label title="Rows going down">Rows<input id="pieceArrayRows" type="number" min="1" max="20" step="1" value="2"></label><label title="Columns going right">Columns<input id="pieceArrayColumns" type="number" min="1" max="20" step="1" value="2"></label><label title="Space between the copies">Gap mm<input id="pieceArrayGap" type="number" min="0" max="100" step=".5" value="2"></label><button type="button" id="pieceArray" title="Make rows and columns of copies; this piece stays at the top left">▦ Array</button></div>`;
 $('pieceTransform').after(repeatSet);
 repeatSet.querySelectorAll('[data-repeat]').forEach(b=>b.onclick=()=>commit('mirror_copy',b.dataset.repeat));
 const whole=id=>Math.round(Number($(id).value)),measure=id=>Number($(id).value);
 $('pieceCircle').onclick=()=>commit('circle',{count:whole('pieceCircleCount'),radius_mm:measure('pieceCircleRadius'),turn:$('pieceCircleTurn').checked});
 $('pieceArray').onclick=()=>commit('array',{rows:whole('pieceArrayRows'),columns:whole('pieceArrayColumns'),gap_mm:measure('pieceArrayGap')});
 const canvas=$('prepared');
 // Knife: drag a straight line across the one selected piece; release cuts it.
 // Satin here: the same drag; the narrow side becomes satin over the rest's fill.
 const knifeOn=(on,satin=false)=>{knife=on?{satin}:null;if(on&&points)pointsOn(false);$('pieceKnife').setAttribute('aria-pressed',String(on&&!satin));$('pieceSatinHere').setAttribute('aria-pressed',String(on&&satin));if(on)feedback(satin?'Drag a line across the piece where the thin part starts.':'Drag a line across the piece to cut it.');};
 $('pieceKnife').onclick=()=>knifeOn(!knife||knife.satin);
 $('pieceSatinHere').onclick=()=>knifeOn(!knife||!knife.satin,true);
 const toMm=([x,y])=>[x*report.scale-report.origin_mm[0],y*report.scale-report.origin_mm[1]];
 canvas.addEventListener('pointerdown',e=>{
  if(!knife||!active||e.button!==0||pending||studio.isBusy())return;
  if(targets().length!==1){feedback('Select one piece to cut.');return}
  e.stopImmediatePropagation();e.preventDefault();knife.from=studio.piecePoint(e,canvas);canvas.setPointerCapture(e.pointerId);
 },true);
 canvas.addEventListener('pointermove',e=>{
  if(!knife||!knife.from)return;e.stopImmediatePropagation();knife.to=studio.piecePoint(e,canvas);
  window.stitchRegionSelection={rings:[[knife.from,knife.to,knife.from]]};studio.redraw();
 },true);
 canvas.addEventListener('pointerup',e=>{
  if(!knife||!knife.from)return;e.stopImmediatePropagation();
  const line=[knife.from,knife.to||knife.from].map(toMm),field=knife.satin?'split_satin':'knife';knifeOn(false);
  if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);
  commit(field,line);
 },true);
 // Points (node reshaping): drag an outline point of the one selected piece, click an edge to add a point
 // there (and drag it), or click a point and press Delete to remove it. Release saves; the stitches rebuild.
 let points=null,zoom=1;
 const pointsOn=on=>{points=on?{rings:null,picked:null}:null;$('piecePoints').setAttribute('aria-pressed',String(!!on));if(on){knifeOn(false);feedback($('piecePoints').title+'.')}studio.redraw()};
 $('piecePoints').onclick=()=>pointsOn(!points);
 const reshape=rings=>{const p=targets()[0];points.rings=points.picked=null;commit('reshape',rings.map(r=>r.map(toMm)),[p.id])};
 canvas.addEventListener('pointerdown',e=>{
  if(!points||!active||e.button!==0||pending||studio.isBusy())return;
  const items=targets();if(items.length!==1)return;const p=items[0];
  const at=studio.piecePoint(e,canvas),reach=8/zoom,rings=p.rings.map(r=>r.map(q=>[...q]));
  let hit=null,best=reach;
  rings.forEach((r,i)=>r.forEach((q,j)=>{const d=Math.hypot(q[0]-at[0],q[1]-at[1]);if(d<best){best=d;hit=[i,j]}}));
  if(!hit){
   // The nearest edge within reach gets a new point where it was clicked.
   let edge=null;best=reach;
   rings.forEach((r,i)=>{for(let j=0;j<(p.line?r.length-1:r.length);j++){const a=r[j],b=r[(j+1)%r.length],dx=b[0]-a[0],dy=b[1]-a[1];
    const t=Math.max(0,Math.min(1,((at[0]-a[0])*dx+(at[1]-a[1])*dy)/(dx*dx+dy*dy||1))),q=[a[0]+t*dx,a[1]+t*dy],d=Math.hypot(q[0]-at[0],q[1]-at[1]);if(d<best){best=d;edge=[i,j+1,q]}}});
   if(!edge){if(points.picked){points.picked=null;studio.redraw()}return}
   rings[edge[0]].splice(edge[1],0,edge[2]);hit=[edge[0],edge[1]];points.added=true;
  }
  e.stopImmediatePropagation();e.preventDefault();
  if(p.locked){feedback('This piece is locked. Unlock it before changing it.');return}
  Object.assign(points,{rings,drag:hit,picked:hit,moved:false});canvas.setPointerCapture(e.pointerId);
  window.stitchRegionSelection={rings};studio.redraw();
 },true);
 canvas.addEventListener('pointermove',e=>{
  if(!points?.drag)return;e.stopImmediatePropagation();
  const at=studio.piecePoint(e,canvas),[i,j]=points.drag;points.rings[i][j]=window.snapPoint?window.snapPoint(at):at;points.moved=true;studio.redraw();
 },true);
 canvas.addEventListener('pointerup',e=>{
  if(!points?.drag)return;e.stopImmediatePropagation();
  if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);
  const changed=points.moved||points.added;points.drag=null;points.added=false;
  if(changed)reshape(points.rings);else studio.redraw();
 },true);
 document.addEventListener('keydown',e=>{
  if(!points?.picked||!active||e.isComposing||(e.key!=='Delete'&&e.key!=='Backspace')||e.target.closest?.('input,select,textarea'))return;
  const p=targets()[0];if(!p||pending)return;e.preventDefault();
  const [i,j]=points.picked,rings=p.rings.map(r=>r.map(q=>[...q]));
  if(rings[i].length<=(p.line?2:3)){feedback(p.line?'A line needs at least two points.':'An outline needs at least three points.');return}
  rings[i].splice(j,1);reshape(rings);
 });
 // Draw a shape: rectangle / ellipse by dragging corners, freehand by dragging, polygon by clicking corners.
 const drawOn=shape=>{drawing=shape&&drawing?.shape!==shape?{shape,points:[]}:null;if(drawing){knifeOn(false);studio.pieceView();feedback(properties.querySelector(`[data-draw="${shape}"]`).title+'.')}window.stitchRegionSelection=null;sync()};
 properties.querySelectorAll('[data-draw]').forEach(b=>b.onclick=()=>drawOn(b.dataset.draw));
 const outline=(points,hover)=>{
  const all=hover?[...points,hover]:points;if(all.length<2)return all;
  if(drawing.shape!=='rectangle'&&drawing.shape!=='ellipse')return all;
  const [a,b]=[all[0],all[all.length-1]],x0=Math.min(a[0],b[0]),x1=Math.max(a[0],b[0]),y0=Math.min(a[1],b[1]),y1=Math.max(a[1],b[1]);
  if(drawing.shape==='rectangle')return [[x0,y0],[x1,y0],[x1,y1],[x0,y1]];
  return Array.from({length:48},(_,i)=>[(x0+x1)/2+(x1-x0)/2*Math.cos(i*Math.PI/24),(y0+y1)/2+(y1-y0)/2*Math.sin(i*Math.PI/24)]);
 };
 const isLine=()=>drawing&&(drawing.shape==='line'||drawing.shape==='freehand_line');
 // Snap (canvas-guides.js): corners and points go to guides, the hoop centre lines and the grid; freehand and Click to fill stay free.
 const snapped=at=>window.snapPoint&&!drawing.shape.startsWith('freehand')&&drawing.shape!=='fill'&&drawing.shape!=='wand'?window.snapPoint(at):at;
 const showDrawing=hover=>{const ring=outline(drawing.points,hover);window.stitchRegionSelection=ring.length>1?{rings:[isLine()?[...ring,...ring.slice(0,-1).reverse()]:[...ring,ring[0]]]}:null;studio.redraw()};
 const finishDrawing=()=>{
  const {shape,points}=drawing,colour=$('pieceDrawColour').value;drawing=null;window.stitchRegionSelection=null;
  const corners=shape==='rectangle'||shape==='ellipse'?[points[0],points[points.length-1]]:points;
  if(corners.length<(shape==='polygon'||shape==='freehand'?3:2)){feedback('Shape not drawn. Choose a shape and try again.');sync();return}
  commit('draw',{shape,points:corners.map(toMm),colour,...(shape==='line'||shape==='freehand_line'?{stitch:$('pieceLineStitch').value}:{})});
 };
 canvas.addEventListener('pointerdown',e=>{
  if(!drawing||!active||e.button!==0||pending||studio.isBusy())return;
  e.stopImmediatePropagation();e.preventDefault();const at=snapped(studio.piecePoint(e,canvas));
  if(drawing.shape==='fill'){
   drawing=null;sync();commit('click_fill',{point:toMm(at),colour:$('pieceDrawColour').value,holes:$('pieceFillHoles').checked});return;
  }
  if(drawing.shape==='wand'){
   drawing=null;sync();commit('magic_wand',{point:toMm(at),tolerance:Math.round(Number($('pieceWandTolerance').value))});return;
  }
  if(drawing.shape==='line'){drawing.points.push(at);showDrawing();return}
  if(drawing.shape==='polygon'){
   const first=drawing.points[0],near=first&&Math.hypot(at[0]-first[0],at[1]-first[1])*report.scale<1.5;
   if(near&&drawing.points.length>=3){finishDrawing();return}
   drawing.points.push(at);showDrawing();return;
  }
  drawing.points=[at];drawing.down=true;canvas.setPointerCapture(e.pointerId);
 },true);
 canvas.addEventListener('pointermove',e=>{
  if(!drawing)return;const at=snapped(studio.piecePoint(e,canvas));
  if(drawing.shape==='polygon'||drawing.shape==='line'){if(drawing.points.length)showDrawing(at);return}
  if(!drawing.down)return;e.stopImmediatePropagation();
  const last=drawing.points[drawing.points.length-1];
  if(drawing.shape==='freehand'||drawing.shape==='freehand_line'){if(Math.hypot(at[0]-last[0],at[1]-last[1])*report.scale>=.5&&drawing.points.length<1990)drawing.points.push(at);showDrawing()}
  else{drawing.points=[drawing.points[0],at];showDrawing()}
 },true);
 canvas.addEventListener('pointerup',e=>{
  if(!drawing||!drawing.down)return;e.stopImmediatePropagation();drawing.down=false;
  if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);finishDrawing();
 },true);
 canvas.addEventListener('dblclick',e=>{if(drawing?.shape==='polygon'||drawing?.shape==='line'){e.stopImmediatePropagation();e.preventDefault();drawing.points=drawing.points.filter((p,i,a)=>!i||Math.hypot(p[0]-a[i-1][0],p[1]-a[i-1][1])>0);finishDrawing()}},true);
 document.addEventListener('keydown',e=>{
  if(!drawing||e.isComposing)return;
  if(e.key==='Escape'){e.preventDefault();drawOn(null);feedback('Drawing cancelled.')}
  else if(e.key==='Enter'&&(drawing.shape==='polygon'||drawing.shape==='line')){e.preventDefault();finishDrawing()}
 });
 canvas.addEventListener('pointerdown',e=>{
  if(!active||$('tool').value==='measure'||studio.navigationGesture(e)||e.button!==0||pending||studio.isBusy())return;
  e.stopImmediatePropagation();const at=studio.piecePoint(e,canvas),context=canvas.getContext('2d');
  const hit=[...report.pieces].reverse().find(p=>{if(!p.visible)return false;const path=new Path2D();for(const r of p.rings){r.forEach(([x,y],i)=>i?path.lineTo(x,y):path.moveTo(x,y));if(!p.line)path.closePath()}
   if(p.line){context.save();context.lineWidth=1.5/report.scale;const on=context.isPointInStroke(path,...at);context.restore();return on}return context.isPointInPath(path,...at,'evenodd')});
  if(!hit)return;if(!selected.has(hit.id)||e.ctrlKey||e.metaKey)choose([hit.id],e.ctrlKey||e.metaKey);
  if(targets().some(p=>p.locked)){feedback('This piece is locked. Unlock it before dragging.');return}
  drag={at,box:aggregate(),items:targets(),pointer:e.pointerId};canvas.setPointerCapture(e.pointerId);e.preventDefault();
 },true);
 canvas.addEventListener('pointermove',e=>{
  if(!drag)return;e.stopImmediatePropagation();const at=studio.piecePoint(e,canvas);let dx=(at[0]-drag.at[0])*report.scale,dy=(at[1]-drag.at[1])*report.scale;
  if(!rotate&&window.snapMove)[dx,dy]=window.snapMove(drag.box,dx,dy);
  if(rotate){const cx=(drag.box.x_mm+report.origin_mm[0])/report.scale,cy=(drag.box.y_mm+report.origin_mm[1])/report.scale;drag.angle=(Math.atan2(at[1]-cy,at[0]-cx)-Math.atan2(drag.at[1]-cy,drag.at[0]-cx))*180/Math.PI;$('pieceRotation').value=format((drag.box.rotation||0)+drag.angle,true)}
  else{$('pieceX').value=format(drag.box.x_mm+dx);$('pieceY').value=format(drag.box.y_mm+dy);drag.position=[drag.box.x_mm+dx,drag.box.y_mm+dy];window.stitchRegionSelection={rings:drag.items.flatMap(p=>p.rings.map(r=>r.map(([x,y])=>[x+dx/report.scale,y+dy/report.scale])))}}studio.redraw();
 },true);
 canvas.addEventListener('pointerup',e=>{if(!drag)return;e.stopImmediatePropagation();const done=drag;drag=null;if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);if(rotate&&done.angle)commit('rotation',(done.items.length===1?done.box.rotation:0)+done.angle);else if(done.position)commit('position',done.position);else sync()},true);
 const cancel=()=>{if(drag){drag=null;sync()}};canvas.addEventListener('pointercancel',cancel,true);canvas.addEventListener('lostpointercapture',cancel,true);
 window.addEventListener('studio:preview',e=>{total.textContent=Number(e.detail.stitchCount||0).toLocaleString()+' total stitches';report=e.detail.report.piece_layout||{pieces:[]};sewn=e.detail.sewParts||[];custom=Array.isArray(e.detail.options.sew_sequence)&&e.detail.options.sew_sequence.length>0;selected=new Set([...selected].filter(id=>report.pieces.some(p=>p.id===id)));traceChoices();renderRows();sync()});
 window.addEventListener('studio:topic',e=>{active=e.detail==='styles';sync()});
 window.addEventListener('studio:controls',()=>{if(!drag)sync()});
 new MutationObserver(()=>sync()).observe(document.documentElement,{attributes:true,attributeFilter:['data-units']});
 window.PiecePanel={targets,commit,paint:(context,scale)=>{
  if(!report.pieces.length||$('middleView').value==='isolated')return;
  if(report.transformed){
   context.save();context.setTransform(1,0,0,1,0,0);context.clearRect(0,0,context.canvas.width,context.canvas.height);context.restore();
   // Filled spaces are sewn first (under the lines): paint them first too.
   for(const p of [...report.pieces].sort((a,b)=>(b.under?1:0)-(a.under?1:0))){if(!p.visible)continue;context.beginPath();for(const ring of p.rings){ring.forEach(([x,y],j)=>j?context.lineTo(x,y):context.moveTo(x,y));if(!p.line)context.closePath()}
    if(p.line){context.save();context.lineWidth=(p.line==='triple'?.6:.35)/report.scale;context.lineCap=context.lineJoin='round';context.strokeStyle=p.colour;context.stroke();context.restore()}else{context.fillStyle=p.colour;context.fill('evenodd')}}
  }
  // Points: a handle on every outline point of the piece being reshaped; the picked one filled.
  zoom=scale;
  const reshaping=active&&points&&targets().length===1?points.rings||targets()[0].rings:null;
  if(reshaping){
   context.save();const size=5/scale;context.lineWidth=1/scale;context.strokeStyle='#1c1c1c';
   reshaping.forEach((r,i)=>r.forEach(([x,y],j)=>{context.fillStyle=points.picked&&points.picked[0]===i&&points.picked[1]===j?'#1c1c1c':'#fff';context.fillRect(x-size/2,y-size/2,size,size);context.strokeRect(x-size/2,y-size/2,size,size)}));
   context.restore();
  }
  // The hoop: always while editing pieces, otherwise when "Show on canvas" is on (hoop-controls.js).
  if(!active&&!window.hoopShown)return;
  const [ox,oy]=report.origin_mm.map(v=>v/report.scale),[w,h]=report.hoop_mm.map(v=>v/report.scale);
  context.save();context.lineWidth=1/scale;context.strokeStyle=getComputedStyle(document.documentElement).getPropertyValue('--ui-muted');context.setLineDash([5/scale,5/scale]);context.strokeRect(ox-w/2,oy-h/2,w,h);
  context.beginPath();context.moveTo(ox-6/scale,oy);context.lineTo(ox+6/scale,oy);context.moveTo(ox,oy-6/scale);context.lineTo(ox,oy+6/scale);context.stroke();context.setLineDash([]);
  context.font=`${11/scale}px system-ui`;context.fillStyle=context.strokeStyle;if(active)context.fillText('0,0 · Y ↓',ox+8/scale,oy-8/scale);if(window.hoopLabel)context.fillText(window.hoopLabel,ox-w/2+4/scale,oy-h/2-6/scale);context.restore();
 }};
 renderRows();sync();
})();
