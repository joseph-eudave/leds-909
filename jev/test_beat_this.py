#!/usr/bin/env python3
import os as _os
"""test_beat_this.py — offline accuracy test of CPJKU beat_this on local tracks.

For each track: detect beats/downbeats, derive BPM from median inter-beat
interval (audio time, octave-guarded), report first/last beats and regularity.
"""
import sys, time
import numpy as np
import torch, torchaudio
from beat_this.inference import File2Beats

def analyze(path, checkpoint='final0'):
    t0 = time.time()
    f2b = File2Beats(checkpoint_path=checkpoint)
    beats, downbeats = f2b(path)
    dt = time.time() - t0
    if len(beats) < 4:
        print('%s: only %d beats' % (path, len(beats)))
        return
    iv = np.diff(beats)
    med = float(np.median(iv))
    bpm = 60.0 / med
    # octave guard into 78..185
    while bpm < 78: bpm *= 2
    while bpm > 185: bpm /= 2
    print('%s [%s]: %d beats, %d downbeats in %.1fs (rtf %.2f)' % (
        path.split('/')[-1], checkpoint, len(beats), len(downbeats), dt,
        dt / max(beats[-1], 1e-9)))
    print('   bpm(raw median)=%.1f  bpm(octave-guarded)=%.1f  interval std=%.3fs (%.1f%%)' % (
        60.0 / med, bpm, float(np.std(iv)), 100 * np.std(iv) / med))
    print('   first beats:', np.round(beats[:8], 2).tolist())

if __name__ == '__main__':
    ckpt = sys.argv[1] if len(sys.argv) > 1 else 'final0'
    tracks = [
        _os.path.join(_os.path.expanduser('~'), 'Music', 'Crash The Party.mp3'),
    ]
    import glob, os
    extra = glob.glob(_os.path.join(_os.path.expanduser('~'), 'Music', '*.mp3'))[:3]
    for t in extra:
        if t not in tracks and os.path.exists(t):
            tracks.append(t)
    for t in tracks:
        if os.path.exists(t):
            try:
                analyze(t, ckpt)
            except Exception as e:
                print(t, 'ERR', repr(e))
