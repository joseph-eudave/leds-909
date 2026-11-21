import os as _os, tempfile as _tf
TEMP = _tf.gettempdir().replace(chr(92), '/')
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))

import base64, json

BASE = ROOT

SVC = """
# services launcher: starts/stops external python sidecars in leds 909
# Duplicate protection: PID file per script + tasklist liveness check.
import subprocess, os, socket, time

BASE = __BASE__
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
    import sys
    exe = sys.executable
    if exe and 'touchdesigner' not in exe.lower():
        return exe
    return 'python'

def start_all():
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

def status():
    return {os.path.basename(s): _running(s) for s in SCRIPTS}
""".replace('__BASE__', repr(BASE))

EXT = """
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

INIT = """
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

script = ("import base64\n"
          "P=op('/project1')\n"
          "svc=P.op('services')\n"
          "if svc is not None:\n"
          "    svc.destroy()\n"
          "svc=P.create(baseCOMP,'services')\n"
          "svc.nodeX=-300; svc.nodeY=600\n"
          "svc.color=[0.3,0.5,0.3]\n"
          "m=svc.create(textDAT,'services_svc')\n"
          "m.text=base64.b64decode('%s').decode()\n"
          "e=svc.create(textDAT,'svc_ext')\n"
          "e.text=base64.b64decode('%s').decode()\n"
          "bs=svc.create(buttonCOMP,'btn_start')\n"
          "bs.par.label.val='START SERVICES'\n"
          "bs.par.ext0object.val=e.path\n"
          "bs.par.ext0name.val='Svc'\n"
          "bp=svc.create(buttonCOMP,'btn_stop')\n"
          "bp.par.label.val='STOP'\n"
          "bp.nodeX=220\n"
          "bp.par.ext0object.val=e.path\n"
          "bp.par.ext0name.val='Svc'\n"
          "ie=svc.create(executeDAT,'svc_init')\n"
          "ie.text=base64.b64decode('%s').decode()\n"
          "exec(compile(m.text,'s','exec'),{'op':op})\n"
          "print('built; start:', op('/project1/services/services_svc').module.start_all())\n"
          "print('status:', op('/project1/services/services_svc').module.status())"
          % (base64.b64encode(SVC.encode()).decode(),
             base64.b64encode(EXT.encode()).decode(),
             base64.b64encode(INIT.encode()).decode()))

json.dump({"script": script}, open(_os.path.join(_tf.gettempdir(), 'svc4.json'), 'w'))
print('payload ok')
