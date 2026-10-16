#!/usr/bin/env python3
"""Builds the single-file web app:  python web/build.py   ->   docs/index.html
Edit the files in web/src, run this, commit docs/. GitHub Pages serves docs/ directly."""
import pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "docs" / "index.html"
MODULES = [("DSP", "dsp.js"), ("ENGRAVE", "engrave.js"), ("LYRICS", "lyrics.js"), ("VOICING", "voicing.js"), ("YT", "yt.js"), ("LISTEN", "listen.js")]
HEAD = ('<title>ChordFlow</title>\n<link rel="manifest" href="manifest.webmanifest">\n<link rel="apple-touch-icon" href="apple-touch-icon.png">\n'
        '<meta name="theme-color" content="#1f2933">\n<meta name="mobile-web-app-capable" content="yes">\n<meta name="apple-mobile-web-app-capable" content="yes">\n'
        '<meta name="apple-mobile-web-app-title" content="ChordFlow">\n<meta name="apple-mobile-web-app-status-bar-style" content="default">')
SW = '<script>if("serviceWorker"in navigator&&/^https?:/.test(location.protocol))addEventListener("load",()=>navigator.serviceWorker.register("sw.js").catch(()=>{}))</script>\n</body>'
t = (HERE / "src" / "template.html").read_text()
for key, fn in MODULES:
    mark = "/*%s*/" % key
    if mark not in t:
        sys.exit("placeholder %s missing in template.html" % mark)
    t = t.replace(mark, (HERE / "src" / fn).read_text())
t = t.replace("<title>ChordFlow</title>", HEAD, 1).replace("</body>", SW, 1)
OUT.write_text(t)
print("wrote", OUT, len(t) // 1024, "KB")
