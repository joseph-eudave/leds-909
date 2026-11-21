
M = op('/project1/mediaSwitcher')
sc = M.op('scenes')
b = sc.op('sc_fire')
if b is not None:
    b.destroy()
b = sc.create(baseCOMP, 'sc_fire')
b.nodeX = -1200
b.nodeY = 800

fb = b.create(feedbackTOP, 'fire_fb')
fb.par.outputresolution.val = 'custom'
fb.par.resolutionw.val = 512; fb.par.resolutionh.val = 288
fb.par.resmult.val = False
fb.par.format.val = 'rgba8fixed'
glsl = b.create(glslTOP, 'fire_sim')
glsl.par.outputresolution.val = 'custom'
glsl.par.resolutionw.val = 512; glsl.par.resolutionh.val = 288
glsl.par.resmult.val = False
glsl.par.format.val = 'rgba8fixed'
sh = b.create(textDAT, 'fire_glsl')
sh.text = __SHADER__
glsl.par.pixeldat.val = sh.path
hn = b.create(nullTOP, 'heat_null')
hn.inputConnectors[0].connect(glsl)
fb.inputConnectors[0].connect(hn)
glsl.inputConnectors[0].connect(fb)

kt = b.create(tableDAT, 'fire_keys')
kt.text = __KEYS__
ramp = b.create(rampTOP, 'fire_ramp')
ramp.par.dat.val = kt.path
lk = b.create(lookupTOP, 'fire_color')
lk.par.method.val = 'secondinput'
lk.inputConnectors[0].connect(hn)
lk.inputConnectors[1].connect(ramp)
lev = b.create(levelTOP, 'fire_level')
lev.inputConnectors[0].connect(lk)
lev.par.opacity.expr = "op('" + b.path + "').par.Brightness"
fl = b.create(flipTOP, 'fire_flip')
fl.inputConnectors[0].connect(lev)
fl.par.flipy.expr = "op('" + b.path + "').par.Direction > 0.5"
o1 = b.create(nullTOP, 'out1')
o1.inputConnectors[0].connect(fl)

ar = b.create(selectCHOP, 'ar_sel')
ar.par.chops.val = "parent(3).op('ar_null')"
ar.par.channames.val = 'bass mid high'

pg = b.appendCustomPage('Fire')
def apar(name, label, dflt, mn, mx):
    try:
        pg.appendPar(name, label=label)
        p = b.par[name]
        p.default = dflt
        p.min = mn
        p.max = mx
        p.normMin = mn
        p.normMax = mx
        p.clampMin = True
        p.clampMax = True
        p.val = dflt
    except Exception as e:
        print('par err', name, repr(e))
apar('Cooling', 'Cooling', 64, 0, 255)
apar('Sparkrate', 'Spark rate', 160, 0, 255)
apar('Boost', 'Boost', 0, 0, 255)
apar('Simspeed', 'Sim speed', 1.0, 0.0, 4.0)
apar('Scale', 'Scale', 1.0, 0.1, 4.0)
apar('Direction', 'Direction', 0, 0, 1)
apar('Brightness', 'Brightness', 1.0, 0.0, 1.0)
apar('Arspark', 'AR Spark', 0.0, 0.0, 1.0)
apar('Arboost', 'AR Boost', 0.0, 0.0, 1.0)
b.par.Direction.help = '0 = flames up, 1 = flames down'

B = b.path
# uniforms via vec blocks (vec0name/vec0valuex ...), values bound by expression
consts = [
    ('uCool', "op('" + B + "').par.Cooling"),
    ('uSpark', "op('" + B + "').par.Sparkrate"),
    ('uBoost', "op('" + B + "').par.Boost"),
    ('uSpeed', "op('" + B + "').par.Simspeed"),
    ('uScale', "op('" + B + "').par.Scale"),
    ('uSeed', 'me.time.frames'),
    ('uBass', "clamp(op('" + B + "/ar_sel')['bass'], 0, 1)"),
    ('uARSpark', "op('" + B + "').par.Arspark"),
    ('uARBoost', "op('" + B + "').par.Arboost"),
]
for i, (nm, ex) in enumerate(consts):
    try:
        glsl.par['vec%dname' % i].val = nm
        glsl.par['vec%dvaluex' % i].expr = ex
    except Exception as e:
        print('vec', i, nm, 'err', repr(e))
print('uniform vecs set')
print('sc_fire built')
