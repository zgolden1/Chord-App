"""Song search through MusicBrainz (free, open data). Each result is one specific RECORDING, so studio,
live and remix versions are separate entries. MusicBrainz asks for a descriptive User-Agent and at most
one request per second; this module keeps to that."""
import os, threading, time

import requests

_lock = threading.Lock()
_last = [0.0]
LIVE_WORDS = {"live": "live", "remix": "remix", "acoustic": "acoustic", "demo": "demo", "instrumental": "instrumental",
              "radio edit": "radio edit", "karaoke": "karaoke", "cover": "cover", "reprise": "reprise"}


def kind_of(disambiguation, title):
    text = ((disambiguation or "") + " " + (title or "")).lower()
    for w, k in LIVE_WORDS.items():
        if w in text:
            return k
    return "studio"


def parse(js):
    out = []
    for r in js.get("recordings", []):
        artist = "".join(a.get("name", "") + a.get("joinphrase", "") for a in r.get("artist-credit", [])) or "Unknown"
        rel = (r.get("releases") or [{}])[0]
        date = rel.get("date") or r.get("first-release-date") or ""
        out.append({
            "mbid": r["id"], "title": r.get("title", ""), "artist": artist, "album": rel.get("title"),
            "year": int(date[:4]) if date[:4].isdigit() else None,
            "length_s": (r["length"] / 1000.0) if r.get("length") else None,
            "kind": kind_of(r.get("disambiguation"), r.get("title")),
            "disambiguation": r.get("disambiguation") or "",
        })
    return out


def musicbrainz(q, limit=10):
    with _lock:                                           # one request per second
        wait = 1.05 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
    ua = "ChordFlow/0.1 ( %s )" % os.environ.get("MB_CONTACT", "set-MB_CONTACT-in-env")
    r = requests.get("https://musicbrainz.org/ws/2/recording", params={"query": q, "fmt": "json", "limit": limit},
                     headers={"User-Agent": ua}, timeout=15)
    r.raise_for_status()
    return parse(r.json())
