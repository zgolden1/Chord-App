"""Turns raw BTC chord labels (start, end, "C:min7/b3") into a ChordFlow analysis file.
Only converts. It never edits or re-guesses the model's output, and does no audio work."""
from server.convert import from_analysis_file

ROOTS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
# ChordFlow quality codes: 0 maj 1 min 2 7 3 maj7 4 min7 5 sus2 6 sus4 7 dim 8 aug 9 m7b5 10 6 11 m6
QUAL = {"": 0, "maj": 0, "min": 1, "7": 2, "maj7": 3, "min7": 4, "sus2": 5, "sus4": 6, "dim": 7, "aug": 8,
        "hdim7": 9, "maj6": 10, "min6": 11,
        "dim7": 7, "minmaj7": 1}   # ChordFlow has no slot for these two: nearest triad (a known simplification)
IVAL = {"1": 0, "b2": 1, "2": 2, "b3": 3, "3": 4, "4": 5, "b5": 6, "5": 7, "#5": 8, "b6": 8, "6": 9, "b7": 10, "7": 11}


def pc(name):
    p = ROOTS[name[0]]
    for ch in name[1:]:
        p += 1 if ch == "#" else -1 if ch == "b" else 0
    return p % 12


def parse(label):
    """-> dict(r, q, slash) or None for no-chord. Raises ValueError on a label it does not know."""
    if label in ("N", "X", ""):
        return None
    main, _, bass = label.partition("/")
    root, _, qual = main.partition(":")
    if qual not in QUAL or root[:1] not in ROOTS:
        raise ValueError("unknown BTC label: " + label)
    r = pc(root)
    out = {"r": r, "q": QUAL[qual], "slash": -1}
    if bass:
        if bass not in IVAL:
            raise ValueError("unknown BTC bass: " + label)
        b = (r + IVAL[bass]) % 12
        out["slash"] = b if b != r else -1
    return out


def btc_to_analysis(segments, duration=None, beats=None):
    """segments: [(start, end, label)] straight from BTC. Silence ("N") is dropped; nothing is merged or smoothed."""
    chords = []
    for t0, t1, lab in segments:
        c = parse(lab)
        if c:
            chords.append({"t0": round(float(t0), 3), "t1": round(float(t1), 3), **c})
    d = {"duration": duration if duration is not None else (segments[-1][1] if segments else 0), "beats": beats or [], "chords": chords}
    return from_analysis_file(d, "btc")
