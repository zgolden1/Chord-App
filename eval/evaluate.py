#!/usr/bin/env python3
"""Measure chord accuracy against reference charts, the way MIREX does (duration-weighted).
  python eval/evaluate.py --ref refs/ --est ests/        # matching names: song.lab  vs  song.json
Reference: Harte .lab files  ("start end C:maj7/3" per line)   Estimate: catalog transcription JSON (or analyze.py output).
Metrics: root, majmin, sevenths, bass  (fractions of reference time that match)."""
import argparse, glob, json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
# interval sets (semitones from root) for Harte shorthand
SH = {"maj": (0, 4, 7), "min": (0, 3, 7), "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11), "min7": (0, 3, 7, 10), "sus2": (0, 2, 7), "sus4": (0, 5, 7),
      "dim": (0, 3, 6), "aug": (0, 4, 8), "hdim7": (0, 3, 6, 10), "maj6": (0, 4, 7, 9), "min6": (0, 3, 7, 9), "dim7": (0, 3, 6, 9),
      "9": (0, 4, 7, 10), "maj9": (0, 4, 7, 11), "min9": (0, 3, 7, 10), "11": (0, 4, 7, 10), "13": (0, 4, 7, 10), "": (0, 4, 7)}
IVNAME = {"3": 4, "b3": 3, "5": 7, "b5": 6, "#5": 8, "7": 11, "b7": 10, "2": 2, "4": 5, "6": 9, "1": 0, "b9": 1, "9": 2, "11": 5, "13": 9}


def pc(name):
    m = re.match(r"^([A-G])([#b]*)$", name)
    if not m:
        raise ValueError(name)
    return (PC[m.group(1)] + m.group(2).count("#") - m.group(2).count("b")) % 12


def parse_harte(label):
    """-> (root, frozenset of intervals, bass) or None for no-chord."""
    if label in ("N", "X"):
        return None
    main, _, bass = label.partition("/")
    root, _, qual = main.partition(":")
    r = pc(root)
    adds = []
    if "(" in qual:
        qual, _, extra = qual.partition("(")
        adds = [x for x in extra.rstrip(")").split(",") if x]
    ivs = set(SH.get(qual, SH[""]))
    for x in adds:
        if x.startswith("*"):
            ivs.discard(IVNAME.get(x[1:], -1))
        elif x in IVNAME:
            ivs.add(IVNAME[x])
    b = (r + IVNAME.get(bass, 0)) % 12 if bass else r
    return r, frozenset(ivs), b


def from_catalog(c):
    from server.logic import NAMES  # noqa: F401
    QI = {0: (0, 4, 7), 1: (0, 3, 7), 2: (0, 4, 7, 10), 3: (0, 4, 7, 11), 4: (0, 3, 7, 10), 5: (0, 2, 7), 6: (0, 5, 7), 7: (0, 3, 6), 8: (0, 4, 8), 9: (0, 3, 6, 10), 10: (0, 4, 7, 9), 11: (0, 3, 7, 9)}
    XT = {1: 1, 2: 2, 3: 3, 5: 5, 6: 6, 8: 8, 9: 9}
    ivs = set(QI[c["q"]]) | {XT[i] for i in c.get("xt", []) if i in XT}
    b = c["slash"] if c.get("slash", -1) >= 0 else c["r"]
    return c["r"], frozenset(ivs), b


def load_ref(path):
    out = []
    for ln in open(path):
        p = ln.split()
        if len(p) >= 3:
            out.append((float(p[0]), float(p[1]), parse_harte(p[2])))
    return out


def load_est(path):
    d = json.load(open(path))
    d = d.get("data", d)
    return [(c["t0"], c["t1"], from_catalog(c)) for c in d["chords"]]


def third(ivs):
    return 3 if 3 in ivs else 4 if 4 in ivs else 2 if 2 in ivs else 5 if 5 in ivs else None


def fifth(ivs):
    return 6 if 6 in ivs and 7 not in ivs else 8 if 8 in ivs and 7 not in ivs else 7


def seventh(ivs):
    return 11 if 11 in ivs else 10 if 10 in ivs else (9 if 9 in ivs and 3 in ivs and 6 in ivs else None)


def scores(ref, est):
    """root: same root.  majmin: + same third and fifth quality.  sevenths: + same seventh.  bass: same bass note."""
    tot = {"root": 0.0, "majmin": 0.0, "sevenths": 0.0, "bass": 0.0}
    used = 0.0
    pts = sorted({t for a, b, _ in ref for t in (a, b)} | {t for a, b, _ in est for t in (a, b)})
    for t0, t1 in zip(pts, pts[1:]):
        mid = (t0 + t1) / 2
        r = next((c for a, b, c in ref if a <= mid < b), "none")
        if r == "none":
            continue
        e = next((c for a, b, c in est if a <= mid < b), None)
        d = t1 - t0
        used += d
        if r is None or e is None:
            if r is None and e is None:
                for k in tot:
                    tot[k] += d
            continue
        if r[0] == e[0]:
            tot["root"] += d
            if third(r[1]) == third(e[1]) and fifth(r[1]) == fifth(e[1]):
                tot["majmin"] += d
                if seventh(r[1]) == seventh(e[1]):
                    tot["sevenths"] += d
        if r[2] == e[2]:
            tot["bass"] += d
    return {k: (v / used if used else 0.0) for k, v in tot.items()}, used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--est", required=True)
    a = ap.parse_args()
    rows, T = [], {"root": 0, "majmin": 0, "sevenths": 0, "bass": 0}
    wt = 0.0
    for rp in sorted(glob.glob(os.path.join(a.ref, "*.lab"))):
        name = os.path.splitext(os.path.basename(rp))[0]
        ep = os.path.join(a.est, name + ".json")
        if not os.path.exists(ep):
            print("missing estimate for", name); continue
        s, used = scores(load_ref(rp), load_est(ep))
        rows.append((name, s)); wt += used
        for k in T: T[k] += s[k] * used
    print("%-28s %6s %7s %9s %6s" % ("song", "root", "majmin", "sevenths", "bass"))
    for n, s in rows:
        print("%-28s %6.1f %7.1f %9.1f %6.1f" % (n[:28], *(100 * s[k] for k in ("root", "majmin", "sevenths", "bass"))))
    if wt:
        print("%-28s %6.1f %7.1f %9.1f %6.1f   (weighted by duration, %d songs)" % ("ALL", *(100 * T[k] / wt for k in ("root", "majmin", "sevenths", "bass")), len(rows)))


if __name__ == "__main__":
    main()
