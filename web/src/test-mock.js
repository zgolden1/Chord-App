(()=>{
 const store=window.__STORE||{};const subs=[];
 const clone=x=>JSON.parse(JSON.stringify(x));
 const snap=(p)=>({id:p.split("/").pop(),exists:p in store,data:()=>p in store?clone(store[p]):undefined,metadata:{}});
 const kids=c=>Object.keys(store).filter(k=>k.startsWith(c+"/")&&k.split("/").length===c.split("/").length+1).sort();
 const qsnap=c=>({docs:kids(c).map(snap),size:kids(c).length,empty:!kids(c).length,metadata:{}});
 const notify=()=>{for(const s of subs.slice())s()};
 const mk=(f)=>{subs.push(f);setTimeout(f,0);return()=>{const i=subs.indexOf(f);if(i>=0)subs.splice(i,1)}};
 const db={doc:p=>({path:p,id:p.split("/").pop(),
   get:async()=>snap(p),
   set:async d=>{store[p]=clone(d);setTimeout(notify,0)},
   update:async d=>{store[p]=Object.assign(store[p]||{},clone(d));setTimeout(notify,0)},
   delete:async()=>{delete store[p];setTimeout(notify,0)},
   onSnapshot:(n)=>mk(()=>n(snap(p)))}),
  collection:c=>({onSnapshot:(n)=>mk(()=>n(qsnap(c))),get:async()=>qsnap(c)})};
 const role=window.__ROLE||"u_a";
 const user={id:async()=>role==="none"?null:role,canEdit:async()=>role==="mod",isOwner:async()=>false,can:async()=>true,
  profiles:async ids=>Object.fromEntries([].concat(ids).map(i=>[i,{id:i,name:"Person "+i,isMe:false}]))};
 window.__SAVED=[];
 const downloads={save:async r=>{window.__SAVED.push(r)}};
 window.claude={use:async n=>({db:role==="none"?null:db,user,downloads}[n]||null)};
 window.__dump=()=>JSON.stringify(store);
})();
