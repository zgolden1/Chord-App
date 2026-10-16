"""Pure functions: validating suggestions, applying them to a transcription, and gathering evidence.
No web or database code here, so everything can be unit-tested."""
import copy, json

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
QUAL = ["", "m", "7", "maj7", "m7", "sus2", "sus4", "dim", "aug", "m7b5", "6", "m6"]
KINDS = ("chord", "key", "bpm", "voicing", "shape", "sync", "video")
import re as _re
YT_ID = _re.compile(r"^[A-Za-z0-9_-]{11}$")


def chord_name(c):
    s = NAMES[c["r"]] + QUAL[c["q"]]
    if c.get("xt"):
        s += "(" + ",".join(str(i) for i in c["xt"]) + ")"
    if c.get("slash", -1) >= 0:
        s += "/" + NAMES[c["slash"]]
    return s


def _int(v, lo, hi):
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def validate(kind, p, dur):
    """Returns an error string, or None when the payload is well formed."""
    if kind not in KINDS:
        return "unknown kind"
    if not isinstance(p, dict):
        return "payload must be an object"
    if kind == "chord":
        c, rg = p.get("chord"), p.get("ranges")
        if not isinstance(c, dict) or not (_int(c.get("r"), 0, 11) and _int(c.get("q"), 0, len(QUAL) - 1) and _int(c.get("slash", -1), -1, 11)):
            return "bad chord"
        if not all(_int(i, 1, 11) for i in c.get("xt", [])) or len(c.get("xt", [])) > 3:
            return "bad extensions"
        if not isinstance(rg, list) or not rg or len(rg) > 400:
            return "ranges must be a list of 1 to 400"
        for r in rg:
            try:
                a, b = float(r["t0"]), float(r["t1"])
            except Exception:
                return "bad range"
            if not (0 <= a < b <= dur + 1.0):
                return "range outside the recording"
    elif kind == "key":
        if not (_int(p.get("r"), 0, 11) and isinstance(p.get("m"), bool)):
            return "bad key"
    elif kind == "bpm":
        if not (isinstance(p.get("bpm"), (int, float)) and 40 <= p["bpm"] <= 240):
            return "bpm must be between 40 and 240"
    elif kind == "voicing":
        if not (isinstance(p.get("key"), str) and isinstance(p.get("lh"), list) and isinstance(p.get("rh"), list)):
            return "bad voicing"
        notes = p["lh"] + p["rh"]
        if not notes or len(notes) > 12 or not all(_int(n, 21, 108) for n in notes):
            return "bad voicing notes"
    elif kind == "shape":
        sh = p.get("sh")
        if not (isinstance(p.get("key"), str) and isinstance(sh, list) and len(sh) == 6 and all(_int(f, -1, 24) for f in sh)):
            return "bad guitar shape"
    elif kind == "video":
        if not (isinstance(p.get("id"), str) and YT_ID.match(p["id"])):
            return "bad YouTube id"
        if not (isinstance(p.get("offset", 0), (int, float)) and not isinstance(p.get("offset", 0), bool) and abs(p.get("offset", 0)) <= 30):
            return "offset must be within 30 seconds"
    elif kind == "sync":
        lyr = p.get("lyr", [])
        if not (_int(p.get("phase"), 0, 3) and isinstance(p.get("cOff", 0), (int, float)) and abs(p.get("cOff", 0)) <= 3):
            return "bad sync"
        if len(lyr) > 600 or any(not (isinstance(x, dict) and isinstance(x.get("h"), str) and isinstance(x.get("t"), (int, float)) and set(x) <= {"h", "t"}) for x in lyr):
            return "bad lyric timings"
        ts = [x["t"] for x in lyr]
        if ts != sorted(ts) or (ts and (ts[0] < 0 or ts[-1] > dur + 5)):
            return "lyric times must increase through the song"
    return None


def same_chord(a, b):
    return (a["r"], a["q"], tuple(a.get("xt", [])), a.get("slash", -1)) == (b["r"], b["q"], tuple(b.get("xt", [])), b.get("slash", -1))


def apply_chord_fix(chords, ranges, chord):
    """Replace the chord inside each time range, cutting existing segments at the range edges."""
    segs = [dict(c) for c in chords]
    new_chord = {k: chord[k] for k in ("r", "q", "xt", "slash") if k in chord}
    new_chord.setdefault("xt", []); new_chord.setdefault("slash", -1)
    for rg in ranges:
        a, b = float(rg["t0"]), float(rg["t1"])
        out = []
        for s in segs:
            if s["t1"] <= a or s["t0"] >= b:
                out.append(s); continue
            if s["t0"] < a:
                out.append({**s, "t1": a})
            if s["t1"] > b:
                out.append({**s, "t0": b})
        out.append({"t0": a, "t1": b, **new_chord, "fixed": True})
        segs = sorted(out, key=lambda s: s["t0"])
    merged = []
    for s in segs:
        if merged and same_chord(merged[-1], s) and abs(merged[-1]["t1"] - s["t0"]) < 1e-6:
            merged[-1]["t1"] = s["t1"]
        else:
            merged.append(s)
    return merged


def apply_suggestion(kind, p, data):
    """Returns a NEW transcription dict with the suggestion applied. The input is not modified."""
    d = copy.deepcopy(data)
    if kind == "chord":
        d["chords"] = apply_chord_fix(d.get("chords", []), p["ranges"], p["chord"])
    elif kind == "key":
        d["key"] = {"r": p["r"], "m": p["m"]}
    elif kind == "bpm":
        d["bpm"] = p["bpm"]
    elif kind in ("voicing", "shape"):
        d.setdefault("voicings", {})[("k:" if kind == "voicing" else "g:") + p["key"]] = {k: v for k, v in p.items() if k != "key"}
    elif kind == "video":
        d["video"] = {"id": p["id"], "offset": round(float(p.get("offset", 0)), 2)}
    elif kind == "sync":
        d["sync"] = {"phase": p["phase"], "cOff": p.get("cOff", 0), "lyr": p.get("lyr", [])}
    return d


def canonical(kind, p):
    """Stable text for 'is this the same suggestion?'. Times are rounded to 0.25 s."""
    q = copy.deepcopy(p)
    if kind == "chord":
        q["ranges"] = sorted([round(float(r["t0"]) * 4) / 4, round(float(r["t1"]) * 4) / 4] for r in q["ranges"])
        q["chord"] = {k: q["chord"].get(k, [] if k == "xt" else -1) for k in ("r", "q", "xt", "slash")}
    q.pop("note", None)
    return json.dumps(q, sort_keys=True)


def chord_at(chords, t):
    for c in chords:
        if c["t0"] <= t < c["t1"]:
            return c
    return None


def evidence(kind, p, official, candidates):
    """Automatic checks that help a moderator decide. Not a verdict."""
    ev = {"valid": True}
    if kind == "chord":
        mids = [(float(r["t0"]) + float(r["t1"])) / 2 for r in p["ranges"]]
        agree = 0
        for cand in candidates:
            hits = sum(1 for m in mids if (c := chord_at(cand.get("chords", []), m)) and same_chord(c, {**p["chord"], "xt": p["chord"].get("xt", []), "slash": p["chord"].get("slash", -1)}))
            if mids and hits / len(mids) >= .6:
                agree += 1
        ev["independent_analyses_agree"] = agree
        low = official.get("confidence", {}).get("low", [])
        ev["inside_low_confidence_section"] = any(a <= mids[0] <= b for a, b in low) if mids else False
        cur = [chord_at(official.get("chords", []), m) for m in mids]
        ev["changes_n_places"] = sum(1 for c in cur if c is None or not same_chord(c, {**p["chord"], "xt": p["chord"].get("xt", []), "slash": p["chord"].get("slash", -1)}))
    return ev
