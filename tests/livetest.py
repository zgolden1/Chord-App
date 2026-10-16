import asyncio,sys,json
from playwright.async_api import async_playwright
import os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE=os.path.join(ROOT,"docs","index.html")
D="/tmp/"
MOCK=open(os.path.join(ROOT,"web","src","test-mock.js")).read()
async def run(wav,secs,full):
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path="/opt/pw-browsers/chromium",args=["--use-fake-ui-for-media-stream","--use-fake-device-for-media-stream","--use-file-for-fake-audio-capture="+wav,"--autoplay-policy=no-user-gesture-required"])
        ctx=await b.new_context(viewport={"width":390,"height":844},permissions=["microphone"])
        pg=await ctx.new_page();logs=[]
        pg.on("console",lambda m:logs.append(m.type+": "+m.text));pg.on("pageerror",lambda e:logs.append("PAGEERROR "+str(e)))
        await pg.add_init_script("window.__ROLE='contrib';window.__STORE={};"+MOCK)
        await pg.goto("file://"+PAGE)
        await pg.click("#lvGo");await pg.wait_for_timeout(1500)
        print("msg:",await pg.inner_text("#lvMsg"))
        for i in range(secs//10):
            await pg.wait_for_timeout(10000)
            print(f"t={10*(i+1)}s now={await pg.inner_text('#lvNow')!r} key={await pg.inner_text('#lvKey')!r} hist={await pg.inner_text("#lvHist")!r}")
        await pg.select_option("#lvTri","s");await pg.wait_for_timeout(300);print("with 7ths+slash:",(await pg.inner_text("#lvLoop")).replace("\n"," | "));await pg.select_option("#lvTri","t");await pg.wait_for_timeout(300)
        print("loop:",(await pg.inner_text("#lvLoop")).replace("\n"," | "))
        await pg.screenshot(path=D+"live_1.png")
        live=await pg.evaluate("LIVE.ev.map(e=>[+e.t.toFixed(1),LV.name(e.r,e.q,true,false)])")
        await pg.click("#lvStop");await pg.wait_for_timeout(500)
        print("after stop:",await pg.inner_text("#lvMsg"),"| chart button visible:",await pg.evaluate("!$('lvAfter').hidden"))
        print("live events:",live[:24])
        if full:
            await pg.click("#lvChart");await pg.wait_for_function("!document.querySelector('#ctl').hidden",timeout=240000)
            off=await pg.evaluate("S.disp.map(g=>[+g.t0.toFixed(1),+g.t1.toFixed(1),NF[g.r]+QS[TRI[g.q]]])")
            print("offline chart:",off[:24])
            # agreement: sample every 0.5s
            def at(seq,t,key):
                cur=None
                for e in seq:
                    if e[0]<=t: cur=e
                return cur
            ok=n=0
            for t in [x*0.5 for x in range(8,int(len(off) and off[-1][1]*2)-4)]:
                o=[c for c in off if c[0]<=t<c[1]]
                l=at(live,t+0.0,0)
                if o and l:
                    n+=1
                    from_root=lambda s:s.rstrip("m7ajb")[:2]
                    ok+= (o[0][2].replace("b","#")[:1]==l[1][:1])
            print("root-letter agreement live vs offline over",n,"samples:",round(100*ok/max(n,1)),"%")
        print("console:",[l for l in logs if "ERR_TUNNEL" not in l and "fonts" not in l] or "clean")
        await b.close()
asyncio.run(run(sys.argv[1],int(sys.argv[2]),len(sys.argv)>3))
