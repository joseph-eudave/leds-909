#!/usr/bin/env python3
"""rave_service.py — RAVE latent modulation for leds 909 (audio pipeline
option 3).

Receives the same UDP audio stream as beat_service (127.0.0.1:7010, raw
float32 mono @16 kHz — we tap it with a second socket via SO_REUSEADDR),
runs the pretrained RAVE encoder (percussion.ts), reduces the latent to
8 dims (PCA fitted on the first frames, warmup), and sends OSC to TD:

    /rave/lat  [l0..l7]   ~11 Hz (RAVE hop), values roughly -3..3
    /rave/vel  [v]         latent velocity (timbre-change energy 0..1)
    /rave/hb   [t]         heartbeat 2 s

Beats/BPM still come from beat_service — RAVE is a modulation layer, not a
beat tracker. Launch: py -3.12 rave_service.py   (auto-started by the
services launcher; port 7012 used as the liveness guard).
"""
import os
import sys
import time
import socket
import struct
import threading
import queue

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

MODEL = os.path.join(HERE, 'models', 'rave', 'percussion.ts')
TD_PORT = 7005
AUDIO_PORT = 7011  # fed by beat_send_cb fan-out

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def osc_send(addr, *args):
    a = addr.encode()
    a += b'\x00' * (4 - len(a) % 4)
    Z = bytes([0])
    t = b',' + b''.join((b's' if isinstance(v, str) else b'f') for v in args)
    t += Z * (4 - len(t) % 4)
    body = b''
    for v in args:
        if isinstance(v, str):
            s = v.encode()
            body += s + Z * (4 - len(s) % 4)
        else:
            body += struct.pack('>f', float(v))
    sock.sendto(a + t + body, ('127.0.0.1', TD_PORT))


# liveness guard: bind the service port so the launcher/watchdog sees us
_guard = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
_guard.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
_guard.bind(('127.0.0.1', 7012))

print('loading RAVE model %s ...' % os.path.basename(MODEL), flush=True)
import numpy as np  # noqa: E402
import torch  # noqa: E402

torch.set_grad_enabled(False)
model = torch.jit.load(MODEL, map_location='cpu')
model.eval()
SR = int(getattr(model, 'sr', 48000)) if hasattr(model, 'sr') else 48000
try:
    SR = int(model.sr)
except Exception:
    SR = 48000
print('RAVE ready (sr %d)' % SR, flush=True)

_q = queue.Queue()


def _audio_tap():
    # second reader on the beat audio stream (SO_REUSEADDR broadcast fan-in
    # is not guaranteed on every stack; if we get nothing, fall back to
    # loopback capture like beat_service does).
    rs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        rs.bind(('127.0.0.1', AUDIO_PORT))
    except Exception:
        pass
    rs.settimeout(1.0)
    while True:
        try:
            data, _ = rs.recvfrom(65536)
            y = np.frombuffer(data, dtype='<f4').copy()
            if len(y):
                _q.put(y)
        except socket.timeout:
            pass
        except Exception:
            time.sleep(0.5)


st = {'resamp': np.zeros(0, dtype=np.float32), 'prev_lat': None,
      'pca': None, 'pca_buf': [], 'frames': 0, 'last_emit': 0.0}


def _resample(y16k):
    if SR == 16000:
        return y16k
    n = int(len(y16k) * SR / 16000.0)
    return y16k[np.linspace(0, len(y16k) - 1, n).astype(np.int32)].astype(np.float32)


def _pca_reduce(lat):
    """lat: np array (n, d). Fit PCA on first ~200 frames, then project."""
    if st['pca'] is None:
        st['pca_buf'].append(lat)
        if len(st['pca_buf']) < 200:
            # during warmup: return first 8 raw dims (scaled down)
            d = lat.shape[-1]
            take = lat[:8] if d >= 8 else np.pad(lat, (0, 8 - d))
            return (take - take.min()) / max(1e-6, take.max() - take.min()) * 4 - 2
        X = np.stack(st['pca_buf'])
        X = X - X.mean(axis=0, keepdims=True)
        C = np.cov(X.T)
        w, V = np.linalg.eigh(C)
        order = np.argsort(w)[::-1][:8]
        st['pca'] = (X.mean(axis=0), V[:, order])
        print('pca fitted on %d frames' % len(X), flush=True)
    mu, P = st['pca']
    return (lat - mu) @ P


def _process(y16k):
    x = torch.from_numpy(_resample(y16k)).unsqueeze(0).unsqueeze(0)  # (1,1,N)
    try:
        z = model.encode(x)              # (1, d, frames)
        if hasattr(z, 'loc'):
            z = z.loc
        lat = z[0].mean(dim=-1).numpy()  # (d,) mean over chunk frames
    except Exception as e:
        print('encode err', repr(e)[:120], flush=True)
        return
    st['frames'] += 1
    lat8 = np.tanh(np.asarray(lat, dtype=np.float64) * 0.5)  # -> -1..1, 4 dims
    prev = st['prev_lat']
    if prev is not None and len(prev) == len(lat8):
        v = float(np.tanh(np.abs(lat8 - prev).mean() * 0.8))
    else:
        v = 0.0
    st['prev_lat'] = lat8
    now = time.time()
    if now - st['last_emit'] >= 0.09:
        st['last_emit'] = now
        osc_send('/rave/lat', *[float(u) for u in lat8])
        osc_send('/rave/vel', v)


def main():
    threading.Thread(target=_audio_tap, daemon=True).start()
    hb_t = 0.0
    while True:
        got = False
        try:
            while True:
                y = _q.get_nowait()
                _process(y)
                got = True
                if _q.qsize() > 30:
                    while _q.qsize() > 10:
                        _q.get()
        except queue.Empty:
            pass
        now = time.time()
        if now - hb_t >= 2.0:
            hb_t = now
            osc_send('/rave/hb', now)
            osc_send('/rave/status', 'running %d frames' % st['frames'])
        if not got:
            time.sleep(0.02)
        else:
            time.sleep(0.005)


if __name__ == '__main__':
    main()
