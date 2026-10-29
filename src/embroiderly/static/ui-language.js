/* Display-only terminology. Never changes saved keys, input values or commands. */
(() => {
'use strict';
const exact={
 'Original':'Artwork','Artwork':'Plan','Prepared':'Plan',
 'Design layers':'Plan preview',
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
// What changed: added nodes and edited text, never the whole page. Walking every text node
// on each change froze the studio while playback updated its counter many times a second.
function roots(records){
 const out=new Set();
 for(const record of records){
  if(record.type==='characterData')out.add(record.target);
  else for(const node of record.addedNodes||[])out.add(node);
 }
 return [...out];
}
if(typeof module!=='undefined')module.exports={label,roots};
if(typeof document==='undefined')return;
const visited=new WeakMap();
function text(node){
 const parent=node.parentElement;if(!parent||parent.closest('script,style,textarea,code,pre'))return;
 if(visited.get(node)===node.nodeValue)return;
 const view=!!parent.closest('[data-view],#middleView');
 const next=label(node.nodeValue,view);
 if(next!==node.nodeValue)node.nodeValue=next;
 visited.set(node,node.nodeValue);
}
function attributes(el){
 for(const attr of ['aria-label','title'])if(el.hasAttribute(attr)){
  const old=el.getAttribute(attr),next=label(old);if(old!==next)el.setAttribute(attr,next);
 }
}
function refresh(root=document.body){
 if(root.nodeType===3){text(root);return}
 if(root.nodeType!==1)return;
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
 for(let node=walker.nextNode();node;node=walker.nextNode())text(node);
 attributes(root);
 for(const el of root.querySelectorAll('[aria-label],[title]'))attributes(el);
}
function start(){
 refresh();
 new MutationObserver(records=>{
  for(const record of records)if(record.type==='attributes')attributes(record.target);
  for(const root of roots(records))if(root.isConnected)refresh(root);
 }).observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['aria-label','title']});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
