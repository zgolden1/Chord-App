import asyncio,json,sys
from playwright.async_api import async_playwright
import os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE=os.path.join(ROOT,"docs","index.html")
D="/tmp/"
MOCK=open(os.path.join(ROOT,"web","src","test-mock.js")).read()
# chart in the catalog format: Honeymoon loop F# E B/D# D, 4 beats each, 120 bpm, 200 s
beats=[i*.5 for i in range(401)]
loop=[(6,0,-1),(4,0,-1),(11,0,3),(2,0,-1)]
chords=[{"t0":i*2.0,"t1":i*2.0+2.0,"r":loop[i%4][0],"q":0,"slash":loop[i%4][2]} for i in range(100)]
chart={"pipeline":"test","duration":200.0,"key":{"r":6,"m":False},"bpm":120,"beats":beats,"phase":0,"chords":chords}
open("/tmp/chart.json","w").write(json.dumps(chart))
FAKE="""<!doctype html><body><script>
let t=0,st=5,rate=1,last=performance.now(),talk=false;window.cmds=[];
addEventListener('message',e=>{let d;try{d=JSON.parse(e.data)}catch(x){return}
 if(d.event==='listening')talk=true;
 if(d.event==='command'){parent.postMessage(JSON.stringify({event:'cmd',info:{}}),'*');window.cmds.push(d.func+':'+(d.args||[]).join(','));
  if(d.func==='playVideo')st=1;if(d.func==='pauseVideo')st=2;if(d.func==='seekTo')t=d.args[0];if(d.func==='setPlaybackRate')rate=d.args[0];
  document.title=window.cmds.join('|')}});
setInterval(()=>{const n=performance.now();if(st===1)t+=(n-last)/1000*rate;last=n;
 if(talk&&%s)parent.postMessage(JSON.stringify({event:'infoDelivery',info:{currentTime:t,playerState:st,duration:200,playbackRate:rate}}),'*')},250);
</script>"""
async def run(responds):
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx=await b.new_context(viewport={"width":390,"height":844})
        pg=await ctx.new_page();logs=[]
        pg.on("console",lambda m:logs.append(m.type+": "+m.text));pg.on("pageerror",lambda e:logs.append("PAGEERROR "+str(e)))
        await pg.route("https://www.youtube.com/embed/**",lambda r:r.fulfill(status=200,content_type="text/html",body=FAKE%("true" if responds else "false")))
        await pg.add_init_script("window.__ROLE='contrib';window.__STORE={};"+MOCK)
        await pg.goto("file://"+PAGE)
        await pg.click("#ytBox summary")
        await pg.click("#ytGo");print("no inputs ->",await pg.inner_text("#ytMsg"))
        await pg.fill("#ytUrl","https://youtu.be/dQw4w9WgXcQ?t=3")
        await pg.click("#ytGo");print("no chart ->",await pg.inner_text("#ytMsg"))
        await pg.set_input_files("#ytChart","/tmp/chart.json")
        await pg.click("#ytGo")
        await pg.wait_for_function("!document.querySelector('#ctl').hidden",timeout=10000)
        print("status:",await pg.inner_text("#st"))
        print("chords:",await pg.evaluate("[...document.querySelectorAll('#strip .blk b')].slice(0,5).map(b=>b.textContent)"),"| key:",await pg.evaluate("S.key"),"| id:",await pg.evaluate("S.id"))
        if not responds:
            await pg.wait_for_timeout(9800);print("no-response message:",await pg.inner_text("#ytMsg"));print("console:",[l for l in logs if "ERR_TUNNEL" not in l and "fonts" not in l]);await b.close();return
        await pg.wait_for_timeout(1500);print("after load msg:",repr(await pg.inner_text("#ytMsg")),"| paused:",await pg.evaluate("au.paused"))
        await pg.click("#pl");await pg.wait_for_timeout(2600)
        print("playing: paused=",await pg.evaluate("au.paused"),"t=",round(await pg.evaluate("au.currentTime"),1),"| button:",await pg.inner_text("#pl"))
        cur=await pg.evaluate("[...document.querySelectorAll('#strip .blk')].findIndex(b=>b.classList.contains('on')||b.classList.contains('cur')||b.classList.contains('now'))")
        print("highlighted block index:",cur,"(t≈2.6s => block 1, E)")
        await pg.click("#strip .blk >> nth=6");await pg.wait_for_timeout(600)
        print("after tapping block 6: t=",round(await pg.evaluate("au.currentTime"),1),"(expect ~12)")
        await pg.fill("#sp","0.75");await pg.dispatch_event("#sp","input");await pg.wait_for_timeout(300)
        print("speed:",await pg.evaluate("au.playbackRate"),await pg.inner_text("#spv"))
        await pg.evaluate("LP.a=20;LP.b=24;au.currentTime=23.5");await pg.wait_for_timeout(1500)
        print("loop 20-24 wraps: t=",round(await pg.evaluate("au.currentTime"),1))
        await pg.click("#pl");await pg.wait_for_timeout(500)
        print("paused again:",await pg.evaluate("au.paused"),"| button:",await pg.inner_text("#pl"))
        fr=[f for f in pg.frames if "youtube" in f.url][0]
        print("commands the player received:",(await fr.evaluate("window.cmds")))
        await pg.click("#tabK");await pg.wait_for_timeout(300);print("keys tab chord:",await pg.inner_text("#kName"))
        await pg.screenshot(path=D+"yt_main.png")
        ok=await pg.evaluate("(()=>{ytStop();return[Object.getOwnPropertyDescriptor(au,'currentTime')===undefined,$('ytWrap').hidden]})()")
        print("after stop, native audio restored:",ok)
        print("console:",[l for l in logs if "ERR_TUNNEL" not in l and "fonts" not in l] or "clean")
        await b.close()
asyncio.run(run(sys.argv[1]!="silent"))
