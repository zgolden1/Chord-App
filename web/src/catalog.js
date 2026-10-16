/* ---------- search -> chart -> YouTube video -> play along ---------- */
/* Talks to the catalog API named in config.js (CF.api). Everything here degrades quietly when the API or sign-in is not set up. */
const CFG=window.CF||{};
const CAT={api:(CFG.api||"").replace(/\/$/,""),token:null,sb:null,user:null,results:[],cur:null,timer:0,seq:0};
const cesc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const catTok=()=>CFG.devToken||CAT.token;                           // devToken only works against a server started with DEV_AUTH=1
async function catApi(path,opt={}){
 const h={};const t=opt.token||catTok();if(t)h.Authorization="Bearer "+t;if(opt.body)h["Content-Type"]="application/json";
 const r=await fetch(CAT.api+path,{method:opt.method||"GET",headers:h,body:opt.body?JSON.stringify(opt.body):undefined});
 let j=null;try{j=await r.json()}catch(e){}
 if(!r.ok){const e=new Error((j&&j.error)||("HTTP "+r.status));e.status=r.status;throw e}
 return j;
}
/* ----- sign-in (Supabase, Google) ----- */
function catAcct(){
 const el=$("acct");if(!CFG.supabaseUrl&&!CFG.devToken){el.innerHTML="";return}
 el.innerHTML=catTok()?`<button id="acctOut" class="ghost" title="${cesc(CAT.user||"")}">Sign out</button>`:`<button id="acctIn" class="ghost">Sign in</button>`;
 const i=$("acctIn");if(i)i.onclick=catSignIn;const o=$("acctOut");if(o)o.onclick=async()=>{try{await CAT.sb.auth.signOut()}catch(e){}CAT.token=null;CAT.user=null;catAcct()};
}
async function catSignIn(){
 if(!CAT.sb){toast("Sign-in isn’t set up yet.");return}
 try{await CAT.sb.auth.signInWithOAuth({provider:"google",options:{redirectTo:location.origin+location.pathname}})}catch(e){toast("Couldn’t start sign-in.")}
}
async function catAuthInit(){
 if(CFG.devToken){CAT.user="test user";catAcct();return}
 if(!CFG.supabaseUrl||!CFG.supabaseKey){catAcct();return}
 try{
  const m=await import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm");
  CAT.sb=m.createClient(CFG.supabaseUrl,CFG.supabaseKey);
  const set=s=>{CAT.token=s?s.access_token:null;CAT.user=s&&s.user?(s.user.email||"Signed in"):null;catAcct()};
  const {data}=await CAT.sb.auth.getSession();set(data.session);CAT.sb.auth.onAuthStateChange((_e,s)=>set(s));
 }catch(e){catAcct()}
}
/* ----- search ----- */
function catMsg(m){$("qmsg").textContent=m||""}
function catRows(){
 $("qres").innerHTML=CAT.results.map((r,i)=>{
  const meta=[r.artist,r.year,r.kind&&r.kind!=="studio"?r.kind:null].filter(Boolean).join(" · ");
  const chip=r.analyzed?`<span class="chip ok">Chart ready</span>`:`<span class="chip">No chart yet${r.requests?" · "+r.requests+" asked":""}</span>`;
  return `<button class="res" data-i="${i}"><span class="rt"><b>${cesc(r.title)}</b><small>${cesc(meta)}</small></span>${chip}</button>`}).join("");
}
async function catSearch(q){
 const my=++CAT.seq;
 if(q.trim().length<2){CAT.results=[];catRows();catMsg("");return}
 catMsg("Searching…");
 try{
  const j=await catApi("/api/search?q="+encodeURIComponent(q.trim()));
  if(my!==CAT.seq)return;
  CAT.results=j.results||[];catRows();catMsg(CAT.results.length?"":(j.note||"Nothing found. Try the artist and song name."));
 }catch(e){if(my===CAT.seq){CAT.results=[];catRows();catMsg("Couldn’t reach the song catalog. Check your connection, or use your own file below.")}}
}
$("q").oninput=e=>{clearTimeout(CAT.timer);CAT.timer=setTimeout(()=>catSearch(e.target.value),350)};
$("qres").onclick=e=>{const b=e.target.closest(".res");if(!b)return;const r=CAT.results[+b.dataset.i];if(!r)return;r.analyzed?catOpen(r):catAskPanel(r)};
/* ----- a song with no chart yet ----- */
function catAskPanel(r){
 CAT.cur=r;$("vidPick").hidden=true;$("askBox").hidden=false;
 $("askTitle").textContent=r.title+" — "+r.artist;
 $("askTxt").textContent=r.requests?`${r.requests} ${r.requests===1?"person has":"people have"} asked for this one.`:"Nobody has asked for this one yet.";
 $("askBtn").textContent=catTok()?"Ask for this chart":"Sign in to ask for this chart";$("askBtn").disabled=false;
 $("askBox").scrollIntoView({block:"nearest",behavior:"smooth"});
}
$("askBtn").onclick=async()=>{
 const r=CAT.cur;if(!r)return;
 if(!catTok()){catSignIn();return}
 $("askBtn").disabled=true;
 try{const j=await catApi("/api/recordings/"+encodeURIComponent(r.mbid)+"/request",{method:"POST",body:{recording:r}});
  r.requests=j.requests;catRows();$("askTxt").textContent=`Thanks. ${j.requests} ${j.requests===1?"person has":"people have"} asked for this chart. It appears in search once it’s made.`;$("askBtn").textContent="Requested"}
 catch(e){$("askBtn").disabled=false;$("askTxt").textContent=e.status===429?"You’ve reached today’s limit for requests.":"Couldn’t send the request. Try again."}
};
/* ----- open a charted song: chart + video ----- */
async function catOpen(r){
 CAT.cur=r;$("askBox").hidden=true;$("vidPick").hidden=true;catMsg("Loading the chart…");
 let j;try{j=await catApi("/api/recordings/"+encodeURIComponent(r.mbid))}catch(e){catMsg("Couldn’t load that chart.");return}
 catMsg("");const a=j.analysis;if(!a){catMsg("That song has no chart yet.");return}
 CAT.chart=a.data;CAT.rec=j.recording;CAT.ver=a.version;
 const v=a.data.video;
 if(v&&v.id)catPlay(v.id,v.offset||0);else catVideoPicker();
}
function catPlay(id,offset){
 const r=CAT.rec;
 try{chartStart(CAT.chart,{id,offset,title:r.title,artist:r.artist,cid:"mb-"+r.mbid,mbid:r.mbid})}catch(e){catMsg("That chart file is damaged.");return}
 $("vidPick").hidden=true;window.scrollTo({top:0});
}
async function catVideoPicker(){
 const r=CAT.rec;$("vidPick").hidden=false;$("vidTitle").textContent=`Choose the video for “${r.title}”`;$("vidList").innerHTML="";$("vidMsg").textContent="Looking for videos…";
 try{
  const j=await catApi("/api/youtube?q="+encodeURIComponent(r.artist+" "+r.title));
  CAT.vids=j.results||[];
  $("vidList").innerHTML=CAT.vids.map((v,i)=>`<button class="res" data-i="${i}"><span class="rt"><b>${cesc(v.title)}</b><small>${cesc(v.channel)}</small></span><span class="chip">Use</span></button>`).join("");
  $("vidMsg").textContent=CAT.vids.length?"Pick the one that matches the recording. You can also paste a link.":(j.error==="no_key"?"Video search isn’t set up yet. Paste a YouTube link instead.":"No videos found. Paste a YouTube link instead.");
 }catch(e){$("vidMsg").textContent="Couldn’t search for videos. Paste a YouTube link instead."}
}
$("vidList").onclick=e=>{const b=e.target.closest(".res");if(b)catPlay(CAT.vids[+b.dataset.i].id,0)};
$("vidGo").onclick=()=>{const id=ytIdOf($("vidUrl").value);if(!id){$("vidMsg").textContent="That doesn’t look like a YouTube link.";return}catPlay(id,0)};
$("vidChange").onclick=()=>{if(CAT.chart)catVideoPicker()};
/* send "this video, with this offset" to the moderators */
$("vidSave").onclick=async()=>{
 if(!S||!S.mbid||!YT.id)return;if(!catTok()){catSignIn();return}
 try{await catApi("/api/recordings/"+encodeURIComponent(S.mbid)+"/suggestions",{method:"POST",body:{kind:"video",payload:{id:YT.id,offset:Math.round((S.cOff||0)*100)/100}}});toast("Sent. A moderator will check it before it changes for everyone.")}
 catch(e){toast(e.status===429?"Daily limit reached.":"Couldn’t send that.")}
};
if(!CAT.api){catMsg("The song catalog isn’t connected yet. You can still use your own audio file or listen with the microphone.");$("q").disabled=true}
catAuthInit();

/* back to search */
$("vidBack").onclick=()=>{try{au.pause()}catch(e){}ytStop();S=null;$("ctl").hidden=true;$("views").hidden=true;$("vidBar").hidden=true;$("load").hidden=false;$("st").textContent="";window.scrollTo({top:0});$("q").focus()};

/* ----- publish a chart analyzed on this device (moderators, or the admin key from Render) ----- */
const PUB={pick:null,seq:0,timer:0};
setInterval(()=>{const on=!!(CAT.api&&S&&S.pcm);if($("pubBox").hidden===on){$("pubBox").hidden=!on;if(on){PUB.pick=null;$("pubMsg").textContent="";$("pubRes").innerHTML="";$("pubQ").value=$("lyTitle").value?($("lyArtist").value+" "+$("lyTitle").value).trim():"";$("pubGo").disabled=false;if($("pubQ").value)$("pubQ").dispatchEvent(new Event("input"))}}$("pubTok").hidden=!!catTok()},800);
$("pubQ").oninput=e=>{clearTimeout(PUB.timer);PUB.timer=setTimeout(async()=>{
 const q=e.target.value.trim(),my=++PUB.seq;if(q.length<2){$("pubRes").innerHTML="";return}
 try{const j=await catApi("/api/search?q="+encodeURIComponent(q));if(my!==PUB.seq)return;PUB.list=j.results||[];$("pubMsg").textContent=PUB.list.length?"":(j.note||"No matches. Try just the song title.");
  $("pubRes").innerHTML=PUB.list.map((r,i)=>`<button class="res" data-i="${i}"><span class="rt"><b>${cesc(r.title)}</b><small>${cesc([r.artist,r.year,r.length_s?fmt(r.length_s):null,r.kind&&r.kind!=="studio"?r.kind:null].filter(Boolean).join(" · "))}</small></span>${r.analyzed?'<span class="chip ok">Has a chart</span>':""}</button>`).join("")}
 catch(err){$("pubRes").innerHTML="";$("pubMsg").textContent="Couldn’t reach the catalog: "+(err.message||err)}},350)};
$("pubRes").onclick=e=>{const b=e.target.closest(".res");if(!b)return;PUB.pick=PUB.list[+b.dataset.i];[...$("pubRes").children].forEach(c=>c.classList.toggle("sel",c===b));
 const d=Math.abs((PUB.pick.length_s||S.dur)-S.dur);$("pubMsg").textContent=PUB.pick.analyzed?"This recording already has a chart, so yours will be saved as a candidate for comparison.":(d>8?`Careful: your file is ${fmt(S.dur)} but this recording is ${fmt(PUB.pick.length_s)}. A different version won’t line up.`:"");$("pubGo").disabled=false};
function pubData(){
 const r=S.autoSegs.map(g=>({t0:+g.t0.toFixed(3),t1:+g.t1.toFixed(3),r:g.r,q:g.q,xt:g.xt||[],slash:Number.isInteger(g.slash)?g.slash:-1,conf:+(g.conf||0).toFixed(3)}));
 const d={pipeline:"in-browser",duration:+S.dur.toFixed(2),key:{r:S.key.r,m:!!S.key.m},bpm:S.bpm,phase:S.phase0,beats:S.beats0.map(x=>+x.toFixed(3)),chords:r};
 const id=ytIdOf($("pubYt").value);if(id)d.video={id,offset:0};return d;
}
$("pubGo").onclick=async()=>{
 if(!PUB.pick){$("pubMsg").textContent="First tap the matching recording in the list above. If no list shows, change the search text a little.";return}
 if(!PUB.pick||!S||!S.pcm)return;if($("pubYt").value.trim()&&!ytIdOf($("pubYt").value)){$("pubMsg").textContent="That doesn’t look like a YouTube link.";return}
 const tok=catTok()||$("pubTok").value.trim();if(!tok){$("pubMsg").textContent="Sign in as a moderator, or enter the admin key.";return}
 $("pubGo").disabled=true;$("pubMsg").textContent="Publishing…";
 try{const j=await catApi("/api/recordings/publish"+(PUB.pick.analyzed?"?as=candidate":""),{method:"POST",token:tok,body:{recording:PUB.pick,data:pubData()}});
  $("pubMsg").textContent=j.status==="candidate"?"Saved as a candidate (the official chart was not changed).":"Published. It now appears in search for everyone.";$("pubTok").value=""}
 catch(e){$("pubGo").disabled=false;$("pubMsg").textContent=e.status===401||e.status===403?"That key or account isn’t allowed to publish.":"Couldn’t publish: "+e.message}
};
