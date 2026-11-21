#!/usr/bin/env python3
"""brain_service.py — music analysis sidecar for leds 909 (2026-11).

The Jev typed-decision model (Qwen3-ASR + ModernBERT + head) was REMOVED —
its speech encoder was a poor fit for music. This service now runs:

  1. Jamendo mood/theme tagging (Essentia Discogs-EffNet ONNX, exact mel)
  2. madmom beat/downbeat BPM per tap
  3. Realtime beats come from beat_service.py (BeatNet loopback) separately.

Watches HOT for 10 s WAV taps and sends:
  /jevbrain/heartbeat <n>     every loop (~0.3 s)
  /jevbrain/jamendo <tags> <conf>
  /jevbrain/bpm <bpm> <conf>

Portable: models live in ./models next to this file.
"""
import json as _json
import sys
import time
import wave
from pathlib import Path
import socket
import struct

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

CMD_PORT = 7003
ANSWER_PORT = 7005  # audio_jev oscin1 (TD-side handler)
HOT = Path('C:/Users/josep/AppData/Local/Temp/jev_hot')

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def osc_send(s, addr, *args):
    a = addr.encode()
    a += b'\x00' * (4 - len(a) % 4)
    t = b',' + b''.join(b'f' if isinstance(v, float) else (b'i' if isinstance(v, int) else b's') for v in args)
    t += b'\x00' * (4 - len(t) % 4)
    body = b''
    for v in args:
        if isinstance(v, (float, int)):
            body += struct.pack('>f', float(v))
        else:
            b = str(v).encode()
            body += b + b'\x00' * (4 - len(b) % 4)
    s.sendto(a + t + body, ('127.0.0.1', ANSWER_PORT))


# ---------------- madmom beats ----------------
_madmom_beat = None
_madmom_dbn = None


def _madmom_bpm(path):
    global _madmom_beat, _madmom_dbn
    if _madmom_beat is None:
        from madmom.features.downbeats import RNNDownBeatProcessor, DBNDownBeatTrackingProcessor
        _madmom_beat = RNNDownBeatProcessor()
        _madmom_dbn = DBNDownBeatTrackingProcessor(beats_per_bar=4, fps=100)
    beats = _madmom_dbn(_madmom_beat(str(path)))
    if beats.ndim == 2 and len(beats) >= 4:
        import numpy as np
        iv = np.diff(beats[:, 0])
        bpm = float(60.0 / np.median(iv))
        conf = float(1.0 - min(1.0, np.std(iv) / max(1e-6, np.mean(iv))))
        return bpm, conf
    return None


# ---------------- jamendo mood/theme ----------------
def _mel_patches(y, sr=16000):
    """Essentia TensorflowInputMusiCNN recipe (see HANDOFF for details)."""
    import numpy as np
    from scipy.fft import rfft
    frame, hop, n_mel, fmin, fmax = 512, 256, 96, 30.0, 15000.0
    nfft = frame
    mlo = 2595.0 * np.log10(1.0 + fmin / 700.0)
    mhi = 2595.0 * np.log10(1.0 + fmax / 700.0)
    centers = 700.0 * (10 ** (np.linspace(mlo, mhi, n_mel + 2) / 2595.0) - 1)
    bins = np.clip(np.floor((nfft + 1) * centers / sr).astype(int), 0, nfft // 2)
    fb = np.zeros((n_mel, nfft // 2 + 1), dtype=np.float32)
    for i in range(n_mel):
        lo, mi, hi = int(bins[i]), int(bins[i + 1]), int(bins[i + 2])
        if mi > lo:
            fb[i, lo:mi] = np.linspace(0.0, 1.0, mi - lo)
        if hi > mi:
            fb[i, mi:hi] = np.linspace(1.0, 0.0, hi - mi)
        if mi <= nfft // 2:
            fb[i, mi] = 1.0
    win = np.hanning(frame).astype(np.float32)
    frames = []
    for s0 in range(0, len(y) - frame, hop):
        spec = np.abs(rfft(y[s0:s0 + frame] * win, nfft)) ** 2
        frames.append(np.log10(10000.0 * np.maximum(fb @ spec, 0.0) + 1.0))
    fr = np.array(frames, dtype=np.float32)
    if len(fr) < 128:
        return None
    return np.stack([fr[s0:s0 + 128] for s0 in range(0, len(fr) - 127, 62)])


_jam = {'tried': False}


def _jam_init():
    if _jam['tried']:
        return
    _jam['tried'] = True
    try:
        import onnxruntime as ort
        d = HERE / 'models' / 'jamendo'
        _jam['e'] = ort.InferenceSession(str(d / 'discogs-effnet-bsdynamic-1.onnx'))
        _jam['h'] = ort.InferenceSession(str(d / 'mtg_jamendo_moodtheme-discogs-effnet-1.onnx'))
        _jam['labels'] = _json.load(open(d / 'mtg_jamendo_moodtheme-discogs-effnet-1.json'))['classes']
        _jam['glabels'] = _json.load(open(d / 'discogs-effnet-labels.json'))['classes']
        _jam['ok'] = True
        print('jamendo ready')
    except Exception as e:
        print('jamendo init skip:', str(e)[:100])


def _jam_analyze(y):
    if not _jam.get('ok'):
        return None
    import numpy as np
    mel = _mel_patches(y)
    if mel is None:
        return None
    emb, gact = _jam['e'].run(None, {'melspectrogram': mel})
    act = _jam['h'].run(None, {'embeddings': emb})[0].mean(axis=0)
    top = np.argsort(act)[::-1][:3]
    gtop = np.argsort(gact.mean(axis=0))[::-1][:2]
    g = ' / '.join(_jam['glabels'][i].split('---')[-1] for i in gtop)
    return ','.join(_jam['labels'][i] for i in top), float(act[top[0]]), g


def main():
    hb = 0
    cmd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cmd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    cmd.bind(('127.0.0.1', CMD_PORT))
    cmd.settimeout(0.3)
    out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print('brain service up (analyzer mode: jamendo + madmom)')
    _jam_init()
    analyzed = set()
    while True:
        try:
            cmd.recvfrom(2048)  # keep legacy command port silent-compatible
        except socket.timeout:
            pass
        hb += 1
        osc_send(out, '/jevbrain/heartbeat', float(hb))
        wavs = sorted(HOT.glob('*.wav'), key=lambda p: p.stat().st_mtime)
        for w in wavs[-1:]:
            if w.name in analyzed:
                continue
            analyzed.add(w.name)
            if len(analyzed) > 40:
                for old in list(analyzed)[:-20]:
                    analyzed.discard(old)
            try:
                import numpy as np
                with wave.open(str(w), 'rb') as f:
                    raw = f.readframes(f.get_nframes())
                y = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                t0 = time.time()
                jr = _jam_analyze(y)
                if jr:
                    osc_send(out, '/jevbrain/jamendo', jr[0], jr[1])
                    osc_send(out, '/jevbrain/genre', jr[2], jr[1])
                mb = _madmom_bpm(w)
                if mb:
                    osc_send(out, '/jevbrain/bpm', mb[0], mb[1])
                osc_send(out, '/jevbrain/done', float(time.time() - t0))
                w.unlink()
            except Exception as e:
                print('analyze ERR:', str(e)[:120])
        time.sleep(0.25)


if __name__ == '__main__':
    main()
