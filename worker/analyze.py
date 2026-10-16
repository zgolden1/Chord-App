#!/usr/bin/env python3
"""
ChordFlow offline analysis: read the notes that are actually sounding in a recording.

    python analyze.py "My Song.mp3"                  -> "My Song.chordflow-notes.json"

Pipeline
  1. Demucs (htdemucs, or htdemucs_ft with --model htdemucs_ft) separates the mix into
     bass / other (keys, guitars, pads) / vocals / drums.
  2. Basic Pitch (Spotify) transcribes notes from the "other" stem and from the "bass" stem.
  3. librosa finds the beats (on the drum stem, which is steadier than the mix).
  4. For every beat the sounding notes are turned into a chord label (root, quality,
     extensions, slash bass), then equal neighbours are merged.
  5. music21 (optional) adds a standard chord-symbol string ("Cmaj7/E") for cross-checking.
Load the JSON in ChordFlow with "Add analysis file" on the Keys tab, using the same audio file.

Install (Python 3.10 or 3.11 is the safe choice for TensorFlow-based Basic Pitch):
    python -m venv cf && source cf/bin/activate          # Windows: cf\\Scripts\\activate
    pip install --upgrade pip
    pip install demucs basic-pitch librosa music21 numpy
    # Demucs reads MP3/M4A through ffmpeg:  macOS: brew install ffmpeg   Ubuntu: sudo apt install ffmpeg
Run:
    python analyze.py song.mp3                           # first run downloads the Demucs model
    python analyze.py song.mp3 --model htdemucs_ft       # slower, a little cleaner stems
    python analyze.py song.mp3 --device cpu              # or cuda / mps
    python analyze.py song.mp3 --stems-dir stems/        # reuse stems from an earlier run
    python analyze.py --selftest                         # checks the chord labeller, needs no audio libraries
"""
import argparse, json, os, subprocess, sys
from pathlib import Path

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# quality ids are the same ones the ChordFlow page uses
QUAL = [
    ("",     [0, 4, 7]),        # 0 maj
    ("m",    [0, 3, 7]),        # 1 min
    ("7",    [0, 4, 7, 10]),    # 2 dom7
    ("maj7", [0, 4, 7, 11]),    # 3 maj7
    ("m7",   [0, 3, 7, 10]),    # 4 m7
    ("sus2", [0, 2, 7]),        # 5
    ("sus4", [0, 5, 7]),        # 6
    ("dim",  [0, 3, 6]),        # 7
    ("aug",  [0, 4, 8]),        # 8
    ("m7b5", [0, 3, 6, 10]),    # 9
    ("6",    [0, 4, 7, 9]),     # 10
    ("m6",   [0, 3, 7, 9]),     # 11
]
EXT = {1: "b9", 2: "9", 3: "#9", 5: "11", 6: "#11", 8: "b13", 9: "13"}
# how much each chord tone matters when matching (root and third define the chord)
W = {0: 1.0, 3: 1.0, 4: 1.0, 2: .8, 5: .8, 6: .9, 7: .8, 8: .9, 9: .75, 10: .8, 11: .8}


def label_window(pc, bass):
    """pc, bass: 12 floats (pitch-class energy of the notes, and of the bass notes).
    Returns dict(r, q, xt, slash, name, conf) or None for silence."""
    tot = sum(pc)
    if tot <= 1e-9:
        return None
    pcn = [x / tot for x in pc]
    btot = sum(bass)
    bn = [x / btot for x in bass] if btot > 1e-9 else [0.0] * 12
    best = None
    for r in range(12):
        for q, (_, iv) in enumerate(QUAL):
            tones = {(r + i) % 12: W.get(i, .8) for i in iv}
            cover = sum(pcn[p] * w for p, w in tones.items())
            outside = sum(pcn[p] for p in range(12) if p not in tones)
            missing = sum(1 for p in tones if pcn[p] < .04)       # a chord tone nobody plays
            score = cover - 1.0 * outside - .35 * missing
            score += .55 * bn[r] + .15 * sum(bn[(r + i) % 12] for i in iv[1:])   # bass supports the root
            score -= .015 * len(iv)                                  # prefer the simpler chord on a tie
            if q >= 2 and q not in (5, 6, 7, 8):                     # a 7th/6th must really be there
                extra = pcn[(r + iv[3]) % 12]
                if extra < .10:
                    score -= .5
            if best is None or score > best[0]:
                best = (score, r, q)
    score, r, q = best
    iv = QUAL[q][1]
    tones = {(r + i) % 12 for i in iv}
    xt = []
    mx = max(pcn)
    for i, n in EXT.items():
        p = (r + i) % 12
        if p in tones or q in (5, 6):          # sus chords already use 2/4
            continue
        if pcn[p] >= .14 and pcn[p] >= .3 * mx:
            xt.append(i)
    xt = sorted(xt, key=lambda i: -pcn[(r + i) % 12])[:2]
    # slash bass: strongest bass note that is a chord tone but not the root
    slash = -1
    if btot > 1e-9:
        bp = max(range(12), key=lambda p: bn[p])
        if bp != r and bp in tones and bn[bp] >= .5:
            slash = bp
    name = NAMES[r] + QUAL[q][0] + ("(" + ",".join(EXT[i] for i in xt) + ")" if xt else "") + ("/" + NAMES[slash] if slash >= 0 else "")
    return dict(r=r, q=q, xt=xt, slash=slash, name=name, conf=round(score, 3))


def same(a, b):
    return a and b and (a["r"], a["q"], tuple(a["xt"]), a["slash"]) == (b["r"], b["q"], tuple(b["xt"]), b["slash"])


def merge_beats(windows, beats, dur, min_beats=2):
    """windows: label per beat. Merge equal neighbours, absorb blips shorter than min_beats."""
    labs = list(windows)
    for _ in range(2):
        i = 0
        while i < len(labs):
            j = i
            while j < len(labs) and same(labs[j], labs[i]) or (j < len(labs) and labs[j] is None and labs[i] is None):
                j += 1
            run = j - i
            if run < min_beats and i > 0 and j < len(labs) and same(labs[i - 1], labs[j]):
                for k in range(i, j):
                    labs[k] = labs[i - 1]
            i = max(j, i + 1)
    out = []
    for b, l in enumerate(labs):
        if out and (same(out[-1]["lab"], l) or (l is None and out[-1]["lab"] is None)):
            out[-1]["b1"] = b + 1
        else:
            out.append(dict(b0=b, b1=b + 1, lab=l))
    res = []
    for o in out:
        if o["lab"] is None:
            continue
        t0 = 0.0 if o["b0"] == 0 else beats[o["b0"]]
        t1 = dur if o["b1"] >= len(beats) else beats[o["b1"]]
        res.append(dict(t0=round(t0, 3), t1=round(t1, 3), **o["lab"]))
    return res


def window_energy(notes, t0, t1, lo, hi):
    pc = [0.0] * 12
    for s, e, p, a in notes:
        if p < lo or p > hi:
            continue
        ov = min(e, t1) - max(s, t0)
        if ov > 0:
            pc[p % 12] += ov * a
    return pc


def selftest():
    def v(*notes, bass=None):
        pc = [0.0] * 12
        for n in notes:
            pc[n % 12] += 1.0
        b = [0.0] * 12
        if bass is not None:
            b[bass % 12] = 1.0
            pc[bass % 12] += 1.0
        return pc, b
    cases = [
        ("C",      v(60, 64, 67, bass=48),               "C"),
        ("Am",     v(57, 60, 64, bass=45),               "Am"),
        ("G7",     v(55, 59, 62, 65, bass=43),           "G7"),
        ("Cmaj7",  v(60, 64, 67, 71, bass=48),           "Cmaj7"),
        ("Dm7",    v(62, 65, 69, 72, bass=50),           "Dm7"),
        ("Csus2",  v(60, 62, 67, bass=48),               "Csus2"),
        ("Bdim",   v(59, 62, 65, bass=47),               "Bdim"),
        ("C/E",    v(60, 64, 67, bass=52),               "C/E"),
        ("Cadd9",  v(60, 62, 64, 67, 67, bass=48),       "C(9)"),
        ("F#",     v(66, 70, 73, bass=42),               "F#"),
        ("B/D#",   v(59, 63, 66, bass=51),               "B/D#"),
    ]
    bad = 0
    for label, (pc, b), want in cases:
        got = label_window(pc, b)["name"]
        ok = got == want
        bad += not ok
        print(("ok   " if ok else "FAIL ") + label.ljust(8) + " -> " + got + ("" if ok else "   (wanted " + want + ")"))
    print("selftest:", "all passed" if not bad else str(bad) + " failed")
    return 1 if bad else 0


def run_demucs(src, model, out_dir, device):
    cmd = [sys.executable, "-m", "demucs", "-n", model, "-o", str(out_dir)]
    if device:
        cmd += ["-d", device]
    cmd.append(str(src))
    print("Separating stems with Demucs (%s)..." % model, flush=True)
    subprocess.run(cmd, check=True)
    d = Path(out_dir) / model / Path(src).stem
    if not d.exists():
        raise SystemExit("Demucs finished but its output folder was not found: %s" % d)
    return d


def transcribe(wav, lo_hz, hi_hz):
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH
    _, _, events = predict(str(wav), ICASSP_2022_MODEL_PATH, onset_threshold=.5, frame_threshold=.3,
                           minimum_note_length=90, minimum_frequency=lo_hz, maximum_frequency=hi_hz)
    return [(float(s), float(e), int(p), float(a)) for s, e, p, a, *_ in events]


def main():
    ap = argparse.ArgumentParser(description="ChordFlow offline note analysis")
    ap.add_argument("audio", nargs="?")
    ap.add_argument("--model", default="htdemucs", choices=["htdemucs", "htdemucs_ft", "htdemucs_6s"])
    ap.add_argument("--device", default=None, help="cpu, cuda or mps (default: Demucs decides)")
    ap.add_argument("--stems-dir", default=None, help="folder with bass.wav and other.wav (skips Demucs)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--min-beats", type=int, default=2, help="chords shorter than this are absorbed when both neighbours agree")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.audio:
        ap.error("give an audio file, or use --selftest")
    src = Path(a.audio)
    out = Path(a.out) if a.out else src.with_suffix(".chordflow-notes.json")
    if a.stems_dir:
        stems = Path(a.stems_dir)
    else:
        stems = run_demucs(src, a.model, src.parent / "chordflow_stems", a.device)
    other = stems / "other.wav"
    bass = stems / "bass.wav"
    drums = stems / "drums.wav"
    if a.model == "htdemucs_6s" and (stems / "guitar.wav").exists():
        print("Note: htdemucs_6s also made guitar.wav and piano.wav; this script reads other.wav only.")
    print("Transcribing notes with Basic Pitch...", flush=True)
    n_other = transcribe(other, 80, 2100)
    n_bass = transcribe(bass, 30, 400)
    print("  %d notes in 'other', %d in 'bass'" % (len(n_other), len(n_bass)))
    import librosa
    y, sr = librosa.load(str(drums if drums.exists() else src), sr=22050, mono=True)
    dur = float(librosa.get_duration(path=str(src)))
    tempo, bf = librosa.beat.beat_track(y=y, sr=sr, units="time")
    beats = [float(x) for x in bf]
    if not beats or beats[0] > .3:
        beats = [0.0] + beats
    print("  %d beats, tempo about %.0f BPM" % (len(beats), float(tempo if not hasattr(tempo, "__len__") else tempo[0])))
    labs = []
    for i, b0 in enumerate(beats):
        b1 = beats[i + 1] if i + 1 < len(beats) else dur
        pc = window_energy(n_other, b0, b1, 48, 90)
        bs = window_energy(n_bass, b0, b1, 28, 55)
        pc = [p + .6 * q for p, q in zip(pc, bs)]       # the bass is part of the chord too
        labs.append(label_window(pc, bs))
    chords = merge_beats(labs, beats, dur, a.min_beats)
    try:                                                 # optional cross-check with music21
        from music21 import chord as m21chord, harmony, pitch
        for c in chords:
            ps = [pitch.Pitch(midi=60 + ((c["r"] + i) % 12)).nameWithOctave for i in dict.fromkeys([0] + QUAL[c["q"]][1])]
            ch = m21chord.Chord(ps)
            c["figure"] = harmony.chordSymbolFigureFromChord(ch)
    except Exception as e:
        print("  (music21 check skipped: %s)" % e)
    res = dict(version=1, audio=src.name, duration=round(dur, 3), model=a.model,
               beats=[round(b, 3) for b in beats], chords=chords,
               notes=dict(other=[[round(s, 3), round(e, 3), p, round(am, 2)] for s, e, p, am in n_other],
                          bass=[[round(s, 3), round(e, 3), p, round(am, 2)] for s, e, p, am in n_bass]))
    out.write_text(json.dumps(res, separators=(",", ":")))
    print("Wrote %s (%d chords, %.0f KB). Load it in ChordFlow with 'Add analysis file'." % (out, len(chords), out.stat().st_size / 1024))


if __name__ == "__main__":
    main()
