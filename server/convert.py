"""Turn the file written by analyze.py into the catalog's transcription format."""
import statistics

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
KS_MAJ = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
KS_MIN = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
IV = [[0, 4, 7], [0, 3, 7], [0, 4, 7, 10], [0, 4, 7, 11], [0, 3, 7, 10], [0, 2, 7], [0, 5, 7], [0, 3, 6], [0, 4, 8], [0, 3, 6, 10], [0, 4, 7, 9], [0, 3, 7, 9]]


def _corr(a, b):
    ma, mb = sum(a) / 12, sum(b) / 12
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** .5
    return num / den if den else 0


def estimate_key(chords):
    prof = [0.0] * 12
    for c in chords:
        d = c["t1"] - c["t0"]
        for i in IV[c["q"]]:
            prof[(c["r"] + i) % 12] += d * (1.5 if i == 0 else 1.0)
    best = None
    for r in range(12):
        rot = prof[r:] + prof[:r]
        for m, tpl in ((False, KS_MAJ), (True, KS_MIN)):
            s = _corr(rot, tpl)
            if best is None or s > best[0]:
                best = (s, r, m)
    return {"r": best[1], "m": best[2]}


def estimate_bpm(beats):
    if len(beats) < 8:
        return None
    gaps = [b - a for a, b in zip(beats, beats[1:]) if .25 < b - a < 1.5]
    if not gaps:
        return None
    bpm = 60.0 / statistics.median(gaps)
    while bpm < 70:
        bpm *= 2
    while bpm > 170:
        bpm /= 2
    return round(bpm)


def from_analysis_file(d, pipeline):
    chords = [{k: c[k] for k in ("t0", "t1", "r", "q", "xt", "slash") if k in c} for c in d["chords"]]
    confs = sorted(c["conf"] for c in d["chords"] if "conf" in c)
    cut = confs[int(len(confs) * .15)] if confs else None
    low = [[c["t0"], c["t1"]] for c in d["chords"] if cut is not None and c.get("conf", 9) <= cut]
    return {"pipeline": pipeline, "duration": d.get("duration"), "key": estimate_key(chords), "bpm": estimate_bpm(d.get("beats", [])),
            "beats": d.get("beats", []), "phase": 0, "chords": chords,
            "confidence": {"mean": round(sum(confs) / len(confs), 3) if confs else None, "low": low}}
