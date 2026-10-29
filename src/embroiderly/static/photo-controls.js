/* Photo lines (photo_lines.py): rows whose zigzag follows the shading, in one
   thread or a few, closed or open. Values live in the
   preparation options like every other setting. */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 const $=id=>document.getElementById(id), studio=window.embroideryStudio;
 const anchor=$('workflowSizeFields');
 if(!studio||!anchor||window.nativeTextConfig)return;
 const box=document.createElement('div');box.className='puff-controls photo-controls';
 box.innerHTML=`<label class="puff-toggle" title="Rows of thread that follow the shading"><input type="checkbox" id="photoLinesOn"> <span>Photo stitch</span></label>
  <div class="puff-more" id="photoLinesMore" hidden>
   <label for="photoColours">Threads</label>
   <select id="photoColours"><option value="1">1 colour</option><option value="2">2 colours</option><option value="3">3 colours</option><option value="4">4 colours</option><option value="5">5 colours</option><option value="6">6 colours</option></select>
   <label for="photoRow">Row spacing</label>
   <select id="photoRow"><option value="0.8">0.8 mm · more detail</option><option value="1" selected>1.0 mm · balanced</option><option value="1.4">1.4 mm · bolder, fewer stitches</option></select>
   <label for="photoAngle">Row direction</label>
   <select id="photoAngle"><option value="0">Horizontal</option><option value="45">Diagonal</option><option value="90">Vertical</option></select>
   <label class="puff-toggle" title="Light areas get no stitches"><input type="checkbox" id="photoOpen"> <span>Open (fabric shows)</span></label>
   <label class="puff-toggle"><input type="checkbox" id="photoLight"> <span>Light thread on dark fabric</span></label>
   <p class="muted">For photos, 10 cm or larger.</p></div>`;
 anchor.after(box);
 const on=$('photoLinesOn'),more=$('photoLinesMore');
 const threads=()=>Number($('photoColours').value);
 const style=()=>threads()>1?{photo_style:'multi_colour',photo_colours:threads()}:{photo_style:'one_colour'};
 const sync=()=>{const o=studio.snapshot();on.checked=['one_colour','multi_colour'].includes(o.photo_style);more.hidden=!on.checked;
  $('photoColours').value=o.photo_style==='multi_colour'?String(o.photo_colours||4):'1';
  $('photoRow').value=String(o.photo_row_mm||1);$('photoAngle').value=String(o.photo_angle||0);
  $('photoOpen').checked=o.photo_open===true;$('photoLight').checked=o.photo_light_thread===true};
 const apply=patch=>{try{studio.apply(patch)}catch(error){sync();(window.studioStatus||console.warn)(error.message)}};
 on.addEventListener('change',()=>{more.hidden=!on.checked;
  apply(on.checked?{...style(),count:2,line_art:false,ink_only:false,photo_row_mm:Number($('photoRow').value)}:{photo_style:null})});
 $('photoColours').addEventListener('change',()=>apply(style()));
 $('photoRow').addEventListener('change',()=>apply({photo_row_mm:Number($('photoRow').value)}));
 $('photoAngle').addEventListener('change',()=>apply({photo_angle:Number($('photoAngle').value)}));
 $('photoOpen').addEventListener('change',()=>apply({photo_open:$('photoOpen').checked}));
 $('photoLight').addEventListener('change',()=>apply({photo_light_thread:$('photoLight').checked}));
 window.addEventListener('studio:controls',sync);window.addEventListener('studio:preview',sync);sync();
});
