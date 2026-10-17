// Three views share a single written-file event sequence.
const views=document.createElement('section');
views.innerHTML='<h2>Design views</h2><div class="player"><button id="v-play">Playback</button><button id="v-flat">Flat stitches</button><button id="v-finish">Finished thread</button><button id="v-both">Compare flat + finished</button><label>Fabric colour <input id="fabric" type="color" value="#c2baa8"></label></div><p>Finished view uses the written export with estimated thread height and fabric lighting. It is not a measured sew-out. For interactive lighting, use the main design workspace.</p>';
const transport=button.closest('.player');transport.before(views);
const container=document.createElement('div');container.style.display='flex';container.style.flexWrap='wrap';container.style.gap='12px';views.append(container);
const flat=document.createElement('canvas');flat.width=900;flat.height=650;flat.style.width='100%';flat.style.background='#c2baa8';flat.setAttribute('aria-label','All stitches with needle penetrations');
const finish=document.createElement('img');finish.alt='Finished embroidered thread appearance';finish.style.maxWidth='100%';finish.style.maxHeight='650px';finish.style.objectFit='contain';
container.append(flat,finish);
const f=flat.getContext('2d');let prior={x:0,y:0};
for(const s of steps){if(s.t==='stitch'){const [x,y]=point(s),[px,py]=point(prior);f.strokeStyle=s.color;f.lineWidth=.8;f.beginPath();f.moveTo(px,py);f.lineTo(x,y);f.stroke();f.fillStyle=s.color;f.beginPath();f.arc(x,y,1.5,0,7);f.fill()}prior=s}
function refreshFinished(){finish.src='/finished/'+location.pathname.split('/').at(-1)+'?fabric='+encodeURIComponent(document.getElementById('fabric').value)+(data.engine?'&engine=inkstitch':'');flat.style.background=document.getElementById('fabric').value}
function show(mode){if(mode!=='play'){playing=false;button.textContent='Play'}transport.hidden=mode!=='play';transport.style.display=mode==='play'?'':'none';canvas.hidden=mode!=='play';flat.hidden=!['flat','both'].includes(mode);finish.hidden=!['finish','both'].includes(mode);flat.style.width=mode==='both'?'48%':'100%';finish.style.width=mode==='both'?'48%':'100%';for(const [id,value] of [['v-play','play'],['v-flat','flat'],['v-finish','finish'],['v-both','both']])document.getElementById(id).setAttribute('aria-pressed',String(mode===value));if(['finish','both'].includes(mode))refreshFinished()}
document.getElementById('v-play').onclick=()=>show('play');document.getElementById('v-flat').onclick=()=>show('flat');document.getElementById('v-finish').onclick=()=>show('finish');document.getElementById('v-both').onclick=()=>show('both');document.getElementById('fabric').onchange=refreshFinished;
finish.onerror=()=>{finish.alt='Finished preview unavailable. Reload playback and try again.'};
show('play');
