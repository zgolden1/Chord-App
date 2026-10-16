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
                     headers={"User-Agent": ua}, timeout=8)
    r.raise_for_status()
    return parse(r.json())


def itunes(q, limit=10):
    """Backup song search (Apple's free iTunes Search API, no key). Used when MusicBrainz refuses the server.
    Ids look like 'it:12345'; they work like MusicBrainz ids everywhere else in the catalog."""
    r = requests.get("https://itunes.apple.com/search", params={"term": q, "media": "music", "entity": "song", "limit": limit}, timeout=8)
    r.raise_for_status()
    out = []
    for t in r.json().get("results", []):
        if not t.get("trackId"):
            continue
        date = t.get("releaseDate") or ""
        out.append({"mbid": "it:%s" % t["trackId"], "title": t.get("trackName", ""), "artist": t.get("artistName", "Unknown"),
                    "album": t.get("collectionName"), "year": int(date[:4]) if date[:4].isdigit() else None,
                    "length_s": (t["trackTimeMillis"] / 1000.0) if t.get("trackTimeMillis") else None,
                    "kind": kind_of(None, t.get("trackName")), "disambiguation": ""})
    return out


def find(q):
    """MusicBrainz first (separates studio, live and remix recordings); if it refuses, the iTunes backup."""
    try:
        return musicbrainz(q)
    except Exception as e:
        print("musicbrainz failed, using backup:", type(e).__name__, str(e)[:120], flush=True)
        return itunes(q)


class NoKey(Exception):
    pass


_yt_cache = {}


def youtube(q, limit=5):
    """Top embeddable music videos for a query, using the YouTube Data API v3 (free quota: about 100 searches a day).
    Needs YOUTUBE_API_KEY in the server's environment. Results are cached for an hour."""
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        raise NoKey()
    hit = _yt_cache.get(q.lower())
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    r = requests.get("https://www.googleapis.com/youtube/v3/search", params={
        "part": "snippet", "q": q, "type": "video", "videoEmbeddable": "true", "videoCategoryId": "10", "maxResults": limit, "key": key}, timeout=15)
    r.raise_for_status()
    out = [{"id": i["id"]["videoId"], "title": i["snippet"]["title"], "channel": i["snippet"]["channelTitle"]} for i in r.json().get("items", []) if i.get("id", {}).get("videoId")]
    _yt_cache[q.lower()] = (time.time(), out)
    return out
