(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const selected = new Set(), facts = new Map();
  let rows = [], version = 0, busy = false, renameRow, renameTrigger, toastTimer, toastDeadline, toastRemaining;
  const initial = new URLSearchParams(location.search);
  let view = ['recent','all','trash'].includes(initial.get('view')) ? initial.get('view') : 'recent';
  $('librarySort').value = ['opened','changed','name','size'].includes(initial.get('sort')) ? initial.get('sort') : 'opened';
  $('librarySearch').value = initial.get('q') || '';
  const text = (tag,value,cls) => { const el=document.createElement(tag); el.textContent=value; if(cls)el.className=cls; return el; };
  const button = (label,handler,cls) => { const el=text('button',label,cls); el.type='button'; el.onclick=handler; return el; };
  const item = row => ({id:row.id,revision:row.revision});
  function persist() {
    const query = new URLSearchParams({view,sort:$('librarySort').value});
    if ($('librarySearch').value) query.set('q',$('librarySearch').value);
    history.replaceState(null,'','?'+query);
  }
  async function api(path, body) {
    const response = await fetch(path,{method:body?'POST':'GET',cache:'no-store',signal:AbortSignal.timeout(20000),
      ...(body?{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});
    const data = await response.json();
    if(!response.ok) throw Error(data.error || 'The library could not complete this request.');
    return data;
  }
  function failure(error) {
    $('libraryStatus').textContent = error.name === 'TimeoutError' ? 'The request timed out. Reload to check whether it completed before trying again.' : error.message;
    $('libraryReload').hidden=false;
  }
  function updateSelection() {
    const count=selected.size;
    document.querySelector('.library-selection').hidden=!count;
    document.querySelector('.library-filters').hidden=!!count;
    $('selectionCount').textContent=`${count} selected`;
    document.querySelector('[data-bulk=restore]').hidden=view!=='trash';
    document.querySelector('[data-bulk=delete]').hidden=view==='trash';
    document.querySelector('[data-bulk=remove_recent]').hidden=view==='trash';
    document.querySelectorAll('.design-card').forEach(card=>{
      card.dataset.selected=String(selected.has(card.dataset.id));
      card.querySelector('input[type=checkbox]').checked=selected.has(card.dataset.id);
    });
  }
  function busyState(value) {
    busy=value;
    document.querySelectorAll('.library-main button,.library-main select,.library-main input').forEach(el=>{el.disabled=value;});
    $('renameDesign').querySelectorAll('button,input').forEach(el=>{el.disabled=value;});
  }
  function detailsText(row) {
    const data=facts.get(row.id);
    if(!data) return ['Reading saved design…','Loading'];
    if(data.error) return ['Saved details could not load.','Details unavailable'];
    const dimensions=`${data.width_mm.toFixed(1)} mm wide × ${data.height_mm.toFixed(1)} mm high`;
    return [dimensions+' · '+(data.stitch_count===null?'No saved stitches':`${data.thread_count} threads · ${data.stitch_count.toLocaleString()} stitches`),data.status];
  }
  function updateCardFacts(row,card) {
    const [description,status]=detailsText(row);
    card.querySelector('.card-facts').textContent=description;
    card.querySelector('.card-status').textContent=status;
  }
  function card(row) {
    const el=document.createElement('article');el.className='design-card';el.dataset.id=row.id;
    const imageBox=document.createElement('div');imageBox.className='card-image';
    const image=new Image();image.alt=`Original artwork: ${row.name}`;image.loading='lazy';
    const error=document.createElement('div');error.className='preview-error';error.hidden=true;
    const retry=button('Rebuild preview',()=>{error.hidden=true;image.hidden=false;image.src=`/api/library/${encodeURIComponent(row.id)}/preview?rebuild=${Date.now()}`;});
    error.append(text('p','Preview did not load'),retry);
    image.onerror=()=>{image.hidden=true;error.hidden=false;};
    image.src=`/api/library/${encodeURIComponent(row.id)}/preview`;
    imageBox.append(image,error);el.append(imageBox);
    const label=document.createElement('label');label.className='card-select';
    const check=document.createElement('input');check.type='checkbox';check.setAttribute('aria-label',`Select ${row.name}`);
    check.onchange=()=>{if(check.checked)selected.add(row.id);else selected.delete(row.id);updateSelection();};
    label.append(check);el.append(label);
    const menu=document.createElement('details');menu.className='card-menu';
    const summary=text('summary','⋯');summary.setAttribute('aria-label',`Actions for ${row.name}`);
    const nav=document.createElement('nav');nav.setAttribute('aria-label',`Actions for ${row.name}`);
    if(view==='trash') nav.append(button('Restore',()=>act('restore',[row])));
    else {
      nav.append(button('Open',()=>act('opened',[row])),button('Rename',()=>rename(row,summary)),
        button('Duplicate',()=>act('duplicate',[row])),button('Remove from recent',()=>act('remove_recent',[row])),
        button('Delete design',()=>act('delete',[row]),'danger'));
    }
    menu.append(summary,nav);menu.addEventListener('toggle',()=>{if(menu.open)document.querySelectorAll('.card-menu[open]').forEach(other=>{if(other!==menu)other.open=false;});});
    el.append(menu);
    const body=document.createElement('div');body.className='card-body';
    const title=document.createElement('h2');
    title.append(view==='trash'?text('span',row.name):button(row.name,()=>act('opened',[row])));
    body.append(text('span','Image','card-kind'),title,text('span','Loading','card-status'),text('p','','card-facts'));
    const opened=row.opened_at ? new Date(row.opened_at*1000).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'}) : 'Not opened yet';
    body.append(text('p',view==='trash'?`${row.days_remaining} days remaining in the planned 30-day period · cleanup paused`:`Last opened: ${opened}`,'card-opened'));
    el.append(body);updateCardFacts(row,el);return el;
  }
  function render() {
    const query=$('librarySearch').value.toLocaleLowerCase().trim();
    const filtered=rows.filter(row=>row.name.toLocaleLowerCase().includes(query));
    const sort=$('librarySort').value;
    filtered.sort((a,b)=>{
      if(sort==='name')return a.name.localeCompare(b.name)||a.id.localeCompare(b.id);
      if(sort==='size')return ((facts.get(b.id)?.width_mm||0)*(facts.get(b.id)?.height_mm||0))-((facts.get(a.id)?.width_mm||0)*(facts.get(a.id)?.height_mm||0))||a.id.localeCompare(b.id);
      return (sort==='changed'?b.changed_at-a.changed_at:(b.opened_at||0)-(a.opened_at||0))||b.changed_at-a.changed_at;
    });
    $('designGrid').replaceChildren(...filtered.map(card));
    if(!filtered.length)$('designGrid').append(text('p',query?'No designs match your search.':view==='trash'?'Trash is empty.':view==='recent'?'No recent designs. Open All designs or start with a new image.':'No saved designs yet. Start with a new image.'));
    $('libraryCount').textContent=`${filtered.length} of ${rows.length} designs`;
    $('librarySearchWrap').hidden=rows.length<=12 && !query;
    $('clearSearch').hidden=!query;
    $('trashNote').hidden=view!=='trash';
    document.querySelectorAll('[data-library-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.libraryView===view)));
    updateSelection();
  }
  async function load() {
    const current=++version;
    $('libraryStatus').textContent='Loading designs…';$('libraryReload').hidden=true;
    try {
      const data=await api('/api/library?view='+view);
      if(current!==version)return;
      rows=data.designs.map(row=>({...row,name:row.name==='Untitled design'||/[a-f0-9]{20}/i.test(row.name)?'Image from '+new Date(row.changed_at*1000).toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'}):row.name}));selected.clear();render();$('libraryStatus').textContent='';
      // Four readers, no digitization work; never start one request per card at once.
      const pending=rows.filter(row=>!facts.has(row.id));
      const readers = Promise.all(Array.from({length:Math.min(4,pending.length)},async()=>{
        while(pending.length && current===version) {
          const row=pending.shift();
          try {facts.set(row.id,await api(`/api/library/${encodeURIComponent(row.id)}/facts`));}
          catch(error) {facts.set(row.id,{error:true});}
          if(current!==version)return;
          const el=[...document.querySelectorAll('.design-card')].find(el=>el.dataset.id===row.id);
          if(el)updateCardFacts(row,el);
        }
      }));
      readers.then(()=>{if(current===version && $('librarySort').value==='size')render();});
    } catch(error) {if(current===version)failure(error);}
  }
  function hideToast(){clearTimeout(toastTimer);$('libraryToast').hidden=true;}
  function undoToast(message,deleted) {
    hideToast();const toast=$('libraryToast');toast.querySelector('span').textContent=message;toast.hidden=false;
    toast.querySelector('button').onclick=()=>{hideToast();act('restore',deleted);};
    toastRemaining=8000;
    const resume=()=>{clearTimeout(toastTimer);toastDeadline=Date.now()+toastRemaining;toastTimer=setTimeout(hideToast,toastRemaining);};
    const pause=()=>{clearTimeout(toastTimer);toastRemaining=Math.max(0,toastDeadline-Date.now());};
    toast.onpointerenter=pause;toast.onpointerleave=resume;toast.onfocusin=pause;toast.onfocusout=resume;resume();
  }
  async function act(action,targets,name) {
    if(busy)return false;
    busyState(true);$('libraryStatus').textContent='Saving library change…';
    try {
      const result=await api('/api/library/action',{action,items:targets.map(item),...(name?{name}:{})});
      if(action==='opened'){location.href='/artwork/'+encodeURIComponent(targets[0].source);return true;}
      document.querySelectorAll('.card-menu[open]').forEach(menu=>{menu.open=false;});
      await load();
      $('libraryStatus').textContent=action==='delete'?'Moved to Trash. Restore it there at any time while cleanup is paused.':action==='remove_recent'?'Removed from recent. Your saved design is still in All designs.':action==='restore'?'Restored. Find it in All designs.':action==='duplicate'?'Copy saved. The original is unchanged.':'Name saved.';
      if(action==='delete')undoToast(targets.length===1?`Deleted “${targets[0].name}”`:`Deleted ${targets.length} designs`,result.designs);
      document.querySelector(`[data-library-view="${view}"]`).focus();
      return true;
    } catch(error) {failure(error);return false;}
    finally {busyState(false);}
  }
  function rename(row,trigger) {
    const card=trigger.closest('.design-card'), title=card.querySelector('h2');
    card.querySelector('.card-menu').open=false;
    if(card.querySelector('.card-rename'))return;
    const form=document.createElement('form');form.className='card-rename';form.noValidate=true;
    const label=text('label','Design name'),input=document.createElement('input');
    input.value=row.name;input.maxLength=120;label.append(input);
    const error=text('p','');error.setAttribute('role','alert');
    const cancel=button('Cancel',()=>{form.remove();title.hidden=false;trigger.focus();});
    const save=text('button','Save name');save.type='submit';
    form.append(label,error,save,cancel);title.hidden=true;title.after(form);
    form.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();cancel.click();}};
    form.onsubmit=async e=>{
      e.preventDefault();if(e.isComposing)return;
      const name=input.value.trim();
      if(!name||name.length>120){error.textContent='Enter a name between 1 and 120 characters.';input.setAttribute('aria-invalid','true');input.focus();return;}
      input.removeAttribute('aria-invalid');
      if(!await act('rename',[row],name)){error.textContent=$('libraryStatus').textContent;input.focus();}
    };
    input.focus();input.select();
  }
  $('renameDesign').querySelector('form').onsubmit=async event=>{
    event.preventDefault();if(event.isComposing)return;
    const name=$('designName').value.trim();
    if(!name||name.length>120){$('renameError').textContent='Enter a name between 1 and 120 characters.';$('designName').setAttribute('aria-invalid','true');$('designName').focus();return;}
    $('designName').removeAttribute('aria-invalid');
    if(await act('rename',[renameRow],name))$('renameDesign').close();
    else $('renameError').textContent=$('libraryStatus').textContent;
  };
  $('designName').setAttribute('aria-describedby','renameError');
  $('renameDesign').querySelector('[data-cancel]').onclick=()=>$('renameDesign').close();
  $('renameDesign').addEventListener('close',()=>{if(renameTrigger?.isConnected)renameTrigger.focus();else document.querySelector(`[data-library-view="${view}"]`).focus();});
  document.querySelectorAll('[data-library-view]').forEach(b=>b.onclick=()=>{if(busy)return;view=b.dataset.libraryView;$('librarySearch').value='';selected.clear();persist();load();});
  document.querySelectorAll('[data-bulk]').forEach(b=>b.onclick=()=>act(b.dataset.bulk,rows.filter(row=>selected.has(row.id))));
  $('cancelSelection').onclick=()=>{selected.clear();updateSelection();};
  $('librarySort').onchange=()=>{persist();render();};
  $('librarySearch').oninput=event=>{if(event.isComposing)return;selected.clear();persist();render();};
  $('librarySearch').addEventListener('compositionend',()=>{persist();render();});
  $('clearSearch').onclick=()=>{$('librarySearch').value='';selected.clear();persist();render();$('librarySearch').focus();};
  $('libraryReload').onclick=()=>{facts.clear();load();};
  document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('.card-menu[open]').forEach(menu=>{menu.open=false;menu.querySelector('summary').focus();});});
  document.addEventListener('pointerdown',e=>{document.querySelectorAll('.card-menu[open]').forEach(menu=>{if(!menu.contains(e.target))menu.open=false;});});
  $('chooseUpload').onclick=()=>$('newDesign').querySelector('input').click();
  $('newDesign').querySelector('input').onchange=()=>{if($('newDesign').querySelector('input').files.length)$('newDesign').requestSubmit();};
  $('newDesign').onsubmit=event=>{
    const file=event.currentTarget.querySelector('input').files[0];
    if(!file||file.size>12*1024*1024){event.preventDefault();$('uploadError').textContent=file?'Choose an image smaller than 12 MB.':'Choose an image first.';return;}
    event.currentTarget.querySelector('button').disabled=true;$('uploadError').textContent='Opening image editor…';
  };
  load();
})();
