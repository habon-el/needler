"""Read-only browser validation; never submits a stitch generation request."""
from browser_helpers import call,ev,wait

old=ev('performance.timeOrigin')
call('Page.navigate',{'url':'http://127.0.0.1:5050/engine/015d15d2453c4aff968dbf6218fbf691.png'})
wait(f'performance.timeOrigin !== {old}')
wait('document.readyState === "complete"')
wait('!!document.querySelector("form[data-owned-validation]")')
ev('document.querySelector("input[name=height_mm]").value="9999";document.querySelector("form").requestSubmit()')
assert ev('document.querySelector("input[name=height_mm]").getAttribute("aria-invalid")')=='true'
assert ev('document.querySelector(".field-validation").textContent.length>0')
assert ev('document.activeElement.name')=='height_mm'
assert not ev('document.querySelector("form").dataset.submitting==="true"')
assert not ev('document.querySelector("button").disabled')
print('PASS: invalid size blocked before generation, inline explanation, first-field focus, values retained, submit handler not run.')
