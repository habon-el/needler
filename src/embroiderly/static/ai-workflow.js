/* Automatic visual review is opt-in. Existing studio/assistant own every edit. */
window.addEventListener('DOMContentLoaded', () => {
  'use strict';
  const studio = window.embroideryStudio, config = window.preparationConfig;
  if (!studio || !config || window.nativeTextConfig) return;
  const preference = 'embroiderly.autoVisualReview.v1';
  const endpoint = '/ai-workflow/' + encodeURIComponent(config.name);
  const node = (tag, text, id) => { const n = document.createElement(tag); if (text) n.textContent = text; if (id) n.id = id; return n; };
  const button = (text, fn) => { const b = node('button', text); b.type = 'button'; b.addEventListener('click', fn); return b; };
  const root = node('section', null, 'aiWorkflow'); root.setAttribute('aria-label', 'Picture review');
  const header = node('div'); header.className = 'ai-workflow-header';
  const heading = node('strong', 'AI picture review');
  const toggle = node('input', null, 'autoAiReview'); toggle.type = 'checkbox';
  try { toggle.checked = localStorage.getItem(preference) === 'yes'; } catch (_) { /* Session-only consent if storage unavailable. */ }
  const permission = node('label'); permission.append(toggle, document.createTextNode(' Auto-review · paid'));
  toggle.setAttribute('aria-describedby', 'autoAiSharing');
  header.append(heading, permission);
  const sharing = node('p', 'Auto-review sends pictures to OpenAI (paid). Your spending caps apply.', 'autoAiSharing');
  const status = node('p', 'Review is off. Manual editing still works.', 'autoAiStatus'); status.setAttribute('role', 'status');
  const explanation = node('details'); explanation.append(node('summary', 'Privacy & limits'));
  explanation.append(node('p', 'This choice is remembered on this browser. Turn it off to stop future requests; already-sent requests may still cost money. Reviews are saved locally so reloads do not repeat a paid review. AI can miss details; highlights are approximate, not cutting outlines. File checks and a sew-out are still needed.'));
  const reviews = node('div', null, 'autoAiResults');
  const retry = button('Retry review', () => { if (failed) { attempts.delete(failed.key); run(failed.stage, true); } }); retry.id = 'autoAiRetry'; retry.hidden = true;
  const local = node('div', null, 'autoLocalCheck');
  const localStatus = node('span', 'Local detail checks run with each preview. ');
  const localReview = button('Review details', () => {
    window.DesignWorkflow?.show('edit'); window.embroideryWorkspace?.showTopic('review');
    const owner = document.getElementById('detailStatus')?.closest('details');
    if (owner) { owner.open = true; owner.scrollIntoView({block: 'nearest'}); }
  });
  local.append(localStatus, localReview);
  const resultsDisclosure = node('details', null, 'autoAiDetails');
  resultsDisclosure.append(node('summary', 'Review results'), reviews, explanation);
  root.append(header, sharing, status, retry, local, resultsDisclosure);
  document.getElementById('stitchStatus').after(root);
  let active = null, enabled = null, failed = null, revision = 0, finalCard = null;
  const attempts = new Set();
  const snapshot = () => { const o = studio.snapshot(); delete o.interactions; return JSON.stringify(o); };
  const keyFor = stage => stage === 'upload' ? 'upload' : 'finished:' + snapshot();
  function paint(result) {
    const card = node('details'); card.className = 'ai-review-card'; card.open = false;
    card.dataset.stage = result.stage;
    card.append(node('summary', (result.stage === 'upload' ? '1 · Your picture' : '2 · Finished stitches') + ' · ' + (result.details.length ? result.details.length + ' details to review' : 'Review ready')));
    card.append(node('p', result.summary));
    const list = node('div'); list.className = 'ai-review-details';
    for (const detail of result.details) {
      const row = node('article');
      const thumb = node('canvas'); thumb.width = 120; thumb.height = 80;
      thumb.setAttribute('aria-label', 'Approximate location: ' + detail.label);
      const image = new Image();
      image.onload = () => {
        const ctx = thumb.getContext('2d'), [x,y,r,b] = detail.bounds;
        const left = Math.max(0,x-8), top = Math.max(0,y-8);
        const w = Math.min(image.width,r+8)-left, h = Math.min(image.height,b+8)-top;
        if (w <= 0 || h <= 0) return;
        for (let yy=0; yy<80; yy+=10) for (let xx=0; xx<120; xx+=10) {
          ctx.fillStyle = (xx+yy)%20 ? '#e5ebec' : '#ffffff'; ctx.fillRect(xx,yy,10,10);
        }
        const scale = Math.min(120/w,80/h);
        ctx.drawImage(image,left,top,w,h,(120-w*scale)/2,(80-h*scale)/2,w*scale,h*scale);
      };
      image.src = config.original;
      row.append(thumb, node('strong', detail.label), node('p', detail.note));
      const actions = node('div'); actions.className = 'ai-detail-actions';
      const note = node('p'); note.className = 'muted'; note.setAttribute('role', 'status');
      const focus = () => {
        window.DesignWorkflow?.show('edit'); studio.focusBounds(detail.bounds); studio.review('original');
        document.getElementById('original').scrollIntoView({block: 'nearest'});
      };
      actions.append(button('Show me', focus));
      for (const intent of ['Keep', 'Remove']) {
        const b = button(intent, () => {
          const question = intent + ' this detail: ' + detail.label + '. ' + detail.note + ' Keep other wanted details unchanged. Show me a draft before applying; if you cannot do this precisely, explain how to select it manually.';
          const ok = window.embroideryAI?.setRequest(question);
          note.textContent = ok ? 'Request prepared in the assistant—not applied. Review it before sending.' : 'Your existing prompt is kept. Finish or clear it before preparing this request.';
        });
        b.title = intent + ' this detail: prepare a request, then review before applying'; actions.append(b);
      }
      actions.append(button('Fix manually', () => {
        focus(); window.embroideryWorkspace?.showTopic('selection'); studio.selectTool('polygon');
        note.textContent = 'Draw the exact outline to keep, or choose Erase area. The AI box is only a guide.';
      }));
      row.append(actions, note); list.append(row);
    }
    card.append(list, node('small', result.model + (result.cached ? ' · saved review' : ' · review complete') + ' · AI advice, not approval'));
    if (result.stage === 'finished') { finalCard?.remove(); finalCard = card; }
    else reviews.querySelector('[data-stage="upload"]')?.remove();
    reviews.append(card);

    updateControls();
  }
  function updateControls() {
    resultsDisclosure.querySelector('summary').textContent = 'Review results · ' + reviews.children.length + (reviews.children.length === 1 ? ' review' : ' reviews');
    root.setAttribute('aria-busy', String(!!active));
    localReview.disabled = studio.isBusy();
    retry.disabled = !!active || studio.isBusy() || !toggle.checked;
    reviews.querySelectorAll('button').forEach(b => { b.disabled = studio.isBusy() || !!window.embroideryAI?.isBusy(); });
  }
  async function run(stage, explicitRetry = false) {
    const key = keyFor(stage);
    if (active || !toggle.checked || !enabled || attempts.has(key) || (stage === 'finished' && (!studio.hasPlayback() || studio.isBusy()))) return;
    const captured = snapshot(), version = revision, controller = new AbortController();
    active = {controller, stage}; attempts.add(key); failed = null; retry.hidden = true; updateControls();
    status.textContent = stage === 'upload' ? 'AI is looking at your picture… You can keep editing.' : 'Comparing your picture, approved artwork and saved stitches…';
    const timeout = setTimeout(() => controller.abort(), 180000);
    try {
      let result;
      for (let poll = 0; poll < 65; poll++) {
        const response = await fetch(endpoint, {method: 'POST', headers: {'Content-Type': 'application/json'}, signal: controller.signal,
          body: JSON.stringify({stage, options: JSON.parse(captured), consent: true, retry: explicitRetry && poll === 0})});
        result = await response.json();
        if (!response.ok) throw Error(result.error || 'Review unavailable. Use the manual tools.');
        if (response.status !== 202) break;
        status.textContent = 'This review is already running. Waiting without another paid call…';
        await new Promise(resolve => setTimeout(resolve, 2000));
        if (controller.signal.aborted) throw new DOMException('Stopped', 'AbortError');
      }
      if (!toggle.checked || (stage === 'finished' && (version !== revision || captured !== snapshot() || !studio.hasPlayback()))) return;
      if (result.state !== 'completed') throw Error('Review is still running. Retry later to check its result.');
      paint(result);
      status.textContent = stage === 'upload' ? 'Choose what to keep, or ask the assistant. Nothing changed.' : (result.details.length ? result.details.length + ' possible differences. Open Review results; nothing changed.' : 'Comparison ready. AI may miss details; machine-file checks still apply.');
    } catch (error) {
      if (toggle.checked && (stage === 'upload' || version === revision)) {
        failed = {key, stage}; retry.hidden = false;
        status.textContent = error.name === 'AbortError' ? 'Stopped waiting. Nothing changed; a sent review may still cost money.' : error.message;
      }
    } finally {
      clearTimeout(timeout); active = null; updateControls();
      if (!failed) schedule();
    }
  }
  function schedule() {
    updateControls();
    if (!toggle.checked || !enabled || active || failed) return;
    if (!attempts.has('upload')) run('upload');
    else if (studio.hasPlayback() && !studio.isBusy()) run('finished');
  }
  function changedPermission() {
    if (!toggle.checked) {
      active?.controller.abort(); status.textContent = 'Auto-review is off. Already-sent requests may still cost money.';
      retry.hidden = true;
    } else { attempts.clear(); failed = null; schedule(); }
    updateControls();
  }
  toggle.addEventListener('change', () => {
    try { localStorage.setItem(preference, toggle.checked ? 'yes' : 'no'); } catch (_) { /* Still works for this page. */ }
    changedPermission();
  });
  window.addEventListener('storage', e => { if (e.key === preference || e.key === null) { toggle.checked = e.newValue === 'yes'; changedPermission(); } });
  window.addEventListener('studio:changed', () => {
    revision++; finalCard?.remove(); finalCard = null;
    for (const key of attempts) if (key.startsWith('finished:')) attempts.delete(key);
    localStatus.textContent = 'Artwork changed; updating detail checks… ';
    if (active?.stage === 'finished') active.controller.abort();
    if (failed?.stage === 'finished') { failed = null; retry.hidden = true; }
    if (toggle.checked) status.textContent = 'Design changed. Make new stitches for a fresh comparison.';
    updateControls();
  });
  window.addEventListener('studio:preview', event => {
    const report = event.detail.report, audit = report.detail_loss;
    const pending = (report.cleanup_review || []).filter(item => item.decision === 'pending').length;
    const changes = audit?.findings?.length || 0, edges = audit?.boundary?.length || 0;
    localStatus.textContent = audit
      ? pending + ' cleanup choices · ' + changes + ' possible changed details · ' + edges + ' edges to check. '
      : 'Detail checks are unavailable for this preview. ';
    localReview.disabled = studio.isBusy();
    schedule();
  });
  window.addEventListener('studio:stitch-state', event => {
    if (event.detail.state === 'generating') {
      revision++; finalCard?.remove(); finalCard = null;
      for (const key of attempts) if (key.startsWith('finished:')) attempts.delete(key);
      if (active?.stage === 'finished') active.controller.abort();
    }
    schedule();
  });
  window.addEventListener('studio:controls', schedule);
  window.addEventListener('pagehide', () => { active?.controller.abort(); });
  fetch(endpoint, {signal: AbortSignal.timeout(10000)}).then(async response => {
    if (!response.ok) throw Error('Restart the app to enable automatic picture review.');
    const data = await response.json(); enabled = data.available;
    if (!enabled) { status.textContent = data.message || 'AI is unavailable. Check your server key and spending limits.'; toggle.disabled = true; }
    else schedule();
  }).catch(error => { status.textContent = error.message; toggle.disabled = true; });
});
