/* Shared validation owner for legacy POST forms; keep constraint metadata. */
(() => {
  'use strict';
  document.addEventListener('submit', event => {
    const form=event.target;
    if(!form.matches('form[data-owned-validation]'))return;
    let first=null;
    for(const field of form.elements){
      if(!field.willValidate)continue;
      let error=field.nextElementSibling;
      if(!error?.classList.contains('field-validation')){
        error=document.createElement('span');error.className='field-validation';
        error.id='field-validation-'+crypto.randomUUID();error.setAttribute('role','status');
        field.after(error);
        field.setAttribute('aria-describedby', [field.getAttribute('aria-describedby'),error.id].filter(Boolean).join(' '));
      }
      const invalid=!field.validity.valid;
      field.setAttribute('aria-invalid',String(invalid));error.hidden=!invalid;
      error.textContent=invalid?field.validationMessage:'';
      if(invalid&&!first)first=field;
    }
    if(first){event.preventDefault();event.stopImmediatePropagation();first.focus();}
    else if(form.dataset.submitting==='true'){event.preventDefault();event.stopImmediatePropagation();}
    else {form.dataset.submitting='true';form.setAttribute('aria-busy','true');}
  },true);
  window.addEventListener('pageshow',()=>{
    document.querySelectorAll('form[data-owned-validation]').forEach(form=>{
      delete form.dataset.submitting;form.removeAttribute('aria-busy');
    });
  });
})();
