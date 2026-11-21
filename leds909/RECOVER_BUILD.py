# LED 909 master recovery — rebuilds everything not stored in the .toe.
# Run this python file, then POST C:/Users/josep/AppData/Local/Temp/recover_all.json
# to the TD exec bridge (or re-run via: python RECOVER_BUILD.py && curl ...).
# Rebuilds: 18 fx scenes, fx_clock/fx_exec (clock+thumbs+watchdog), services
# launcher (absolute python path), auto_vj, http_cb autovj/auto fields,
# ui_stream auto field. Requires leds909/fx909/programs.json on disk.
import base64, json

FXDIR = 'C:/Users/josep/OneDrive/Escritorio/leds 909/leds909/fx909'

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
    tt = M.create(fitTOP, 'thumb_fit') if M.op('thumb_fit') is None else M.op('thumb_fit')
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

EXEC_DAT = ("def onFrameStart(dat):\n"
            "\top('/project1/mediaSwitcher/fx_clock').module.fx_tick()\n"
            "\top('/project1/mediaSwitcher/fx_clock').module.fx_thumbs()\n"
            "\ttry:\n"
            "\t\top('/project1/services/services_svc').module.svc_watch()\n"
            "\texcept Exception:\n"
            "\t\tpass\n"
            "\treturn\n")

SVC = """
# services launcher: starts/stops external python sidecars in leds 909
import subprocess, os, time

BASE = 'C:/Users/josep/OneDrive/Escritorio/leds 909'
SCRIPTS = ['jev/beat_service.py', 'jev/brain_service.py']

def _pid_file(s):
    return os.path.join(BASE, 'jev', 'svc_' + os.path.basename(s) + '.pid')

def _running(s):
    try:
        with open(_pid_file(s)) as f:
            pid = f.read().strip()
        if not pid:
            return False
        r = subprocess.run(['tasklist', '/FI', 'PID eq ' + pid],
                           capture_output=True, text=True, timeout=5)
        return str(pid) in r.stdout
    except Exception:
        return False

def _python_exe():
    import sys, os
    cands = ['C:/Users/josep/AppData/Local/Programs/Python/Python312/python.exe',
             'C:/Python312/python.exe']
    for c in cands:
        if os.path.exists(c):
            return c
    exe = sys.executable
    if exe and 'touchdesigner' not in exe.lower():
        return exe
    return 'python'

def start_all():
    op('/project1/services').store('svc_hold_until', 0.0)
    exe = _python_exe()
    started = []
    for s in SCRIPTS:
        p = os.path.join(BASE, s)
        if not os.path.exists(p) or _running(s):
            continue
        log = open(os.path.join(BASE, 'jev', 'svc_' + os.path.basename(s) + '.log'), 'w')
        proc = subprocess.Popen([exe, p], cwd=os.path.dirname(p),
                                creationflags=0x00000008 | 0x00000200,
                                close_fds=True, stdout=log, stderr=subprocess.STDOUT)
        with open(_pid_file(s), 'w') as f:
            f.write(str(proc.pid))
        started.append((os.path.basename(s), proc.pid))
    op('/project1/services').store('last_start', (time.time(), started))
    return started

def stop_all():
    for s in SCRIPTS:
        try:
            with open(_pid_file(s)) as f:
                pid = f.read().strip()
            if pid:
                subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
        except Exception:
            pass
        try:
            os.remove(_pid_file(s))
        except Exception:
            pass
    op('/project1/services').store('svc_hold_until', time.time() + 3600.0)

def svc_watch():
    M0 = op('/project1/services')
    if M0 is None:
        return
    t = time.time()
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

def status():
    return {os.path.basename(s): _running(s) for s in SCRIPTS}
"""

SVC_EXT = """
class Svc:
    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
    def onOffToOn(self, panelValue):
        try:
            mod = op('/project1/services/services_svc').module
            if self.ownerComp.name == 'btn_start':
                print('services started:', mod.start_all())
            elif self.ownerComp.name == 'btn_stop':
                mod.stop_all()
                print('services stopped')
        except Exception as e:
            print('svc button error:', repr(e))
"""

SVC_INIT = """
def onStart(engine):
    import time
    time.sleep(2.0)
    try:
        r = op('/project1/services/services_svc').module.start_all()
        print('services autostarted:', r)
    except Exception as e:
        print('autostart error:', repr(e))
    return
"""

AV_MOD = r'''
# auto_vj - unsupervised show driver: genre/mood buckets + beat/bar dwell.
import random

def _names(M):
    t = M.op('source_tbl')
    return [t[r, 1].val for r in range(1, t.numRows)]

def _bucket(AV, text):
    t = AV.op('auto_rules')
    text = (text or '').lower()
    fallback = None
    for r in range(1, t.numRows):
        pat = t[r, 0].val.strip().lower()
        scenes = [s.strip() for s in t[r, 1].val.split(',') if s.strip()]
        if pat in ('*', 'default'):
            fallback = scenes
            continue
        if any(tok.strip() and tok.strip() in text for tok in pat.split('|')):
            return scenes
    return fallback or []

def tick():
    M = op('/project1/mediaSwitcher')
    AV = op('/project1/auto_vj')
    if M is None or AV is None or not AV.par.Enabled.eval():
        return
    bo = op('/project1/audio_jev/beat_out_null')
    if bo is None:
        return
    try:
        bc = float(bo['beatcount'].eval())
        pos = int(bo['beatpos'].eval()) if bo['beatpos'] is not None else 1
    except Exception:
        return
    last = AV.fetch('av_last_beat', None)
    AV.store('av_last_beat', bc)
    if last is None or bc <= last:
        return
    if pos != 1:
        return
    minbars = max(1, int(AV.par.Minbars.eval()))
    last_change = AV.fetch('av_last_change', None)
    if last_change is not None and (bc - last_change) < minbars * 4:
        return
    A = op('/project1/audio_jev')
    genre = str(A.fetch('j_genre', '')) if A is not None else ''
    mood = str(A.fetch('j_mood', '')) if A is not None else ''
    bucket = _bucket(AV, genre + ' ' + mood)
    names = _names(M)
    cands = [s for s in bucket if s in names]
    if not cands:
        cands = [n for n in names if n.lower() != 'black']
    st = M.fetch('state', {})
    prog = int(st.get('program', 0))
    cur = names[prog] if 0 <= prog < len(names) else None
    pool = [c for c in cands if c != cur] or cands
    pick = random.choice(pool)
    idx = names.index(pick)
    M.op('c_preview').par.const0value = idx
    M.op('c_swap').par.const0value = 1.0
    M.store('swap_release', True)
    AV.store('av_last_change', bc)
    M.store('av_reason', ('%s/%s -> %s' % (genre or '?', mood or '?', pick)))
    print('auto_vj:', M.fetch('av_reason'))
    return
'''

AV_RULES = """match\tscenes
hardcore|drum and bass|dnb|happy hardcore|gabber\tEstallido, Corte, Rebote, Tunel, Vortice
techno|house|electro|trance|edm|dance\tPlasma, Flujo, Espiral, Caleidoscopio, Marea
ambient|chill|downtempo|lounge|new age\tAurora, Titileo, Brasa, Marea, Goteo
rock|metal|punk|alternative\tEstallido, Corte, Barrido, Rebote
pop|dance\tEspiral, Vortice, Tunel, Barrido, Estallido
electronic|idm|experimental\tFlujo, Caleidoscopio, Plasma, Lluvia
*\tFuego, Plasma, Aurora, Flujo, Espiral, Caleidoscopio, Titileo, Lluvia
"""

AV_EXEC = ("def onFrameStart(dat):\n"
           "\ttry:\n"
           "\t\top('/project1/auto_vj/auto_vj_mod').module.tick()\n"
           "\texcept Exception:\n"
           "\t\tpass\n"
           "\treturn\n")

HTTP_CB_LOCAL = r'''
import re, sys
p = FXDIR.replace('fx909', '')  # not used; kept for clarity
t = open(r'C:/Users/josep/AppData/Local/Temp/http_cb_now.txt', newline='').read()
# strip any previous autovj/auto remnants
t = re.sub(r"\tif cmd == 'autovj':\n(\t+.*\n)+", '', t)
t = t.replace("\t\t'auto': (op('/project1/auto_vj') is not None and op('/project1/auto_vj').par.Enabled.eval() > 0.5),", '')
t = t.replace("\t\t'auto_info': str(M.fetch('av_reason', '')),", '')
block = ("\tif cmd == 'autovj':\n"
         "\t\ttry:\n"
         "\t\t\tAV = op('/project1/auto_vj')\n"
         "\t\t\tif AV is not None:\n"
         "\t\t\t\tAV.par.Enabled.val = 1 if int(m.get('value', 0)) else 0\n"
         "\t\texcept Exception:\n"
         "\t\t\tpass\n")
anchor = "\tif cmd == 'preview':"
if anchor not in t:
    # handler may be at zero indent in some revisions
    anchor0 = "if cmd == 'preview':"
    assert anchor0 in t, 'preview anchor missing'
    t = t.replace(anchor0, block.replace('\t', '', 0) + anchor0, 1)
else:
    t = t.replace(anchor, block + anchor, 1)
mark = "\t\t'bhb': (absTime.seconds - A.fetch('beat_hb_t', -1e9)) < 5.0,"
assert mark in t, 'bhb anchor missing'
t = t.replace(mark, mark + "\n\t\t'auto': (op('/project1/auto_vj') is not None and op('/project1/auto_vj').par.Enabled.eval() > 0.5),\n\t\t'auto_info': str(M.fetch('av_reason', '')),", 1)
compile(t, 'h', 'exec')
open(r'C:/Users/josep/AppData/Local/Temp/http_cb_fixed.txt', 'w', newline='').write(t)
print('http_cb patched locally')
'''

UI_LOCAL = r'''
t = open(r'C:/Users/josep/AppData/Local/Temp/ui_stream_now.txt', newline='').read()
if "'auto':" not in t:
    mark = "\t\t'bhb': (absTime.seconds - A.fetch('beat_hb_t', -1e9)) < 5.0,"
    assert mark in t, 'bhb anchor missing in ui_stream'
    t = t.replace(mark, mark + "\n\t\t'auto': (op('/project1/auto_vj') is not None and op('/project1/auto_vj').par.Enabled.eval() > 0.5),\n\t\t'auto_info': str(M.fetch('av_reason', '')),", 1)
compile(t, 'u', 'exec')
open(r'C:/Users/josep/AppData/Local/Temp/ui_stream_fixed.txt', 'w', newline='').write(t)
print('ui_stream patched locally')
'''

# ---------- TD payload ----------
script = ("import base64, json\n"
          "P=op('/project1')\n"
          "M=op('/project1/mediaSwitcher')\n"
          # 1) services launcher
          "svc=P.op('services')\n"
          "if svc is not None:\n"
          "    svc.destroy()\n"
          "svc=P.create(baseCOMP,'services')\n"
          "svc.nodeX=-300; svc.nodeY=600\n"
          "svc.color=[0.3,0.5,0.3]\n"
          "m0=svc.create(textDAT,'services_svc'); m0.text=base64.b64decode('%s').decode()\n"
          "e0=svc.create(textDAT,'svc_ext'); e0.text=base64.b64decode('%s').decode()\n"
          "bs=svc.create(buttonCOMP,'btn_start'); bs.par.label.val='START SERVICES'\n"
          "bs.par.ext0object.val=e0.path; bs.par.ext0name.val='Svc'\n"
          "bp=svc.create(buttonCOMP,'btn_stop'); bp.par.label.val='STOP'; bp.nodeX=220\n"
          "bp.par.ext0object.val=e0.path; bp.par.ext0name.val='Svc'\n"
          "i0=svc.create(executeDAT,'svc_init'); i0.text=base64.b64decode('%s').decode()\n"
          # 2) fx builder + scenes
          "b=M.op('fx_builder')\n"
          "if b is None:\n"
          "    b=M.create(textDAT,'fx_builder')\n"
          "bd=open(r'%s/builder.py').read()\n"
          "B=bd[bd.index(chr(39)*3, bd.index('BUILDER = '+chr(39)*3)+11)+0:]\n"  # placeholder, fixed below
          )
# builder extraction is fragile; do it here instead:
bd = open(FXDIR + '/builder.py').read()
i = bd.index("BUILDER = '''") + len("BUILDER = '''")
j = bd.index("'''", i)
BUILDER_DAT = bd[i:j]

script = ("import base64, json\n"
          "P=op('/project1')\n"
          "M=op('/project1/mediaSwitcher')\n"
          "svc=P.op('services')\n"
          "if svc is not None:\n"
          "    svc.destroy()\n"
          "svc=P.create(baseCOMP,'services')\n"
          "svc.nodeX=-300; svc.nodeY=600\n"
          "svc.color=[0.3,0.5,0.3]\n"
          "m0=svc.create(textDAT,'services_svc'); m0.text=base64.b64decode('%s').decode()\n"
          "e0=svc.create(textDAT,'svc_ext'); e0.text=base64.b64decode('%s').decode()\n"
          "bs=svc.create(buttonCOMP,'btn_start'); bs.par.label.val='START SERVICES'\n"
          "bs.par.ext0object.val=e0.path; bs.par.ext0name.val='Svc'\n"
          "bp=svc.create(buttonCOMP,'btn_stop'); bp.par.label.val='STOP'; bp.nodeX=220\n"
          "bp.par.ext0object.val=e0.path; bp.par.ext0name.val='Svc'\n"
          "i0=svc.create(executeDAT,'svc_init'); i0.text=base64.b64decode('%s').decode()\n"
          "b=M.op('fx_builder')\n"
          "if b is None:\n"
          "    b=M.create(textDAT,'fx_builder')\n"
          "b.text=base64.b64decode('%s').decode()\n"
          "progs=json.loads(open(r'%s/programs.json','rb').read().decode())\n"
          "g={'op':op,'json':json,'baseCOMP':baseCOMP,'textDAT':textDAT,'glslTOP':glslTOP,'nullTOP':nullTOP}\n"
          "exec(compile(b.text,'builder','exec'), g)\n"
          "made=g['build_all'](json.dumps(progs))\n"
          "ov=M.fetch('scene_disp', {})\n"
          "for d in progs['progs']:\n"
          "    ov['/project1/mediaSwitcher/scenes/fx_' + d['id'] + '/out1'] = d['name']\n"
          "M.store('scene_disp', ov)\n"
          "M.op('scenes_sync').module.rebuild(M)\n"
          "c=M.op('fx_clock')\n"
          "if c is None:\n"
          "    c=M.create(textDAT,'fx_clock')\n"
          "c.text=base64.b64decode('%s').decode()\n"
          "e=M.op('fx_exec')\n"
          "if e is None:\n"
          "    e=M.create(executeDAT,'fx_exec')\n"
          "e.text=base64.b64decode('%s').decode()\n"
          "e.par.framestart.val=True\n"
          "AV=P.op('auto_vj')\n"
          "if AV is not None:\n"
          "    AV.destroy()\n"
          "AV=P.create(baseCOMP,'auto_vj')\n"
          "AV.nodeX=-300; AV.nodeY=900\n"
          "AV.color=[0.5,0.4,0.2]\n"
          "pg=AV.appendCustomPage('Auto VJ')\n"
          "pg.appendPar('Enabled', label='Enabled')\n"
          "AV.par.Enabled.val=0; AV.par.Enabled.min=0; AV.par.Enabled.max=1\n"
          "pg.appendPar('Minbars', label='Min Dwell (bars)')\n"
          "AV.par.Minbars.val=8; AV.par.Minbars.min=1; AV.par.Minbars.max=64\n"
          "am=AV.create(textDAT,'auto_vj_mod'); am.text=base64.b64decode('%s').decode()\n"
          "ar=AV.create(tableDAT,'auto_rules'); ar.text=base64.b64decode('%s').decode()\n"
          "ae=AV.create(executeDAT,'auto_exec'); ae.text=base64.b64decode('%s').decode(); ae.par.framestart.val=True\n"
          # export + note for local http_cb/ui patching (done by caller)
          "open(r'C:/Users/josep/AppData/Local/Temp/http_cb_now.txt','w',newline='').write(M.op('http_cb').text)\n"
          "open(r'C:/Users/josep/AppData/Local/Temp/ui_stream_now.txt','w',newline='').write(M.op('ui_stream').text)\n"
          "exec(compile(op('/project1/services/services_svc').text,'s','exec'),{'op':op})\n"
          "print('recovered. scenes:', len(made), 'services:', op('/project1/services/services_svc').module.start_all())"
          % (base64.b64encode(SVC.encode()).decode(),
             base64.b64encode(SVC_EXT.encode()).decode(),
             base64.b64encode(SVC_INIT.encode()).decode(),
             base64.b64encode(BUILDER_DAT.encode()).decode(),
             FXDIR,
             base64.b64encode(CLOCK.encode()).decode(),
             base64.b64encode(EXEC_DAT.encode()).decode(),
             base64.b64encode(AV_MOD.encode()).decode(),
             base64.b64encode(AV_RULES.encode()).decode(),
             base64.b64encode(AV_EXEC.encode()).decode()))

json.dump({"script": script}, open(r'C:/Users/josep/AppData/Local/Temp/recover_all.json', 'w'))
open(r'C:/Users/josep/AppData/Local/Temp/http_local.py', 'w').write(HTTP_CB_LOCAL)
open(r'C:/Users/josep/AppData/Local/Temp/ui_local.py', 'w').write(UI_LOCAL)
print('recover payload ready')
