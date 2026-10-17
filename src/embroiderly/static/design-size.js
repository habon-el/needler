/* Width is an adapter of preparation.options.height_mm, never separate state.
   Both are canvas dimensions, including empty margins. New stitches require
   explicit generation; existing machine coordinates are never scaled here. */
(() => {
 'use strict';
 if(window.preparationConfig.nativeText)return; // Native size rebuilds the font recipe.
 const studio=window.embroideryStudio, height=document.querySelector('[data-option="height_mm"]');
 const make=(tag,text)=>{const el=document.createElement(tag);if(text)el.textContent=text;return el;};
 const width=make('input');width.id='canvasWidth';width.type='number';width.step='.1';
 const label=make('label','Canvas width (mm)');label.htmlFor=width.id;label.append(width);
 height.closest('label').before(label);
 height.id='canvasHeight';height.step='.1';height.oninput=null;
 const help=make('p','Width and height stay in proportion. Enter a size, then press Enter or leave the field. Update stitches rebuilds the plan; it does not stretch old stitches.');
 help.id='canvasSizeHelp';height.closest('label').after(help);
 const feedback=make('p');feedback.id='canvasSizeStatus';feedback.setAttribute('role','status');feedback.setAttribute('aria-live','polite');help.after(feedback);
 for(const input of [width,height])input.setAttribute('aria-describedby','canvasSizeHelp canvasSizeStatus');
 const resize=make('div');resize.id='canvasResize';feedback.after(resize);
 for(const [text,factor] of [['10% smaller',.9],['10% larger',1.1]]){
  const button=make('button',text);button.type='button';
  button.onclick=()=>{height.value=(studio.snapshot().height_mm*factor).toFixed(1);apply(height);};resize.append(button);
 }
 const warning=make('p');warning.id='letteringSizeWarning';warning.setAttribute('role','status');resize.after(warning);
 const edit=make('button','Review words and embroidery fonts');edit.type='button';edit.id='reviewSmallText';warning.after(edit);
 edit.onclick=()=>{document.getElementById('textTool')?.click();};
 function ratio(){const size=studio.imageSize();return size.width/size.height;}
 function sync(){
  const opts=studio.snapshot(),r=ratio(),h=opts.height_mm;
  width.value=(h*r).toFixed(1);height.value=h.toFixed(1);width.min=(10*r).toFixed(2);width.max=(400*r).toFixed(2);
  const m=window.letteringSizeMetrics;warning.hidden=edit.hidden=!m;
  if(!m)return;
  if(m.unavailable){warning.textContent='Typed text: letter-height measurement is unavailable. A small canvas does not prove that each letter is stitchable.';return;}
  const cap=h*m.capital_per_canvas_mm;
  warning.textContent=`${m.line_count} line${m.line_count===1?'':'s'} · reference capitals about ${cap.toFixed(1)} mm high, not the whole block height. `+
   (cap<4?'Picture-based fills can break lettering this small. Try embroidery fonts, more space or different line breaks. ':'Picture-based fills are not embroidery-font stitches. ')+
   'Estimate from the source font, before piece edits and stitching. Your words are unchanged.';
 }
 function apply(input){
  if(studio.isBusy()){sync();feedback.textContent='Wait for the current preview to finish, then enter the size again.';return;}
  const value=Number(input.value),h=input===width?value/ratio():value;
  if(!input.value.trim()||!Number.isFinite(h)||h<10||h>400){sync();input.setAttribute('aria-invalid','true');feedback.textContent=`Size not changed. Canvas height must be 10–400 mm; width follows its proportions (${(10*ratio()).toFixed(1)}–${(400*ratio()).toFixed(1)} mm).`;return;}
  for(const field of [width,height])field.removeAttribute('aria-invalid');
  if(Math.abs(h-studio.snapshot().height_mm)<1e-8)return;
  try{studio.apply({height_mm:h});sync();feedback.textContent=`Canvas width ${width.value} mm × height ${Number(height.value).toFixed(1)} mm. Review the subject, then Update stitches.`;}
  catch(e){sync();feedback.textContent=e.message;}
 }
 for(const input of [width,height]){
  input.addEventListener('change',()=>apply(input));
  input.addEventListener('keydown',e=>{if(e.isComposing)return;if(e.key==='Enter'){e.preventDefault();apply(input);}if(e.key==='Escape'){e.preventDefault();e.stopPropagation();sync();input.removeAttribute('aria-invalid');feedback.textContent='Size edit cancelled.';}});
 }
 window.addEventListener('studio:controls',sync);window.addEventListener('studio:preview',sync);
 sync();
})();
