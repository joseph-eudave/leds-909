# REMOVE_RAVE — run when TouchDesigner is open (finishes the RAVE removal).
#   python leds909/REMOVE_RAVE.py
#   curl -s -X POST http://127.0.0.1:9981/api/td/server/exec \
#     -H "Content-Type: application/json" --data-binary @C:/Users/josep/AppData/Local/Temp/rm_rave.json
import json

script = r'''
# 1) launcher: drop rave_service entry
svc = op('/project1/services/services_svc')
t = svc.text
t = t.replace("SCRIPTS = ['jev/beat_service.py', 'jev/brain_service.py', 'jev/rave_service.py']",
              "SCRIPTS = ['jev/beat_service.py', 'jev/brain_service.py']")
t = t.replace(", 'jev/rave_service.py': 7012", "")
svc.text = t
compile(t, 's', 'exec')

# 2) kill the running rave process (by pid file) if any
import subprocess, os, time
BASE = 'C:/Users/josep/OneDrive/Escritorio/leds 909'
pf = os.path.join(BASE, 'jev', 'svc_rave_service.py.pid')
if os.path.exists(pf):
    pid = open(pf).read().strip()
    if pid:
        subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
    os.remove(pf)

# 3) beat_send_cb: remove the 7011 fan-out
import re
cb = op('/project1/audio_jev/beat_send_cb')
ct = cb.text
ct = ct.replace('PORT = 7010' + chr(10) + 'PORT_RAVE = 7011  # rave_service tap', 'PORT = 7010')
ct = re.sub(r'[ \t]*try:[ \t]*\n[ \t]*s\.sendto\(bytes\(buf\), \(\'127\.0\.0\.1\', PORT_RAVE\)\)[ \t]*\n[ \t]*except Exception:[ \t]*\n[ \t]*pass[ \t]*\n', chr(10), ct)
ct = ct.replace(chr(10) + chr(10) + chr(10) + chr(10), chr(10) + chr(10))
cb.text = ct
compile(cb.text, 'cb', 'exec')
print('fan-out removed:', 'PORT_RAVE' not in cb.text)

# 4) beat model switch back to 0-2
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
print('beat model 0-2 only:', 'rave' not in m.text)

# 5) leave rave_out CHOP + /rave osc handlers in place (inert: uRvel
#    expression reads rave_out which outputs zeros once the service is gone).
# restart services without rave
mod = svc.module
mod.stop_all()
time.sleep(0.5)
mod.start_all()
time.sleep(6)
print('services:', mod.status())
print('RAVE removal complete')
'''
json.dump({"script": script}, open(r'C:/Users/josep/AppData/Local/Temp/rm_rave.json', 'w'))
print('payload ready at C:/Users/josep/AppData/Local/Temp/rm_rave.json')
