"""The ⋯ on each chord opens a sheet with alternative piano voicings and guitar shapes."""
import asyncio, os, sys
from playwright.async_api import async_playwright
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SHOT = sys.argv[1] if len(sys.argv) > 1 else None
ok = True
def check(n, c, x=""):
    global ok; ok = ok and bool(c); print(("PASS " if c else "FAIL ") + n, "" if c else x)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pg = await (await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)).new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.add_init_script("window.CF={};")
        await pg.goto("file://" + os.path.join(ROOT, "docs", "index.html"))
        await pg.set_input_files("#fp", "/tmp/synth.wav"); await pg.wait_for_function("!document.querySelector('#ctl').hidden", timeout=120000)
        check("every chart chord has a ⋯", await pg.locator("#strip .blk .vo").count() == await pg.locator("#strip .blk").count() > 0)
        t0 = await pg.evaluate("au.currentTime")
        await pg.click("#strip .blk >> nth=1 >> .vo")
        check("sheet opens", await pg.locator("#vsh").is_visible())
        check("chord named in the sheet", (await pg.inner_text("#voT")).strip() != "")
        check("three piano voicings drawn", await pg.locator("#voB svg.vp").count() == 3 and await pg.evaluate("[...document.querySelectorAll('#voB svg.vp')].every(s=>s.innerHTML.length>200)"))
        check("guitar shapes shown", await pg.locator("#voB .cd").count() >= 1)
        check("opening the sheet did not seek the song", abs(await pg.evaluate("au.currentTime") - t0) < .05)
        if SHOT: await pg.screenshot(path=SHOT + "_sheet.png")
        await pg.click("#voX"); check("closes", not await pg.locator("#vsh").is_visible())
        # lyrics view with chords over words
        await pg.evaluate("()=>{S.lyr={lines:[{t:0.2,text:'Georgia wrap me up'},{t:2.2,text:'I want you in my arms'},{t:4.2,text:'Oh let me hold you'}]};buildLyrics();setTab('l')}")
        await pg.wait_for_timeout(300)
        n = await pg.locator("#lyOut .ch .vo").count()
        check("lyrics chords have ⋯", n > 0, str(n))
        if SHOT: await pg.screenshot(path=SHOT + "_lyrics.png")
        await pg.click("#lyOut .ch >> nth=0")
        check("tapping a lyric chord opens the sheet", await pg.locator("#vsh").is_visible())
        await pg.keyboard.press("Escape"); check("Escape closes", not await pg.locator("#vsh").is_visible())
        check("no page errors", not errs, str(errs))
        await b.close()
asyncio.run(main()); print("\nall passed" if ok else "\nFAILURES"); sys.exit(0 if ok else 1)
