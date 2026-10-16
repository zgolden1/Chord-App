/* ---------- lyrics: parsing, syllables, timing, alignment (no DOM) ---------- */
const LYR=(()=>{
"use strict";
const norm=w=>w.toLowerCase().replace(/[^a-z0-9]/g,"");
/* [mm:ss.xx] text  (several stamps per line allowed; metadata tags like [ar:..] ignored) */
function parseLRC(txt){
 const out=[];let off=0;
 const om=txt.match(/^\s*\[offset:\s*([+-]?\d+)\s*\]/im);if(om)off=-(+om[1])/1000;
 for(const raw of txt.split(/\r?\n/)){
  const m=raw.match(/^\s*((?:\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]\s*)+)(.*)$/);
  if(!m)continue;
  const text=m[2].replace(/<\d{1,3}:\d{2}(?:[.:]\d{1,3})?>/g,"").trim();
  for(const st of m[1].matchAll(/\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]/g)){
   const frac=st[3]?+("0."+st[3]):0;out.push({t:+st[1]*60+ +st[2]+frac+off,text})}
 }
 out.sort((a,b)=>a.t-b.t);return out;
}
function parsePlain(txt){return txt.split(/\r?\n/).map(s=>s.trim()).filter(s=>s&&!/^\[[^\]]*\]$/.test(s)).map(text=>({t:null,text}))}
/* split a word into syllables (English heuristic) */
const V=/[aeiouy]/i;
function syllables(word){
 const m=word.match(/^([^A-Za-z']*)(.*?)([^A-Za-z']*)$/),pre=m[1],core=m[2],post=m[3];
 if(core.length<=3||!V.test(core))return[word];
 const lw=core.toLowerCase();let groups=[];
 for(let i=0;i<lw.length;){if(V.test(lw[i])){let j=i;while(j<lw.length&&V.test(lw[j]))j++;groups.push([i,j]);i=j}else i++}
 if(groups.length>1){
  const last=groups[groups.length-1];
  if(last[1]===lw.length&&lw.slice(last[0])==="e"&&!/[^aeiouy]le$/.test(lw))groups.pop();
  else if(lw.length-last[1]===1&&lw[last[0]]==="e"&&last[1]-last[0]===1&&(lw.endsWith("ed")&&!/[td]ed$/.test(lw)||lw.endsWith("es")&&!/(s|x|z|ch|sh|ce|ge|se)s$/.test(lw)&&!/[sxz]es$|(ch|sh)es$|[cg]es$/.test(lw)))groups.pop();
 }
 if(groups.length<2)return[word];
 const cuts=[];
 for(let g=0;g<groups.length-1;g++){
  const a=groups[g][1],b=groups[g+1][0],cl=b-a,c=lw.slice(a,b);let cut;
  const isLE=g+1===groups.length-1&&/[^aeiouy]le$/.test(lw)&&groups[g+1][0]===lw.length-1;
  if(isLE)cut=Math.max(a,b-2);
  else if(cl===0)cut=b;else if(cl===1)cut=a;
  else if(/^(th|sh|ch|ph|wh)/.test(c))cut=a;
  else if(/^ck/.test(c)||(/^ng/.test(c)&&lw.endsWith("ing")&&b===lw.length-3))cut=a+2;
  else cut=a+1;
  if(g===groups.length-2&&groups.length>1&&b>=lw.length)continue;
  cuts.push(cut)}
 const parts=[];let s=0;const cw=core;
 for(const c of cuts){if(c>s&&c<cw.length){parts.push(cw.slice(s,c));s=c}}
 parts.push(cw.slice(s));
 parts[0]=pre+parts[0];parts[parts.length-1]+=post;return parts;
}
/* level 1: words -> syllables */
function wordsOf(text){return text.split(/\s+/).filter(Boolean).map(w=>({w,syl:syllables(w)}))}
/* give every syllable a start time inside [t0,t1). If word times are known (wt[i]={s,e}) use them. */
function timeLine(text,t0,t1,wt){
 const words=wordsOf(text),flat=[];
 const total=words.reduce((a,w)=>a+w.syl.length,0)||1;
 let k=0;
 words.forEach((w,wi)=>{
  let ws,we;
  if(wt&&wt[wi]){ws=wt[wi].s;we=wt[wi].e}
  else{ws=t0+(t1-t0)*k/total;we=t0+(t1-t0)*(k+w.syl.length)/total}
  w.syl.forEach((s,si)=>flat.push({txt:s,t:ws+(we-ws)*si/w.syl.length,wi,first:si===0,lastOfWord:si===w.syl.length-1}));
  k+=w.syl.length;
 });
 return{words,syl:flat,t0:flat.length?flat[0].t:t0,t1};
}
/* line end estimate: don't stretch a sung line across a long instrumental gap */
function lineEnd(text,t0,nextT){
 const n=wordsOf(text).reduce((a,w)=>a+w.syl.length,0);
 const est=t0+n*.34+.5;return nextT==null?est:Math.min(nextT,est);
}
/* chords over syllables. chords: [{t0,t1,name}] ; returns lines with per-syllable chord label */
function layout(lines,chords,opts={}){
 const gapMin=opts.gap??3,rows=[];
 const chordAt=t=>{for(let i=chords.length-1;i>=0;i--)if(chords[i].t0<=t+.12)return i;return 0};
 let prevEnd=null,prevChord=-1;
 const instr=(a,b)=>{ // chord-only row between a and b
  const idx=[];for(let i=0;i<chords.length;i++)if(chords[i].t1>a&&chords[i].t0<b)idx.push(i);
  if(idx.length&&b-a>=gapMin)rows.push({kind:"inst",t:a,names:idx.map(i=>chords[i].name)})};
 const real=lines.filter(l=>l.t!=null);
 real.forEach((ln,i)=>{
  if(!ln.text){return}
  const nextT=(()=>{for(let j=i+1;j<real.length;j++)if(real[j].text)return real[j].t;return null})();
  const t0=ln.t,t1=ln.words?ln.words[ln.words.length-1].e:lineEnd(ln.text,t0,nextT);
  const wt=ln.words||null;
  if(prevEnd===null)instr(0,t0);else instr(prevEnd,t0);
  const tl=timeLine(ln.text,t0,t1,wt);
  const labels=new Array(tl.syl.length).fill(null);
  let ci=chordAt(t0);
  labels[0]={name:chords[ci]?.name,cont:ci===prevChord};
  for(let c=ci+1;c<chords.length&&chords[c].t0<t1;c++){
   if(chords[c].t0<t0)continue;
   let best=0,bd=1e9;tl.syl.forEach((s,k)=>{const d=Math.abs(s.t-chords[c].t0);if(d<bd){bd=d;best=k}});
   if(best===0&&chordAt(t0)!==c){labels[0]={name:chords[c].name,cont:false}}else labels[best]={name:chords[c].name,cont:false};
   ci=c}
  prevChord=ci;prevEnd=t1;
  rows.push({kind:"line",t:t0,t1,syl:tl.syl.map((s,k)=>({...s,ch:labels[k]})),words:tl.words});
 });
 if(prevEnd!==null&&chords.length)instr(prevEnd,chords[chords.length-1].t1);
 return rows;
}
/* ---- align lyric words to recognised words (global alignment, fuzzy match) ---- */
function lev(a,b){if(a===b)return 0;const m=a.length,n=b.length;if(!m||!n)return Math.max(m,n);const d=[];for(let i=0;i<=m;i++){d[i]=[i]}for(let j=1;j<=n;j++)d[0][j]=j;
 for(let i=1;i<=m;i++)for(let j=1;j<=n;j++)d[i][j]=Math.min(d[i-1][j]+1,d[i][j-1]+1,d[i-1][j-1]+(a[i-1]===b[j-1]?0:1));return d[m][n]}
function sim(a,b){if(a===b)return 2;if(a.length>=4&&b.length>=4&&lev(a,b)<=1)return 1.2;if(a.length>=3&&b.length>=3&&lev(a,b)<=Math.floor(Math.min(a.length,b.length)/3))return .5;return -1}
/* lyrics: lines [{text}] ; heard: [{w,s,e}] -> lines with t and words[{s,e}] */
function alignLyrics(lines,heard){
 const L=[];lines.forEach((ln,li)=>ln.text.split(/\s+/).filter(Boolean).forEach((w,wi)=>L.push({li,wi,n:norm(w)})));
 const H=heard.map(h=>({...h,n:norm(h.w)})).filter(h=>h.n);
 const n=L.length,m=H.length,GAP=-.6;
 const sc=new Float32Array((n+1)*(m+1)),tb=new Uint8Array((n+1)*(m+1));
 for(let i=1;i<=n;i++){sc[i*(m+1)]=i*GAP;tb[i*(m+1)]=1}
 for(let j=1;j<=m;j++){sc[j]=0;tb[j]=2}      // free to skip leading heard words
 for(let i=1;i<=n;i++)for(let j=1;j<=m;j++){
  const d=sc[(i-1)*(m+1)+j-1]+sim(L[i-1].n,H[j-1].n),u=sc[(i-1)*(m+1)+j]+GAP,l=sc[i*(m+1)+j-1]+(i===n?0:GAP);
  let best=d,t=0;if(u>best){best=u;t=1}if(l>best){best=l;t=2}sc[i*(m+1)+j]=best;tb[i*(m+1)+j]=t}
 // best end (free trailing heard words)
 let i=n,j=0,bs=-1e9;for(let jj=0;jj<=m;jj++)if(sc[n*(m+1)+jj]>bs){bs=sc[n*(m+1)+jj];j=jj}
 const match=new Array(n).fill(-1);
 while(i>0&&j>=0){const t=tb[i*(m+1)+j];
  if(t===0&&j>0){if(sim(L[i-1].n,H[j-1].n)>0)match[i-1]=j-1;i--;j--}else if(t===1||j===0){i--}else j--}
 // fill times: matched words take heard times; others interpolate between neighbours
 const ts=new Array(n).fill(null);
 for(let k=0;k<n;k++)if(match[k]>=0)ts[k]={s:H[match[k]].s,e:H[match[k]].e,real:true};
 let k=0;
 while(k<n){if(ts[k]){k++;continue}
  let a=k-1,b=k;while(b<n&&!ts[b])b++;
  const sT=a>=0?ts[a].e:(b<n?ts[b].s-.4*(b-k):0),eT=b<n?ts[b].s:sT+.4*(b-k);
  for(let q=k;q<b;q++){const f0=(q-k)/(b-k),f1=(q-k+1)/(b-k);ts[q]={s:sT+(eT-sT)*f0,e:sT+(eT-sT)*f1,real:false}}
  k=b}
 const out=lines.map(l=>({text:l.text,words:[]}));
 L.forEach((w,idx)=>out[w.li].words.push({s:ts[idx].s,e:Math.max(ts[idx].e,ts[idx].s+.05),real:ts[idx].real}));
 out.forEach(l=>{l.t=l.words.length?l.words[0].s:null;l.matched=l.words.filter(w=>w.real).length/(l.words.length||1)});
 return out;
}
/* turn heard words into lines at pauses */
function heardToLines(heard,pause=.9,maxWords=9){
 const lines=[];let cur=null;
 for(const h of heard){const w=h.w.trim();if(!w)continue;
  if(!cur||h.s-cur.words[cur.words.length-1].e>pause||cur.words.length>=maxWords){cur={words:[],text:""};lines.push(cur)}
  cur.words.push({s:h.s,e:h.e,w});cur.text+=(cur.text?" ":"")+w}
 return lines.map(l=>({t:l.words[0].s,text:l.text,words:l.words.map(x=>({s:x.s,e:x.e,real:true}))}));
}
/* tiny ID3v2 reader for title/artist */
function id3(buf){
 const b=new Uint8Array(buf);if(b.length<10||b[0]!==73||b[1]!==68||b[2]!==51)return{};
 const ver=b[3],size=((b[6]&127)<<21)|((b[7]&127)<<14)|((b[8]&127)<<7)|(b[9]&127),end=Math.min(b.length,10+size);
 let p=10;const out={};
 const dec=(a,enc)=>{try{return new TextDecoder(enc===1||enc===2?(enc===2?"utf-16be":"utf-16"):enc===3?"utf-8":"iso-8859-1").decode(a).replace(/\0+$/,"").replace(/^﻿/,"")}catch(e){return""}};
 while(p+10<=end){
  const id=String.fromCharCode(b[p],b[p+1],b[p+2],b[p+3]);if(!/^[A-Z0-9]{4}$/.test(id))break;
  const sz=ver===4?((b[p+4]&127)<<21)|((b[p+5]&127)<<14)|((b[p+6]&127)<<7)|(b[p+7]&127):((b[p+4]<<24)|(b[p+5]<<16)|(b[p+6]<<8)|b[p+7])>>>0;
  if(sz<=0||p+10+sz>end)break;
  if(id==="TIT2"||id==="TPE1"){const enc=b[p+10],txt=dec(b.subarray(p+11,p+10+sz),enc);if(id==="TIT2")out.title=txt;else out.artist=txt}
  p+=10+sz}
 return out;
}
function nameGuess(fn){
 let s=fn.replace(/\.[^.]+$/,"").replace(/^[0-9a-f]{8}-/,"").replace(/_/g," ").replace(/\s+/g," ").trim();
 s=s.replace(/^\d{1,2}[\s.\-]+(?=\D)/,"");
 const m=s.split(/\s+-\s+/);
 return m.length>=2?{artist:m[0].trim(),title:m.slice(1).join(" - ").trim()}:{artist:"",title:s};
}
return{parseLRC,parsePlain,syllables,wordsOf,timeLine,lineEnd,layout,alignLyrics,heardToLines,id3,nameGuess,norm};
})();
if(typeof module!=="undefined")module.exports=LYR;
