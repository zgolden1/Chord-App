#!/usr/bin/env python3
"""Put a song you analyzed on your own computer into the shared catalog.

  1. python analyze.py song.mp3                       -> song.chordflow-notes.json
  2. python worker/publish.py song.chordflow-notes.json --search "Honeymoon Avenue Ariana Grande"
     (lists matches; pick one with --pick 1)  or give --mbid directly.

Env: CATALOG_URL (default http://localhost:8000), CATALOG_TOKEN (a moderator or worker token).
Only chords, beats and timing are uploaded. The audio file never leaves your computer."""
import argparse, json, os, sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from server.convert import from_analysis_file          # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("notes_json")
    ap.add_argument("--search")
    ap.add_argument("--pick", type=int, default=0)
    ap.add_argument("--mbid")
    ap.add_argument("--candidate", action="store_true", help="store as a candidate (for comparison) instead of the official version")
    ap.add_argument("--pipeline", default=None)
    a = ap.parse_args()
    base = os.environ.get("CATALOG_URL", "http://localhost:8000").rstrip("/")
    tok = os.environ.get("CATALOG_TOKEN")
    if not tok:
        sys.exit("Set CATALOG_TOKEN (moderator or worker token).")
    H = {"Authorization": "Bearer " + tok}
    d = json.load(open(a.notes_json))
    rec = None
    if a.search:
        res = requests.get(base + "/api/search", params={"q": a.search}, timeout=30).json()["results"]
        for i, r in enumerate(res, 1):
            ln = "%d:%02d" % divmod(int(r["length_s"] or 0), 60)
            print("%2d. %s - %s  [%s, %s, %s]%s" % (i, r["artist"], r["title"], r.get("kind"), r.get("year") or "?", ln, "  (already in catalog)" if r.get("analyzed") else ""))
        if not a.pick:
            return print("\nRe-run with --pick N to publish to that recording (check the length matches your file: %d:%02d)." % divmod(int(d.get("duration", 0)), 60))
        rec = res[a.pick - 1]
    elif a.mbid:
        rec = {"mbid": a.mbid, "title": os.path.basename(a.notes_json), "artist": ""}
    else:
        sys.exit("Give --search or --mbid.")
    if rec.get("length_s") and d.get("duration") and abs(rec["length_s"] - d["duration"]) > 8:
        print("WARNING: the file is %.0fs but the recording is %.0fs. Different version?" % (d["duration"], rec["length_s"]))
        if input("Publish anyway? [y/N] ").lower() != "y":
            return
    data = from_analysis_file(d, a.pipeline or ("%s" % d.get("model", "htdemucs")))
    r = requests.post(base + "/api/recordings/publish" + ("?as=candidate" if a.candidate else ""), json={"recording": rec, "data": data}, headers=H, timeout=60)
    print(r.status_code, r.text)


if __name__ == "__main__":
    main()
