/* Display-only terminology. Never changes saved keys, input values or commands. */
(() => {
'use strict';
const exact={
 'Original':'Artwork','Artwork':'Plan','Prepared':'Plan',
 'Ink/Stitch trial':'Stitch generation','Design layers':'Plan preview',
 'Layer preview':'Plan preview','Drop':'Remove','Apply outline':'Keep outline',
 'Apply proposal':'Accept proposal','Apply portrait mode':'Use portrait mode',
 'Apply detail recovery':'Recover detail','Execute':'Confirm',
 'Current objects are editable path geometry. Satin/fill classification, catalogue matching and underlay generation are not yet represented by these paths.':'These legacy objects contain running paths. Their stitch type and underlay cannot be changed here.'
};
function label(text,view=false){
 const trimmed=text.trim();
 // Artwork / Plan disambiguation is contextual, not a global word swap.
 if(view&&Object.hasOwn(exact,trimmed))return text.replace(trimmed,exact[trimmed]);
 if(Object.hasOwn(exact,trimmed)&&!['Artwork','Original','Prepared'].includes(trimmed))return text.replace(trimmed,exact[trimmed]);
 return text.replace(/\bregions\b/g,'objects').replace(/\bRegions\b/g,'Objects')
  .replace(/\bregion\b/g,'object').replace(/\bRegion\b/g,'Object')
  .replace(/\bpalette\b/g,'thread set').replace(/\bPalette\b/g,'Thread set')
  .replace(/\bCut:\s/g,'Trim: ').replace(/\bdecoded cuts\b/g,'decoded trims');
}
if(typeof module!=='undefined')module.exports={label};
if(typeof document==='undefined')return;
const visited=new WeakMap();
function refresh(){
 const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 for(let node=walker.nextNode();node;node=walker.nextNode()){
  const parent=node.parentElement;if(!parent||parent.closest('script,style,textarea,code,pre'))continue;
  if(visited.get(node)===node.nodeValue)continue;
  const view=!!parent.closest('[data-view],#middleView');
  node.nodeValue=label(node.nodeValue,view);visited.set(node,node.nodeValue);
 }
 for(const el of document.querySelectorAll('[aria-label],[title]')){
  for(const attr of ['aria-label','title'])if(el.hasAttribute(attr)){
   const old=el.getAttribute(attr),next=label(old);if(old!==next)el.setAttribute(attr,next);
  }
 }
}
function start(){refresh();let pending=false;new MutationObserver(()=>{if(pending)return;pending=true;queueMicrotask(()=>{refresh();pending=false})}).observe(document.body,{subtree:true,childList:true,characterData:true})}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
