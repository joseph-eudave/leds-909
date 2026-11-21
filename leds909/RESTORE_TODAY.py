# RESTORE_TODAY — one-shot TD-side restore after the 2026-11-20 crash.
# Run when TouchDesigner is open:
#   python "C:\Users\josep\OneDrive\Escritorio\leds 909\leds909\RESTORE_TODAY.py"
#   curl -s -X POST http://127.0.0.1:9981/api/td/server/exec \
#     -H "Content-Type: application/json" --data-binary @C:/Users/josep/AppData/Local/Temp/restore_today.json
# Re-applies (in RAM until you SAVE in TD):
#   1. RAVE removal (launcher, beatmodel 0-2, clean beat_send_cb)
#   2. webserver port 9090 (8080 is taken by TD's CEF debugger + steamwebhelper)
#   3. webrtc track list with grid (correct tuple syntax)
#   4. thumb_grid recreated FRESH (setInputs only works at creation) + vso_grid
#   5. fx_clock grid-rewire hook
# NOTE: never grow layout TOP inputs one-by-one via inputConnectors — that
# hung/crashed TD on 2026-11-20. Create the node fresh and setInputs once.
import base64, json

SCRIPT = r'''
import base64, time

# ---------- 1) RAVE removal ----------
svc = op('/project1/services/services_svc')
t = svc.text
t = t.replace("SCRIPTS = ['jev/beat_service.py', 'jev/brain_service.py', 'jev/rave_service.py']",
              "SCRIPTS = ['jev/beat_service.py', 'jev/brain_service.py']")
t = t.replace(", 'jev/rave_service.py': 7012", "")
svc.text = t

import subprocess, os
BASE = 'C:/Users/josep/OneDrive/Escritorio/leds 909'
pf = os.path.join(BASE, 'jev', 'svc_rave_service.py.pid')
if os.path.exists(pf):
    pid = open(pf).read().strip()
    if pid:
        subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
    os.remove(pf)

CB = """# beat_send - stream TD audio to beat_service.py (UDP 7010).
# Module-global socket cache (never operator storage - sockets cannot be
# pickled into the .toe).
import socket
import struct as _st

PORT = 7010
_sock = [None]


def onCook(scriptOp):
    scriptOp.clear()
    A = parent()
    if _sock[0] is None:
        _sock[0] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s = _sock[0]
    src = scriptOp.inputs[0] if scriptOp.inputs else None
    if src is not None and src.numSamples:
        ch = src.chan(0)
        if ch is not None:
            n = src.numSamples
            buf = bytearray(4 * n)
            for i in range(n):
                v = ch[i]
                v = 0.0 if v is None else float(v)
                buf[4*i:4*i+4] = _st.pack('<f', v)
            try:
                s.sendto(bytes(buf), ('127.0.0.1', PORT))
                A.store('beat_sent', A.fetch('beat_sent', 0) + n)
            except Exception:
                pass
    return
"""
cb = op('/project1/audio_jev/beat_send_cb')
cb.text = base64.b64decode('CB_B64').decode()
compile(cb.text, 'cb', 'exec')

A = op('/project1/audio_jev')
bm = A.par['Beatmodel']
if bm is not None:
    bm.val = min(bm.eval(), 2)
    bm.max = 2
    bm.normMax = 2
m = A.op('beat_cmd')
mt = m.text
mt = mt.replace(", 3: 'rave'", "")
m.text = mt

# ---------- 2) webserver port ----------
ws = op('/project1/mediaSwitcher/webserver1')
ws.par.port.val = 9090

# ---------- 3) http_cb track list with grid (line-exact fix) ----------
h = op('/project1/mediaSwitcher/http_cb')
ht = h.text
if "'grid'" not in ht:
    lines = ht.split(chr(10))
    for i, L in enumerate(lines):
        if "('vso_mprog', 'mprog'), ('vso_mprev', 'mprev')" in L and L.rstrip().endswith('),'):
            lines[i] = L.rstrip()[:-1] + ','
            lines.insert(i + 1, "\t\t\t                  ('vso_grid', 'grid')):")
            break
    ht = chr(10).join(lines)
    h.text = ht
compile(h.text, 'h', 'exec')

# ---------- 4) thumb_grid FRESH + vso_grid ----------
M = op('/project1/mediaSwitcher')
old = M.op('thumb_grid')
if old is not None:
    old.destroy()
g = M.create(layoutTOP, 'thumb_grid')
st_ = M.op('source_tbl')
rows = [st_[r, 0].val for r in range(1, st_.numRows)]
srcs = [op(p) for p in rows if op(p) is not None]
try:
    g.par.align.val = 'gridrows'
    g.par.maxcols.val = 6
    g.par.fit.val = 'fill'
except Exception:
    pass
g.par.outputresolution.val = 'custom'
g.par.resolutionw.val = 1080
g.par.resolutionh.val = 608
g.par.resmult.val = False
g.setInputs(srcs)
g.nodeX = 1300; g.nodeY = 900

if M.op('vso_grid') is None:
    M.create(videostreamoutTOP, 'vso_grid')
v = M.op('vso_grid')
v.inputConnectors[0].connect(g)
v.nodeX = 1500; v.nodeY = 900
g.cook(force=True)
print('grid:', g.width, 'x', g.height, 'inputs:', sum(len(ic.connections) for ic in g.inputConnectors))

# ---------- 5) fx_clock hook ----------
c = M.op('fx_clock')
ct = c.text
if 'thumb_grid' not in ct:
    hook = """    # keep the all-scenes grid composite wired to the current sources
    try:
        nsrc = len(rows)
        if nsrc and nsrc != M.fetch('grid_n', -1):
            M.store('grid_n', nsrc)
            tg = M.op('thumb_grid')
            if tg is not None:
                tg.setInputs([op(p) for p in rows if op(p) is not None])
    except Exception:
        pass
"""
    a2 = "    M.store('thumb_i', idx + 1)\n"
    ct = ct.replace(a2, a2 + hook, 1)
    c.text = ct
compile(ct, 'c', 'exec')

# ---------- restart services ----------
mod = svc.module
mod.stop_all()
time.sleep(0.5)
mod.start_all()
time.sleep(6)
print('services:', mod.status())
print('RESTORE_TODAY complete — SAVE THE PROJECT in TD now.')
'''.replace('CB_B64', base64.b64encode(CB.encode()).decode())

json.dump({"script": SCRIPT}, open(r'C:/Users/josep/AppData/Local/Temp/restore_today.json', 'w'))
print('payload ready: C:/Users/josep/AppData/Local/Temp/restore_today.json')
