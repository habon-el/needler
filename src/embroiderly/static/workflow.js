/* Presentation adapter only. Existing controllers still own values, generation,
   approval and downloads. Move their nodes; never copy form values or files. */
document.addEventListener('DOMContentLoaded', () => {
 'use strict';
 const $=id=>document.getElementById(id), studio=window.embroideryStudio;
 if(!studio)return;
 const native=!!window.nativeTextConfig, inspector=document.querySelector('.inspector');
 const node=(tag,text,id)=>{const e=document.createElement(tag);if(text)e.textContent=text;if(id)e.id=id;return e;};
 const details=(title,id)=>{const d=node('details','',id);d.append(node('summary',title));return d;};
 const button=(text,id,fn)=>{const b=node('button',text,id);b.type='button';b.onclick=fn;return b;};
 let step='edit',result=null,everChecked=!!window.preparationConfig.previous,changed=false,saved=!native&&Object.keys(window.preparationConfig.options||{}).length>0,checking=false,downloading=false,downloadVersion=0;
 document.body.classList.add('clear-workflow');
 const nav=node('nav','','workflowSteps');nav.setAttribute('aria-label','Design steps');
 for(const [i,key,label] of [[1,'edit','Edit'],[2,'check','Check stitches'],[3,'download','Save and download']]){
  const b=button(i+'  '+label,'',()=>show(key));b.dataset.workflow=key;nav.append(b);
 }
 document.querySelector('.statusbar').before(nav);
 const saveState=node('span','Saved','workflowSaved');saveState.setAttribute('role','status');$('save').before(saveState);
 const next=button('Save and download','workflowNext',()=>show('download'));next.className='primary';$('stitch').after(next);
 const edit=node('section','','workflowEdit'),check=node('section','','workflowCheck'),download=node('section','','workflowDownloadPanel');
 const expert=details('Expert settings','workflowExpert');
 const oldChildren=[...inspector.children];
 inspector.append(edit,check,download);
 if(native){
  edit.append(node('h1','Your text'));
  const wordsLabel=document.querySelector('label[for=letteringWords]');edit.append(wordsLabel,$('letteringWords'));
  edit.append(document.querySelector('label[for=nativeFont]'),$('nativeFont'));
  // Shape of the line: straight, arch (curves up), smile (curves down), full circle or wave, how much
  // it curves, and an optional fixed length along the line.
  const shape=node('fieldset','','workflowTextShape');shape.append(node('legend','Shape'));
  const shapes=node('div','','workflowShapeButtons');shapes.setAttribute('role','group');
  const pick=value=>{const b=$('nativeBaseline');if(b.value===value)return;b.value=value;
   b.dispatchEvent(new Event('input',{bubbles:true}));b.dispatchEvent(new Event('change',{bubbles:true}));};
  for(const [value,label,title] of [['straight','▬ Straight','Words on a straight line'],['arc_over','⌒ Arch','Words curve up, like the top of a badge'],['arc_under','⌣ Smile','Words curve down, like the bottom of a badge'],['circle','◯ Circle','Words round a whole circle: the first line over the top, a second line along the bottom'],['wave','∿ Wave','Words follow an S-shaped wave']]){
   const b=button(label,'',()=>pick(value));b.dataset.baseline=value;b.title=title;shapes.append(b);
  }
  const pressed=()=>shapes.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.baseline===$('nativeBaseline').value)));
  $('nativeBaseline').addEventListener('input',pressed);$('nativeBaseline').addEventListener('change',pressed);
  document.addEventListener('lettering:layout',pressed);pressed();
  shape.append(shapes,$('nativeCurveField'),$('nativeCircleField'),$('nativeWaveField'),$('nativeEnvelopeField'),$('nativeFitLengthField'));edit.append(shape);
  // Monogram: a satin frame around the words, an ornament and the classic three-initial layout.
  const monogram=node('fieldset','','workflowTextFrame');monogram.append(node('legend','Monogram & frame'));
  monogram.append(document.querySelector('label[for=nativeFrame]'),$('nativeFrame'),$('nativeFrameWidthField'),
   document.querySelector('label[for=nativeOrnament]'),$('nativeOrnament'),$('nativeClassicField'));
  edit.append(monogram);
  const row=node('div','','workflowSizeFields');
  for(const id of ['nativeHeight','nativeWidth']){
   const field=node('div');field.append(document.querySelector('label[for='+id+']'),$(id));row.append(field);
  }
  // What it is for: sets the space on the item (and the cap fabric and centre-out order for caps).
  const product=node('label','','workflowTextProduct');product.append('For ');
  const item=node('select');item.id='workflowTextItem';
  for(const [value,label] of [['','Choose an item…'],['cap','Cap front · up to 110 mm wide'],['chest','Left chest · up to 90 mm wide'],
   ['sleeve','Sleeve · up to 70 mm wide'],['back','Jacket back · up to 280 mm wide']])item.append(new Option(label,value));
  item.onchange=()=>{const set={cap:{available_width_mm:110,fabric_preset:'cap',sequence:'centre'},chest:{available_width_mm:90},
   sleeve:{available_width_mm:70},back:{available_width_mm:280}}[item.value];if(set)window.NeedlerTextApply?.(set);};
  product.append(item);edit.append(product);
  edit.append(row,$('nativeResize'));
  document.querySelector('label[for=nativeWidth]').textContent='Max width (mm)';
  // The height entered is the stitched height of the words (small_lettering.scale_for).
  document.querySelector('label[for=nativeHeight]').textContent='Height (mm)';
  $('nativeHeight').title='Height of your stitched words, top of the tallest letter to the bottom of the lowest, all lines.';
  $('nativeWidth').title='The widest your words may be on your item. Too-wide words are shown, never shrunk automatically.';
  const size=node('p','Check stitches to measure the finished width × height.','workflowMeasuredSize');edit.append(size);
  const hint=node('p','','workflowLetterTip');edit.append(hint);
  const extras=node('div','','workflowTextExtras');extras.append($('letteringAlign').closest('label'),$('letteringColour').closest('label'));edit.append(extras);
  const fabric=node('div','','workflowTextFabric');fabric.append(document.querySelector('label[for=nativeFabric]'),$('nativeFabric'));edit.append(fabric);
  const spacing=details('Spacing & letter order','workflowTextSpacing');
  for(const id of ['nativeLetterSpacing','nativeLineSpacing','nativeSequence','nativeJoin'])spacing.append(document.querySelector('label[for='+id+']'),$(id));
  edit.append(spacing);
  const help=details('About the height','workflowTextDetails');help.append($('nativeHelp'));edit.append(help);
  expert.querySelector('summary').textContent='About these stitches';
  expert.append(node('p','Stitch settings come from the selected embroidery font. They are not editable here.'));
  expert.append($('nativeChanges'));
  const fontLink=$('nativeLettering').querySelector('a[href^="https:"]');if(fontLink)expert.append(fontLink.closest('p'));
  edit.append(expert);
  const tip=()=>{
   const value=Number($('nativeHeight').value),el=$('workflowLetterTip');
   el.dataset.level=value<4?'red':value<5?'amber':'green';
   el.textContent=(value<4?'Very small text — check the preview and sew a sample first.':value<5?'Small text — sew a sample first.':'Sew a sample before using this on your item.')+' Height is the stitched height of your words.';
  };
  $('nativeHeight').addEventListener('input',tip);tip();
  // One result, not a second preview or a second set of approval buttons.
  check.append(node('h1','Check your stitches'),$('nativeResult'),$('nativeFit'),$('nativeProblems'));
  $('nativeProblems').open=true;
  const caution=node('p','File checks cannot prove readability, density or needle safety; sew a sample on your fabric.','workflowSafety');check.append(caution);
 }else{
  const basics=node('div','','workflowBasics');
  basics.append(node('h1','Your design'));
  const sizes=node('div','','workflowSizeFields');
  for(const [id,title] of [['canvasWidth','↔ Width (mm)'],['canvasHeight','↕ Height (mm)']]){
   const input=$(id);if(!input)continue;
   const label=input.closest('label');label.replaceChildren(document.createTextNode(title),input);sizes.append(label);
  }
  basics.append(sizes);
  for(const id of ['canvasResize','canvasSizeStatus','letteringSizeWarning'])if($(id))basics.append($(id));
  const help=details('About this size');help.append(node('p','Width and height change together.','workflowProportions'));if($('canvasSizeHelp'))help.append($('canvasSizeHelp'));basics.append(help);
  // One route into each existing tool, not another settings owner.
  const choices=node('nav','','workflowChoices');choices.setAttribute('aria-label','Embroidery tools');
  const basicTools=[
   ['workflowAskAI','ask','AI assistant','Describe a cutout, or ask about your artwork. Nothing changes until you apply it.'],
   ['workflowBackground','selection','Background','Choose the subject and remove unwanted background.'],
   ['textTool',null,'New text','Create a separate editable lettering design. This picture stays unchanged.'],
   ['workflowColours','colours','Colours','Choose, replace or exclude thread colours.'],
   ['workflowStyles','styles','Stitch styles','Choose stitches for selected colours or areas.'],
   ['workflowBorders','borders','Borders','Add an outline around the subject.'],
   ['workflowDetails','review','Review details','Compare the original with the stitch artwork.'],
  ];
  let returnTo='workflowAskAI';
  const openTopic=(key,id)=>{
   returnTo=id;window.embroideryWorkspace.showTopic(key);inspector.scrollTop=0;
   const panel=$('topic-'+key);panel.tabIndex=-1;panel.focus({preventScroll:true});
  };
  for(const [id,key,title,hint] of basicTools){
   // Text retains its dialog handler and focus restoration; do not create a proxy.
   const choice=key?button('',id,()=>openTopic(key,id)):$(id);
   if(!choice)continue;
   const source=key?document.querySelector('[data-topic="'+key+'"] .ui-icon'):choice.querySelector('.ui-icon');
   const glyph=source?.cloneNode(true);
   choice.replaceChildren();if(glyph)choice.append(glyph);
   choice.append(node('span',title));choice.title=hint;choice.setAttribute('aria-label',title);
   if(key)choice.setAttribute('aria-controls','topic-'+key);
   choices.append(choice);
   if(key)document.querySelector('[data-topic="'+key+'"]').hidden=true;
  }
  basics.querySelector('h1').after(choices);
  basics.append($('confirmed').closest('label'));
  edit.append(basics);
  const toolPanel=node('section','','workflowToolPanel');toolPanel.hidden=true;
  const back=button('← All tools','workflowBack',()=>{
   const panel=toolPanel.querySelector('.topic-panel');if(panel){panel.hidden=true;expert.append(panel);}
   toolPanel.hidden=true;basics.hidden=false;expert.hidden=false;inspector.scrollTop=0;
   $(returnTo)?.focus();
  });
  toolPanel.append(back);edit.append(toolPanel);
  // Keep one instance of each setting. Basic tools open directly, not in Expert.
  for(const child of oldChildren)expert.append(child);
  edit.append(expert);
  const reviewPanel=$('topic-review');
  if($('designReview')){
   reviewPanel.querySelectorAll(':scope > details').forEach(d=>{d.open=false;d.dataset.disclosure='manual';});
   reviewPanel.querySelector('.topic-hint').after($('designReview'));
  }
  window.addEventListener('studio:topic',event=>{
   const panel=$('topic-'+event.detail),basic=basicTools.some(([,key])=>key===event.detail);
   const previous=toolPanel.querySelector('.topic-panel');if(previous)expert.append(previous);
   if(basic){toolPanel.append(panel);expert.open=false;returnTo=basicTools.find(([,key])=>key===event.detail)[0];}
   toolPanel.hidden=!basic;basics.hidden=basic;expert.hidden=basic;
   if(!basic)expert.open=true;
   show('edit',false);
  });
  const measure=node('p','','workflowCanvasSize');measure.setAttribute('aria-live','polite');
  document.querySelector('.panels').after(measure);
  const measurements=()=>{
   const size=studio.imageSize(),height=studio.snapshot().height_mm;
   if(size.height)measure.textContent='↔ '+(height*size.width/size.height).toFixed(1)+' mm wide   ·   ↕ '+height.toFixed(1)+' mm high — includes empty margins';
  };
  window.addEventListener('studio:controls',measurements);window.addEventListener('studio:preview',measurements);measurements();
  check.append(node('h1','Check your stitches'));
 }
 // Existing audit and location controls remain available, with warnings open.
 // Kept clean: the Problems panel (problems-panel.js) lists what to fix. Design health
 // shows only when selected details cannot be stitched at all; route statistics stay
 // inside the closed expert section.
 const health=$('healthSummary').closest('details');health.open=true;check.append(health);
 const healthVisible=()=>{health.hidden=native||!/cannot be stitched/.test($('healthSummary').textContent)};
 new MutationObserver(healthVisible).observe($('healthSummary'),{childList:true,characterData:true,subtree:true});healthVisible();
 const route=$('routeNext').closest('details');route.open=false;route.append($('routeSummary'),$('routeWarning'));check.append(route);
 if(!native){
  window.addEventListener('studio:cleanup-needed',()=>{
   show('edit');window.embroideryWorkspace.showTopic('review');
   const section=$('detailMap').closest('details');section.open=true;
   // Wait until the preparation controller releases its busy controls.
   setTimeout(()=>{const target=$('cleanupChoice')||section.querySelector('summary');target.scrollIntoView({block:'center'});target.focus();},0);
  });
 }
 const downloadNote=node('p','','workflowDownloadNote');
 download.append(node('h1','Save and download'),downloadNote);
 const format=node('select','','workflowFormat');
 // Same list as release_gate.FORMATS; every format is re-checked on the server.
 for(const [value,label] of [['dst','DST — Tajima and most commercial machines'],['pes','PES — Brother / Babylock'],['jef','JEF — Janome'],['exp','EXP — Melco / Bernina'],['xxx','XXX — Singer'],['u01','U01 — Barudan'],['pec','PEC — Brother (older)']]){const o=node('option',label);o.value=value;format.append(o);}
 const formatLabel=node('label','Machine file');formatLabel.htmlFor=format.id;download.append(formatLabel,format);
 const downloadError=node('section','','workflowDownloadError');downloadError.hidden=true;downloadError.setAttribute('role','alert');download.append(downloadError);
 const getFile=button('Download DST','workflowDownload',async ()=>{
  sync();if(getFile.disabled)return;
  const fmt=format.value;
  // Call the existing download owner. No bypass, new writer or new check.
  if(native&&(fmt==='dst'||fmt==='pes')){$('native'+fmt[0].toUpperCase()+fmt.slice(1)).click();return;}
  const target={href:native?`/lettering/native/${result&&result.id}/download/${fmt}`:$('exportDst').href.replace(/\/[a-z0-9]+$/,'/'+fmt)},version=downloadVersion;
  downloading=true;downloadError.hidden=true;sync();
  const originalLabel=getFile.textContent;getFile.textContent='Preparing file…';
  try{
   const response=await fetch(target.href,{signal:AbortSignal.timeout(60000)});
   if(version!==downloadVersion)return;
   if(!response.ok){
    let problem;try{problem=await response.json();}catch(_){problem={error:'The file could not be downloaded. Check your connection and try again.'};}
    downloadError.replaceChildren();
    const issues=Array.isArray(problem.issues)?problem.issues:[],counts={};
    for(const issue of issues)counts[issue.code]=(counts[issue.code]||0)+1;
    const descriptions={short:'stitches are too short',long:'stitches are too long',crossing:'stitches cross gaps',travel:'thread travels across a visible gap'};
    const summary=Object.entries(counts).map(([key,count])=>count+' '+(descriptions[key]||'other stitch problems')).join(' · ');
    downloadError.append(node('strong','Not ready to download'),node('p',summary||problem.error||'The file could not be downloaded. Try again.'),node('p','Review the design and check stitches again. Your design has not been changed.'));
    const locations=details('See every problem');
    const list=node('ul');
    for(const issue of issues){const p=issue.location||{};list.append(node('li',(issue.reason||'Stitch problem')+' — X '+p.x_mm+' mm, Y '+p.y_mm+' mm (stitch command '+p.command+').'));}
    locations.append(list);if(issues.length)downloadError.append(locations);
    downloadError.append(button('Back to checks','workflowBackToChecks',()=>show('check')));
    downloadError.hidden=false;downloadError.scrollIntoView({block:'nearest'});return;
   }
   const blob=await response.blob();if(version!==downloadVersion)return;
   const link=node('a');link.href=URL.createObjectURL(blob);link.download='embroidery.'+fmt;
   document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
  }catch(error){
   if(version===downloadVersion){downloadError.replaceChildren(node('strong','Download did not finish'),node('p',error.name==='TimeoutError'?'The download took too long. Try again.':'Check your connection and try again. Your design is unchanged.'));downloadError.hidden=false;}
  }finally{downloading=false;getFile.textContent=originalLabel;sync();}
 });getFile.className='primary';format.onchange=()=>{getFile.textContent='Download '+format.value.toUpperCase();};download.append(getFile);
 // Appliqué: the fabric shapes at actual size, for a cutter or a paper template.
 const cutting=node('a','Download appliqué cutting shapes (SVG)','workflowCutting');cutting.hidden=true;download.append(cutting);
 // Same stitched design as the machine-file link (outputs are kept under the prepared picture's name).
 window.addEventListener('studio:preview',e=>{
  const source=$('exportDst')?.getAttribute('href')?.match(/\/studio-export\/([^/]+)\//);
  cutting.hidden=!e.detail?.applique||!source;if(source)cutting.href='/applique-cut/'+source[1];});
 // Printable worksheet: sequence, threads, stops, backing, hoop and the design at actual size.
 const sheet=node('a','Print worksheet (sequence, threads, backing, actual size)','workflowWorksheet');sheet.target='_blank';sheet.rel='noopener';sheet.hidden=true;download.append(sheet);
 window.addEventListener('studio:preview',()=>{
  if(native)return;const source=$('exportDst')?.getAttribute('href')?.match(/\/studio-export\/([^/]+)\//);
  sheet.hidden=!source;if(source)sheet.href='/worksheet/'+source[1];});
 document.addEventListener('lettering:result',e=>{if(native&&e.detail?.id){sheet.href='/lettering/native/'+e.detail.id+'/worksheet';sheet.hidden=false}});
 document.addEventListener('lettering:invalidated',()=>{if(native)sheet.hidden=true});
 download.append(node('p','Always test the file on your own fabric and machine before a production run.'));
 if(native)oldChildren.forEach(child=>{child.hidden=true;});
 inspector.append(edit,check,download);
 // One player, still owned by preparation.js. Its handlers switch to the
 // stitched canvas themselves, preserving pause/resume and the current cursor.
 const playbackHeading=node('div','','workflowPlaybackHeading');
 const playbackHint=node('p','','workflowPlaybackHint');playbackHint.setAttribute('role','status');
 playbackHeading.append(node('h2','Watch it stitch'),playbackHint);
 document.querySelector('.transport').before(playbackHeading);
 $('run').setAttribute('aria-describedby','workflowPlaybackHint');
 // One visible result summary, sourced only from the actual playback owner.
 const resultBanner=node('section','','workflowResult');resultBanner.setAttribute('role','status');
 resultBanner.setAttribute('aria-live','polite');
 const resultTitle=node('strong'),resultMessage=node('span');
 resultBanner.append(resultTitle,resultMessage);document.querySelector('.panels').before(resultBanner);
 $('finish').textContent='Show full design';
 const compare=document.querySelector('[data-view="compare"]');
 if(!native)compare.onclick=()=>studio.review(step==='edit'?'compare':'review');
 const originalStitch=$('stitch').onclick;
 $('stitch').onclick=event=>{if(studio.hasPlayback())show('check');else{if(!native)show('check');originalStitch.call($('stitch'),event);if(native&&checking)show('check');}};
 function sync(){
  const available=studio.hasPlayback(),ready=native?!!result?.checks_passed:available;
  const info=studio.resultInfo();
  const state=native&&checking?'generating':info.state;
  resultBanner.dataset.state=state;
  const messages={
   ready:['Stitch preview ready',info.stitches.toLocaleString()+' stitches · '+info.trims.toLocaleString()+' cuts. Play shows the sewing order; a sample sew-out is still needed.'],
   generating:['Making stitches…','Your finished stitch preview will appear here.'],
   preparing:['Preparing artwork…','This is not a finished stitch plan yet.'],
   blocked:['Stitches not made yet',info.blockers?info.blockers.toLocaleString()+(info.blockers===1?' detail has':' details have')+' no usable stitch outline. See the detail warnings below; nothing has been removed.':info.pending.toLocaleString()+' cleanup choices need your review before stitching.'],
   error:['Stitches could not be prepared',info.error],
   empty:['Artwork only — no stitches yet','Approve your subject, then choose Check stitches.']
  };
  if(native&&state==='empty')messages.empty=['No stitches yet','Enter your text and choose Check stitches.'];
  const copy=messages[state];resultTitle.textContent=copy[0];resultMessage.textContent=copy[1];
  compare.textContent=step==='edit'&&!native?'Compare artwork':'Compare stitches';
  compare.disabled=(step!=='edit'||native)&&!available;
  compare.setAttribute('aria-pressed',String(compare.dataset.active==='true'));
  playbackHint.textContent=available?'Press Play to follow the stitch order. Preview only — test on your machine.':'Use Check stitches to prepare a preview. Play becomes available when the stitches are ready.';
  $('workflowSaved').textContent=saved?'Saved':'Unsaved changes';
  $('stitch').textContent=changed&&everChecked?'Update stitches':'Check stitches';
  $('stitch').classList.toggle('primary',step==='edit'||!available);
  $('stitch').style.display=step==='edit'||!available?'':'none';
  if(available && !checking && !studio.isBusy() && $('stitch').disabled)$('stitch').disabled=false;
  next.hidden=step!=='check';next.disabled=!ready||checking;
  getFile.disabled=!(native?result?.approved:available)||checking||downloading||studio.isBusy();
  downloadNote.textContent=!ready?'Check stitches first. Resolve any warnings that block the file, then return here.':native&&!result?.approved?'Review the stitches, then use Save design in the top bar to approve this version.':'Choose the file your machine uses. We check it again before downloading.';
  if(native && result){const r=result.reports.dst;$('workflowMeasuredSize').textContent=r.width_mm+' mm wide × '+r.height_mm+' mm high';}
 }
 function show(nextStep,changeCanvas=true){
  step=nextStep;document.body.dataset.workflow=step;
  for(const [key,el] of [['edit',edit],['check',check],['download',download]])el.hidden=key!==step;
  nav.querySelectorAll('button').forEach(b=>{const current=b.dataset.workflow===step;b.setAttribute('aria-current',current?'step':'false');});
  if(changeCanvas)studio.review(step==='edit'?'original':'stitched');
  inspector.scrollTop=0;sync();
 }
 window.addEventListener('studio:stitch-state',()=>{if(studio.hasPlayback()){everChecked=true;changed=false;}sync();});
 window.addEventListener('studio:view',e=>{
  compare.dataset.active=String(['compare','review'].includes(e.detail));
  if(['stitched','review'].includes(e.detail)&&step==='edit')show('check',false);
  if(['proposal','prepared','isolated'].includes(e.detail)&&step!=='edit')show('edit',false);
  sync();
 });
 window.addEventListener('studio:changed',()=>{downloadVersion++;downloadError.hidden=true;changed=true;saved=false;sync();});
 window.addEventListener('studio:preview',e=>{
  if(studio.hasPlayback()){everChecked=true;changed=false;}
  // Reuse the same warning controls: generation blockers must be visible
  // before approval, including while the user is still in Edit.
  if(!native){
   const blocked=!!e.detail?.report?.generation_blockers?.length||(e.detail?.report?.cleanup_review||[]).some(item=>item.decision==='pending');
   (blocked?inspector:check).append(health);
   if(blocked)health.open=true;
   health.classList.toggle('has-generation-blockers',blocked);
  }
  sync();
 });
 // These are notifications from the existing request owner, never new state
 // sent to generation. The saved label cannot become true on a failed save.
 window.addEventListener('studio:saved',()=>{saved=true;sync();});
 document.addEventListener('lettering:invalidated',()=>{result=null;changed=true;saved=false;if($('workflowMeasuredSize'))$('workflowMeasuredSize').textContent='Size needs checking';sync();});
 document.addEventListener('lettering:busy',e=>{checking=e.detail;sync();});
 document.addEventListener('lettering:result',e=>{result=e.detail;saved=!!result.approved;everChecked=true;changed=false;sync();});
 // Invalidation clears playback after studio:changed; observe the player's
 // owner disabling it so the explanation cannot describe a stale plan.
 new MutationObserver(sync).observe($('run'),{attributes:true,attributeFilter:['disabled']});
 new MutationObserver(sync).observe($('stitch'),{attributes:true,attributeFilter:['disabled']});
 new MutationObserver(sync).observe($('exportDst'),{attributes:true,attributeFilter:['hidden','href']});
 new MutationObserver(()=>{if($('nativeProblems')?.hidden===false)$('nativeProblems').open=true;}).observe($('nativeProblems'),{attributes:true,attributeFilter:['hidden']});
 show(new URL(location.href).searchParams.get('view')==='stitched'||studio.hasPlayback()?'check':'edit');
 $('textTool')?.addEventListener('click',()=>{if(native){show('edit');$('letteringWords').focus();}});
 $('rulerEditSize')?.addEventListener('click',()=>{show('edit');});
 window.DesignWorkflow={show,sync};
});
