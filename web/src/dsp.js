/* ChordFlow analysis engine. No DOM. Input: mono Float32Array + sample rate. */
const ChordDSP=(()=>{
"use strict";
const NMAX=16384;
const TWC=new Float32Array(NMAX/2),TWS=new Float32Array(NMAX/2);
for(let i=0;i<NMAX/2;i++){TWC[i]=Math.cos(-2*Math.PI*i/NMAX);TWS[i]=Math.sin(-2*Math.PI*i/NMAX)}
function fft(re,im){
 const n=re.length;
 for(let i=1,j=0;i<n;i++){let b=n>>1;for(;j&b;b>>=1)j^=b;j^=b;if(i<j){let t=re[i];re[i]=re[j];re[j]=t;t=im[i];im[i]=im[j];im[j]=t}}
 for(let l=2;l<=n;l<<=1){const h=l>>1,st=NMAX/l;
  for(let i=0;i<n;i+=l)for(let j=0;j<h;j++){const a=i+j,b=a+h,wr=TWC[j*st],wi=TWS[j*st],vr=re[b]*wr-im[b]*wi,vi=re[b]*wi+im[b]*wr;re[b]=re[a]-vr;im[b]=im[a]-vi;re[a]+=vr;im[a]+=vi}}
}
const hann=n=>{const w=new Float32Array(n);for(let i=0;i<n;i++)w[i]=.5-.5*Math.cos(2*Math.PI*i/(n-1));return w};
const tick=()=>new Promise(r=>setTimeout(r));

/* ---- note dictionary (harmonic series per note), 3 bins per semitone from A1 ---- */
const NN=64,J=NN*3,M0=33;
const DICT=(()=>{
 const cols=[];
 for(let i=0;i<NN;i++){
  const v=new Float32Array(J);
  for(let h=1;h<=8;h++){const j=1+3*i+36*Math.log2(h);
   if(j<J-1)for(const [d,w] of [[-1,.5],[0,1],[1,.5]]){const jj=Math.round(j)+d;if(jj>=0&&jj<J)v[jj]+=w*Math.pow(.8,h-1)}}
  let s=0;for(let j=0;j<J;j++)s+=v[j]*v[j];s=Math.sqrt(s)||1;for(let j=0;j<J;j++)v[j]/=s;
  cols.push(v)}
 const dtd=new Float32Array(NN*NN);
 for(let a=0;a<NN;a++)for(let b=0;b<NN;b++){let s=0;for(let j=0;j<J;j++)s+=cols[a][j]*cols[b][j];dtd[a*NN+b]=s}
 const nz=cols.map(c=>{const o=[];for(let j=0;j<J;j++)if(c[j]>0)o.push([j,c[j]]);return o});
 return{nz,dtd}})();

/* ---- pitch analysis: spectrum -> log-frequency bins -> whitening -> note activations -> treble/bass chroma ---- */
async function chromaFrames(d,sr,prog){
 const W=16384,H=4096,win=hann(W),nF=Math.floor((d.length-W)/H)+1;
 const re=new Float32Array(W),im=new Float32Array(W);
 const kLo=new Int32Array(J),fr=new Float32Array(J);
 for(let j=0;j<J;j++){const f=55*Math.pow(2,(j-1)/36),k=f*W/sr;kLo[j]=Math.min(Math.floor(k),W/2-2);fr[j]=Math.min(1,k-kLo[j])}
 const kMax=kLo[J-1]+2,mag=new Float32Array(kMax+1),y=new Float32Array(J),yw=new Float32Array(J),tmp=new Float32Array(45);
 const x=new Float32Array(NN),dty=new Float32Array(NN);
 const treb=new Float32Array(nF*12),bass=new Float32Array(nF*12);
 for(let f=0;f<nF;f++){
  const o=f*H;for(let i=0;i<W;i++){re[i]=d[o+i]*win[i];im[i]=0}
  fft(re,im);for(let k=0;k<=kMax;k++)mag[k]=Math.hypot(re[k],im[k]);
  for(let j=0;j<J;j++)y[j]=Math.pow(mag[kLo[j]]*(1-fr[j])+mag[kLo[j]+1]*fr[j],.8);
  for(let j=0;j<J;j++){const a=Math.max(0,j-22),b=Math.min(J-1,j+22),n=b-a+1;for(let i=0;i<n;i++)tmp[i]=y[a+i];const s=tmp.subarray(0,n).sort();yw[j]=Math.max(0,y[j]-s[n>>1])}
  for(let i=0;i<NN;i++){let s=0;for(const [j,w] of DICT.nz[i])s+=w*yw[j];dty[i]=s;x[i]=.1}
  for(let it=0;it<40;it++)for(let i=0;i<NN;i++){let s=0;const r=i*NN;for(let k=0;k<NN;k++)s+=DICT.dtd[r+k]*x[k];x[i]*=dty[i]/(s+1e-9)}
  for(let i=0;i<NN;i++){const m=M0+i,pc=m%12;if(m<=56)bass[f*12+pc]+=x[i]*(m<=50?1:.6);if(m>=52)treb[f*12+pc]+=x[i]}
  if(f%20===0){prog(.05+.5*f/nF);await tick()}
 }
 return{treb,bass,nF,hopT:H/sr};
}

/* ---- beat tracking: spectral flux -> tempo (autocorrelation) -> dynamic programming ---- */
async function beatTrack(d,sr,prog){
 const W=1024,H=512,win=hann(W),nF=Math.floor((d.length-W)/H)+1,re=new Float32Array(W),im=new Float32Array(W);
 let prev=new Float32Array(W/2),cur=new Float32Array(W/2);const fl=new Float32Array(nF);
 for(let f=0;f<nF;f++){
  const o=f*H;for(let i=0;i<W;i++){re[i]=d[o+i]*win[i];im[i]=0}fft(re,im);
  let s=0;for(let k=0;k<W/2;k++){cur[k]=Math.log1p(100*Math.hypot(re[k],im[k]));if(f>0){const df=cur[k]-prev[k];if(df>0)s+=df}}
  fl[f]=s;const t=prev;prev=cur;cur=t;
  if(f%400===0){prog(.55+.1*f/nF);await tick()}}
 let mu=0;for(const v of fl)mu+=v;mu/=nF;let sd=0;for(const v of fl)sd+=(v-mu)*(v-mu);sd=Math.sqrt(sd/nF)||1;
 const o=new Float32Array(nF);for(let i=0;i<nF;i++)o[i]=Math.max(0,(fl[i]-mu)/sd);
 const fps=sr/H;
 const ac=lag=>{const l0=Math.floor(lag),fr=lag-l0;let s=0,n=0;for(let i=0;i+l0+1<nF;i++){s+=o[i]*(o[i+l0]*(1-fr)+o[i+l0+1]*fr);n++}return n?s/n:0};
 let bpm=110,bv=-1e9;
 for(let b=75;b<=170;b+=.5){const v=ac(fps*60/b)*Math.exp(-.5*Math.pow(Math.log2(b/110)/.8,2));if(v>bv){bv=v;bpm=b}}
 const T=fps*60/bpm,lo=Math.max(1,Math.floor(T/2)),hi=Math.ceil(2*T),pen=[];
 for(let t=lo;t<=hi;t++)pen[t-lo]=-100*Math.pow(Math.log(t/T),2);
 const C=Float32Array.from(o),P=new Int32Array(nF).fill(-1);
 for(let t=0;t<nF;t++){let best=-1e9,bj=-1;for(let tau=lo;tau<=hi;tau++){const c=t-tau;if(c<0)break;const v=C[c]+pen[tau-lo];if(v>best){best=v;bj=c}}
  if(bj>=0){C[t]=o[t]+best;P[t]=bj}}
 let t=nF-1,bm=-1e9;for(let i=Math.max(0,nF-Math.ceil(2*T));i<nF;i++)if(C[i]>bm){bm=C[i];t=i}
 const b=[t];while(P[t]>=0){t=P[t];b.push(t)}b.reverse();
 return{beats:b.map(i=>(i*H+W/2)/sr),bpm};
}

/* ---- chord models ---- */
const NSH=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
const TPL=(()=>{const T=[];for(const iv of [[0,4,7],[0,3,7]])for(let r=0;r<12;r++){const v=new Float32Array(12);[1,.8,.9].forEach((w,i)=>v[(r+iv[i])%12]=w);let n=0;for(const x of v)n+=x*x;n=Math.sqrt(n);for(let i=0;i<12;i++)v[i]/=n;T.push(v)}return T})();
const KP={maj:[6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88],min:[6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17]};
function pear(a,b){const ma=a.reduce((x,y)=>x+y)/12,mb=b.reduce((x,y)=>x+y)/12;let n=0,da=0,db=0;for(let i=0;i<12;i++){const x=a[i]-ma,y=b[i]-mb;n+=x*y;da+=x*x;db+=y*y}return n/Math.sqrt(da*db||1)}
function viterbi(S,nb,stays){
 const K=24,dd=new Float32Array(nb*K),bp=new Int16Array(nb*K),G=10;
 for(let k=0;k<K;k++)dd[k]=S[k]*G;
 for(let t=1;t<nb;t++){const s=stays[t],ls=Math.log(s),lc=Math.log((1-s)/(K-1));
  let b1=0,b2=-1;for(let k=0;k<K;k++){if(dd[(t-1)*K+k]>dd[(t-1)*K+b1])b1=k}
  for(let k=0;k<K;k++){let best=-1e30,bj=0;for(let j=0;j<K;j++){const v=dd[(t-1)*K+j]+(j===k?ls:lc);if(v>best){best=v;bj=j}}dd[t*K+k]=best+S[t*K+k]*G;bp[t*K+k]=bj}}
 let k=0;for(let j=1;j<K;j++)if(dd[(nb-1)*K+j]>dd[(nb-1)*K+k])k=j;
 const p=new Int16Array(nb);p[nb-1]=k;for(let t=nb-1;t>0;t--){k=bp[t*K+k];p[t-1]=k}return p;
}
const BASS_PRIOR=1.2;
const BASS_OCT={v:.5};
const median=a=>{const s=Float32Array.from(a).sort();return s[s.length>>1]};


/* ---- bass line: harmonic salience per note, guided by the detected chords, smoothed, split at attacks ---- */
async function bassLine(d,sr,segs,prog){
 const W=8192,H=1536,win=hann(W),nF=Math.floor((d.length-W)/H)+1,M0=31,NN=25;
 const re=new Float32Array(W),im=new Float32Array(W),kmax=Math.floor(1000*W/sr),Y=new Float32Array(kmax+2),Yw=new Float32Array(kmax+2),pre=new Float64Array(kmax+3);
 const whs=[1,.7,.5,.35],kLow=Math.floor(250*W/sr);
 const sal=new Float32Array(nF*NN),lb=new Float32Array(nF);
 const at=(fq)=>{const p=fq*W/sr,j=Math.floor(p),fr=p-j;return j+1>kmax?0:Yw[j]*(1-fr)+Yw[j+1]*fr};
 for(let f=0;f<nF;f++){
  const o=f*H;for(let i=0;i<W;i++){re[i]=d[o+i]*win[i];im[i]=0}fft(re,im);
  let e=0;for(let k=0;k<=kmax+1;k++){const m=Math.hypot(re[k],im[k]);Y[k]=Math.pow(m,.8);if(k<kLow)e+=m*m}
  lb[f]=Math.sqrt(e);
  pre[0]=0;for(let k=0;k<=kmax+1;k++)pre[k+1]=pre[k]+Y[k];
  for(let k=0;k<=kmax+1;k++){const a=Math.max(0,k-15),b=Math.min(kmax+1,k+15);Yw[k]=Math.max(0,Y[k]-(pre[b+1]-pre[a])/(b-a+1))}
  for(let i=0;i<NN;i++){const f0=440*Math.pow(2,(M0+i-69)/12);let s=0;
   for(let h=1;h<=4;h++){const fh=f0*h;if(fh>900)break;s+=whs[h-1]*Math.max(at(fh*.9981),at(fh),at(fh*1.0019))}
   sal[f*NN+i]=s}
  if(f%60===0){prog(.72+.25*f/nF);await tick()}
 }
 /* chord prior */
 const E=new Float32Array(nF*NN);let si=0;
 for(let f=0;f<nF;f++){
  const t=(f*H+W/2)/sr;while(si<segs.length-1&&t>=segs[si].t1)si++;
  const s=segs[si],minor=(s.q===1||s.q===4),w=new Float32Array(12);
  w[s.r]=1;w[(s.r+7)%12]=Math.max(w[(s.r+7)%12],.45);w[(s.r+(minor?3:4))%12]=Math.max(w[(s.r+(minor?3:4))%12],.3);if(s.slash>=0)w[s.slash]=Math.max(w[s.slash],.9);
  let mx=1e-9;for(let i=0;i<NN;i++)mx=Math.max(mx,sal[f*NN+i]);
  for(let i=0;i<NN;i++)E[f*NN+i]=sal[f*NN+i]/mx+BASS_PRIOR*w[(M0+i)%12]-BASS_OCT.v*Math.max(0,M0+i-43)/12;
 }
 const stay=.85,ls=Math.log(stay),lc=Math.log((1-stay)/(NN-1)),G=8,dd=new Float32Array(nF*NN),bp=new Int8Array(nF*NN);
 for(let i=0;i<NN;i++)dd[i]=E[i]*G;
 for(let t=1;t<nF;t++){let b1=0;for(let k=1;k<NN;k++)if(dd[(t-1)*NN+k]>dd[(t-1)*NN+b1])b1=k;
  for(let k=0;k<NN;k++){let best=-1e30,bj=0;for(let j=0;j<NN;j++){const v=dd[(t-1)*NN+j]+(j===k?ls:lc);if(v>best){best=v;bj=j}}dd[t*NN+k]=best+E[t*NN+k]*G;bp[t*NN+k]=bj}}
 const path=new Int8Array(nF);let k=0;for(let j=1;j<NN;j++)if(dd[(nF-1)*NN+j]>dd[(nF-1)*NN+k])k=j;
 path[nF-1]=k;for(let t=nF-1;t>0;t--){k=bp[t*NN+k];path[t-1]=k}
 /* voiced / attacks from low-band energy */
 const srt=Float32Array.from(lb).sort(),thr=srt[Math.floor(nF*.25)];
 const voiced=new Uint8Array(nF);for(let t=0;t<nF;t++)voiced[t]=lb[t]>thr?1:0;
 for(let t=1;t<nF-1;t++)if(!voiced[t]&&voiced[t-1]&&voiced[t+1]&&path[t-1]===path[t+1])voiced[t]=1; // bridge 1-frame dropouts
 const notes=[];let cur=null,last=-9,gap=0;
 const tc=f=>(f*H+W/2)/sr;
 for(let t=0;t<nF;t++){
  const att=t>0&&lb[t]>lb[t-1]*1.4&&lb[t]>thr*1.5&&t-last>=3;
  if(!voiced[t]){gap++;if(cur&&gap>2){cur.t1=tc(t-gap+1)-H/sr/2;notes.push(cur);cur=null}continue}
  gap=0;const m=M0+path[t];
  if(cur&&(cur.m!==m||att)){cur.t1=tc(t)-H/sr/2;notes.push(cur);cur=null}
  if(!cur){cur={m,t0:tc(t)-H/sr/2,t1:0};last=t}
 }
 if(cur){cur.t1=tc(nF-1);notes.push(cur)}
 let out=notes.filter(n=>n.t1-n.t0>=.1);
 /* a short note an octave above its neighbour is usually the attack, not a separate note */
 out=out.filter((n,i)=>{if(n.t1-n.t0>=.3)return true;const nx=out[i+1],pv=out[i-1];
  return !((nx&&nx.m%12===n.m%12&&Math.abs(nx.m-n.m)===12&&nx.t0-n.t1<.15)||(pv&&pv.m%12===n.m%12&&Math.abs(pv.m-n.m)===12&&n.t0-pv.t1<.15))});
 return out;
}

async function analyze(x,sr,prog=()=>{}){
 prog(.02);
 const st=Math.max(1,Math.round(sr/22050)),sr2=sr/st,n2=Math.floor(x.length/st),d=new Float32Array(n2);
 for(let i=0;i<n2;i++){let s=0;for(let k=0;k<st;k++)s+=x[i*st+k];d[i]=s/st}
 if(n2<16384*3)throw new Error("short");
 const dur=x.length/sr;
 const cf=await chromaFrames(d,sr2,prog);
 const bt=await beatTrack(d,sr2,prog);
 prog(.68);await tick();
 let beats=bt.beats;
 if(beats.length<16){const T=60/bt.bpm;beats=[];for(let t=0;t<dur;t+=T)beats.push(t)}
 const nb=beats.length-1;
 /* beat-synchronous chroma */
 const Cb=new Float32Array(nb*12),Bb=new Float32Array(nb*12),cnt=new Int32Array(nb);
 for(let f=0,j=0;f<cf.nF;f++){const t=(f+.5)*cf.hopT;while(j<nb&&beats[j+1]<=t)j++;if(j>=nb)break;if(t<beats[0])continue;
  for(let p=0;p<12;p++){Cb[j*12+p]+=cf.treb[f*12+p];Bb[j*12+p]+=cf.bass[f*12+p]}cnt[j]++}
 for(let j=0;j<nb;j++){let a=0,b=0;const c=Math.max(cnt[j],1);for(let p=0;p<12;p++){Cb[j*12+p]/=c;Bb[j*12+p]/=c;a+=Cb[j*12+p]**2;b+=Bb[j*12+p]}
  a=Math.sqrt(a)+1e-9;b+=1e-9;for(let p=0;p<12;p++){Cb[j*12+p]/=a;Bb[j*12+p]/=b}}
 /* emission: template match + bass evidence */
 const E=new Float32Array(nb*24),LAM=1.5;
 for(let t=0;t<nb;t++)for(let k=0;k<24;k++){let s=0;for(let p=0;p<12;p++)s+=Cb[t*12+p]*TPL[k][p];const r=k%12;E[t*24+k]=s+LAM*(Bb[t*12+r]+.3*Bb[t*12+(r+7)%12])}
 /* bar phase: where do chords change most often? */
 const nov=new Float32Array(nb);for(let t=1;t<nb;t++){let s=0;for(let p=0;p<12;p++)s+=Cb[t*12+p]*Cb[(t-1)*12+p];nov[t]=1-s}
 let phase=0,pb=-1;for(let ph=0;ph<4;ph++){let s=0,n=0;for(let t=ph;t<nb;t+=4){s+=nov[t];n++}s/=Math.max(n,1);if(s>pb){pb=s;phase=ph}}
 const stays=new Float32Array(nb);for(let t=0;t<nb;t++)stays[t]=((t-phase)%4+4)%4===0?.8:.97;
 prog(.72);await tick();
 let p=viterbi(E,nb,stays);
 /* drop rarely used chords, decode again */
 const use=new Float32Array(24);for(const k of p)use[k]++;
 const E2=Float32Array.from(E);for(let t=0;t<nb;t++)for(let k=0;k<24;k++)if(use[k]/nb<.03)E2[t*24+k]=-5;
 p=viterbi(E2,nb,stays);
 /* segments (merge 1-beat blips) */
 let runs=[];for(let t=0;t<nb;t++){const l=runs[runs.length-1];if(l&&l.k===p[t])l.n++;else runs.push({k:p[t],a:t,n:1})}
 const m=[];for(const r of runs){const l=m[m.length-1];if(l&&(r.n<2||l.k===r.k)){l.n+=r.n}else m.push({...r})}
 if(m.length>1&&m[0].n<2){m[1].a=m[0].a;m[1].n+=m[0].n;m.shift()}
 /* describe each segment */
 const segs=[];
 for(const s of m){
  const a=s.a,b=s.a+s.n;let k=s.k;
  const med=new Float32Array(12);
  for(let pc=0;pc<12;pc++){const v=[];for(let t=a;t<b;t++)v.push(Cb[t*12+pc]);med[pc]=s.n>=3?median(v):v.reduce((x,y)=>x+y)/v.length}
  const bass=new Float32Array(12);for(let t=a;t<b;t++)for(let pc=0;pc<12;pc++)bass[pc]+=Bb[t*12+pc];
  let bp=0;for(let pc=1;pc<12;pc++)if(bass[pc]>bass[bp])bp=pc;const bsh=bass[bp]/(s.n||1);
  /* inversion check: does a chord with the bass note as its 3rd or 5th fit the upper notes better? */
  const tc=k2=>{let z=0;for(let p=0;p<12;p++)z+=med[p]*TPL[k2][p];return z/(Math.hypot(...med)+1e-9)};
  let slash=-1;
  if(bsh>=.25&&bp===k%12){
   /* bass sits on the root: could this be a chord whose 3rd is the bass note (e.g. B/D# heard as D#m)? */
   for(const k2 of [(bp+8)%12]){const r2=k2%12;
    if(bass[r2]/(s.n||1)>=.12&&tc(k2)>=tc(k)-ChordDSP.INV2){k=k2;slash=bp;break}}
  }else if(bsh>=.25&&bp!==k%12){
   let bk=-1,bs=tc(k)+ChordDSP.INV;
   for(let k2=0;k2<24;k2++){const r2=k2%12,th=(r2+(k2>=12?3:4))%12,fi=(r2+7)%12;if(k2===k||(bp!==th&&bp!==fi))continue;const z=tc(k2);if(z>bs){bs=z;bk=k2}}
   if(bk>=0){k=bk;slash=bp}
  }
  const r=k%12,minor=k>=12?1:0,third=(r+(minor?3:4))%12,fifth=(r+7)%12;
  const ct=(med[r]+med[third]+med[fifth])/3+1e-9;
  let q=minor;const c7=med[(r+10)%12]/ct,cM=med[(r+11)%12]/ct;
  if(!minor){if(c7>=ChordDSP.T7&&c7>cM)q=2;else if(cM>=ChordDSP.TM7&&cM>c7)q=3}else if(c7>=ChordDSP.T7)q=4;
  const xt=[];for(const iv of (minor?[1,2,5,6,8,9]:[1,2,3,5,6,8,9])){const v=med[(r+iv)%12]/ct;if(v>=ChordDSP.TX)xt.push([iv,v])}
  xt.sort((u,v)=>v[1]-u[1]);
  if(slash<0&&bp!==r&&bsh>=.3&&new Set([third,fifth,(r+10)%12,(r+11)%12]).has(bp))slash=bp;
  if(slash===r)slash=-1;
  const mean=new Float32Array(24);for(let t=a;t<b;t++)for(let kk=0;kk<24;kk++)mean[kk]+=E[t*24+kk]/s.n;
  let alt=-1,am=-1e9;for(let kk=0;kk<24;kk++)if(kk%12!==r&&mean[kk]>am){am=mean[kk];alt=kk}
  const margin=mean[k]-am;
  segs.push({t0:a===0?0:beats[a],t1:b>=nb?dur:beats[b],b0:a,b1:b,r,q,xt:xt.slice(0,2).map(u=>u[0]),slash,margin,unsure:margin<.08,alt:margin<.2?{r:alt%12,q:alt>=12?1:0}:null,conf:mean[k],dbg:{c7,cM,xv:xt.map(u=>+u[1].toFixed(2))}});
 }
 /* key */
 const av=new Array(12).fill(0);for(let t=0;t<nb;t++)for(let pc=0;pc<12;pc++)av[pc]+=Cb[t*12+pc];
 let key={r:0,m:0,s:-9};
 for(let r=0;r<12;r++)for(const mi of [0,1]){const rot=av.map((_,i)=>av[(i+r)%12]),sc=pear(rot,KP[mi?"min":"maj"]);if(sc>key.s)key={r,m:mi,s:sc}}
 const bass=await bassLine(d,sr2,segs,prog);
 prog(1);
 return{segs,key,bpm:Math.round(bt.bpm),beats,phase,dur,nb,bass};
}
return{analyze,NSH,BASS_OCT,T7:.7,TM7:.8,TX:1.6,INV:.04,INV2:.03};
})();
if(typeof module!=="undefined")module.exports=ChordDSP;
