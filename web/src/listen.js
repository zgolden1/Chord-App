/* ---------- live listening: hold the phone up to a song and read the chords as they happen ---------- */
/* Runs on the microphone, in the page. Nothing is uploaded. Pure functions are exposed as LV for testing. */
const LV=(()=>{
 const FFT_N=8192,HOP=4096,SHARP=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"],FLAT=["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","B"];
 const QN=["","m","7","maj7","m7"],QIV=[[0,4,7],[0,3,7],[0,4,7,10],[0,4,7,11],[0,3,7,10]],QW=[[1,.85,.85],[1,.85,.85],[1,.8,.8,.55],[1,.8,.8,.55],[1,.8,.8,.55]];
 const TRI=[0,1,0,0,1],ROM=["I","bII","II","bIII","III","IV","bV","V","bVI","VI","bVII","VII"];
 const FLATMAJ=new Set([5,10,3,8,1]),FLATMIN=new Set([2,7,0,5,10]);
 const KM=[6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88],KN=[6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17];
 /* FFT */
 const win=new Float32Array(FFT_N),cosT=new Float32Array(FFT_N/2),sinT=new Float32Array(FFT_N/2),rev=new Uint16Array(FFT_N);
 for(let i=0;i<FFT_N;i++)win[i]=.5-.5*Math.cos(2*Math.PI*i/(FFT_N-1));
 for(let i=0;i<FFT_N/2;i++){cosT[i]=Math.cos(2*Math.PI*i/FFT_N);sinT[i]=-Math.sin(2*Math.PI*i/FFT_N)}
 for(let i=0,b=Math.log2(FFT_N);i<FFT_N;i++){let r=0;for(let j=0;j<b;j++)if(i&(1<<j))r|=1<<(b-1-j);rev[i]=r}
 const re=new Float32Array(FFT_N),im=new Float32Array(FFT_N);
 function fft(){
  for(let i=0;i<FFT_N;i++){const j=rev[i];if(j>i){let t=re[i];re[i]=re[j];re[j]=t;t=im[i];im[i]=im[j];im[j]=t}}
  for(let size=2;size<=FFT_N;size<<=1){const half=size>>1,step=FFT_N/size;
   for(let i=0;i<FFT_N;i+=size)for(let j=0,k=0;j<half;j++,k+=step){const a=i+j,b=a+half,tr=re[b]*cosT[k]-im[b]*sinT[k],ti=re[b]*sinT[k]+im[b]*cosT[k];re[b]=re[a]-tr;im[b]=im[a]-ti;re[a]+=tr;im[a]+=ti}}
 }
 /* one frame of samples (FFT_N long) -> {chroma[12], bass[12], rms} */
 function frame(x,sr){
  let e=0;for(let i=0;i<FFT_N;i++){re[i]=x[i]*win[i];im[i]=0;e+=x[i]*x[i]}
  const rms=Math.sqrt(e/FFT_N);fft();
  const hz=sr/FFT_N,k0=Math.ceil(50/hz),k1=Math.min(FFT_N/2-1,Math.floor(2200/hz)),kb=Math.floor(260/hz);
  let mx=1e-9;const mag=new Float32Array(k1+2);
  for(let k=k0;k<=k1+1;k++){mag[k]=Math.hypot(re[k],im[k]);if(k<=k1&&mag[k]>mx)mx=mag[k]}
  const ch=new Float32Array(12),bs=new Float32Array(12),bpk=[];
  for(let k=k0+1;k<=k1;k++){
   if(!(mag[k]>=mag[k-1]&&mag[k]>=mag[k+1]))continue;                /* spectral peaks only */
   /* parabolic interpolation for the real peak frequency */
   const a=mag[k-1],b=mag[k],c=mag[k+1],d=a-2*b+c,off=d?0.5*(a-c)/d:0,f=(k+off)*hz;
   const p=69+12*Math.log2(f/440),pr=Math.round(p);if(Math.abs(p-pr)>.4)continue;
   const v=Math.pow(b/mx,.6),pc=((pr%12)+12)%12;
   if(f>=140){                                                         /* upper chroma: damp the overtones of the bass notes */
    let w=1;for(const a of bpk){const ratio=f/a.f,h=Math.round(ratio);if(h>=2&&h<=8&&Math.abs(ratio-h)<.035*h&&b<a.b*1.05){w=.3;break}}
    ch[pc]+=v*w;
   }
   if(f<=300&&f>=50){
    /* skip overtones of a lower bass note: a 3rd/5th/6th/7th harmonic would read as the wrong note (D# bass -> A#) */
    let harm=false;for(const a of bpk){const ratio=f/a.f,h=Math.round(ratio);if((h===3||h===5||h===6||h===7)&&Math.abs(ratio-h)<.035*h&&b<=a.b*1.1){harm=true;break}}
    if(!harm){bpk.push({f,b});bs[pc]+=v*Math.min(1,b/mx*2)}
   }
  }
  return{chroma:ch,bass:bs,rms};
 }
 const norm=v=>{let s=0;for(const x of v)s+=x*x;s=Math.sqrt(s)||1;return v.map(x=>x/s)};
 const TPL=[];for(let r=0;r<12;r++)for(let q=0;q<5;q++){const t=new Float32Array(12);QIV[q].forEach((iv,i)=>t[(r+iv)%12]=QW[q][i]);TPL.push({r,q,t:norm(t)})}
 /* best chord for smoothed chroma + bass */
 function pick(chroma,bass,lam=.8){
  const c=norm(chroma);let bsum=0,bp=0;for(let p=0;p<12;p++){bsum+=bass[p];if(bass[p]>bass[bp])bp=p}bsum=bsum||1;
  const share=bass[bp]/bsum;
  let best=null,bs=-9,second=-9;
  for(const T of TPL){let s=0;for(let p=0;p<12;p++)s+=c[p]*T.t[p];
   const iv=(bp-T.r+12)%12,inChord=QIV[T.q].includes(iv);
   /* the bass note is evidence for the chord it belongs to: full credit on the root, partial on the 3rd/5th (a slash chord) */
   if(iv===0)s+=lam*share;else if(inChord&&(iv===3||iv===4||iv===7))s+=.85*lam*share;
   s+=.15*lam*(bass[(T.r+7)%12]/bsum);
   if(T.q>=2)s-=.06;                                                  /* prefer plain triads unless the 7th is clear */
   if(s>bs){second=bs;bs=s;best=T}else if(s>second)second=s}
  const iv=(bp-best.r+12)%12;
  const slash=share>=.4&&iv!==0&&QIV[best.q].includes(iv)&&iv!==10&&iv!==11?bp:-1;
  return{r:best.r,q:best.q,slash,score:bs,gap:bs-second};
 }
 /* all 60 chord scores for one frame (+ the bass note), used by the tracker */
 function scoreAll(chroma,bass,lam=.8){
  const c=norm(chroma);let bsum=0,bp=0;for(let p=0;p<12;p++){bsum+=bass[p];if(bass[p]>bass[bp])bp=p}bsum=bsum||1;
  const share=bass[bp]/bsum,out=new Float64Array(TPL.length);
  TPL.forEach((T,i)=>{let s=0;for(let p=0;p<12;p++)s+=c[p]*T.t[p];
   const iv=(bp-T.r+12)%12,inChord=QIV[T.q].includes(iv);
   if(iv===0)s+=lam*share;else if(inChord&&(iv===3||iv===4||iv===7))s+=.85*lam*share;
   s+=.15*lam*(bass[(T.r+7)%12]/bsum);
   if(T.q>=2)s-=.06;out[i]=s});
  return{s:out,bp,share};
 }
 /* an online "forward" filter over the 60 chords: a chord is held until the evidence clearly moves, and chords heard before in this song are favoured */
 function tracker(opt={}){
  const stay=opt.stay??.93,beta=opt.beta??14,N=TPL.length;
  let a=new Float64Array(N).fill(1/N);const seen=new Float64Array(N);let seenTot=0;
  return{step(chroma,bass){
   const {s,bp,share}=scoreAll(chroma,bass);let mx=-9;for(const v of s)if(v>mx)mx=v;
   const na=new Float64Array(N);let sum=0;
   for(let k=0;k<N;k++){
    const pr=stay*a[k]+(1-stay)/N;
    const em=Math.exp(beta*(s[k]-mx))*(1+6*seen[k]/(seenTot+40));
    na[k]=pr*em;sum+=na[k]}
   let best=0;for(let k=0;k<N;k++){na[k]/=sum;if(na[k]>na[best])best=k}
   a=na;seen[best]++;seenTot++;
   const T=TPL[best],iv=(bp-T.r+12)%12;
   const slash=share>=.4&&iv!==0&&QIV[T.q].includes(iv)&&iv!==10&&iv!==11?bp:-1;
   return{r:T.r,q:T.q,slash,p:na[best]};
  }};
 }
 function keyOf(events){
  const pr=new Array(12).fill(0);for(const e of events)for(const iv of QIV[e.q])pr[(e.r+iv)%12]+=e.d*(iv===0?1.5:1);
  const co=(a,b)=>{const ma=a.reduce((x,y)=>x+y)/12,mb=b.reduce((x,y)=>x+y)/12;let n=0,da=0,db=0;for(let i=0;i<12;i++){n+=(a[i]-ma)*(b[i]-mb);da+=(a[i]-ma)**2;db+=(b[i]-mb)**2}return n/Math.sqrt(da*db||1)};
  let best={r:0,m:0,s:-9};for(let r=0;r<12;r++)for(const m of[0,1]){const sc=co(pr.map((_,i)=>pr[(i+r)%12]),m?KN:KM);if(sc>best.s)best={r,m,s:sc}}return best;
 }
 const useFlats=k=>k.m?FLATMIN.has(k.r):FLATMAJ.has(k.r);
 const name=(r,q,tri,flat,sl)=>(flat?FLAT:SHARP)[r]+QN[tri?TRI[q]:q]+(!tri&&sl>=0?"/"+(flat?FLAT:SHARP)[sl]:"");
 /* find the repeating loop at the end of the chord list: the shortest cycle (2..8 chords) that fits the last stretch */
 function collapse(ev0,tri){const o=[];/* a chord heard for under ~1 s that sits between two others is the blend of a change, not a chord */
  const ev=ev0.filter((e,i)=>i===ev0.length-1||e.d>=.9);
  for(const e of ev){const l=o[o.length-1];if(l&&l.r===e.r&&(tri?TRI[l.q]===TRI[e.q]:(l.q===e.q&&l.slash===e.slash)))l.d+=e.d;else o.push({...e})}return o}
 function findLoop(ev0,tri){
  const ev=collapse(ev0,tri);
  const s=ev.map(e=>(e.r*5+(tri?TRI[e.q]:e.q))*13+(tri?0:e.slash+1));
  for(let L=2;L<=8;L++){
   if(s.length<L*2)continue;
   const n=Math.min(s.length,L*3);let ok=0,tot=0;
   for(let i=s.length-n;i<s.length-L;i++){tot++;if(s[i]===s[i+L])ok++}
   if(tot>=L&&ok/tot>=.8){
    /* the loop is the most common chord at each position, read from the last L events */
    const loop=ev.slice(s.length-L);
    /* start the loop on the chord that most often follows a long chord / is the key chord: start at the tonic if it is in there */
    return{loop,L};
   }
  }
  return null;
 }
 return{frame,pick,scoreAll,tracker,keyOf,collapse,name,useFlats,findLoop,ROM,TRI,SHARP,FLAT,FFT_N,HOP};
})();

const LIVE={key:null,on:false,ctx:null,stream:null,node:null,src:null,buf:null,fill:0,sr:44100,t:0,chS:new Float32Array(12),bsS:new Float32Array(12),cur:null,cand:null,candN:0,
 ev:[],rec:[],recN:0,tri:true,silent:0,peak:0};
const LIVE_MAX_SEC=480;
function liveSet(m){$("lvMsg").textContent=m}
function liveRender(){
 const ev=LIVE.ev,key=LIVE.key||(ev.length>=4?LV.keyOf(ev):null),fl=key?LV.useFlats(key):false,tri=LIVE.tri;
 const cur=LIVE.cur;
 $("lvNow").textContent=cur?LV.name(cur.r,cur.q,tri,fl,cur.slash):(LIVE.silent>6?"…":"–");
 $("lvKey").textContent=key?(LIVE.key?"Key: ":"Key (guess): ")+(fl?LV.FLAT:LV.SHARP)[key.r]+(key.m?" minor":" major"):"Listening for the key…";
 const last=LV.collapse(ev,tri).slice(-8);
 $("lvHist").innerHTML=last.map((e,i)=>`<span class="lvc${i===last.length-1?" now":""}">${LV.name(e.r,e.q,tri,fl,e.slash)}</span>`).join("");
 const lp=ev.length>=4?LV.findLoop(ev,tri):null;
 if(lp&&key){
  const rel=e=>LV.ROM[(e.r-key.r+12)%12];
  $("lvLoop").innerHTML=`<b>Progression (repeats every ${lp.L} chords)</b><div class="lvp">${lp.loop.map(e=>`<span class="lvc">${LV.name(e.r,e.q,tri,fl,e.slash)}</span>`).join("")}</div><div class="lvr">${lp.loop.map(e=>rel(e)+((tri?LV.TRI[e.q]:e.q)===1||(tri?LV.TRI[e.q]:e.q)===4?"m":"")).join(" – ")}</div>`;
 }else $("lvLoop").innerHTML="";
 $("lvTime").textContent=fmt(LIVE.t);
}
function liveProcess(){
 const x=LIVE.buf,{chroma,bass,rms}=LV.frame(x,LIVE.sr);
 LIVE.t+=LV.HOP/LIVE.sr;
 if(rms<.004){LIVE.silent++;return}
 LIVE.silent=0;LIVE.warm=(LIVE.warm||0)+1;
 /* heavy smoothing + a sticky tracker: on a real band recording a quick guess flickers; this settles on the chord about a second late */
 const a=.08;for(let p=0;p<12;p++){LIVE.chS[p]=(1-a)*LIVE.chS[p]+a*chroma[p];LIVE.bsS[p]=(1-a)*LIVE.bsS[p]+a*bass[p]}
 if(LIVE.warm<3)return;
 const b=LIVE.trk.step(LIVE.chS,LIVE.bsS);
 const same=(u,v)=>u.r===v.r&&(LIVE.tri?LV.TRI[u.q]===LV.TRI[v.q]:u.q===v.q&&u.slash===v.slash);
 if(!LIVE.cur){LIVE.cur=b;LIVE.ev.push({r:b.r,q:b.q,slash:b.slash,t:LIVE.t,d:0});return}
 if(same(b,LIVE.cur)){LIVE.candN=0;LIVE.cand=null}
 else{
  if(LIVE.cand&&same(LIVE.cand,b))LIVE.candN++;else{LIVE.cand=b;LIVE.candN=1}
  if(LIVE.candN>=2){LIVE.cur=b;LIVE.cand=null;LIVE.candN=0;LIVE.ev.push({r:b.r,q:b.q,slash:b.slash,t:LIVE.t,d:0})}
 }
 const l=LIVE.ev[LIVE.ev.length-1];if(l)l.d+=LV.HOP/LIVE.sr;
 if(LIVE.ev.length>400)LIVE.ev.splice(0,100);
}
async function liveStart(){
 if(LIVE.on)return;
 if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){liveSet("This browser can’t use the microphone here.");return}
 try{
  LIVE.stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false,channelCount:1}});
 }catch(e){
  liveSet(e&&e.name==="NotAllowedError"?"Microphone access was blocked. Allow it for this page in your browser settings, then try again.":"Couldn’t open the microphone ("+(e&&e.name||"error")+"). If this page is embedded, open ChordFlow in its own tab.");return}
 const AC=window.AudioContext||window.webkitAudioContext;LIVE.ctx=new AC();if(LIVE.ctx.resume)await LIVE.ctx.resume();
 LIVE.sr=LIVE.ctx.sampleRate;LIVE.buf=new Float32Array(LV.FFT_N);LIVE.fill=0;LIVE.t=0;LIVE.cur=null;LIVE.cand=null;LIVE.candN=0;LIVE.ev=[];LIVE.rec=[];LIVE.recN=0;LIVE.chS.fill(0);LIVE.bsS.fill(0);LIVE.silent=0;LIVE.warm=0;LIVE.trk=LV.tracker({stay:.99,beta:8});
 LIVE.src=LIVE.ctx.createMediaStreamSource(LIVE.stream);
 const node=LIVE.ctx.createScriptProcessor(4096,1,1);LIVE.node=node;let pend=0;
 node.onaudioprocess=e=>{
  if(!LIVE.on)return;const inp=e.inputBuffer.getChannelData(0);
  if(LIVE.recN<LIVE_MAX_SEC*LIVE.sr){LIVE.rec.push(new Float32Array(inp));LIVE.recN+=inp.length}else{liveStop();return}
  /* slide the analysis window */
  const n=inp.length;LIVE.buf.copyWithin(0,n>=LV.FFT_N?LV.FFT_N:n);
  if(n>=LV.FFT_N)LIVE.buf.set(inp.subarray(n-LV.FFT_N));else LIVE.buf.set(inp,LV.FFT_N-n);
  LIVE.fill=Math.min(LV.FFT_N,LIVE.fill+n);pend+=n;
  if(LIVE.fill>=LV.FFT_N&&pend>=LV.HOP){pend=0;liveProcess();liveRender()}
 };
 LIVE.src.connect(node);node.connect(LIVE.ctx.destination);                                   /* destination is silent: we write no output */
 LIVE.on=true;$("live").hidden=false;$("lvGo").hidden=true;$("lvStop").hidden=false;$("lvAfter").hidden=true;liveSet("Hold the phone near the speaker. The chord shows after a moment.");liveRender();
 try{if(navigator.wakeLock)LIVE.wl=await navigator.wakeLock.request("screen")}catch(e){}
}
function liveStop(){
 if(!LIVE.on)return;LIVE.on=false;
 try{LIVE.node.disconnect();LIVE.src.disconnect()}catch(e){}
 try{LIVE.stream.getTracks().forEach(t=>t.stop())}catch(e){}
 try{LIVE.ctx.close()}catch(e){}
 try{if(LIVE.wl)LIVE.wl.release()}catch(e){}
 $("lvGo").hidden=false;$("lvStop").hidden=true;
 const secs=LIVE.recN/LIVE.sr;
 if(secs>=20){$("lvAfter").hidden=false;liveSet("Stopped. Heard "+fmt(secs)+". Make a full chart from what was heard to get the beat, bars, 7ths and the Keys and Guitar tabs.")}
 else liveSet("Stopped.");
}
function liveWav(){
 const n=LIVE.recN,sr=Math.round(LIVE.sr),b=new ArrayBuffer(44+n*2),v=new DataView(b);
 const w=(o,s)=>{for(let i=0;i<s.length;i++)v.setUint8(o+i,s.charCodeAt(i))};
 w(0,"RIFF");v.setUint32(4,36+n*2,true);w(8,"WAVEfmt ");v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,sr,true);v.setUint32(28,sr*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);w(36,"data");v.setUint32(40,n*2,true);
 let o=44;for(const c of LIVE.rec)for(let i=0;i<c.length;i++){const s=Math.max(-1,Math.min(1,c[i]));v.setInt16(o,s<0?s*32768:s*32767,true);o+=2}
 return new Blob([b],{type:"audio/wav"});
}
$("lvGo").onclick=liveStart;$("lvStop").onclick=liveStop;
$("lvTri").onchange=e=>{LIVE.tri=e.target.value==="t";liveRender()};
$("lvChart").onclick=()=>{
 const f=new File([liveWav()],"Heard live "+new Date().toLocaleTimeString([], {hour:"numeric",minute:"2-digit"})+".wav",{type:"audio/wav"});
 $("live").hidden=true;LIVE.rec=[];LIVE.recN=0;load(f);
};
$("lvDrop").onclick=()=>{LIVE.rec=[];LIVE.recN=0;LIVE.ev=[];LIVE.cur=null;$("live").hidden=true;$("lvAfter").hidden=true;liveSet("")};

(()=>{const o=['<option value="">Key: auto</option>'];[0,1].forEach(m=>{for(let r=0;r<12;r++)o.push(`<option value="${r}|${m}">${LV.SHARP[r]}${m?" minor":" major"}</option>`)});$("lvKeySel").innerHTML=o.join("")})();
$("lvKeySel").onchange=e=>{const v=e.target.value;LIVE.key=v?{r:+v.split("|")[0],m:+v.split("|")[1]}:null;liveRender()};
