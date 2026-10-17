/* Presentation only: move existing controls, never clone their settings/state. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const inspector = document.querySelector('.inspector');
  if (!inspector || !window.embroideryStudio) return;
  const paths = {
    chat: 'M4 4h16v12H9l-5 4V4zM8 8h8M8 12h5',
    select: 'M5 3H3v4m14-4h4v4M3 17v4h4m14-4v4h-4M8 8h8v8H8z',
    outline: 'M5 5l13-2 3 13-12 5-6-9zM5 5h.01M18 3h.01M21 16h.01M9 21h.01',
    erase: 'M4 14l9-10a2 2 0 0 1 3 0l5 5a2 2 0 0 1 0 3l-8 9H9l-5-4a2 2 0 0 1 0-3ZM8 9l9 8M13 21h8',
    brush: 'M14 4l6 6M7 14 17 3l4 4-10 11M7 14c-4 0-5 4-5 7 3 0 7-1 7-5z',
    pan: 'M12 3v18M3 12h18M8 7l4-4 4 4M8 17l4 4 4-4M7 8l-4 4 4 4m10-8 4 4-4 4',
    undo: 'M8 5 3 10l5 5M3 10h11a6 6 0 0 1 0 12',
    redo: 'm16 5 5 5-5 5m5-5H10a6 6 0 0 0 0 12',
    colour: 'M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 1-4c-1-2 1-3 3-3h2c3 0 3-5 0-8a10 10 0 0 0-7-3ZM7 9h.01M11 6h.01M16 8h.01M6 14h.01',
    border: 'M5 3h14l2 2v14l-2 2H5l-2-2V5zM7 7h10v10H7z',
    size: 'm3 16 13-13 5 5-13 13zM7 12l3 3m1-7 3 3m1-7 3 3',
    detail: 'M15 15l6 6M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14M7 10h6m-3-3v6',
    review: 'M8 3H5v18h14V3h-3M8 2h8v4H8zM8 13l3 3 5-6',
    image: 'M3 3h18v18H3zM3 16l6-6 5 5 3-3 4 4M16 7h.01',
    stitch: 'm4 20 9-17 5 3-14 14m8-13 4 2M5 21h15',
    compare: 'M12 2v20M8 4H3v16h5m8-16h5v16h-5',
    plus: 'M12 5v14M5 12h14', minus: 'M5 12h14',
  };
  function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('aria-hidden', 'true');
    svg.classList.add('ui-icon');
    const path = document.createElementNS(svg.namespaceURI, 'path');
    path.setAttribute('d', paths[name] || paths.select); svg.append(path); return svg;
  }
  function label(button, name, text) {
    const span = document.createElement('span'); span.textContent = text;
    button.replaceChildren(icon(name), span); button.setAttribute('aria-label', text);
  }
  function disclosure(title, nodes) {
    const d = document.createElement('details'), s = document.createElement('summary');
    s.textContent = title; d.append(s, ...nodes); return d;
  }

  const toolLabels = {
    box: ['select', 'Select'], polygon: ['outline', 'Outline'], lasso: ['outline', 'Freehand'],
    keep: ['plus', 'Keep hint'], remove: ['minus', 'Remove hint'], 'colour-remove': ['colour','Remove colour'],
    'erase-outline': ['erase', 'Erase area'], erase: ['brush', 'Brush erase'],
    paint: ['brush', 'Paint'], pan: ['pan', 'Move view'],
  };
  document.querySelectorAll('[data-tool]').forEach(b => label(b, ...toolLabels[b.dataset.tool]));
  label($('undo'), 'undo', 'Undo'); label($('redo'), 'redo', 'Redo');
  const viewLabels = {original:['image','Original image'],isolated:['select','Subject'],prepared:['colour','Stitch artwork'],stitched:['stitch','Stitches'],compare:['compare','Compare']};
  document.querySelectorAll('[data-view]').forEach(b => label(b, ...viewLabels[b.dataset.view]));
  const heading = inspector.querySelector('h1'); heading.textContent = 'Edit design';
  const intro = inspector.querySelector(':scope > p');
  if (intro) intro.textContent = 'Choose what you want to adjust.';
  const lineStyles=disclosure('Black-line stitches',[$('inkStitchSettings')]);
  const sections = {
    selection: [$('confirmed').closest('details')],
    colours: [$('swatches').closest('details')],
    styles: [$('stitchStyles'),lineStyles],
    borders: [document.querySelector('[data-border]').closest('details')],
    size: [document.querySelector('[data-option="height_mm"]').closest('details'), $('generateSizes').closest('details')],
    details: [document.querySelector('[data-option="brightness"]').closest('details'), $('portraitPropose').closest('details'), $('assistSubject').closest('details')],
    ask: $('askAiPanel') ? [$('askAiPanel')] : [],
    review: [$('reviewSide').closest('details'), $('detailMap').closest('details'), $('metrics').closest('details'), $('routeNext').closest('details')],
  };
  const definitions = [
    ...($('askAiPanel') ? [['ask','chat','AI assistant','Preview first. You choose what to apply.']] : []),
    ['selection','select','Background & selection','Choose what to keep. Preview any removal before applying it.'],
    ['colours','colour','Colours','Choose, replace or exclude thread colours.'],
    ['borders','border','Borders','Outline the edge of your subject.'],
    ['size','size','Size & fabric','Set the design size and preview fabric.'],
    ['details','detail','Fine-tune','Clean up detail, or review a suggested change.'],
    ['review','review','Picture details','Check what changed before you make stitches.'],
    ['styles','stitch','Stitch styles','Choose stitches for each artwork area.'],
  ];
  const topicNav = document.createElement('nav'); topicNav.className = 'topic-nav';
  topicNav.setAttribute('aria-label', 'Design settings');
  intro.after(topicNav);
  const topics = new Map();
  for (const [key, name, title, hint] of definitions) {
    const panel = document.createElement('section'); panel.className = 'topic-panel';
    panel.id = 'topic-' + key; panel.setAttribute('aria-label', title); panel.hidden = true;
    const h = document.createElement('h2'); h.textContent = title;
    const p = document.createElement('p'); p.className = 'topic-hint'; p.textContent = hint;
    panel.append(h, p);
    sections[key].forEach((section, i) => { section.open = i === 0; panel.append(section); });
    inspector.append(panel);
    const button = document.createElement('button'); button.type = 'button';
    button.dataset.topic = key; button.setAttribute('aria-controls', panel.id);
    label(button, name, title); topicNav.append(button); topics.set(key, {button,panel});
    button.addEventListener('click', () => showTopic(key));
  }
  function showTopic(key) {
    window.dispatchEvent(new CustomEvent('studio:topic',{detail:key}));
    topics.forEach(({button,panel}, name) => {
      panel.hidden = name !== key; button.setAttribute('aria-pressed', String(name === key));
    });
  }
  // Move less frequent tools into the owning topic, retaining their original handlers.
  const extraTools = ['lasso','keep','remove','erase'].map(t => document.querySelector(`[data-tool="${t}"]`));
  const extra = disclosure('More selection tools', extraTools);
  extra.className = 'extra-tools';
  const caution = document.createElement('p'); caution.className = 'muted';
  caution.textContent = 'Keep / Remove hints can recalculate an automatic selection. Erase area removes only inside your outline.';
  extra.append(caution);
  const brushLabel=$('radius').closest('label'), brushText=document.createTextNode('Brush width ');
  const brushValue=document.createElement('output');brushValue.value=(Number($('radius').value)*2)+' px';
  brushLabel.replaceChildren(brushText,brushValue,$('radius'));
  $('radius').addEventListener('input',()=>{brushValue.value=(Number($('radius').value)*2)+' px';window.embroideryStudio.redraw()});
  extra.append(brushLabel); sections.selection[0].append(extra);
  sections.colours[0].prepend(document.querySelector('[data-tool="paint"]'));

  // Explanations remain available; dynamic warnings/status messages stay in place.
  Object.values(sections).flat().forEach(section => {
    const copy = [...section.querySelectorAll(':scope > p.muted:not([id])')];
    if (copy.length) section.append(disclosure('How this works', copy));
  });
  const rename = (section, text) => section.querySelector(':scope > summary').textContent = text;
  rename(sections.selection[0], 'Select & approve');
  rename(sections.colours[0], 'Thread colours');
  rename(sections.borders[0], 'Subject outline');
  rename(sections.details[0], 'Artwork adjustments');
  rename(sections.details[1], 'Photographs & portraits');
  rename(sections.details[2], 'Suggested changes');
  rename(sections.review[0], 'Compare & repair');
  rename(sections.review[1], 'More detail checks');
  rename(sections.review[3], 'Directions & jumps');
  const selectionHelp = document.createElement('p'); selectionHelp.className = 'selection-help';
  selectionHelp.textContent = 'Outline: click around the subject, then Keep outline. Erase area: outline what to remove, then apply.';
  sections.selection[0].querySelector('summary').after(selectionHelp);
  $('outlineSubject').textContent = 'Outline subject';
  $('unprotectSubject').textContent = 'Use automatic edge cleanup';
  $('full').textContent = 'Use full image';

  document.querySelectorAll('[data-tool]').forEach(b => b.addEventListener('click', () => {
    if (b.dataset.tool === 'paint') showTopic('colours');
    else if (b.dataset.tool !== 'pan') showTopic('selection');
  }));
  $('inspectDetail').addEventListener('click', () => showTopic('review'));
  const canvasArea = document.querySelector('.canvas-area');
  function updateView(view) {
    canvasArea.dataset.canvasView = view;
    const sewing = ['stitched','review','wipe'].includes(view);
    for (const e of document.querySelectorAll('.transport,.thread-info,#colourStops')) e.hidden = false;
  }
  window.addEventListener('studio:view', e => updateView(e.detail));
  showTopic('selection'); updateView('original');
  window.embroideryWorkspace = {showTopic};
})();
