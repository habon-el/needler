/* Read-only photo review. No access to studio.apply or a design-write endpoint. */
(() => {
  'use strict';
  const studio=window.embroideryStudio,config=window.preparationConfig;
  if(config.nativeText)return; // Photo review requires an artwork project, not a text recipe.
  const host=document.querySelector('#topic-review');if(!host||!studio)return;
  const panel=document.createElement('details');panel.id='sewoutReview';
  panel.innerHTML=`<summary>Sew-out assistance</summary>
    <p>Compare a photograph of your real sew-out with the saved stitch plan. This does not edit your design.</p>
    <p id="sewoutValidation" class="muted"></p>
    <p id="sewoutCapture" class="muted">Loading photo guidance…</p>
    <label>Photo of the sewn sample<input id="sewoutPhoto" type="file" accept="image/png,image/jpeg,image/webp" aria-describedby="sewoutPrivacy sewoutFileHelp"></label>
    <p id="sewoutFileHelp" class="muted">PNG, JPG or WebP · up to 12 MB</p>
    <button type="button" id="sewoutClear" hidden>Remove photo</button>
    <p id="sewoutPrivacy" class="muted">The review report is saved locally with this design. The photo is not saved locally. A new photo and the stitch-plan render are sent only to OpenAI, with your permission.</p>
    <label><input id="sewoutConsent" type="checkbox"> Allow this photo review to use OpenAI’s paid API</label>
    <button type="button" id="sewoutRun" disabled>Review sewn sample</button>
    <p id="sewoutStatus" role="status" aria-live="polite">Checking photo review availability…</p>
    <p id="sewoutBudget" class="muted"></p><div id="sewoutResult"></div>
    <details><summary>Earlier sample reviews</summary><button type="button" id="sewoutHistory">Refresh history</button><div id="sewoutHistoryList"></div></details>`;
  host.append(panel);
  const $=id=>document.getElementById(id);let available=false,busy=false,photoUrl,history=[];
  function node(tag,value){const el=document.createElement(tag);el.textContent=value;return el;}
  function controls(){
    $('sewoutRun').disabled=busy||!available||!$('sewoutPhoto').files.length;
    $('sewoutPhoto').disabled=busy;$('sewoutConsent').disabled=busy;
    $('sewoutHistory').disabled=busy;$('sewoutClear').disabled=busy;
    $('sewoutClear').hidden=!$('sewoutPhoto').files.length;
  }
  function citation(value){return `${value.table}#${value.row_id} · version ${value.version} · ${value.verified_by_user?'shop verified':'unverified seed data'}`;}
  function show(report,currentPhoto) {
    const out=$('sewoutResult');out.replaceChildren();out.append(node('p',report.message));
    if(currentPhoto){const img=new Image();img.src=currentPhoto;img.alt='Uploaded physical sample for this review';img.style.cssText='width:100%;max-height:240px;object-fit:contain';out.append(img);}
    out.append(node('p',report.comparison_limit));
    const summary=report.design_comparison;
    out.append(node('p',`Saved plan: ${summary.stitch_count.toLocaleString()} stitches · ${summary.thread_count} threads. These are file counts, not measurements from the photo.`));
    for(const finding of report.findings){
      const section=document.createElement('details');section.open=true;section.append(node('summary',finding.visible_observation));
      section.append(node('p','Possible causes (hypotheses, not a diagnosis; a photo cannot establish the cause): '+finding.possible_causes.join('; ')),node('p',finding.remedy));
      section.append(node('p',`Setting: ${finding.setting}. Exact adjustment: ${finding.adjustment===null?'not established by this evidence':finding.adjustment}.`));
      section.append(node('p','Not available to Apply: '+finding.capability_gap));
      section.append(node('small',citation(finding.citation)));out.append(section);
    }
    out.append(node('p','Not measurable from this review: '+report.limitations.join(', ')+'.'));
    for(const source of report.citations)out.append(node('small',citation(source)));
    out.append(node('p',report.cached_observation?'Reused the stored observation; no unchanged photo was sent again.':'Read-only review. No design settings were applied.'));
  }
  async function refresh(){
    try{
      const response=await fetch('/advisors/sewout/'+encodeURIComponent(config.name),{cache:'no-store',signal:AbortSignal.timeout(12000)});
      if(!response.ok)throw Error('Review history could not load. Manual editing is unaffected.');
      const data=await response.json();available=data.configured;history=data.history;
      $('sewoutCapture').textContent=data.capture_guidance+' ['+citation(data.citation)+']';
      $('sewoutValidation').textContent=data.validation_status;
      $('sewoutStatus').textContent=available?'Ready. Review requires permission for a new photo.':(data.provider_blocked_reason||'Photo model unavailable. Manual tools still work.');
      $('sewoutBudget').textContent=`${data.requests_used} of ${data.request_limit} photo requests used. USD caps also gate generation. Failed or uncertain requests retain their maximum-cost reservation.`;
      $('sewoutHistoryList').replaceChildren();
      if(!history.length)$('sewoutHistoryList').append(node('p','No sample reviews saved yet.'));
      for(const entry of history){const b=node('button',new Date(entry.created*1000).toLocaleString());b.type='button';b.onclick=()=>show(entry.report,null);$('sewoutHistoryList').append(b);}
    }catch(error){$('sewoutStatus').textContent=error.message;}finally{controls();}
  }
  $('sewoutPhoto').onchange=()=>{if(photoUrl)URL.revokeObjectURL(photoUrl);photoUrl=null;$('sewoutResult').replaceChildren();controls();};
  $('sewoutHistory').onclick=refresh;
  $('sewoutClear').onclick=()=>{$('sewoutPhoto').value='';$('sewoutPhoto').onchange();$('sewoutPhoto').focus();};
  $('sewoutRun').onclick=async()=>{
    if(busy)return;
    const file=$('sewoutPhoto').files[0];if(!file)return;
    if(file.size>12*1024*1024){$('sewoutStatus').textContent='Choose a photo smaller than 12 MB.';return;}
    const snapshot=JSON.stringify(studio.snapshot());const body=new FormData();
    body.append('photo',file);body.append('options',snapshot);body.append('consent',String($('sewoutConsent').checked));
    $('sewoutConsent').checked=false;busy=true;controls();$('sewoutStatus').textContent='Reviewing the sample. Your design remains unchanged…';
    try{
      const response=await fetch('/advisors/sewout/'+encodeURIComponent(config.name),{method:'POST',body,signal:AbortSignal.timeout(60000)});
      const data=await response.json();if(!response.ok)throw Error(data.error||'Photo review unavailable.');
      await refresh();
      if(snapshot!==JSON.stringify(studio.snapshot())){$('sewoutStatus').textContent='Your design changed during review. The earlier-plan report is saved in history; it is not a review of the new edits.';return;}
      if(photoUrl)URL.revokeObjectURL(photoUrl);photoUrl=URL.createObjectURL(file);show(data.report,photoUrl);
      $('sewoutStatus').textContent='Report saved locally. No changes applied.';
    }catch(error){$('sewoutStatus').textContent=error.name==='TimeoutError'?'Review timed out. Refresh history before retrying; it may have completed.':error.message;}
    finally{busy=false;controls();}
  };
  refresh();
})();
