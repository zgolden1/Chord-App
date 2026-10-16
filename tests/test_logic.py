import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from server.convert import from_analysis_file
from eval.evaluate import parse_harte, scores, from_catalog
# Honeymoon Avenue loop F# E B/D# D, converted and scored against a hand-written reference
d = {"duration": 32, "beats": [i * .5 for i in range(64)], "chords": [
    {"t0": 0, "t1": 8, "r": 6, "q": 0, "conf": .9}, {"t0": 8, "t1": 16, "r": 4, "q": 0, "conf": .8},
    {"t0": 16, "t1": 24, "r": 11, "q": 0, "slash": 3, "conf": .7}, {"t0": 24, "t1": 32, "r": 2, "q": 0, "conf": .6}]}
t = from_analysis_file(d, "x")
# The Honeymoon loop (F# E B D) is modal, so a profile-based key guess can land on B: keys are estimates, which is
# why the catalog has a "key" suggestion kind. A plain I-IV-V-I must come out right:
plain = from_analysis_file({"duration": 32, "beats": [], "chords": [dict(t0=i * 8, t1=i * 8 + 8, r=r, q=0) for i, r in enumerate([0, 5, 7, 0])]}, "x")
assert plain["key"] == {"r": 0, "m": False}, plain["key"]
assert t["bpm"] == 120, t["bpm"]
ref = [(0, 8, parse_harte("F#:maj")), (8, 16, parse_harte("E:maj")), (16, 24, parse_harte("B:maj/3")), (24, 32, parse_harte("D:maj"))]
est = [(c["t0"], c["t1"], from_catalog(c)) for c in t["chords"]]
s, used = scores(ref, est)
assert used == 32 and all(v == 1.0 for v in s.values()), s
est[2] = (16, 24, from_catalog({"r": 11, "q": 0, "slash": -1}))
s, _ = scores(ref, est)
assert s["majmin"] == 1.0 and s["bass"] == .75, s
print("logic tests passed")
