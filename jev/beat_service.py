#!/usr/bin/env python3
"""beat_service.py — REALTIME beat/downbeat tracking for leds 909.

Audio source (in priority order):
  1. UDP stream from TouchDesigner (beat_send bridge, port 7010,
     raw float32 mono @16 kHz)
  2. WASAPI loopback of the default output device (repaired fallback)

Engine: BeatNet online (CRNN + particle filter, hop 441 @ 22050 Hz).

Tempo logic (v2, 2026-11-18):
  - BPM from inter-beat intervals in AUDIO TIME (decoder timestamps),
    median over the last 16 intervals — immune to network/CPU jitter.
  - Octave policy with hysteresis: hardcore is legitimately 190-220 BPM, so
    half-time engages only above 240 BPM sustained for 8 beats, and releases
    only below 200 BPM sustained for 8 beats. No per-beat flip-flopping.

OSC out (audio_jev oscin1 :7005), unchanged protocol:
    /beat/beat      [t, beatnum]
    /beat/downbeat  [t]
    /beat/tempo     [bpm]          every 2 s
    /beat/status    [str]
    /beat/hb        [t]            every 2 s

Portable: runs from this folder. Launch: py -3.12 beat_service.py
"""
import os
import sys
import time
import socket
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

TD_PORT = 7005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def osc_send(addr, *args):
    a = addr.encode()
    a += b'\x00' * (4 - len(a) % 4)
    t = b',' + b''.join(b'f' if isinstance(v, float) else (b'i' if isinstance(v, int) else b's') for v in args)
    t += b'\x00' * (4 - len(t) % 4)
    body = b''
    for v in args:
        if isinstance(v, (float, int)):
            body += struct.pack('>f', float(v))
        else:
            s = str(v).encode()
            body += s + b'\x00' * (4 - len(s) % 4)
    sock.sendto(a + t + body, ('127.0.0.1', TD_PORT))


print('loading BeatNet...', flush=True)
import numpy as np  # noqa: E402
np.in1d = np.isin  # BeatNet PF uses in1d (removed in numpy 2)
import torch  # noqa: E402
from BeatNet.BeatNet import BeatNet  # noqa: E402

bn = BeatNet(1, mode='online', inference_model='PF', plot=[])
HOP = bn.log_spec_hop_length           # 441 @ 22050 (20 ms)
WIN = bn.log_spec_win_length + 2 * HOP
SR = bn.sample_rate                    # 22050
print('BeatNet ready (hop %d, sr %d)' % (HOP, SR), flush=True)

import threading, queue
_udp_q = queue.Queue()


def _cmd_listener():
    # commands from TD (port 7011): "model online|beatnet-file|beatthis-file",
    # "file <path>", "pos <seconds>" (authoritative playhead)
    rs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rs.bind(('127.0.0.1', 7011))
    while True:
        try:
            data, _ = rs.recvfrom(4096)
            msg = data.decode(errors='replace').strip()
            _handle_cmd(msg)
        except Exception:
            time.sleep(0.2)


def _handle_cmd(msg):
    try:
        if msg.startswith('model '):
            mode = msg.split(' ', 1)[1].strip()
            if mode in ('online', 'beatnet-file', 'beatthis-file'):
                if mode == st['mode'] and (mode == 'online' or st.get('file_beats')):
                    return  # already in this mode: idempotent, keep clock
                st['mode'] = mode
                st['file_beats'] = []
                st['clock'] = 0.0
                st['next_beat_i'] = 0
                print('model -> %s' % mode, flush=True)
                osc_send('/beat/status', mode)
                _ensure_file_analysis()
        elif msg.startswith('file '):
            st['file_path'] = msg.split(' ', 1)[1].strip()
            st['file_beats'] = []
            st['next_beat_i'] = 0
            _ensure_file_analysis()
        elif msg.startswith('pos '):
            st['td_pos'] = float(msg.split(' ', 1)[1])
            st['td_pos_t'] = time.time()
    except Exception as e:
        print('cmd err', repr(e), flush=True)


def _ensure_file_analysis():
    if st['mode'] == 'online' or st.get('analysing'):
        return
    path = st.get('file_path')
    if not path or not os.path.exists(path):
        print('file mode but no file: %r' % path, flush=True)
        return
    st['analysing'] = True
    threading.Thread(target=_analyze_file, args=(path, st['mode']), daemon=True).start()


def _analyze_file(path, mode):
    try:
        t0 = time.time()
        if mode == 'beatthis-file':
            from beat_this.inference import File2Beats
            f2b = File2Beats(checkpoint_path='final0', dbn=False)
            beats, down = f2b(path)
            dset = set(np.round(down, 3))
            rows = [(float(b), 1 if round(float(b), 3) in dset else 2) for b in beats]
        else:
            bn2 = BeatNet(1, mode='offline', inference_model='DBN', plot=[])
            out = bn2.process(path)
            rows = [(float(r[0]), int(round(float(r[1])))) for r in np.atleast_2d(out)]
        st['file_beats'] = sorted(rows)
        st['file_len'] = rows[-1][0] + 5.0 if rows else 0.0
        st['next_beat_i'] = 0
        st['clock'] = None
        print('analysed %s [%s]: %d beats in %.1fs' % (
            os.path.basename(path), mode, len(rows), time.time() - t0), flush=True)
    except Exception as e:
        print('analyze err', repr(e), flush=True)
        osc_send('/beat/status', 'analyze-err')
    finally:
        st['analysing'] = False


def _udp_listener():
    rs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rs.bind(('127.0.0.1', 7010))
    rs.settimeout(1.0)
    while True:
        try:
            data, _ = rs.recvfrom(65536)
            _udp_q.put(np.frombuffer(data, dtype='<f4').copy())
            st['udp_t'] = time.time()
        except socket.timeout:
            pass
        except Exception:
            time.sleep(0.5)


st = {'win': np.zeros(WIN, dtype=np.float32), 'counter': 0,
      'beats': 0, 'downbeats': 0, 'resid': np.zeros(0, dtype=np.float32),
      'last_emit_t': -1.0, 'udp_t': -1e9,
      # tempo state
      'ats': [],            # audio-time stamps of recent beats
      'raw_bpm': 0.0, 'disp_bpm': 0.0,
      'half': False, 'half_evidence': 0, 'full_evidence': 0,
      'half_sub': 0,
      # model switching
      'mode': 'online', 'file_path': None, 'file_beats': [], 'file_len': 0.0,
      'next_beat_i': 0, 'clock': None, 'analysing': False,
      'td_pos': None, 'td_pos_t': -1e9}

HALF_ON_BPM = 240.0    # engage half-time above this (audio-time median)
HALF_OFF_BPM = 200.0   # release half-time below this
EVIDENCE_N = 8         # beats of consistent evidence required to switch


def _update_tempo(at):
    """at: audio time (s) of the newest detected beat."""
    ats = st['ats']
    ats.append(at)
    del ats[:-17]
    if len(ats) >= 5:
        iv = np.diff(ats)
        st['raw_bpm'] = 60.0 / float(np.median(iv))
    # hysteresis octave switch (needs EVIDENCE_N consecutive beats of proof)
    if not st['half'] and st['raw_bpm'] > HALF_ON_BPM:
        st['half_evidence'] += 1
        if st['half_evidence'] >= EVIDENCE_N:
            st['half'] = True
            st['half_sub'] = st['beats']
            st['half_evidence'] = 0
            print('tempo: half-time engaged (%.0f bpm raw)' % st['raw_bpm'], flush=True)
    else:
        st['half_evidence'] = max(0, st['half_evidence'] - 1)
    if st['half'] and st['raw_bpm'] < HALF_OFF_BPM:
        st['full_evidence'] += 1
        if st['full_evidence'] >= EVIDENCE_N:
            st['half'] = False
            st['full_evidence'] = 0
            print('tempo: half-time released (%.0f bpm raw)' % st['raw_bpm'], flush=True)
    else:
        st['full_evidence'] = max(0, st['full_evidence'] - 1)
    st['disp_bpm'] = st['raw_bpm'] / 2.0 if st['half'] else st['raw_bpm']


def _emit_beat(t, b):
    st['beats'] += 1
    _update_tempo(t)
    if st['half']:
        if (st['beats'] - st['half_sub']) % 2 == 1:
            return  # swallow the off-beat detection (8th-note lock)
    osc_send('/beat/beat', t, float(b))
    if b == 1:
        st['downbeats'] += 1
        osc_send('/beat/downbeat', t)
    print('beat %d (pos %d) bpm %.1f%s' % (
        st['beats'], b, st['disp_bpm'], ' (half)' if st['half'] else ''), flush=True)


def feed_22050(chunk):
    """chunk: float32 mono @22050. Emits beats via PF decoder."""
    buf = np.concatenate([st['resid'], chunk])
    n_hops = len(buf) // HOP
    st['resid'] = buf[n_hops * HOP:]
    for k in range(n_hops):
        hop = buf[k * HOP:(k + 1) * HOP]
        st['win'] = np.append(st['win'][HOP:], hop)
        if st['counter'] < 5:
            st['counter'] += 1
            pred = np.zeros([1, 2])
        else:
            with torch.no_grad():
                feats = bn.proc.process_audio(st['win']).T[-1]
                f = torch.from_numpy(feats).unsqueeze(0).unsqueeze(0).to(bn.device)
                p = bn.model(f)[0]
                p = bn.model.final_pred(p)
                pred = np.transpose(p.cpu().detach().numpy()[:2, :])
        try:
            out = bn.estimator.process(pred)
        except Exception:
            out = None
        if out is not None and len(out):
            rows = np.atleast_2d(out)
            # PF returns its running beat list per frame: LAST row is newest.
            # A NEW beat = newest time advanced since last call.
            row = rows[-1]
            t, b = float(row[0]), int(round(float(row[1])))
            if t <= st['last_emit_t'] + 1e-6 or t - st['last_emit_t'] < 0.2:
                if t > st['last_emit_t']:
                    st['last_emit_t'] = t
            else:
                st['last_emit_t'] = t
                _emit_beat(t, b)


def _file_mode_clock(samples):
    # Clock = TD playhead extrapolated between pos updates (the UDP chunk
    # stream repeats data because the CHOP cooks faster than audio fills, so
    # raw sample accumulation over-counts). Fall back to accumulation only
    # when TD pos messages stop.
    now = time.time()
    td_pos = st.get('td_pos')
    fresh = td_pos is not None and now - st.get('td_pos_t', -1e9) < 3.0
    if fresh:
        st['clock'] = td_pos + (now - st['td_pos_t'])
    else:
        if now - st.get('last_chunk_t', -1e9) > 1.5:
            st['clock'] = None
            st['next_beat_i'] = 0
        st['last_chunk_t'] = now
        if st['clock'] is None:
            st['clock'] = 0.0
        st['clock'] += samples / 16000.0


def _emit_file_beats():
    fb = st.get('file_beats') or []
    i = st.get('next_beat_i', 0)
    pos = st['clock']
    last_t = st.get('last_emitted_pos', -1e9)
    if pos < last_t - 0.05:
        # playhead rewound (seek/loop): re-arm from the new position
        i = 0
        while i < len(fb) and fb[i][0] <= pos:
            i += 1
        st['ats'] = []
        print('rewind: pos %.2f -> next beat %d' % (pos, i), flush=True)
    st['last_emitted_pos'] = pos
    while i < len(fb) and fb[i][0] <= pos:
        t_abs, b = fb[i]
        # wall-time stamp for latency: now minus how far pos ran past the beat
        lag = max(0.0, pos - t_abs)
        now = time.time() - lag
        osc_send('/beat/beat', now, float(b))
        if b == 1:
            st['downbeats'] += 1
            osc_send('/beat/downbeat', now)
        st['beats'] += 1
        ats = st['ats']
        ats.append(t_abs)
        del ats[:-17]
        if len(ats) >= 5:
            st['raw_bpm'] = 60.0 / float(np.median(np.diff(ats)))
        st['disp_bpm'] = st['raw_bpm']
        i += 1
    st['next_beat_i'] = i


def _feed_udp():
    # bounded drain: never process more than 12 chunks per call (~0.25 s of
    # audio); if the queue backs up (CPU slower than realtime), DROP stale
    # chunks and keep only the newest few so we stay live.
    dropped = 0
    while _udp_q.qsize() > 24:
        _udp_q.get()
        dropped += 1
    if dropped:
        print('dropped %d stale chunks' % dropped, flush=True)
    n = 0
    while not _udp_q.empty() and n < 12:
        y = _udp_q.get()
        n += 1
        if not len(y):
            continue
        if st['mode'] != 'online':
            _file_mode_clock(len(y))
            if st['file_beats']:
                _emit_file_beats()
            continue
        n2 = int(len(y) * SR / 16000.0)
        feed_22050(y[np.linspace(0, len(y) - 1, n2).astype(np.int32)] if len(y) > 1 else y)


def _housekeeping():
    now = time.time()
    if now - _housekeeping.t >= 2.0:
        _housekeeping.t = now
        osc_send('/beat/hb', now)
        osc_send('/beat/tempo', float(st['disp_bpm']))


_housekeeping.t = 0.0


def _housekeeping_thread():
    # dedicated thread: tempo/heartbeat OSC must never be starved by DSP load
    while True:
        time.sleep(2.0)
        try:
            _housekeeping()
        except Exception:
            pass


# ---------- loopback fallback (repaired) ----------
def _resample_to_22050(y, sr_in):
    if sr_in == SR:
        return y.astype(np.float32)
    n = int(len(y) * SR / float(sr_in))
    return y[np.linspace(0, len(y) - 1, n).astype(np.int32)].astype(np.float32)


def _open_loopback():
    import pyaudiowpatch as pyaudio
    p = pyaudio.PyAudio()
    wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    default_out = p.get_device_info_by_index(wasapi['defaultOutputDevice'])
    spk = None
    for i in range(p.get_device_count()):
        d = p.get_device_info_by_index(i)
        if d.get('isLoopbackDevice') and d.get('maxInputChannels', 0) > 0:
            if d['name'].startswith(default_out['name'][:20]):
                spk = d
                break
    if spk is None:
        spk = default_out
    cap_sr = int(spk['defaultSampleRate'])

    # WASAPI loopback devices are often stereo-only: opening them mono gives
    # paInvalidDevice (-9996). Open the native channel count and downmix.
    ch = int(spk.get('maxInputChannels', 0)) or 2

    def cb(in_data, frame_count, time_info, status):
        y = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        if ch > 1:
            y = y.reshape(-1, ch).mean(axis=1)
        feed_22050(_resample_to_22050(y, cap_sr))
        return (None, pyaudio.paContinue)

    stream = p.open(format=pyaudio.paInt16, channels=ch, rate=cap_sr, input=True,
                    input_device_index=spk['index'],
                    frames_per_buffer=int(cap_sr * 0.02),
                    stream_callback=cb)
    stream.start_stream()
    return stream, cap_sr


def main():
    threading.Thread(target=_udp_listener, daemon=True).start()
    threading.Thread(target=_housekeeping_thread, daemon=True).start()
    threading.Thread(target=_cmd_listener, daemon=True).start()
    _ensure_file_analysis()
    time.sleep(2.0)
    stream = None
    cap_sr = 0
    while True:
        if time.time() - st['udp_t'] < 5.0:
            # PRIMARY: audio streamed from TouchDesigner
            osc_send('/beat/status', 'td-audio')
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
                stream = None
            _feed_udp()
            time.sleep(0.02)
            _housekeeping()
            continue
        try:
            if stream is None:
                stream, cap_sr = _open_loopback()
                osc_send('/beat/status', 'loopback %dHz' % cap_sr)
            _housekeeping()
            time.sleep(0.2)
        except Exception as e:
            osc_send('/beat/status', 'err %s' % str(e)[:60])
            print('ERR', e, flush=True)
            stream = None
            time.sleep(2.0)


if __name__ == '__main__':
    main()
