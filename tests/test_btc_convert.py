import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from server.btc_convert import parse, btc_to_analysis
assert parse("Db:maj") == {"r": 1, "q": 0, "slash": -1}
assert parse("F:min") == {"r": 5, "q": 1, "slash": -1}
assert parse("Eb:7") == {"r": 3, "q": 2, "slash": -1}
assert parse("Ab:maj7") == {"r": 8, "q": 3, "slash": -1}
assert parse("B:maj/3") == {"r": 11, "q": 0, "slash": 3}          # B/D#
assert parse("C:hdim7")["q"] == 9 and parse("C:sus4")["q"] == 6 and parse("A:min7/b7")["slash"] == 7
assert parse("C:maj/5")["slash"] == 7 and parse("C:maj/1")["slash"] == -1
assert parse("N") is None
try: parse("C:wat"); raise SystemExit("should reject unknown labels")
except ValueError: pass
segs = [(0.09, 1.76, "Db:maj"), (1.76, 3.43, "Eb:7"), (3.43, 5.09, "Ab:maj"), (5.09, 7.22, "F:min"), (7.22, 9.0, "N"), (9.0, 10.0, "Db:maj")]
a = btc_to_analysis(segs)
assert [(c["t0"], c["t1"], c["r"], c["q"]) for c in a["chords"]] == [(0.09, 1.76, 1, 0), (1.76, 3.43, 3, 2), (3.43, 5.09, 8, 0), (5.09, 7.22, 5, 1), (9.0, 10.0, 1, 0)]
assert a["pipeline"] == "btc" and a["key"] == {"r": 5, "m": True} or a["key"] == {"r": 8, "m": False}, a["key"]
print("btc convert tests passed", a["key"])
