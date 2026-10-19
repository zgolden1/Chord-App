"""Run in the Colab where LiveChord and BTC already work. Writes one ChordFlow analysis file per MP3 into
MyDrive/Music/chordflow_btc/. Raw BTC output only: no merging, no filtering."""
import sys, json, os, glob
sys.path.insert(0, "/content/LiveChord/backend")
import chord_detect as cd
cd._load_model()
out = "/content/drive/MyDrive/Music/chordflow_btc"; os.makedirs(out, exist_ok=True)
for f in sorted(glob.glob("/content/drive/MyDrive/Music/songs/*.mp3")):
    segs = cd._run_btc(f)
    name = os.path.splitext(os.path.basename(f))[0]
    json.dump({"source": "btc_large_voca", "segments": [[float(a), float(b), c] for a, b, c in segs]}, open(f"{out}/{name}.btc.json", "w"))
    print(name, len(segs), "segments")
