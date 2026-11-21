import base64, json

CLOCK = '''
def fx_tick():
    M = op('/project1/mediaSwitcher')
    bo = op('/project1/audio_jev/beat_out_null')
    t = absTime.seconds
    beat = 0.0; phase = 0.0; bpm = 0.0
    if bo is not None:
        try:
            bc = bo['beatcount']; bp = bo['beatpos']; bb = bo['bpm']
            if bc is not None: beat = float(bc.eval())
            if bp is not None: phase = float(bp.eval())
            if bb is not None: bpm = float(bb.eval())
        except Exception:
            pass
    if bpm <= 0.0:
        bpm = 120.0
        beats = t * 2.0
        beat = float(int(beats) % 4096)
        phase = beats - int(beats)
    bass = 0.0; mid = 0.0; high = 0.0
    ar = M.op('ar_null')
    if ar is not None:
        try:
            for nm in ('bass', 'mid', 'high'):
                c = ar[nm]
                if c is not None:
                    v = min(max(float(c.eval()), 0.0), 1.0)
                    if nm == 'bass': bass = v
                    elif nm == 'mid': mid = v
                    else: high = v
        except Exception:
            pass
    vals = {'uFxTime': t, 'uBeat': beat, 'uBeatPhase': phase, 'uBpm': bpm,
            'uBass': bass, 'uMid': mid, 'uHigh': high}
    for s in M.op('scenes').children:
        m = s.fetch('fx_ctx', None)
        if m is None:
            continue
        g = s.op('fx')
        if g is None:
            continue
        for nm, i in m.items():
            try:
                p = g.par['vec%dvaluex' % i]
                if p is not None:
                    p.val = vals[nm]
            except Exception:
                pass
    return


def fx_thumbs():
    import base64 as _b
    M = op('/project1/mediaSwitcher')
    ws = M.op('webserver1')
    if ws is None:
        return
    clients = ws.webSocketConnections
    if not clients:
        return
    if absTime.seconds - M.fetch('thumb_t', -1e9) < 0.12:
        return
    M.store('thumb_t', absTime.seconds)
    tt = M.op('thumb_fit')
    if tt is None:
        tt = M.create(fitTOP, 'thumb_fit')
        tt.par.outputresolution.val = 'custom'
        tt.par.resolutionw.val = 96
        tt.par.resolutionh.val = 54
        tt.par.resmult.val = False
    st = M.op('source_tbl')
    rows = [st[r, 0].val for r in range(1, st.numRows)]
    idx = M.fetch('thumb_i', 0)
    if idx >= len(rows):
        idx = 0
    M.store('thumb_i', idx + 1)
    src = op(rows[idx])
    if src is None:
        return
    tt.inputConnectors[0].connect(src)
    try:
        tt.save('C:/Users/josep/AppData/Local/Temp/msw_thumb.jpg')
        with open('C:/Users/josep/AppData/Local/Temp/msw_thumb.jpg', 'rb') as f:
            d = 'data:image/jpeg;base64,' + _b.b64encode(f.read()).decode()
    except Exception:
        return
    msg = '{"type": "thumb", "i": %d, "d": "%s"}' % (idx, d)
    for cl in clients:
        try:
            ws.webSocketSendText(cl, msg)
        except Exception:
            pass
    return
'''

EXEC = ("def onFrameStart(dat):\n"
        "\top('/project1/mediaSwitcher/fx_clock').module.fx_tick()\n"
        "\top('/project1/mediaSwitcher/fx_clock').module.fx_thumbs()\n"
        "\ttry:\n"
        "\t\top('/project1/services/services_svc').module.svc_watch()\n"
        "\texcept Exception:\n"
        "\t\tpass\n"
        "\treturn\n")

WATCH = """

def svc_watch():
    M0 = op('/project1/services')
    if M0 is None:
        return
    t = __import__('time').time()
    if t - M0.fetch('svc_check_t', -1e9) < 30.0:
        return
    M0.store('svc_check_t', t)
    if t < M0.fetch('svc_hold_until', -1e9):
        return
    dead = [s for s in SCRIPTS if not _running(s)]
    if dead:
        started = start_all()
        if started:
            print('svc watchdog restarted:', started)
    return
"""

HOLD = """
    import time as _t
    op('/project1/services').store('svc_hold_until', _t.time() + 3600.0)
"""

script = ("import base64\n"
          "M=op('/project1/mediaSwitcher')\n"
          "c=M.op('fx_clock')\n"
          "if c is None:\n"
          "    c=M.create(textDAT,'fx_clock')\n"
          "c.text=base64.b64decode('%s').decode()\n"
          "e=M.op('fx_exec')\n"
          "if e is None:\n"
          "    e=M.create(executeDAT,'fx_exec')\n"
          "e.text=base64.b64decode('%s').decode()\n"
          "e.par.framestart.val=True\n"
          "m=op('/project1/services/services_svc')\n"
          "if 'svc_watch' not in m.text:\n"
          "    t=m.text+base64.b64decode('%s').decode()\n"
          "    i=t.index('def status():')\n"
          "    t=t[:i]+base64.b64decode('%s').decode()+chr(10)+t[i:]\n"
          "    t=t.replace('    started = []', \"    op('/project1/services').store('svc_hold_until', 0.0)\\n    started = []\")\n"
          "    m.text=t\n"
          "compile(m.text,'m','exec')\n"
          "compile(e.text,'e','exec')\n"
          "print('clock/exec/watch restored')\n"
          # run one tick to verify + set auto exec framestart
          "op('/project1/auto_vj/auto_exec').par.framestart.val=True\n"
          "print('auto_exec framestart on')"
          % (base64.b64encode(CLOCK.encode()).decode(),
             base64.b64encode(EXEC.encode()).decode(),
             base64.b64encode(WATCH.encode()).decode(),
             base64.b64encode(HOLD.encode()).decode()))

json.dump({"script": script}, open(r'C:/Users/josep/AppData/Local/Temp/reinfra.json', 'w'))
print('ok')
