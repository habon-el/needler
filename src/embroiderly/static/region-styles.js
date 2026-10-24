/* One region-style editor backed by preparation options, not a second design model. */
(() => {
 'use strict';
 const $=id=>document.getElementById(id),studio=window.embroideryStudio;
 if(!studio||!$('stitchRegion'))return;
 let report={areas:[],catalog:[],stale:[],unavailable:''},selected='',active=false,ready=false;
 const grid=document.createElement('div');grid.className='stitch-choice-grid';
 const group=document.createElement('fieldset');group.className='stitch-chooser';
 const legend=document.createElement('legend');legend.textContent='Stitch type';group.append(legend,grid);$('regionStyleGallery').append(group);
 // Remove / fill holes: one switch, shown only when the chosen areas have holes.
 const holes=document.createElement('label');holes.className='region-holes';holes.hidden=true;
 const holeBox=document.createElement('input');holeBox.type='checkbox';holeBox.id='regionHoles';
 holes.append(holeBox,' Sew over holes in this area');$('regionStyleGallery').append(holes);
 const areaOf=id=>report.areas.find(a=>a.id===id);
 holeBox.addEventListener('change',()=>{
  const chosen={...(studio.snapshot().area_holes||{})};
  for(const t of targets()){const a=areaOf(t.id);if(!a||!a.holes)continue;if(holeBox.checked)chosen[a.id]='fill';else delete chosen[a.id];}
  try{studio.apply({area_holes:chosen})}catch(error){$('regionStyleStatus').textContent=error.message;holeBox.checked=!holeBox.checked}
 });
 function targets(){if(window.PiecePanel)return window.PiecePanel.targets();return selected.startsWith('colour:')?report.areas.filter(a=>a.colour===selected.slice(7)):report.areas.filter(a=>a.id===selected)}
 function selectArea(){
  selected=$('stitchRegion').value;
  const areas=targets();
  window.stitchRegionSelection=active&&ready&&areas.length?{rings:areas.flatMap(a=>a.rings)}:null;
  studio.redraw();sync();
 }
 function sync(){
  const options=studio.snapshot(),areas=targets(),area=areas[0],busy=$('save').disabled;
  const styles=new Set(areas.map(a=>options.region_styles?.[a.id]||'tatami'));
  const incompatible=areas.filter(a=>a.satin_reason).length;
  const blocked=!ready||!!report.unavailable||busy;
  $('stitchRegion').disabled=blocked||!report.areas.length;
  $('clearRegionStyles').disabled=busy||!Object.keys(options.region_styles||{}).length;
  for(const input of grid.querySelectorAll('input')){
   const limited=['satin','raised_satin'].includes(input.value)&&incompatible>0;
   input.checked=styles.size===1&&styles.has(input.value);
   input.disabled=blocked||!area||limited||areas.some(a=>a.locked);
   input.closest('label').dataset.selected=String(input.checked);
  }
  const withHoles=areas.map(t=>areaOf(t.id)).filter(a=>a&&a.holes);
  holes.hidden=!withHoles.length;holeBox.disabled=blocked||areas.some(a=>a.locked);
  holeBox.checked=withHoles.length>0&&withHoles.every(a=>(options.area_holes||{})[a.id]==='fill');
  $('regionStyleStatus').textContent=!ready?'Preparing current areas…':report.unavailable||(!area?(report.areas.length?'Choose a colour or one area first. Nothing is selected.':'No filled areas available.'):`${selected.startsWith('colour:')?area.colour+' · '+areas.length+' areas':'Area '+(report.areas.indexOf(area)+1)+' · '+area.colour}. Green is only a target highlight in Thread plan, not thread colour. ${styles.size>1?'Mixed stitch styles.':'Current style: '+(report.catalog.find(c=>c[0]===[...styles][0])?.[1]||'Tatami')+'.'} Choose a style, then Update stitches.`);
  if(report.stale.length)$('regionStyleStatus').textContent+=' Artwork changed: '+report.stale.length+' assignments no longer match. Reset area styles before generating.';
  $('regionStyleNote').textContent=incompatible?`${incompatible} of ${areas.length} selected areas cannot use Satin or 3D satin. Choose an individual area to inspect it. No areas will be silently skipped.`: '3D satin uses three stitched layers, not foam. Embossed is a diamond overlay on Tatami; these are experimental textures. Sew a physical sample. Decorative fills leave open fabric.';
 }
 function render(){
  const previous=selected;$('stitchRegion').replaceChildren();
  const placeholder=document.createElement('option');placeholder.value='';placeholder.textContent='Choose a colour or area…';$('stitchRegion').append(placeholder);
  const colours=document.createElement('optgroup');colours.label='All areas of a colour';
  for(const colour of new Set(report.areas.map(a=>a.colour))){const option=document.createElement('option');option.value='colour:'+colour;option.textContent=colour+' · '+report.areas.filter(a=>a.colour===colour).length+' areas';colours.append(option)}
  $('stitchRegion').append(colours);
  const individual=document.createElement('optgroup');individual.label='One area only';$('stitchRegion').append(individual);
  report.areas.forEach((area,i)=>{const option=document.createElement('option');option.value=area.id;option.textContent=`Area ${i+1} · ${area.colour} · ${area.bounds[2]} × ${area.bounds[3]} px`;individual.append(option)});
  $('stitchRegion').value=Array.from($('stitchRegion').options).some(o=>o.value===previous)?previous:'';
  grid.replaceChildren();
  for(const [id,name,hint] of report.catalog){
   const label=document.createElement('label');label.className='stitch-choice';
   const input=document.createElement('input');input.type='radio';input.name='area-stitch-style';input.value=id;
   const title=document.createElement('strong');title.textContent=name;
   const help=document.createElement('small');help.textContent=hint;
   label.append(input,window.StitchSamples(id),title,help);grid.append(label);
   input.addEventListener('change',()=>{
    if(!input.checked||input.disabled)return;
    if(window.PiecePanel){window.PiecePanel.commit('style',id);return}
    const styles={...(studio.snapshot().region_styles||{})};
    for(const area of targets()){if(id==='tatami')delete styles[area.id];else styles[area.id]=id;}
    try{studio.apply({region_styles:styles})}catch(error){$('regionStyleStatus').textContent=error.message}
    sync();
   });
  }
  selectArea();
 }
 $('stitchRegion').parentElement.firstChild.textContent='Apply style to';
 $('stitchRegion').addEventListener('change',selectArea);
 $('clearRegionStyles').addEventListener('click',()=>{try{studio.apply({region_styles:{}})}catch(error){$('regionStyleStatus').textContent=error.message}});
 window.addEventListener('studio:preview',event=>{report=event.detail.report.stitch_regions||report;ready=true;render()});
 window.addEventListener('studio:changed',()=>{ready=false;window.stitchRegionSelection=null;sync()});
 window.addEventListener('studio:controls',sync);
 window.addEventListener('studio:topic',event=>{active=event.detail==='styles';selectArea()});
 sync();
})();
