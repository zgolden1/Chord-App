"""Writes /tmp/synth.wav: the loop F# E B/D# D, 2 s each, six times, with room noise. Used by livetest.py."""
import wave
import numpy as np
sr = 44100
def tone(f, t): return sum((0.6 ** h) * np.sin(2 * np.pi * f * (h + 1) * t) for h in range(6))
def chord(root, ivs, bass, dur):
    t = np.arange(int(sr * dur)) / sr
    f0 = lambda m: 440 * 2 ** ((m - 69) / 12)
    y = sum(tone(f0(60 + root + iv), t) * 0.5 for iv in ivs) + tone(f0(36 + bass), t) * 1.2
    return y * np.minimum(1, t * 30) * np.minimum(1, (dur - t) * 30)
loop = [(6, [0, 4, 7], 6), (4, [0, 4, 7], 4), (11, [0, 4, 7], 3), (2, [0, 4, 7], 2)]
y = np.concatenate([chord(r, iv, b, 2.0) for _ in range(6) for r, iv, b in loop])
y += np.random.default_rng(1).normal(0, 0.15, len(y))
y = y / np.abs(y).max() * 0.6
w = wave.open("/tmp/synth.wav", "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((y * 32767).astype("<i2").tobytes()); w.close()
print("wrote /tmp/synth.wav", len(y) / sr, "s")
