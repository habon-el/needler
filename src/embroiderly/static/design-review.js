/* Read-only review, nested in the existing detail panel. No studio.apply calls. */
(() => {
  'use strict';
  const studio = window.embroideryStudio, config = window.preparationConfig;
  const owner = document.getElementById('detailStatus');
  if (!studio || !owner || window.nativeTextConfig) return;
  const node = (tag, text) => { const el = document.createElement(tag); el.textContent = text; return el; };
  const button = (text, id) => { const el = node('button', text); el.type = 'button'; el.id = id; return el; };
  const root = node('section', ''); root.id = 'designReview'; root.setAttribute('aria-label', 'Check my design');
  const check = button('Check my design', 'checkMyDesign'); check.disabled = true;
  const status = node('p', 'Did any details disappear? Compare the two pictures. Nothing will be changed.');
  status.id = 'designReviewStatus'; status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  status.style.minHeight = '3em';
  const cloud = node('details', ''); cloud.dataset.disclosure = 'manual'; cloud.append(node('summary', 'Optional AI explanation'));
  const cloudStatus = node('p', 'Checking whether cloud review is configured…');
  const consent = document.createElement('input'); consent.type = 'checkbox'; consent.id = 'designReviewConsent';
  const label = node('label', ''); label.append(consent, document.createTextNode(' Send these artwork images and crops to OpenAI for this review.'));
  const ai = button('Ask AI about these differences', 'askDesignReview'); ai.disabled = true;
  const cancel = button('Cancel review', 'cancelDesignReview'); cancel.hidden = true;
  cloud.append(cloudStatus, label, ai);
  const list = node('div', ''); list.id = 'designReviewFindings';
  const more = button('Show more differences', 'moreDesignDifferences'); more.hidden = true;
  root.append(check, cancel, status, list, more, cloud); owner.before(root);
  let controller = null, epoch = 0, ready = false, cloudReady = false, data = null, shown = 0, snapshot = '';
  const endpoint = '/design-review/' + encodeURIComponent(config.name);
  const state = () => JSON.stringify(studio.snapshot());
  function controls() {
    check.disabled = !ready || !!controller || studio.isBusy();
    ai.disabled = !cloudReady || !consent.checked || !data || !!controller || studio.isBusy() || snapshot !== state();
    cancel.hidden = !controller;
    root.setAttribute('aria-busy', String(!!controller));
  }
  function invalidate(message) {
    epoch++; controller?.abort(); controller = null; data = null; consent.checked = false;
    list.replaceChildren(); more.hidden = true; status.textContent = message; controls();
  }
  function crop(url, bounds, title) {
    const figure = node('figure', ''); figure.style.margin = '0';
    const canvas = document.createElement('canvas'); canvas.width = 160; canvas.height = 110;
    canvas.style.cssText = 'width:100%;height:auto;display:block;border:1px solid var(--ui-muted)';
    canvas.setAttribute('aria-label', title);
    const image = new Image(), version = epoch;
    image.onload = () => {
      if (version !== epoch) return;
      const [x, y, r, b] = bounds, left = Math.max(0, x-10), top = Math.max(0, y-10);
      const w = Math.min(image.width, r+10)-left, h = Math.min(image.height, b+10)-top;
      const scale = Math.min(canvas.width/w, canvas.height/h), ctx = canvas.getContext('2d');
      // Same crop and scale for both versions; transparency shown on a neutral checker.
      for (let yy=0; yy<110; yy+=10) for (let xx=0; xx<160; xx+=10) {
        ctx.fillStyle = ((xx+yy)/10)%2 ? '#e5ebec' : '#ffffff'; ctx.fillRect(xx, yy, 10, 10);
      }
      ctx.drawImage(image, left, top, w, h, (160-w*scale)/2, (110-h*scale)/2, w*scale, h*scale);
    };
    image.src = url; figure.append(canvas, node('figcaption', title)); return figure;
  }
  function page() {
    if (!data || snapshot !== state()) return;
    for (const region of data.regions.slice(shown, shown+5)) {
      const article = node('article', ''); article.style.cssText = 'margin:1rem 0;overflow-wrap:anywhere';
      const finding = data.ai.findings.find(item => item.region_id === region.id);
      article.append(node('strong', finding ? 'AI suggestion: '+finding.detail : region.removed_pixels ? 'Is this part missing?' : 'Does this change look right?'));
      if (finding) article.append(node('p', finding.observation+' Check the pictures before deciding.'));
      article.append(node('p', `${region.position} · ${region.width_mm} × ${region.height_mm} mm`));
      const pair = node('div', ''); pair.style.cssText = 'display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0.5rem';
      pair.append(crop(data.reference, region.bounds, 'Your picture'), crop(data.artwork, region.bounds, 'Before stitching'));
      const locate = button('Show me', 'review-region-'+region.id);
      locate.addEventListener('click', () => { if (snapshot === state() && !studio.isBusy()) studio.focusBounds(region.bounds); });
      article.prepend(pair); article.append(locate); list.append(article);
    }
    shown = Math.min(shown+5, data.regions.length);
    more.hidden = shown >= data.regions.length;
    more.textContent = `Show more differences (${shown} of ${data.regions.length})`;
  }
  function render(result) {
    data = result; shown = 0; list.replaceChildren(); page();
    status.textContent = (result.total_regions
      ? `${result.total_regions} parts look different. Compare the pictures below; a colour change may be intentional.`
      : 'No clear differences found in this check. Small details can still be missed.')
      + ' This checks the picture, not stitches. Nothing was changed.';
    if (result.total_regions > result.shown_regions) status.textContent += ` Showing the largest ${result.shown_regions}.`;
    if (result.ai.status === 'completed') cloudStatus.textContent = `AI reviewed ${result.ai.regions_reviewed} candidate areas${result.ai.cached ? ' (reused result)' : ''}. Suggestions may be wrong; this does not certify the design.`;
    if (result.ai.status === 'not_needed') cloudStatus.textContent = 'No candidate areas were sent. No AI call was made.';
    if (result.ai.status === 'unavailable') cloudStatus.textContent = result.ai.message;
  }
  async function run(mode) {
    if (controller || studio.isBusy() || !ready) return;
    if (mode === 'ai' && (!cloudReady || !consent.checked || !data || snapshot !== state())) return;
    const version = ++epoch, captured = state(), active = new AbortController(); controller = active;
    const body = {options: JSON.parse(captured), mode};
    if (mode === 'ai') Object.assign(body, {consent: true, snapshot: data.snapshot});
    consent.checked = false;
    controls(); status.textContent = mode === 'ai' ? 'AI is reviewing these differences. Your design is unchanged.' : 'Comparing artwork. Your design is unchanged.';
    const timer = setTimeout(() => active.abort(), 100000);
    try {
      const response = await fetch(endpoint, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body), signal: active.signal});
      const result = await response.json();
      if (version !== epoch || captured !== state()) return;
      if (!response.ok && !result.regions) throw Error(result.error || 'Review unavailable. Try again; your design is unchanged.');
      snapshot = captured; render(result);
    } catch (error) {
      if (version === epoch) status.textContent = error.name === 'AbortError' ? 'Review timed out. Try again; your design is unchanged. A cloud request already sent may still be charged.' : error.message;
    } finally {
      clearTimeout(timer);
      if (controller === active) controller = null;
      controls();
    }
  }
  check.addEventListener('click', () => run('local'));
  ai.addEventListener('click', () => run('ai'));
  cancel.addEventListener('click', () => invalidate('Review cancelled. Your design is unchanged. A cloud request already sent may still be charged.'));
  more.addEventListener('click', page); consent.addEventListener('change', controls);
  window.addEventListener('studio:changed', () => { ready = false; invalidate('Design changed. Wait for the preview, then check again.'); });
  window.addEventListener('studio:preview', () => { ready = true; controls(); });
  window.addEventListener('pagehide', () => { epoch++; controller?.abort(); });
  // Local checks do not depend on readiness or any remote call.
  const readyController = new AbortController();
  const readyTimer = setTimeout(() => readyController.abort(), 10000);
  fetch(endpoint, {signal: readyController.signal}).then(response => {
    if (!response.ok) throw Error('unavailable'); return response.json();
  }).then(result => { cloudReady = result.ai_available; cloudStatus.textContent = result.message; controls(); })
    .catch(() => { cloudStatus.textContent = 'AI availability could not be checked. Local comparison is still available.'; })
    .finally(() => clearTimeout(readyTimer));
})();
