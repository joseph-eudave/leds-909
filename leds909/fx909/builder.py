# TD-side: install fx builder module + beat clock, then build all scenes from fx_progs.json
# (this python runs INSIDE TouchDesigner via the exec bridge)
import json

progs = json.loads(__import__('base64').b64decode(PROGS_B64).decode())

M = op('/project1/mediaSwitcher')
sc = M.op('scenes')

# ---------- builder module (stored as a DAT so it can rebuild later) ----------
BUILDER = '''
import json

def build_all(defs_json):
    M = op('/project1/mediaSwitcher')
    sc = M.op('scenes')
    defs = json.loads(defs_json)
    made = []
    for d in defs['progs']:
        made.append(build_one(sc, d))
    return made

def build_one(sc, d):
    M = op('/project1/mediaSwitcher')
    name = 'fx_' + d['id']
    b = sc.op(name)
    if b is not None:
        b.destroy()
    b = sc.create(baseCOMP, name)
    b.nodeX = -1200
    b.nodeY = 1600
    sh = b.create(textDAT, 'fx_glsl')
    sh.text = d['glsl']
    g = b.create(glslTOP, 'fx')
    g.par.outputresolution.val = 'custom'
    g.par.resolutionw.val = 512
    g.par.resolutionh.val = 288
    g.par.resmult.val = False
    g.par.format.val = 'rgba8fixed'
    g.par.pixeldat.val = sh.path
    o1 = b.create(nullTOP, 'out1')
    o1.inputConnectors[0].connect(g)

    pg = b.appendCustomPage('FX')
    def apar(nm, label, dflt, mn, mx):
        nm = nm.capitalize()
        pg.appendPar(nm, label=label)
        p = b.par[nm]
        p.default = dflt; p.min = mn; p.max = mx
        p.normMin = mn; p.normMax = mx
        p.clampMin = True; p.clampMax = True
        p.val = dflt
    for (nm, label, dflt, mn, mx) in d['params']:
        apar(nm, label, dflt, mn, mx)
    ca, cb = d['colA'], d['colB']
    for i, c in enumerate('RGB'):
        apar('Cola' + c.lower(), 'Color A ' + c, ca[i], 0.0, 1.0)
    for i, c in enumerate('RGB'):
        apar('Colb' + c.lower(), 'Color B ' + c, cb[i], 0.0, 1.0)

    B = b.path
    vecs = []
    for (nm, label, dflt, mn, mx) in d['params']:
        vecs.append(('u' + nm.capitalize(), "op('" + B + "').par." + nm.capitalize()))
    # colors: two vec3 uniforms, components expression-bound
    vecs.append(('uColA', None))   # handled specially
    vecs.append(('uColB', None))
    ctx = ['uFxTime', 'uBeat', 'uBeatPhase', 'uBpm']
    names = [v[0] for v in vecs] + ctx
    total = len(names)
    try:
        g.par.vec.val = total
    except Exception:
        pass
    g.cook(force=True)
    idx = 0
    for (uname, expr) in vecs:
        if uname == 'uColA':
            comps = ['Colar', 'Colag', 'Colab']
        elif uname == 'uColB':
            comps = ['Colbr', 'Colbg', 'Colbb']
        else:
            comps = None
        g.par['vec%dname' % idx].val = uname
        if comps:
            for ci, cn in enumerate(comps):
                g.par['vec%dvalue%s' % (idx, 'xyz'[ci])].expr = "op('" + B + "').par." + cn.capitalize()
        else:
            g.par['vec%dvaluex' % idx].expr = expr
        idx += 1
    for cn in ctx:
        g.par['vec%dname' % idx].val = cn
        g.par['vec%dvaluex' % idx].val = 0.0
        idx += 1
    b.store('fx_ctx', dict(zip(ctx, [len(vecs) + i for i in range(4)])))
    b.store('fx_def', d)
    return name
'''

bdat = M.op('fx_builder')
if bdat is None:
    bdat = M.create(textDAT, 'fx_builder')
bdat.text = BUILDER

# ---------- beat clock driver ----------
CLOCK = '''
def onFrameStart(dat):
    M = op('/project1/mediaSwitcher')
    bo = op('/project1/audio_jev/beat_out_null')
    t = absTime.seconds
    beat = 0.0; phase = 0.0; bpm = 120.0
    if bo is not None:
        try:
            bc = bo['beatcount']; bp = bo['beatpos']; bb = bo['bpm']
            if bc is not None: beat = float(bc.eval())
            if bp is not None: phase = float(bp.eval())
            if bb is not None: bpm = float(bb.eval())
        except Exception:
            pass
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
                    p.val = t if nm == 'uTime' else (beat if nm == 'uBeat' else (phase if nm == 'uBeatPhase' else bpm))
            except Exception:
                pass
    return
'''
cdat = M.op('fx_clock')
if cdat is None:
    cdat = M.create(textDAT, 'fx_clock')
cdat.text = CLOCK

# check beat_out channels exist
bo = op('/project1/audio_jev/beat_out_null')
if bo is not None:
    print('beat_out chans:', [c.name for c in bo.chans()])
else:
    print('WARNING: beat_out_null missing')

# ---------- build all scenes ----------
g = {'op': op, 'json': json, 'baseCOMP': baseCOMP, 'textDAT': textDAT, 'glslTOP': glslTOP, 'nullTOP': nullTOP}
exec(compile(bdat.text, 'builder', 'exec'), g)
made = g['build_all'](json.dumps(progs))
print('built:', made)

# display names
ov = M.fetch('scene_disp', {})
for d in progs['progs']:
    ov['/project1/mediaSwitcher/scenes/fx_%s/out1' % d['id']] = d['name']
M.store('scene_disp', ov)
try:
    M.op('scenes_sync').module.rebuild(M)
except Exception as e:
    print('sync err', repr(e))
print('done')
