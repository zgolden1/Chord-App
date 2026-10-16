/* ---------- play along from a YouTube link (official embedded player) + a chart file ---------- */
/* The page never touches the audio: the YouTube player plays it. We stand in for the <audio> element so
   the rest of the page (highlighting, loop, speed, seeking) works unchanged. */
const YT={on:false,id:"",t:0,stamp:0,state:-1,rate:1,dur:0,heard:false,hs:null};
const YT_ORIGIN="https://www.youtube.com",YT_RATES=[.25,.5,.75,1,1.25,1.5,1.75,2];
const ytPlaying=()=>YT.state===1||YT.state===3;
function ytCmd(func,args){const f=$("ytf");try{f.contentWindow.postMessage(JSON.stringify({event:"command",func,args:args||[]}),YT_ORIGIN)}catch(e){}}
function ytIdOf(s){s=(s||"").trim();const m=s.match(/(?:v=|youtu\.be\/|embed\/|shorts\/|live\/)([A-Za-z0-9_-]{11})/);if(m)return m[1];return/^[A-Za-z0-9_-]{11}$/.test(s)?s:""}
function ytShim(on){
 const def=(k,d)=>Object.defineProperty(au,k,Object.assign({configurable:true},d));
 if(!on){for(const k of["currentTime","paused","duration","playbackRate"])delete au[k];delete au.play;delete au.pause;return}
 def("currentTime",{get(){let t=YT.t;if(ytPlaying())t+=(performance.now()-YT.stamp)/1000*YT.rate;return Math.max(0,YT.dur?Math.min(t,YT.dur):t)},
  set(v){v=Math.max(0,+v||0);YT.t=v;YT.stamp=performance.now();ytCmd("seekTo",[v,true])}});
 def("paused",{get(){return!ytPlaying()}});
 def("duration",{get(){return YT.dur||(S&&S.dur)||0}});
 def("playbackRate",{get(){return YT.rate},set(v){const r=YT_RATES.reduce((a,b)=>Math.abs(b-v)<Math.abs(a-v)?b:a);YT.rate=r;ytCmd("setPlaybackRate",[r]);$("spv").textContent=r.toFixed(2)+"×"}});
 au.play=()=>{YT.stamp=performance.now();ytSet(1);ytCmd("playVideo");return Promise.resolve()};
 au.pause=()=>{YT.t=au.currentTime;YT.stamp=performance.now();ytSet(2);ytCmd("pauseVideo")};
}
function ytSet(st){const was=ytPlaying();YT.state=st;if(ytPlaying()&&!was)au.dispatchEvent(new Event("play"));else if(!ytPlaying()&&was)au.dispatchEvent(new Event("pause"))}
window.addEventListener("message",e=>{
 if(e.origin!==YT_ORIGIN||!YT.on||e.source!==$("ytf").contentWindow)return;
 let d;try{d=JSON.parse(e.data)}catch(x){return}
 if(!d||!d.event)return;
 if(!YT.heard){YT.heard=true;clearInterval(YT.hs);clearTimeout(YT.to);$("ytMsg").textContent=""}
 const i=d.info;if(!i||typeof i!=="object")return;
 if(typeof i.duration==="number"&&i.duration>0)YT.dur=i.duration;
 if(typeof i.playbackRate==="number")YT.rate=i.playbackRate;
 if(typeof i.currentTime==="number"){const wasP=ytPlaying();if(!wasP||Math.abs(i.currentTime-au.currentTime)>.35||i.playerState!==undefined){YT.t=i.currentTime;YT.stamp=performance.now()}}
 if(typeof i.playerState==="number")ytSet(i.playerState);
});
function ytStart(id){
 YT.on=true;YT.id=id;YT.t=0;YT.state=-1;YT.heard=false;YT.rate=1;YT.dur=0;
 ytShim(true);au.pause&&0;
 const f=$("ytf"),org=/^https?:/.test(location.origin)?"&origin="+encodeURIComponent(location.origin):"";
 f.onload=()=>{clearInterval(YT.hs);let n=0;YT.hs=setInterval(()=>{ // ask the player to start sending its state
   try{f.contentWindow.postMessage(JSON.stringify({event:"listening",id:"cf",channel:"widget"}),YT_ORIGIN)}catch(e){}
   if(YT.heard||++n>40)clearInterval(YT.hs)},250)};
 f.allow="autoplay; encrypted-media; picture-in-picture";f.referrerPolicy="strict-origin-when-cross-origin";f.src=YT_ORIGIN+"/embed/"+id+"?enablejsapi=1&playsinline=1&rel=0&modestbranding=1"+org;
 $("ytWrap").hidden=false;$("ytMsg").textContent="Loading the video…";
 clearTimeout(YT.to);YT.to=setTimeout(()=>{if(!YT.heard)$("ytMsg").textContent="The video player didn’t respond. This page may block embedded video here. Use your own audio file instead, or open ChordFlow in its own tab."},9000);
}
function ytStop(){if(!YT.on)return;YT.on=false;clearInterval(YT.hs);clearTimeout(YT.to);ytShim(false);try{au.pause()}catch(e){}$("ytf").src="about:blank";$("ytWrap").hidden=true;$("ytMsg").textContent=""}

/* ---------- build a song from a chart file (catalog format, or analyze.py output) ---------- */
function chartKey(segs){
 const KM=[6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88],Kn=[6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17];
 const pr=new Array(12).fill(0);for(const s of segs)for(const iv of QIV[s.q])pr[(s.r+iv)%12]+=(s.t1-s.t0)*(iv===0?1.5:1);
 const co=(a,b)=>{const ma=a.reduce((x,y)=>x+y)/12,mb=b.reduce((x,y)=>x+y)/12;let n=0,da=0,db=0;for(let i=0;i<12;i++){n+=(a[i]-ma)*(b[i]-mb);da+=(a[i]-ma)**2;db+=(b[i]-mb)**2}return n/Math.sqrt(da*db||1)};
 let best={r:0,m:0,s:-9};for(let r=0;r<12;r++)for(const m of[0,1]){const sc=co(pr.map((_,i)=>pr[(i+r)%12]),m?Kn:KM);if(sc>best.s)best={r,m,s:sc}}return best;
}
function chartToR(d){
 if(!d||!Array.isArray(d.chords)||!d.chords.length||!Array.isArray(d.beats)||d.beats.length<16)throw new Error("That isn’t a ChordFlow chart file (it needs chords and beats).");
 const beats=d.beats.slice(),nb=beats.length-1,dur=d.duration||beats[nb];
 const near=t=>{let lo=0,hi=nb;while(lo<hi){const m=(lo+hi)>>1;if(beats[m]<t)lo=m+1;else hi=m}return lo>0&&Math.abs(beats[lo-1]-t)<Math.abs(beats[lo]-t)?lo-1:lo};
 const segs=[];let prev=0;
 for(const c of d.chords){
  if(![c.r,c.q].every(Number.isInteger)||c.r<0||c.r>11||c.q<0||c.q>11)continue;
  let b1=near(c.t1);if(c===d.chords[d.chords.length-1]||c.t1>=dur-.5)b1=nb;
  if(b1<=prev)continue;
  segs.push({t0:prev===0?0:beats[prev],t1:b1>=nb?dur:beats[b1],b0:prev,b1,r:c.r,q:c.q,xt:(c.xt||[]).slice(0,2),slash:Number.isInteger(c.slash)?c.slash:-1,margin:1,unsure:false,alt:null,conf:c.conf??1,dbg:{}});prev=b1;
 }
 if(!segs.length)throw new Error("No usable chords in that file.");
 if(prev<nb)segs[segs.length-1].b1=nb,segs[segs.length-1].t1=dur;
 const k=d.key&&Number.isInteger(d.key.r)?{r:d.key.r,m:d.key.m?1:0,s:1}:chartKey(segs);
 let bpm=d.bpm;if(!bpm){const g=[];for(let i=1;i<beats.length;i++)g.push(beats[i]-beats[i-1]);g.sort((a,b)=>a-b);bpm=60/g[g.length>>1];while(bpm<70)bpm*=2;while(bpm>170)bpm/=2;bpm=Math.round(bpm)}
 /* bass line: the chart has no bass notes, so show each chord's bass note (root or slash) */
 const bass=segs.map(s=>{const pc=s.slash>=0?s.slash:s.r;return{t0:s.t0,t1:s.t1,m:40+((pc-4+12)%12)}});
 return{segs,key:k,bpm,beats,phase:Number.isInteger(d.phase)?d.phase:0,dur,nb,bass};
}
function chartStart(d,o){
 const r=chartToR(d);ytStop();
 const title=o.title||"Chart";
 S={...r,autoSegs:r.segs,fx:new Array(r.nb).fill(null),items:[],vPin:{},gPin:{},beats0:r.beats.slice(),cOff:0,phase0:r.phase,hold:false,shift:0,nt:"c",ac:"a",ex:0,pcm:null,sr:0,dur:r.dur,lyr:null,lyOff:0,cid:o.cid||("yt-"+(o.id||"none")),fromChart:true,mbid:o.mbid||null,chart:d};
 $("lyTitle").value=title;$("lyArtist").value=o.artist||"";$("lyText").value="";lyMsg("");LP={a:null,b:null};
 $("sb").max=r.dur;$("ttl").textContent=title;
 S.id=songId();sgWatch();
 if(d.notes&&Array.isArray(d.notes.other)&&d.version===1){S.an=d;S.heardC={};anUi()}
 $("ctl").hidden=false;$("views").hidden=false;$("sn").value="c";$("sa").value="a";$("sx").value="0";
 $("sp").step=".25";$("sp").value=1;$("spv").textContent="1.00×";
 if(o.offset)setCOffRaw(+o.offset);
 if(o.id)ytStart(o.id);
 $("load").hidden=true;$("vidBar").hidden=false;$("vidChange").hidden=$("vidSave").hidden=!o.mbid;
 refresh();setTab("c");
 $("st").textContent=S.disp.length+" chords.";
}
async function loadChart(file,url){
 const id=ytIdOf(url);
 if(!id){$("ytMsg").textContent="That doesn’t look like a YouTube link.";return}
 if(!file){$("ytMsg").textContent="Choose the chart file for this song too (the .json from analyze.py or the catalog).";return}
 let d;try{d=JSON.parse(await file.text());d=d.data||d;chartToR(d)}catch(e){$("ytMsg").textContent=e.message||"Couldn’t read that chart file.";return}
 chartStart(d,{id,title:(file.name||"chart").replace(/\.chordflow-notes\.json$|\.json$/i,"")});
}
$("ytGo").onclick=()=>loadChart($("ytChart").files[0],$("ytUrl").value);
