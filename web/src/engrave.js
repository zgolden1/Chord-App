/* ---------- bass staff + tab, drawn as SVG ---------- */
const ENG=(()=>{
const SP=8,DW=214,STEMLEN=26;
const LET=[0,0,1,1,2,3,3,4,4,5,5,6];                 // pitch class -> letter index (C=0) when spelled with sharps
const LETF=[0,1,1,2,2,3,4,4,5,5,6,6];                // ... spelled with flats
const SHARPN={0:0,7:1,2:2,9:3,4:4,11:5,6:6,1:7,8:8,3:9,10:10,5:11}; // (unused extras)
const KEYSIG_MAJOR_SHARPS={0:0,7:1,2:2,9:3,4:4,11:5,6:6};
const KEYSIG_MAJOR_FLATS={0:0,5:1,10:2,3:3,8:4,1:5,6:6};
const SHARP_STEPS=[24,21,25,22,19,23,20],FLAT_STEPS=[20,23,19,22,18,21,24];
const SHARP_LET=[3,0,4,1,5,2,6],FLAT_LET=[6,2,5,1,4,0,3];   // F C G D A E B ; B E A D G C F
const OPEN=[43,38,33,28];                                   // G D A E (sounding)
function keyInfo(tonicPc,minor,flats){
 const maj=minor?(tonicPc+3)%12:tonicPc;
 const n=flats?(KEYSIG_MAJOR_FLATS[maj]??0):(KEYSIG_MAJOR_SHARPS[maj]??0);
 return{n,flats};
}
/* spell a sounding midi note (written an octave up), using the key's own spelling first */
const NATPC=[0,2,4,5,7,9,11];
function sigOf(ks){const a=new Array(7).fill(0);for(let i=0;i<ks.n;i++)a[ks.flats?FLAT_LET[i]:SHARP_LET[i]]=ks.flats?-1:1;return a}
function spell(m,ks){
 const w=m+12,pc=((w%12)+12)%12,oct=Math.floor(w/12)-1,sig=sigOf(ks);
 for(let l=0;l<7;l++)if(((NATPC[l]+sig[l])%12+12)%12===pc)return{step:oct*7+l,acc:sig[l],letter:l,sig:sig[l]};
 const li=ks.flats?LETF[pc]:LET[pc];let acc=pc-NATPC[li];if(acc>6)acc-=12;if(acc<-6)acc+=12;
 return{step:oct*7+li,acc,letter:li,sig:sig[li]};
}
const yOf=(step,top)=>top+4*SP-(step-18)*SP/2;
function sharp(x,y){return`<path d="M${x-2},${y-6}v12M${x+2},${y-7}v12" stroke="currentColor" stroke-width="1"/><path d="M${x-4},${y-1.5}l8,-2.2M${x-4},${y+3}l8,-2.2" stroke="currentColor" stroke-width="2"/>`}
function flat(x,y){return`<path d="M${x-2},${y-9}V${y+4}C${x+6},${y-1} ${x+6},${y-7} ${x-2},${y-1.5}" stroke="currentColor" stroke-width="1.4" fill="none"/>`}
function natural(x,y){return`<path d="M${x-2},${y-7}v10M${x+2},${y-3}v10" stroke="currentColor" stroke-width="1"/><path d="M${x-2},${y-1.5}l4,-1.2M${x-2},${y+3.3}l4,-1.2" stroke="currentColor" stroke-width="1.6"/>`}
function bassClef(x,top){const y4=top+SP,c=`<circle cx="${x+4}" cy="${y4}" r="3.3" fill="currentColor"/>`;
 return c+`<path d="M${x+4},${y4-3} C${x+4},${y4-12} ${x+17},${y4-10} ${x+17},${y4+1} C${x+17},${y4+13} ${x+8},${y4+21} ${x-1},${y4+26}" stroke="currentColor" stroke-width="2.4" fill="none"/><circle cx="${x+21}" cy="${y4-SP/2}" r="1.5" fill="currentColor"/><circle cx="${x+21}" cy="${y4+SP/2}" r="1.5" fill="currentColor"/>`}
const ALLOWED=[16,12,8,6,4,3,2,1];
function fitDur(d){for(const a of ALLOWED)if(a<=d)return a;return 1}
function fillRests(pos,gap,out){
 while(gap>0){let r=1;for(const c of [16,8,4,2,1])if(c<=gap&&pos%c===0){r=c;break}
  out.push({rest:true,s:pos,d:r});pos+=r;gap-=r}
}
/* events -> a measure's notes and rests (slots 0..L) */
function layoutMeasure(evs,L){
 const o=[];let pos=0;
 for(let i=0;i<evs.length;i++){const e=evs[i];if(e.s<pos)continue;
  if(e.s>pos){fillRests(pos,e.s-pos,o);pos=e.s}
  const next=i+1<evs.length?evs[i+1].s:L,d=fitDur(Math.min(e.d,next-e.s,L-e.s));
  o.push({s:e.s,d,m:e.m});pos=e.s+d;
  if(e.d>d&&next>pos&&false){}
 }
 if(pos<L)fillRests(pos,L-pos,o);
 return o;
}
function fingering(m,last){
 let best=null;
 for(let s=0;s<4;s++){const f=m-OPEN[s];if(f<0||f>15)continue;
  const cost=f*.5+(f>9?3:0)+Math.abs(f-(last??3))*.2+(f===0?-.3:0);
  if(!best||cost<best.c)best={s,f,c:cost}}
 return best||{s:3,f:Math.max(0,m-OPEN[3])};
}
function noteSvg(n,x,top,tabTop,ks,stemUp,beamY,flagLevel,tabInfo,showAcc){
 const sp=spell(n.m,ks),y=yOf(sp.step,top);let g="";
 // ledger lines
 const lx1=x-7,lx2=x+7;
 if(sp.step<18)for(let st=16;st>=sp.step;st-=2)g+=`<line x1="${lx1}" x2="${lx2}" y1="${yOf(st,top)}" y2="${yOf(st,top)}" stroke="currentColor" stroke-width="1"/>`;
 if(sp.step>26)for(let st=28;st<=sp.step;st+=2)g+=`<line x1="${lx1}" x2="${lx2}" y1="${yOf(st,top)}" y2="${yOf(st,top)}" stroke="currentColor" stroke-width="1"/>`;
 if(showAcc)g+=sp.acc>0?sharp(x-9,y):sp.acc<0?flat(x-9,y):natural(x-9,y);
 const hollow=n.d>=8,whole=n.d>=16;
 g+=`<ellipse cx="${x}" cy="${y}" rx="4.7" ry="3.4" transform="rotate(-20 ${x} ${y})" ${hollow?`fill="var(--bg)" stroke="currentColor" stroke-width="1.5"`:`fill="currentColor"`}/>`;
 if(n.d===3||n.d===6||n.d===12){const dy=((sp.step-18)%2===0)?-SP/2:0;g+=`<circle cx="${x+8}" cy="${y+dy}" r="1.4" fill="currentColor"/>`}
 let stemEnd=null;
 if(!whole){const sx=stemUp?x+4.4:x-4.4,ey=beamY!==null?beamY:(stemUp?y-STEMLEN:y+STEMLEN);stemEnd={x:sx,y:ey};
  g+=`<line x1="${sx}" x2="${sx}" y1="${y}" y2="${ey}" stroke="currentColor" stroke-width="1.3"/>`;
  if(flagLevel>0){for(let k=0;k<flagLevel;k++){const fy=stemUp?ey+k*5:ey-k*5,d=stemUp?1:-1;g+=`<path d="M${sx},${fy} C${sx+1},${fy+d*7} ${sx+9},${fy+d*8} ${sx+7},${fy+d*17}" stroke="currentColor" stroke-width="1.8" fill="none"/>`}}}
 // tab
 const fr=tabInfo;const ty=tabTop+fr.s*9;const t=String(fr.f);
 g+=`<rect x="${x-3.2*t.length-1}" y="${ty-6}" width="${6.4*t.length+2}" height="12" fill="var(--bg)"/><text x="${x}" y="${ty+4}" text-anchor="middle" class="fret">${t}</text>`;
 return{svg:g,stem:stemEnd,y};
}
function restSvg(r,x,top){
 const y=top+SP*2; // middle line
 if(r.d>=16)return`<rect x="${x-5}" y="${top+SP}" width="10" height="${SP/2}" fill="currentColor"/>`;
 if(r.d>=8)return`<rect x="${x-5}" y="${top+SP*2-SP/2}" width="10" height="${SP/2}" fill="currentColor"/>`;
 if(r.d>=4)return`<path d="M${x-2},${top+SP*.6} l5,5 l-5,5 c4,2 4,4 0,7 M${x+3},${top+SP*3.6}" stroke="currentColor" stroke-width="2" fill="none"/>`;
 const lv=r.d===1?2:1;let g=`<path d="M${x+3},${y-4} l-6,12" stroke="currentColor" stroke-width="1.4"/>`;
 for(let k=0;k<lv;k++)g+=`<circle cx="${x-2}" cy="${y-3+k*5}" r="2" fill="currentColor"/>`;
 return g;
}
function chordTxt(t,x,y){return`<text x="${x}" y="${y}" class="chd">${t}</text>`}
/* main: build all systems */
function render(S,evs,opts){
 const per=opts.per,ks=opts.ks,names=opts.names;           // names: [{slot,text}] by global slot
 const rows=[];let svgs="";
 const meas=S.meas;let last=null;
 for(let r=0;r*per<meas.length;r++){
  const ms=meas.slice(r*per,r*per+per),lm=44+ks.n*9;
  let w=lm;const widths=ms.map(m=>Math.max(96,DW*m.n/4));widths.forEach(x=>w+=x);
  const top=44,tabTop=top+4*SP+40,H=tabTop+3*9+26;let g="";
  // staff + tab lines
  for(let i=0;i<5;i++)g+=`<line x1="4" x2="${w}" y1="${top+i*SP}" y2="${top+i*SP}" stroke="currentColor" stroke-width="1"/>`;
  for(let i=0;i<4;i++)g+=`<line x1="4" x2="${w}" y1="${tabTop+i*9}" y2="${tabTop+i*9}" stroke="currentColor" stroke-width="1"/>`;
  g+=`<line x1="4" x2="4" y1="${top}" y2="${top+4*SP}" stroke="currentColor" stroke-width="2"/><line x1="4" x2="4" y1="${tabTop}" y2="${tabTop+27}" stroke="currentColor" stroke-width="2"/>`;
  g+=bassClef(10,top);
  for(let i=0;i<ks.n;i++){const st=ks.flats?FLAT_STEPS[i]:SHARP_STEPS[i];g+=ks.flats?flat(36+i*9,yOf(st,top)):sharp(36+i*9,yOf(st,top))}
  g+=`<text x="10" y="${tabTop+9}" class="tabw">T</text><text x="10" y="${tabTop+19}" class="tabw">A</text><text x="10" y="${tabTop+29}" class="tabw">B</text>`;
  let x0=lm;
  ms.forEach((m,mi)=>{
   const gi=r*per+mi,wd=widths[mi],L=m.n*4,base=m.b*4,xAt=s=>x0+12+(s/L)*(wd-22);
   g+=`<rect class="mbg" data-m="${gi}" x="${x0}" y="${top-24}" width="${wd}" height="${tabTop+27-top+34}" fill="transparent"/>`;
   g+=`<text x="${x0+3}" y="${top-30}" class="mno">${gi+1}</text>`;
   // chord names
   for(const c of names)if(c.slot>=base&&c.slot<base+L)g+=chordTxt(c.text,xAt(c.slot-base)-4,top-12);
   // notes
   const mine=evs.filter(e=>e.g>=base&&e.g<base+L).map(e=>({s:e.g-base,d:e.d,m:e.m}));
   const items=layoutMeasure(mine,L);const accState=new Map();
   // beams: groups of short notes within a beat
   const groups=[];let cur=null;
   for(const it of items){const beamable=!it.rest&&it.d<4;
    if(beamable){const beat=Math.floor(it.s/4);if(cur&&cur.beat===beat&&cur.end===it.s){cur.list.push(it);cur.end=it.s+it.d}else{cur={beat,end:it.s+it.d,list:[it]};groups.push(cur)}}else cur=null}
   const gmap=new Map();
   for(const gr of groups){
    const sps=gr.list.map(n=>spell(n.m,ks).step),avg=sps.reduce((a,b)=>a+b)/sps.length,up=avg<22;
    const ys=gr.list.map(n=>yOf(spell(n.m,ks).step,top));
    const by=gr.list.length>1?(up?Math.min(...ys)-STEMLEN:Math.max(...ys)+STEMLEN):null;
    gr.up=up;gr.by=by;for(const n of gr.list)gmap.set(n,gr)}
   for(const it of items){
    const x=xAt(it.s);
    if(it.rest){g+=restSvg(it,x+4,top);continue}
    const f=fingering(it.m,last?.f);last=f;
    const gr=gmap.get(it),sp=spell(it.m,ks);
    const up=gr?gr.up:sp.step<22,by=gr&&gr.by!==null?gr.by:null,flag=gr&&gr.by===null?(it.d===1?2:1):0;
    const exp=accState.has(sp.step)?accState.get(sp.step):sp.sig,showA=sp.acc!==exp;accState.set(sp.step,sp.acc);
    const out=noteSvg(it,x,top,tabTop,ks,up,by,flag,f,showA);g+=out.svg;it.stem=out.stem;
   }
   for(const gr of groups){if(gr.list.length<2)continue;const first=gr.list[0].stem,lastN=gr.list[gr.list.length-1].stem;if(!first||!lastN)continue;
    const dir=gr.up?1:-1;
    g+=`<line x1="${first.x}" x2="${lastN.x}" y1="${gr.by}" y2="${gr.by}" stroke="currentColor" stroke-width="3.4"/>`;
    for(let i=0;i<gr.list.length;i++){const n=gr.list[i];if(n.d!==1)continue;const st=n.stem;if(!st)continue;
     const nb=gr.list[i+1]&&gr.list[i+1].d===1?gr.list[i+1].stem:null,pv=gr.list[i-1]&&gr.list[i-1].d===1?gr.list[i-1].stem:null;
     const y=gr.by+dir*5.2;
     if(nb)g+=`<line x1="${st.x}" x2="${nb.x}" y1="${y}" y2="${y}" stroke="currentColor" stroke-width="3"/>`;
     else if(!pv)g+=`<line x1="${st.x}" x2="${st.x+7}" y1="${y}" y2="${y}" stroke="currentColor" stroke-width="3"/>`}}
   x0+=wd;
   g+=`<line x1="${x0}" x2="${x0}" y1="${top}" y2="${top+4*SP}" stroke="currentColor" stroke-width="1.4"/><line x1="${x0}" x2="${x0}" y1="${tabTop}" y2="${tabTop+27}" stroke="currentColor" stroke-width="1.4"/>`;
  });
  svgs+=`<svg class="sys" viewBox="0 0 ${w+6} ${H}" width="100%" preserveAspectRatio="xMinYMin meet" role="img" aria-label="Bass line, bars ${r*per+1} to ${r*per+ms.length}">${g}</svg>`;
 }
 return svgs;
}
/* Which key to SHOW. Presentation only: it never touches chords, timestamps or the detected key.
   1 published key (when someone supplies a verified one), 2 detected major, 3 relative major of a detected minor, 4 unknown. */
function validKey(k){return !!k&&Number.isInteger(k.r)&&k.r>=0&&k.r<12}
function keyDisplay(detected,published){
 const det=validKey(detected)?{r:detected.r,m:detected.m?1:0}:null;
 if(validKey(published)){
  const pub={r:published.r,m:published.m?1:0};
  const rel=k=>k.m?(k.r+3)%12:k.r;                     // same key signature = same relative-major pitch
  return{detected_key:det,published_key:pub,display_key:pub,key_source:"published",conflict:!!det&&rel(det)!==rel(pub)};
 }
 if(!det)return{detected_key:null,published_key:null,display_key:null,key_source:"unknown",conflict:false};
 if(!det.m)return{detected_key:det,published_key:null,display_key:det,key_source:"detected_major",conflict:false};
 return{detected_key:det,published_key:null,display_key:{r:(det.r+3)%12,m:0},key_source:"relative_major_default",conflict:false};
}
return{render,keyInfo,keyDisplay,fitDur,layoutMeasure};
})();
