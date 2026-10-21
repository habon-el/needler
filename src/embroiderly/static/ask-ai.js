/* One prompt owner. AI drafts are previews; existing studio owns Apply/Undo/stitches. */
(() => {
  'use strict';
  const studio = window.embroideryStudio, config = window.preparationConfig;
  if (!studio || !config || window.nativeTextConfig) return;
  const el = (tag, text = '', id) => { const n = document.createElement(tag); n.textContent = text; if (id) n.id = id; return n; };
  const button = (text, id, fn) => { const b = el('button', text, id); b.type = 'button'; b.addEventListener('click', fn); return b; };
  const endpoint = '/design-review/' + encodeURIComponent(config.name), draftEndpoint = '/ai-draft/' + encodeURIComponent(config.name);
  let ready = false, cloudReady = false, draftReady = false, mode = 'draft', history = [], controller = null, epoch = 0, job = null, proposal = null, applying = false, availabilityInfo = null;
  const state = () => JSON.stringify(studio.snapshot());
  const root = el('section', '', 'askAiPanel'); root.setAttribute('aria-label', 'AI assistant');
  const modes = el('div', '', 'askAiModes'); modes.setAttribute('aria-label', 'AI task');
  const draftMode = button('Make a draft', 'askAiDraftMode', () => switchMode('draft'));
  const adviceMode = button('Ask a question', 'askAiAdviceMode', () => switchMode('ask')); modes.append(draftMode, adviceMode);
  const availability = el('p', 'Checking connection…', 'askAiAvailability'); availability.setAttribute('role', 'status');
  const label = el('label', 'What would you like?', 'askAiLabel'); label.htmlFor = 'askAiQuestion';
  const input = el('textarea', '', 'askAiQuestion'); input.rows = 3; input.maxLength = 1000; input.style.resize = 'none';
  input.setAttribute('aria-describedby', 'askAiHelp askAiStatus');
  const examples = el('div', '', 'askAiExamples');
  // These are editable prompt starters, never provider calls or approval.
  for (const [id, title, task, question] of [
    ['askAiBackgroundExample', 'Remove background', 'draft', 'Remove the background and keep the main subject.'],
    ['askAiDetailsExample', 'Keep fine details', 'draft', 'Keep the main subject, including fine hair and face details, and remove the background.'],
    ['askAiReviewExample', 'Find missing details', 'ask', 'Compare the original with the stitch artwork. What details might be missing or changed? Do not change anything.'],
  ]) {
    examples.append(button(title, id, () => {
      if (controller) return;
      switchMode(task); input.value = question; input.focus(); update();
    }));
  }
  const consent = document.createElement('input'); consent.type = 'checkbox'; consent.id = 'askAiConsent';
  const permission = el('label', '', 'askAiPermission'); permission.append(consent, document.createTextNode(' Share artwork + prompt with OpenAI (paid).'));
  const help = el('details', '', 'askAiDetails'); help.append(el('summary', 'How it works'));
  help.append(el('p', 'Draft: up to 4 AI calls to select, review and correct (at most 2 correction rounds). Images and your prompt are shared. Questions include the last 3 exchanges. Your spending caps apply. No keys or passwords in prompts.', 'askAiHelp'),
    el('p', 'Drafts expire after 30 minutes or a server restart. Chat clears on reload. AI can miss details; file checks and a sew-out are still needed.', 'askAiRetention'));
  const send = button('Preview draft', 'askAiSend', ask); send.className = 'primary';
  const cancel = button('Stop', 'askAiCancel', () => stop('Stopped. A sent request may still cost money.'));
  const actions = el('div', '', 'askAiActions'); actions.append(send, cancel);
  const status = el('p', 'Nothing changes until you approve.', 'askAiStatus'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  const log = el('div', '', 'askAiMessages'); log.setAttribute('aria-label', 'AI results');
  const reset = button('Clear', 'askAiClear', () => { if (controller) return; history = []; input.value = ''; log.replaceChildren(); hideDraft(); consent.checked = false; update(); });
  root.append(modes, label, input, examples, permission, actions, availability, status, log, reset, help);
  document.querySelector('.inspector h1').after(root);
  const visual = el('section', '', 'aiDraftPreview'); visual.hidden = true; visual.setAttribute('aria-label', 'Draft comparison');
  document.querySelector('.panels').before(visual);
  function hideDraft() { proposal = null; visual.hidden = true; visual.replaceChildren(); document.body.classList.remove('ai-draft-visible'); root.classList.remove('has-draft'); studio.redraw(); }
  function switchMode(next) {
    if (controller) return;
    mode = next; consent.checked = false;
    showAvailability();
    input.placeholder = mode === 'draft' ? 'Keep the logo, remove the background, 100 mm wide…' : 'What details might be missing?';
    update();
  }
  function update() {
    const busy = !!controller;
    send.textContent = mode === 'draft' ? 'Preview draft' : 'Send question';
    send.disabled = busy || !ready || !(mode === 'draft' ? draftReady : cloudReady) || studio.isBusy() || !input.value.trim() || !consent.checked;
    input.disabled = busy; consent.disabled = busy; cancel.hidden = !busy;
    draftMode.disabled = adviceMode.disabled = busy;
    draftMode.setAttribute('aria-pressed', String(mode === 'draft')); adviceMode.setAttribute('aria-pressed', String(mode === 'ask'));
    examples.querySelectorAll('button').forEach(b => b.disabled = busy);
    log.querySelectorAll('button').forEach(b => b.disabled = busy || studio.isBusy() || (b.id === 'aiDraftApply' && proposal?.data.selection_review && proposal.data.selection_review !== 'acceptable'));
    reset.hidden = !history.length && !input.value && !proposal; reset.disabled = busy;
    root.setAttribute('aria-busy', String(busy));
    root.classList.toggle('is-waiting', busy);
    input.style.height = 'auto'; input.style.height = Math.max(88, Math.min(180, input.scrollHeight)) + 'px';
  }
  function cancelJob(id) { if (id) fetch(draftEndpoint + '/' + id, {method: 'DELETE', keepalive: true}).catch(() => {}); }
  function stop(message) { epoch++; if (controller) cancelJob(job); controller?.abort(); controller = null; job = null; consent.checked = false; status.textContent = message; update(); }
  async function json(url, args = {}) {
    const response = await fetch(url, args); let data;
    try { data = await response.json(); } catch (_) { throw Error('Restart the updated app, then try again.'); }
    if (!response.ok) throw Error(data.error || data.ai?.message || 'The request did not finish. Your design is unchanged.');
    return data;
  }
  function showProposal(data, captured, question) {
    proposal = {data, captured, question}; root.classList.add('has-draft'); log.replaceChildren();
    log.append(el('strong', data.subject), el('p', data.subject_width_mm + ' × ' + data.subject_height_mm + ' mm subject'));
    const notices = [];
    if (data.method !== 'SAM2') notices.push('SAM2 unavailable; a basic cutout tool was used. Check the edges.');
    if (data.review_error) notices.push(data.review_error);
    if (data.review?.summary) notices.push(data.review.summary);
    notices.push(...(data.review?.concerns || []));
    notices.push(...(data.review?.artwork_concerns || []).map(t => 'Thread plan: ' + t));
    if (data.selection_review && data.selection_review !== 'acceptable') notices.push('Cutout still needs checking. Keep editing before making stitches.');
    if (data.warnings.boundary) notices.push(data.warnings.boundary + ' edge areas need checking in the cutout.');
    if (data.warnings.details) notices.push(data.warnings.details + ' details may have changed. Compare the thread plan.');
    if (data.warnings.generation) notices.push(data.warnings.generation + ' small areas cannot be stitched yet. Apply to edit them; generation remains blocked.');
    for (const text of notices) log.append(el('p', text));
    log.append(el('p', 'Draft only — not stitches. Check both pictures before applying.'));
    const apply = button('Use & make stitches', 'aiDraftApply', () => approve(true)); apply.className = 'primary';
    const edit = button('Use & keep editing', 'aiDraftEdit', () => approve(false));
    const revise = button('Change my request', 'aiDraftRevise', () => { hideDraft(); log.replaceChildren(); input.focus(); update(); });
    const discard = button('Discard', 'aiDraftDiscard', () => { hideDraft(); log.replaceChildren(); status.textContent = 'Discarded. Your design is unchanged.'; update(); });
    log.append(apply, edit, revise, discard);
    const evidence = el('details'); evidence.append(el('summary', 'AI details'));
    evidence.append(el('p', 'Model: ' + data.model), el('p', 'Cutout tool: ' + data.method + ' · ' + (data.correction_rounds || 0) + ' correction rounds'));
    const usage = data.usage || [];
    evidence.append(el('p', usage.length + ' completed AI responses · ' +
      usage.reduce((n,u) => n + (Number(u.input_tokens) || 0), 0) + ' input tokens · ' +
      usage.reduce((n,u) => n + (Number(u.output_tokens) || 0), 0) + ' output tokens. ' +
      'A reused draft does not make another AI call. Failed calls may also be billed.'));
    log.append(evidence);
    const heading = el('div', '', 'aiDraftHeading'); heading.append(el('strong', 'Review your draft'));
    const cut = button('Cutout', 'aiDraftCutout', () => change('cutout')), art = button('Thread plan', 'aiDraftArtwork', () => change('artwork'));
    heading.append(cut, art); visual.replaceChildren(heading);
    const pair = el('div', '', 'aiDraftPair');
    function figure(src, title) { const f = el('figure'), im = el('img'); im.src = src; im.alt = title; f.append(im, el('figcaption', title)); return f; }
    const right = figure(data.cutout, 'Proposed cutout'); pair.append(figure(data.original, 'Original'), right); visual.append(pair);
    function change(view) {
      right.querySelector('img').src = data[view]; right.querySelector('img').alt = view === 'cutout' ? 'Proposed cutout' : 'Prepared artwork — not stitches';
      right.querySelector('figcaption').textContent = right.querySelector('img').alt;
      cut.setAttribute('aria-pressed', String(view === 'cutout')); art.setAttribute('aria-pressed', String(view === 'artwork'));
    }
    change('cutout'); visual.hidden = false; document.body.classList.add('ai-draft-visible');
  }
  async function approve(generate) {
    if (!proposal || controller || studio.isBusy()) return;
    if (generate && proposal.data.selection_review && proposal.data.selection_review !== 'acceptable') return;
    const p = proposal;
    if (state() !== p.captured) { hideDraft(); status.textContent = 'Design changed. Make a new draft.'; return; }
    const active = new AbortController(), version = ++epoch; controller = active; update();
    const timer = setTimeout(() => active.abort(), 15000);
    try {
      const checked = await json(draftEndpoint + '/' + p.data.id, {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({options: JSON.parse(p.captured), question: p.question}), signal: active.signal});
      if (version !== epoch || state() !== p.captured) return;
      controller = null; applying = true; hideDraft(); input.value = ''; log.replaceChildren();
      if (generate) studio.acceptRefinement(checked.patch); else studio.apply(checked.patch);
      status.textContent = generate ? 'Draft applied. Making stitches with the existing checks…' : 'Draft applied. Undo restores the previous design.';
    } catch (error) { if (version === epoch) status.textContent = error.name === 'AbortError' ? 'Approval timed out. Nothing was applied; try again.' : error.message; }
    finally { clearTimeout(timer); applying = false; if (controller === active) controller = null; update(); }
  }
  async function ask() {
    if (controller || studio.isBusy() || !ready || !(mode === 'draft' ? draftReady : cloudReady)) return;
    const question = input.value.trim();
    if (!question || question.length > 1000) { input.setAttribute('aria-invalid', 'true'); status.textContent = 'Write 1–1,000 characters.'; input.focus(); return; }
    if (!consent.checked) { status.textContent = 'Allow sharing before sending.'; consent.focus(); return; }
    if (/\bsk-[A-Za-z0-9_-]{16,}/.test(question)) { input.setAttribute('aria-invalid', 'true'); status.textContent = 'Remove the API key from your question. Keys belong only in the server terminal.'; return; }
    hideDraft();
    const captured = state(), version = ++epoch, active = new AbortController(), task = mode; controller = active;
    consent.checked = false; input.removeAttribute('aria-invalid'); update(); status.textContent = task === 'draft' ? 'Starting your draft…' : 'AI is looking at your question…';
    const timer = setTimeout(() => active.abort(), 180000);
    try {
      if (task === 'draft') {
        // Do not abort the initial submission: retain its ID to cancel server work
        // if the user stops or edits while the request is being acknowledged.
        let result = await json(draftEndpoint, {method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({options: JSON.parse(captured), question, consent: true}), signal: AbortSignal.timeout(20000)});
        if (version !== epoch || captured !== state()) { cancelJob(result.id); return; }
        job = result.id;
        while (!['ready', 'question', 'failed', 'cancelled'].includes(result.state)) {
          status.textContent = result.message;
          await new Promise(resolve => setTimeout(resolve, 650));
          if (active.signal.aborted) throw new DOMException('Aborted', 'AbortError');
          result = await json(draftEndpoint + '/' + job, {signal: active.signal});
          if (version !== epoch || captured !== state()) return;
        }
        if (result.state === 'ready') { showProposal(result, captured, question); status.textContent = 'Compare the pictures. Nothing applied yet.'; }
        else if (result.state === 'question') { log.replaceChildren(el('p', result.message)); status.textContent = 'Add a little more detail, then try again.'; }
        else throw Error(result.message);
        availability.textContent = result.model || 'AI draft';
      } else {
        const result = await json(endpoint, {method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({mode: 'ask', options: JSON.parse(captured), question, history, consent: true}), signal: active.signal});
        if (version !== epoch || captured !== state()) return;
        if (result.ai?.status !== 'completed' || typeof result.ai.answer !== 'string') throw Error(result.ai?.message || 'AI could not answer.');
        history.push({role: 'user', content: question}, {role: 'assistant', content: result.ai.answer}); history = history.slice(-6); log.replaceChildren();
        for (const item of history) { const article = el('article'); article.className = 'ask-ai-message'; article.dataset.speaker = item.role; article.append(el('strong', item.role === 'user' ? 'You' : 'AI · advice only'), el('p', item.content)); log.append(article); }
        input.value = ''; availability.textContent = result.ai.model + (result.ai.cached ? ' · reused answer' : ' · live answer'); status.textContent = 'Answer ready. No design changes.';
      }
    } catch (error) {
      cancelJob(job);
      if (version === epoch) status.textContent = error.name === 'AbortError' ? 'Stopped waiting. Your prompt is kept; a sent request may still cost money.' : error.message;
    } finally { clearTimeout(timer); if (controller === active) controller = null; update(); }
  }
  input.addEventListener('input', () => { input.removeAttribute('aria-invalid'); update(); });
  input.addEventListener('keydown', event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && !event.isComposing) { event.preventDefault(); ask(); } });
  consent.addEventListener('change', update);
  window.addEventListener('studio:changed', () => { ready = false; history = []; log.replaceChildren(); hideDraft(); if (!applying) stop('Design changed. Your prompt is kept; make a fresh draft.'); });
  window.addEventListener('studio:preview', () => { ready = true; update(); }); window.addEventListener('studio:controls', update);
  window.addEventListener('beforeunload', event => { if (input.value.trim()) { event.preventDefault(); event.returnValue = ''; } });
  window.addEventListener('pagehide', () => { epoch++; controller?.abort(); cancelJob(job); });
  document.querySelectorAll('[data-view],#run,.tools button').forEach(b => b.addEventListener('click', () => { if (proposal) { hideDraft(); log.replaceChildren(); status.textContent = 'Draft dismissed. Nothing applied.'; } }));
  function showAvailability() {
    if (!availabilityInfo) return;
    const [a, d] = availabilityInfo, item = mode === 'draft' ? d : a;
    availability.textContent = (mode === 'draft' ? draftReady : cloudReady)
      ? 'GPT-5.4 mini · ready when you send'
      : item.status === 'fulfilled' ? (item.value.message || item.value.ai_message || 'AI is unavailable. Check server settings.')
      : 'Restart the app to enable AI drafts.';
  }
  Promise.allSettled([json(endpoint, {signal: AbortSignal.timeout(10000)}), json(draftEndpoint, {signal: AbortSignal.timeout(10000)})]).then(([a, d]) => {
    cloudReady = a.status === 'fulfilled' && a.value.ai_available && a.value.questions_supported;
    draftReady = d.status === 'fulfilled' && d.value.available && d.value.supported;
    availabilityInfo = [a, d]; showAvailability(); update();
    // Clean UI: when no AI service is set up on this computer, the assistant button is
    // hidden instead of opening a form that cannot send. "Digitize for me" stays.
    document.documentElement.dataset.aiAssistant = cloudReady || draftReady ? 'on' : 'off';
  });
  // Review cards compose a request here; they never send it or approve edits.
  window.embroideryAI = {
    isBusy: () => !!controller,
    setRequest: (question) => {
      if (controller || input.value.trim()) return false;
      switchMode('draft'); input.value = question; update();
      document.getElementById('workflowAskAI')?.click(); input.focus();
      return true;
    }
  };
  switchMode('draft');
})();
