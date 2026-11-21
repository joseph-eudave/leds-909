# WLED effect ports for TouchDesigner

Template per effect = scene COMP in /project1/mediaSwitcher/scenes:
  <name>_glsl (text DAT shader) -> fire_sim glslTOP (pixeldat par)
  heat/state buffer in a feedbackTOP loop (rgba8fixed, 512x288)
  colorize: <name>_keys table (pos r g b a) -> rampTOP -> lookupTOP(method=secondinput)
  custom par page on the scene base; uniforms via glslTOP vec blocks
  (vec{i}name + vec{i}valuex, expression-bound to parent pars)

## TD quirks discovered (2025.x GLSL TOP)
- glslTOP: shader DAT goes in `pixeldat` (not glsl1). `const` blocks are
  SPECIALIZATION constants (compile-time, no expressions) - use `vec` blocks
  for runtime uniforms (1 component: vec{i}valuex).
- Sequence/count pars (vec, const) respond to .val=N but report 0 immediately;
  member pars vec{i}name appear after the next cook.
- Par expressions are Python: no clamp()/mix(); use min(max(x,0),1).
  Channel refs like op('x')['chan'] fail inside par expressions - drive those
  uniforms from a textDAT onFrameStart callback (see fire_exec) or CHOP export.
- appendPar(name, label=...) only; set default/min/max/clamp via par properties
  afterwards. No menu style via appendPar - use float 0/1.
- ar hook: selectCHOP with chops EXPRESSION parent(3).op('ar_null') (.val no-ops).

## fire2012 (WLED FX 66)
- Faithful port of wled00/FX.cpp mode_fire_2012: cool -> diffuse up
  (h[k]=(h[k-1]+2h[k-2])/3) -> spark in ignition zone -> heat->palette.
- WLED slider map: Cooling=speed, Spark rate=intensity, Boost=custom3.
  2D Blur (custom2) not ported (per-column strips are already independent).
- Palette = lava_gp (fire_keys); edit the table to change colors.
- GPU-parallel adaptation: WLED sparks once per strip per 32ms tick at random
  y; we spark per-pixel with probability sparkP/ign so the expected spark
  count per column per tick matches.
