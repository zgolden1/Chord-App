"""Key-display rule: relative major by default, published key wins, chords/timestamps/transposition untouched.
Part 1 tests the pure function in node; part 2 drives the real page in headless Chromium."""
import asyncio, json, os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ok = True
def check(name, cond, extra=""):
    global ok; ok = ok and bool(cond); print(("PASS " if cond else "FAIL ") + name, "" if cond else extra)

NODE = r"""
const src=require('fs').readFileSync(process.argv[1],'utf8');
const ENG=new Function(src+';return ENG')();
const f=o=>{Object.freeze(o);return o};
const out={};
const cases={Fm:[{r:5,m:1}],Am:[{r:9,m:1}],Csm:[{r:1,m:1}],Fsm:[{r:6,m:1}],Ab:[{r:8,m:0}],
 pubFm:[{r:5,m:1},{r:5,m:1}],pubNone:[{r:5,m:1},null],pubUnknown:[{r:5,m:1},{}],pubBad:[{r:5,m:1},{r:"x"}],
 conflict:[{r:5,m:1},{r:2,m:0}],same:[{r:5,m:1},{r:8,m:0}],none:[null,null],
 gb:[{r:6,m:0}],ebm:[{r:3,m:1}]};
for(const k in cases){const [d,p]=cases[k];const dd=d&&f({...d}),pp=p&&typeof p==='object'?f({...p}):p;out[k]=ENG.keyDisplay(dd,pp)}
console.log(JSON.stringify(out));
"""
r = subprocess.run(["node", "-e", NODE, os.path.join(ROOT, "web/src/engrave.js")], capture_output=True, text=True)
check("node ran", r.returncode == 0, r.stderr)
o = json.loads(r.stdout)
dk = lambda k: o[k]["display_key"]
check("F minor shows Ab major", dk("Fm") == {"r": 8, "m": 0} and o["Fm"]["key_source"] == "relative_major_default")
check("A minor shows C major", dk("Am") == {"r": 0, "m": 0})
check("C# minor shows E major", dk("Csm") == {"r": 4, "m": 0})
check("F# minor shows A major", dk("Fsm") == {"r": 9, "m": 0})
check("Ab major stays Ab major", dk("Ab") == {"r": 8, "m": 0} and o["Ab"]["key_source"] == "detected_major")
check("published F minor overrides the default", dk("pubFm") == {"r": 5, "m": 1} and o["pubFm"]["key_source"] == "published" and not o["pubFm"]["conflict"])
check("no/unknown/invalid published key is not verified", all(o[k]["key_source"] == "relative_major_default" for k in ("pubNone", "pubUnknown", "pubBad")))
check("raw detection preserved", o["Fm"]["detected_key"] == {"r": 5, "m": 1} and o["pubFm"]["detected_key"] == {"r": 5, "m": 1})
check("conflicting published key is flagged, not applied silently", o["conflict"]["conflict"] and not o["same"]["conflict"])
check("no detection and no published key is unknown", o["none"]["key_source"] == "unknown" and dk("none") is None)
check("enharmonic pitch classes agree (Gb/F#, Eb minor)", dk("gb") == {"r": 6, "m": 0} and dk("ebm") == {"r": 6, "m": 0})

from playwright.async_api import async_playwright
async def page_tests():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pg = await (await b.new_context(viewport={"width": 390, "height": 844})).new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.add_init_script("window.CF={};")
        await pg.goto("file://" + os.path.join(ROOT, "docs", "index.html"))
        await pg.set_input_files("#fp", "/tmp/synth.wav"); await pg.wait_for_function("!document.querySelector('#ctl').hidden", timeout=120000)
        snap = "()=>({names:S.disp.map(g=>g.main+'|'+g.ex),t:S.disp.map(g=>g.t0),segs:JSON.stringify(S.segs),key:JSON.stringify(S.key),shift:S.shift,mk:document.getElementById('mk').textContent,sk:[...document.getElementById('sk').options].map(o=>o.textContent+':'+o.value+':'+o.selected)})"
        # force a known detection: F minor, then re-render
        await pg.evaluate("()=>{S.key={r:5,m:1};S.pubKey=null;S.nt='c';refresh()}")
        a = await pg.evaluate(snap)
        check("page: Fm detection is shown as Ab major", "Key of Ab major" in a["mk"], a["mk"])
        check("page: no transposition from the label change", a["shift"] == 0 and json.loads(a["key"]) == {"r": 5, "m": 1})
        check("page: key picker selects Ab major at shift 0", any(s.startswith("Ab major:5:true") for s in a["sk"]), str(a["sk"]))
        await pg.evaluate("()=>{S.pubKey={r:5,m:1};refresh()}")
        c = await pg.evaluate(snap)
        check("page: published F minor is shown as F minor", "Key of F minor" in c["mk"], c["mk"])
        check("page: chord names, timestamps and raw segments identical across key display modes", a["names"] == c["names"] and a["t"] == c["t"] and a["segs"] == c["segs"])
        await pg.evaluate("()=>{S.pubKey=null;refresh()}")
        # explicit transposition: choose C major in the picker (value = raw tonic slot). Raw tonic F -> C is +7 semitones.
        before = await pg.evaluate(snap)
        await pg.evaluate("()=>{const e=document.getElementById('sk');e.value='0';e.dispatchEvent(new Event('change'))}")
        d = await pg.evaluate(snap)
        check("page: explicit transposition sets the right shift (F to C = 7)", d["shift"] == 7, str(d["shift"]))
        check("page: after transposing, label follows (Eb major from Eb... C minor -> Eb major)", "Key of Eb major" in d["mk"], d["mk"])
        check("page: transposed chords moved, timestamps did not", d["names"] != before["names"] and d["t"] == before["t"] and d["segs"] == before["segs"])
        await pg.evaluate("()=>{const e=document.getElementById('sk');e.value='5';e.dispatchEvent(new Event('change'))}")
        e = await pg.evaluate(snap)
        check("page: transposing back restores the original chords", e["names"] == a["names"] and e["shift"] == 0)
        check("page: no page errors", not errs, str(errs))
        await b.close()
asyncio.run(page_tests())
print("\nall passed" if ok else "\nFAILURES"); sys.exit(0 if ok else 1)
