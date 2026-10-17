/* One preference service; no design values are written by this panel. */
(() => {
  'use strict';
  const root = document.documentElement;
  const dark = matchMedia('(prefers-color-scheme: dark)');
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  let state, trigger;
  const dialog = document.createElement('dialog');
  dialog.className = 'settings-panel';
  dialog.setAttribute('aria-labelledby', 'settings-title');
  dialog.innerHTML = `<header><h1 id="settings-title">Settings</h1><button type="button" data-close aria-label="Close settings">Close</button></header>
    <p class="settings-intro">Preferences for this computer. Your design stays open.</p>
    <section><h2>Appearance</h2>
    <label>Measurement units<select name="units"><option value="mm">Millimetres</option><option value="in">Inches</option></select></label>
    <label>Theme<select name="theme"><option value="system">Match my computer</option><option value="dark">Dark</option><option value="light">Light</option></select></label>
    <label>Detail level<select name="detail"><option value="simple">Simple</option><option value="standard">Standard</option><option value="expert">Expert</option></select></label>
    <p>Changes which explanations open by default. All tools remain available.</p>
    <label>Reduce motion<select name="motion"><option value="system">Match my computer</option><option value="on">On</option><option value="off">Off</option></select></label>
    <label>Interface size<select name="density"><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></label></section>
    <section><h2>Account</h2><p>Not signed in — your designs are saved on this computer only.</p><button disabled>Create account</button><p>Coming soon</p></section>
    <p class="settings-feedback" role="status" aria-live="polite"></p><button type="button" data-retry hidden>Reload settings</button>`;
  document.body.append(dialog);
  dialog.addEventListener('keydown', event => event.stopPropagation());
  const feedback = dialog.querySelector('.settings-feedback');
  const fields = [...dialog.querySelectorAll('select')];
  const retry = dialog.querySelector('[data-retry]');
  function apply(values) {
    root.dataset.theme = values.theme === 'system' ? (dark.matches ? 'dark' : 'light') : values.theme;
    root.dataset.motion = values.motion === 'system' ? (motion.matches ? 'reduce' : 'normal') : (values.motion === 'on' ? 'reduce' : 'normal');
    root.dataset.density = values.density;
    root.dataset.units = values.units || 'mm';
    // Disclosure only. Never hide controls, clear inputs or change design options.
    if (root.dataset.detail !== values.detail) {
      document.querySelectorAll('.topic-panel details').forEach(d => {
        if(d.dataset.disclosure === 'manual') return; // Workflow-owned help stays closed until opened.
        d.open = values.detail === 'expert' || (values.detail === 'standard' && d.parentElement.classList.contains('topic-panel'));
      });
      root.dataset.detail = values.detail;
    }
    fields.forEach(field => { field.value = values[field.name]; });
  }
  async function load() {
    fields.forEach(f => { f.disabled = true; }); retry.hidden = true;
    feedback.textContent = 'Loading settings…';
    try {
      const response = await fetch('/api/settings', {cache:'no-store', signal:AbortSignal.timeout(12000)});
      if (!response.ok) throw Error('Settings could not load. Your design is unchanged.');
      state = await response.json(); apply(state.values);
      fields.forEach(f => { f.disabled = false; }); feedback.textContent = '';
    } catch (error) { feedback.textContent = error.message; retry.hidden = false; }
  }
  fields.forEach(field => field.addEventListener('change', async () => {
    const patch = {[field.name]: field.value};
    fields.forEach(f => { f.disabled = true; }); feedback.textContent = 'Saving…'; retry.hidden = true;
    try {
      const response = await fetch('/api/settings', {method:'PATCH', signal:AbortSignal.timeout(12000), headers:{'Content-Type':'application/json'}, body:JSON.stringify({values:patch, revision:state.revision})});
      const result = await response.json();
      if (!response.ok) throw Error(result.error || 'Settings could not save.');
      state = result; apply(state.values); feedback.textContent = 'Saved on this computer';
      fields.forEach(f => { f.disabled = false; });
    } catch (error) {
      apply(state.values); feedback.textContent = error.message; retry.hidden = false;
    }
  }));
  [dark, motion].forEach(query => query.addEventListener('change', () => { if (state) apply(state.values); }));
  retry.onclick = load;
  dialog.querySelector('[data-close]').onclick = () => dialog.close();
  dialog.addEventListener('close', () => trigger?.focus());
  const button = document.createElement('button'); button.type = 'button'; button.id = 'openSettings';
  button.innerHTML = '<svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path d="M3 5h14M3 10h14M3 15h14M7 3v4m6 1v4m-7 1v4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg><span>Settings</span>';
  button.onclick = () => { trigger = document.activeElement; dialog.showModal(); load(); };
  (document.querySelector('header .actions') || document.querySelector('main')).append(button);
  load();
})();
