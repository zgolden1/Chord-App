"""Browser test of the whole flow: enter site, search, open a charted song, embedded video plays, chords follow.
Real API server (SQLite, fake MusicBrainz/YouTube lookups), real page, headless Chromium, simulated YouTube player.
Run:  python web/build.py && python tests/e2e_flow.py"""
import asyncio, json, os, sys, tempfile, threading, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
td = tempfile.mkdtemp()
os.environ.update(DATABASE_URL="sqlite:///%s/e.db" % td, DEV_AUTH="1", UPLOAD_DIR=td + "/up")
import requests, uvicorn
from playwright.async_api import async_playwright
from server import app as A

MBS = [dict(mbid="mb-1", title="Loop Song", artist="Test Band", album=None, year=2013, length_s=200.0, kind="studio"),
       dict(mbid="mb-3", title="Charted Without Video", artist="Test Band", album=None, year=2015, length_s=200.0, kind="live"),
       dict(mbid="mb-2", title="Not Charted Yet", artist="Test Band", album=None, year=2020, length_s=200.0, kind="studio")]
A.SEARCH_FN[0] = lambda q: [dict(r) for r in MBS]
A.YT_FN[0] = lambda q: [{"id": "AAAAAAAAAAA", "title": q + " (official)", "channel": "Chan"}, {"id": "BBBBBBBBBBB", "title": q + " (live)", "channel": "Other"}]
threading.Thread(target=uvicorn.Server(uvicorn.Config(A.app, port=8766, log_level="error")).run, daemon=True).start(); time.sleep(1.2)
API = "http://127.0.0.1:8766"; M = {"Authorization": "Bearer dev:mod:bob"}
chart = json.load(open(os.path.join(ROOT, "docs", "sample-chart.json")))
requests.post(API + "/api/recordings/publish", headers=M, json={"recording": MBS[0], "data": dict(chart, video={"id": "dQw4w9WgXcQ", "offset": 0})})
requests.post(API + "/api/recordings/publish", headers=M, json={"recording": MBS[1], "data": chart})
FAKE = """<!doctype html><body><script>
let t=0,st=5,rate=1,last=performance.now(),talk=false;
addEventListener('message',e=>{let d;try{d=JSON.parse(e.data)}catch(x){return}
 if(d.event==='listening')talk=true;
 if(d.event==='command'){if(d.func==='playVideo')st=1;if(d.func==='pauseVideo')st=2;if(d.func==='seekTo')t=d.args[0];if(d.func==='setPlaybackRate')rate=d.args[0]}});
setInterval(()=>{const n=performance.now();if(st===1)t+=(n-last)/1000*rate;last=n;
 if(talk)parent.postMessage(JSON.stringify({event:'infoDelivery',info:{currentTime:t,playerState:st,duration:200,playbackRate:rate}}),'*')},250);
</script>"""
bad = []
def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name, "" if ok else extra)
    if not ok: bad.append(name)

async def newpage(b, cf, w=390):
    ctx = await b.new_context(viewport={"width": w, "height": 844}); pg = await ctx.new_page(); logs = []
    pg.on("pageerror", lambda e: logs.append("PAGEERROR " + str(e)))
    await pg.route("https://www.youtube.com/embed/**", lambda r: r.fulfill(status=200, content_type="text/html", body=FAKE))
    await pg.add_init_script("window.CF=%s;" % json.dumps(cf))
    await pg.goto("file://" + os.path.join(ROOT, "docs", "index.html")); return pg, logs

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        # 0. catalog not configured
        pg, logs = await newpage(b, {})
        check("no API: search is disabled with a clear message", await pg.is_disabled("#q") and "isn’t connected" in await pg.inner_text("#qmsg"))
        # 1-4. the flow
        pg, logs = await newpage(b, {"api": API, "devToken": "dev:alice"})
        check("home shows the search box first", await pg.is_visible("#q") and await pg.is_visible("#lvGo"))
        await pg.fill("#q", "loop"); await pg.wait_for_selector("#qres .res")
        rows = await pg.evaluate("[...document.querySelectorAll('#qres .res')].map(r=>[r.querySelector('b').textContent,r.querySelector('.chip').textContent])")
        print("   results:", rows)
        check("results show chart ready / no chart yet", [r[1] for r in rows] == ["Chart ready", "Chart ready", "No chart yet"], str(rows))
        await pg.screenshot(path="/tmp/e2e_search.png")
        await pg.click('#qres .res >> nth=0'); await pg.wait_for_function("!document.querySelector('#ctl').hidden")
        src = await pg.get_attribute("#ytf", "src")
        check("embedded YouTube loads the chart's video", "/embed/dQw4w9WgXcQ" in (src or ""), str(src))
        check("title and chords come from the catalog", await pg.inner_text("#ttl") == "Loop Song" and await pg.evaluate("[...document.querySelectorAll('#strip .blk b')].slice(0,4).map(b=>b.textContent)") == ["F#", "E", "B", "D"])
        check("search hides after choosing a song", not await pg.is_visible("#q")); await pg.click("#pl"); await pg.wait_for_timeout(2800)
        t = await pg.evaluate("au.currentTime"); on = await pg.evaluate("[...document.querySelectorAll('#strip .blk')].findIndex(b=>/\\b(on|cur|now)\\b/.test(b.className))")
        check("play starts the video clock and the chords follow", 2 < t < 4 and on == 1, "t=%s block=%s" % (t, on))
        check("video bar offered for catalog songs", await pg.is_visible("#vidBar"))
        await pg.screenshot(path="/tmp/e2e_play.png")
        await pg.click("#vidBack"); await pg.wait_for_timeout(300)
        check("Search button returns to search", await pg.is_visible("#q") and not await pg.is_visible("#ytWrap") and await pg.evaluate("S===null"))
        # chart with no video: picker, choose, save for everyone
        pg, logs = await newpage(b, {"api": API, "devToken": "dev:alice"})
        await pg.fill("#q", "charted"); await pg.wait_for_selector("#qres .res"); await pg.click('#qres .res >> nth=1')
        await pg.wait_for_selector("#vidList .res")
        check("no video saved: the picker offers candidates", await pg.locator("#vidList .res").count() == 2)
        await pg.screenshot(path="/tmp/e2e_pick.png")
        await pg.click("#vidList .res >> nth=1"); await pg.wait_for_function("!document.querySelector('#ctl').hidden")
        check("chosen video plays", "/embed/BBBBBBBBBBB" in await pg.get_attribute("#ytf", "src"))
        await pg.click("#vidSave"); await pg.wait_for_timeout(800)
        q = requests.get(API + "/api/moderation/queue", headers=M).json()["queue"]
        check("'save for everyone' becomes a video suggestion for moderators", any(s["kind"] == "video" and s["payload"]["id"] == "BBBBBBBBBBB" and s["mbid"] == "mb-3" for s in q), str(q)[:200])
        # no chart yet -> request
        pg, logs = await newpage(b, {"api": API, "devToken": "dev:alice"})
        await pg.fill("#q", "not"); await pg.wait_for_selector("#qres .res"); await pg.click('#qres .res >> nth=2')
        check("uncharted song shows the request box", await pg.is_visible("#askBox"))
        await pg.click("#askBtn"); await pg.wait_for_timeout(800)
        top = requests.get(API + "/api/moderation/requests", headers=M).json()["requests"]
        check("request reaches the moderator list", len(top) == 1 and top[0]["mbid"] == "mb-2" and top[0]["n"] == 1, str(top))
        check("page confirms the request", "asked for this chart" in await pg.inner_text("#askTxt"))
        await pg.screenshot(path="/tmp/e2e_ask.png")
        # signed out: asking needs sign-in
        pg, logs = await newpage(b, {"api": API})
        await pg.fill("#q", "not"); await pg.wait_for_selector("#qres .res"); await pg.click('#qres .res >> nth=2')
        check("signed out: button says sign in", "Sign in" in await pg.inner_text("#askBtn"))
        errs = [l for l in logs if "PAGEERROR" in l]
        check("no page errors", not errs, str(errs))
        await b.close()
asyncio.run(main())
print("\nFAILURES: " + ", ".join(bad) if bad else "\nall passed"); sys.exit(1 if bad else 0)
