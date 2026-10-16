/* ---------- voicings, guitar shapes, scales (no DOM) ---------- */
const VOI=(()=>{
"use strict";
const IV=[[0,4,7],[0,3,7],[0,4,7,10],[0,4,7,11],[0,3,7,10],[0,2,7],[0,5,7],[0,3,6],[0,4,8],[0,3,6,10],[0,4,7,9],[0,3,7,9]];
const TRIQ=[0,1,0,0,1,5,6,7,8,7,0,1];
const NS=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
/* chord as {r,q,xt,slash} -> pitch classes in order root,3rd,5th,7th,... */
function tones(c,detail){
 const q=detail?c.q:TRIQ[c.q],iv=IV[q].slice();
 if(detail===2)for(const x of (c.xt||[]))if(!iv.includes(x))iv.push(x);
 return{q,iv,pcs:iv.map(i=>(c.r+i)%12)};
}
/* ----- piano voicings ----- */
const near=(pc,mid)=>{let m=Math.round((mid-pc)/12)*12+pc;return m};
function sortedAround(pcs,low){ // ascending stack starting from the first pc at/after low
 const out=[];let m=low;for(const pc of pcs){while(m%12!==pc)m++;out.push(m);m++}
 return out;
}
function rhCandidates(pcs,lo,hi){
 const cands=[];
 for(let rot=0;rot<pcs.length;rot++){
  const order=pcs.slice(rot).concat(pcs.slice(0,rot));
  for(let base=lo;base<lo+12;base++){if(base%12!==order[0])continue;
   const notes=sortedAround(order,base);if(notes[notes.length-1]<=hi)cands.push(notes)}}
 return cands;
}
function dist(a,b){if(!b||a.length!==b.length){const ca=a.reduce((x,y)=>x+y)/a.length;return Math.abs(ca-(b?b.reduce((x,y)=>x+y)/b.length:64))*2}let s=0;for(let i=0;i<a.length;i++)s+=Math.abs(a[i]-b[i]);return s}
/* style: "triad" or "jazz". prev: previous suggestion for smooth voice leading. */
function suggest(c,detail,style,prev,alt){
 const t=tones(c,detail),bassPc=detail&&c.slash>=0?c.slash:c.r;
 const lh=[near(bassPc,41)];if(lh[0]<36)lh[0]+=12;if(lh[0]>47)lh[0]-=12;
 let rhPcs;
 if(style==="jazz"&&t.iv.length>=4){rhPcs=t.pcs.slice(1)}              // 3rd 5th 7th (+ extensions): rootless
 else if(style==="jazz"){rhPcs=t.pcs.slice(1).concat(t.pcs[0])}         // triad: 3rd 5th root
 else rhPcs=t.pcs.slice();
 if(style==="jazz"&&t.iv.length>=4){lh.push(lh[0]+7>47?lh[0]+7-12:lh[0]+7)}
 const cands=rhCandidates(rhPcs,55,77);
 const cs=cands.map(k=>({k,d:dist(k,prev&&prev.rh)})).sort((a,b)=>a.d-b.d);const best=cs.length?cs[(alt||0)%cs.length].k:null;
 return{lh:lh.sort((a,b)=>a-b),rh:best||[]};
}
/* ----- guitar shapes (standard tuning) ----- */
const STR=[40,45,50,55,59,64];
function shapes(c,detail,max=3){
 const t=tones(c,detail),bassPc=detail&&c.slash>=0?c.slash:c.r;
 const need=new Set([t.pcs[0],t.pcs[1]]);if(t.iv.length>=4)need.add(t.pcs[3]);
 const allowed=new Set(t.pcs);const res=[];
 const seen=new Set();
 for(let p=0;p<=9;p++){
  const frets=[null,0];if(p===0){frets.push(1,2,3)}else{for(let f=p;f<=p+3;f++)frets.push(f)}
  const cur=new Array(6);
  (function rec(s){
   if(s===6){evalShape(cur.slice());return}
   for(const f of frets){cur[s]=f===null?-1:f;
    if(f===null&&s>0&&cur.slice(0,s).some(x=>x>=0)&&false)continue;rec(s+1)}
  })(0);
 }
 function evalShape(sh){
  const pl=[];for(let s=0;s<6;s++)if(sh[s]>=0)pl.push(s);
  if(pl.length<(t.iv.length>=4?4:4))return;
  // sounded strings contiguous
  for(let i=pl[0];i<=pl[pl.length-1];i++)if(sh[i]<0)return;
  const pcs=pl.map(s=>(STR[s]+sh[s])%12),pcset=new Set(pcs);
  for(const pc of pcset)if(!allowed.has(pc))return;
  for(const n of need)if(!pcset.has(n))return;
  if(pcs[0]!==bassPc)return;
  const fr=pl.map(s=>sh[s]).filter(f=>f>0);
  if(fr.length&&Math.max(...fr)>=4&&pl.some(s=>sh[s]===0))return;
  if(fr.length){const mn=Math.min(...fr),mx=Math.max(...fr);if(mx-mn>3)return}
  // fingers: barre when the lowest fret is used on 2+ strings and nothing below it is open/muted between them
  let fingers=fr.length,barre=false;
  if(fr.length){const mn=Math.min(...fr),idx=pl.filter(s=>sh[s]===mn);
   if(idx.length>=2){const a=idx[0],b=idx[idx.length-1];let ok=true;for(let s=a;s<=b;s++)if(sh[s]<mn)ok=false;if(ok){barre=true;fingers=fr.filter(f=>f!==mn).length+1}}}
  if(fingers>4)return;
  const key=sh.join(",");if(seen.has(key))return;seen.add(key);
  const mutes=6-pl.length,opens=pl.filter(s=>sh[s]===0).length,minF=fr.length?Math.min(...fr):0,maxF=fr.length?Math.max(...fr):0;
  const cost=maxF*.22+minF*.1+fingers*.7+mutes*.5-opens*.35+(barre?1.1:0)+(pcset.size<t.pcs.length-(t.pcs.length>=4?1:0)?.6:0)-(pl.length>=5?.3:0);
  res.push({sh,cost,minF,barre,fingers});
 }
 res.sort((a,b)=>a.cost-b.cost);
 const out=[];const used=new Set();
 for(const r of res){const pos=r.minF>0?Math.floor((r.minF-1)/3):0;const k=pos+""+r.barre;if(used.has(k)&&out.length<max)continue;out.push(r);used.add(k);if(out.length>=max)break}
 return out;
}
/* ----- scales ----- */
const SCALES={
 "Major pentatonic":[0,2,4,7,9],"Minor pentatonic":[0,3,5,7,10],"Major scale":[0,2,4,5,7,9,11],"Natural minor":[0,2,3,5,7,8,10],"Blues":[0,3,5,6,7,10]
};
function fretNotes(maxFret){const out=[];for(let s=0;s<6;s++)for(let f=0;f<=maxFret;f++)out.push({s,f,pc:(STR[s]+f)%12});return out}
return{tones,suggest,shapes,SCALES,fretNotes,STR,NS};
})();
if(typeof module!=="undefined")module.exports=VOI;
