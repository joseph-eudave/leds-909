# LED 909 — Handoff notes

## Zone gizmo textures in popViewer (final, verified 2026-11-13)

Constraint: popViewer renders ONE global texture (its `Texture` par) onto all
displayed POPs via per-point `Tex` uvs. Per-point `color` is NOT reliable on the
gizmo boxes (works on the dense Panel grids, not on sparse boxes).

Working implementation (atlas routing):
- `ztex{i}` → `zatlas{i}` (fitTOP, 256x256, fillmode=fill) → `ztex_atlas`
  (layoutTOP, align=verttb, fit=nativeres, custom res 256 x 256*N).
- popViewer `Texture` = `/project1/leds909/ztex_atlas`.
- Per zone inside the gizmo: box(attribute3 ← box directly) → zone1_lookup1
  (samples ztex{i} via fit ← topin ← COMP input0, writes point 'color') →
  `uvband` (rerangePOP) → xf → out2.
- `uvband` remaps Tex.i01 from [0,1] to [(i-1)/N, i/N].
  CRITICAL: layout verttb stacks with the LAST input at TOP → zone 1 is the
  BOTTOM band. Wrong assumption here caused the "mixed textures" bug.
- Box UVs: boxPOP `texture`='vertNormals' (texmethod boxinside) = per-face
  full 0-1 uvs. Do NOT use texturemapPOP xyznorm (top-down projection that
  collapses side faces into slivers). A material cannot fix UVs — MATs sample
  through the same Tex uvs.
- `zones_wire.rewire()` calls `atlas_rewire()`: rebuilds zatlas/atlas inputs,
  uvband band ranges, box UV wiring and popViewer.Texture for the current zone
  count. zoneMaster template contains uvband; replicator clones copy structure.

## sc_waves thirds reassembly (2026-11-12)
- Exact 1/3 crop fractions of 1280 round to 427x3 = 1281 px (1 px overlap per
  seam). Integer split: crop1 [0,427) crop2 [427,854) crop3 [854,1280) via
  cropleft/cropright = 427/1280, 854/1280.
- Reassembly: xf_l/xf_c/xf_r transformTOPs (1280x720, extend=zero, tunit=pixels,
  tx = -426.5 / +0.5 / +427) → addr1 (add) → `reassembled` (add).
  Numeric diff vs original: mean 0.2/255 (quantization only).

## TD quirks reminder
- Crop TOP pars are kept-region bounds (full = 0/1/0/1, zeros = 1x1 empty).
- par[name]=v silently no-ops; use .val. Menu pars silently ignore invalid values.
- layoutTOP: use setInputs(); the `tops` par ignores .val assignment.
- Exec bridge cannot resolve `mod.*` of TD DATs; exec the function source instead.
- popViewer out1 ← select1 ← render1 (the pane the user sees); render2 is grid view.

## Scene auto-sync TD -> VJ app (2026-11-13)
- `mediaSwitcher/scenes_sync` (text DAT module): `sig(M)` = tuple of scene
  out1 paths in container order; `rebuild(M)` rewrites `source_tbl` from the
  scenes container — drops rows whose op is gone, appends new scenes, keeps
  custom display names (override map stored as M 'scene_disp', seeded from
  source_tbl where name != basename), remaps preview/program by PATH
  (c_preview, state['program'], sel_prog retarget if its path vanished,
  pending fades cleared), and clears zone_tbl rows whose source disappeared.
- Hook: `ui_stream.onFrameStart` compares scenes_sync.sig each frame and calls
  rebuild on change; the pre-existing source_tbl.text signature then triggers
  the 'sources' websocket broadcast, so the VJ app pallet + vjpanel buttons
  (both read source_tbl) sync automatically on add/remove/rename.
- Verified live: add (sc_dummytest appeared), rename (sc_renamed77 replaced
  old row), remove (row dropped, preview remapped).
- Renaming a scene COMP loses its custom display name (override is keyed by
  path); it falls back to the new node name.

## WLED FX port — sc_fire (Fire 2012) (2026-11-13)
- Scene at /project1/mediaSwitcher/scenes/sc_fire, auto-registered as "Fire 2012"
  (display-name override in M 'scene_disp').
- Architecture: fire_fb (feedbackTOP 512x288 rgba8, heat in R) -> fire_sim
  (glslTOP, shader in fire_glsl text DAT via `pixeldat` par) -> heat_null ->
  fire_color (lookupTOP, secondinput ramp from fire_keys=lava_gp) -> fire_level
  (Brightness) -> fire_flip (Direction) -> out1.
- Custom par page "Fire": Cooling, Sparkrate, Boost, Simspeed, Scale,
  Direction (0 up / 1 down), Brightness, Arspark, Arboost.
- Uniforms via glslTOP vec blocks (vec{i}name/vec{i}valuex) expression-bound to
  the scene pars; uBass driven by fire_exec textDAT onFrameStart (par
  expressions cannot index CHOP channels in this build).
- Template + quirks documented in leds909/wled_fx/README.md (shader, keys,
  build script saved there).

## 909club program ports — fx_* scenes (2026-11-13)
- Source: C:\Users\josep\Downloads\909club-main\909club-main\server\programs\*.js
  (per-LED stateless compute over venue pixels; ported to stateless GLSL TOPs).
- 18 scenes built in /project1/mediaSwitcher/scenes/: fx_fuego, fx_aurora,
  fx_plasma, fx_espiral, fx_tunel, fx_marea, fx_titileo, fx_brasa, fx_corazon,
  fx_vortice, fx_flujo, fx_caleidoscopio, fx_goteo, fx_barrido, fx_corte,
  fx_rebote, fx_estallido, fx_lluvia (display names via scene_disp overrides).
- Structure per scene: fx_glsl (text DAT shader) -> fx (glslTOP 512x288,
  pixeldat) -> out1. Custom par page "FX": program params + ColaR/G/B +
  ColbR/G/B (palette A core / B tips, 0-1 floats).
- Uniforms via vec blocks: params first (expr -> scene pars), then uColA/uColB
  (3-component exprs), then ctx uTime/uBeat/uBeatPhase/uBpm (CONSTANT, driven
  per-frame by mediaSwitcher/fx_clock textDAT from audio_jev/beat_out_null
  channels beatcount/beatpos/bpm; scene storage 'fx_ctx' maps name->vec index).
- mediaSwitcher/fx_builder (text DAT): build_all(defs_json) rebuilds scenes
  from a defs JSON (portable copy: leds909/fx909/programs.json).
- Texture space = one canvas across all panels (u along strip/room-x,
  v across strip/height); venue depth z is NOT representable — programs using
  z run per-strip instead (noted compromise).
- Ported math: azar() integer hash, suave smoothstep, mezclar A/B palette,
  suelo=fondo simplification (photosafety floors not ported yet), medioTiempo
  not ported. Not ported yet: firma, revelacion, sigilo, sonda, acepta,
  recorridoPlano, telepata, vasos, organismo, cardumen, monzon, meteoro,
  niveles, dialogo, cruce, teletransporte, carga.
- FIX static scenes: 'uTime' is a TouchDesigner BUILT-IN uniform — declaring it
  in a glslTOP shader gets silently shadowed. All fx_* shaders now use uFxTime
  (vec block renamed too). Frame driver: mediaSwitcher/fx_exec (executeDAT,
  framestart=True) -> fx_clock.module.fx_tick() writes vec uniform pars every
  frame (plain textDAT onFrameStart callbacks do NOT fire; ui_stream hooks run
  only at 2Hz).
- Static-scenes fix 2: beat-driven scenes froze because beat_out was all zeros
  (no live detection). fx_clock now synthesizes a 120 BPM clock (wrapped at
  4096 beats for float32 shader precision) whenever bpm<=0, and uses the real
  beatcount/beatpos/bpm when detection is live.

## Audio system audit (2026-11-17)
- Deleted from audio_jev (dead): spec_proxy, src (selectCHOP), oscout1,
  scene_sm (jev stub), parexec1 (jev launcher), beat_out_callbacks +
  beat_send_callbacks (unused TD template DATs; live ones are beat_out_cb /
  beat_send_cb). Also removed jev/__pycache__.
- LIVE audio graph:
  audiofilein1 (music file, e.g. Hardcore track) -> audio_in (null)
    -> bands (scriptCHOP, bands_cb) -> bands_out -> mediaSwitcher/ar_ctrl
       -> ar_null -> GUI meters + AR scenes (fx_clock uBass/uMid/uHigh)
    -> beat_send (scriptCHOP) --UDP float32 127.0.0.1:7010--> beat_service.py
       (NOT auto-started; run manually from leds 909/jev)
    -> beat_out (scriptCHOP) <- OSC /beat/* via oscin1 <- beat_service
       -> beat_out_null -> fx_clock musical clock + GUI BPM/beat infobar
  audiodevout1 <- audiofilein1 (speaker monitoring of the track)
  oscin1_callbacks also handles /jevbrain/* from brain_service.py (genre/mood;
  also manual-start).
- If beat_service is not running: beat_out is all zeros, fx_clock falls back
  to a synthetic 120 BPM clock (see fx_clock), and beat_send UDP goes nowhere
  (harmless).

## Services launcher (2026-11-17)
- /project1/services COMP: START SERVICES / STOP buttons (buttonCOMPs with
  svc_ext extension class) + services_svc module + svc_init executeDAT
  (autostarts 2s after TD start). Build script: leds909/svc_launcher_build.py.
- Launches jev/beat_service.py + jev/brain_service.py detached, logs to
  jev/svc_<name>.log, PID files jev/svc_<name>.pid guard against duplicates
  (port-probing was unreliable: TD binds 0.0.0.0:7005; Windows allows multiple
  UDP binds on 7003).
- CRITICAL: interpreter must be the absolute user python (Python312 with
  torch/BeatNet). Bare 'python' resolved to a different env -> ModuleNotFound.
- Verified: both services live (ports 7003 + 7010), beat detection running
  (bpm~117 from current track), beat_out feeding the fx musical clock.

## Auto-VJ + services watchdog (2026-11-18)
- IMPORTANT: TD was restarted and an OLD .toe was loaded - all unsaved fx scenes
  were lost. Recovery: rebuild scenes via leds909/fx909 (programs.json +
  builder), then leds909/fx909/reinfra.py restores fx_clock/fx_exec/watchdog.
  SAVE THE PROJECT after changes!
- /project1/auto_vj COMP: par Enabled (0/1), Minbars (dwell in bars, default 8),
  auto_rules tableDAT (pattern|scenes; '|' OR tokens, substring match against
  "genre mood"; '*' fallback row), auto_vj_mod.tick() driven by auto_exec
  executeDAT onFrameStart. On downbeat (beatpos==1) after dwell: picks a random
  scene from the genre/mood bucket (no immediate repeat), sets c_preview and
  triggers the standard swap (c_swap + swap_release). Reason string stored as
  M 'av_reason'.
- GUI: AUTO button in the SHOW tab infobar (green when active) sends
  {cmd:'autovj', value:0/1}; state now includes 'auto' + 'auto_info' (reason)
  in BOTH http_cb._state_msg and ui_stream._state (keep in sync!).
- Services watchdog: fx_exec frame loop calls services_svc.svc_watch() every
  30s; restarts dead sidecars. Manual STOP sets svc_hold_until = now+1h so the
  watchdog respects it; START clears the hold. svc_init executeDAT autostarts
  services 2s after TD load. NOTE: services_svc._python_exe MUST use the
  absolute Python312 path (torch env) - bare 'python' resolves wrong.
- Verified end to end: services auto-start, beats flow (bpm~97), auto-VJ
  changed program 29->32 with reason logged.

## MASTER RECOVERY (2026-11-18)
- The project rolled back twice (TD restarts without saving). Full recovery is
  now ONE command:
    python "leds 909/leds909/RECOVER_BUILD.py"
    curl -s -X POST http://127.0.0.1:9981/api/td/server/exec \
      -H "Content-Type: application/json" \
      --data-binary @C:/Users/josep/AppData/Local/Temp/recover_all.json
    python C:/Users/josep/AppData/Local/Temp/http_local.py
    python C:/Users/josep/AppData/Local/Temp/ui_local.py
    (then push_web.json step — see RECOVER_BUILD docstring/header)
- It rebuilds: services launcher (+watchdog), 18 fx scenes (from fx909/
  programs.json), fx_clock/fx_exec (clock + thumbnails + svc_watch), auto_vj
  (rules/pars/tick), and re-patches http_cb (autovj cmd + auto state fields)
  and ui_stream (auto fields) via local-file patching.
- NOT auto-recovered (older, do manually if needed): sc_fire (wled_fx/
  fire2012_build.py), sc_waves thirds reassembly (see sc_waves section).
- After ANY recovery or new work: SAVE THE PROJECT IN TD (Ctrl+S).

## beat_service v2 — steady tempo + live housekeeping (2026-11-18)
- A/B test (4 hardcore tracks, offline): BeatNet+DBN clearly steadier than
  beat_this peak-picking (e.g. 2.8% vs 54% interval std); beat_this+DBN halves
  hardcore tempo. DECISION: keep BeatNet, fix service logic. beat_this stays
  installed (test script: jev/test_beat_this.py) for future re-evaluation.
- beat_service.py v2 changes:
  - BPM from AUDIO-TIME beat intervals (median of last 16) — no wall clock.
  - Octave hysteresis: half-time only above 240 BPM sustained 8 beats,
    released below 200 BPM sustained 8 beats (hardcore 190-220 is legit).
  - Bounded UDP drain (12 chunks/call) + drop stale audio when queue > 24
    chunks — the old unbounded drain STARVED housekeeping, which is why
    /beat/tempo never reached TD (bpm always 0).
  - _housekeeping_thread: dedicated thread for /beat/tempo + /beat/hb every
    2 s, immune to DSP load.
  - Loopback fallback repaired (CAP_SR/audio_callback were undefined).
- Verified live: bpm_rt/beat_out bpm ~150-167 steady, no flip-flop, stale
  chunk drops logged, downbeat pulses firing.

## Beat model switch (2026-11-18)
- audio_jev custom par "Beatmodel" (Beat page): 0 = Live (BeatNet online PF,
  default), 1 = File/BeatNet (offline DBN pre-analysis of audiofilein1 track,
  beats replayed time-aligned), 2 = File/beat_this.
- File modes: beat_service analyzes the whole file in ~2s, then emits the
  analyzed beat grid clocked by the TD playhead (extrapolated between 0.5s
  'pos' updates sent by audio_jev/beat_pos_exec; 'pos' uses audiofilein1
  'index' par which is NOT a live playhead - constant offset, harmless since
  emission is wall-clock aligned). Rewind/seek re-arms emission.
- Control path: beat_cmd module (audio_jev) sends 'model X' / 'file <path>' /
  'pos <s>' via UDP 7011; 'model' cmds are idempotent; beat_cmd.watch()
  (called from fx_exec) applies par changes + re-sends every 15s so service
  restarts re-sync. parameterexecuteDAT proved unreliable - don't use it.
- UDP chunk stream repeats audio (CHOP cooks faster than audio fills) - never
  use raw chunk accumulation as a clock.
- Verified: switch 0<->1 live; file mode gives rock-steady bpm 157.9 (true
  offline value) vs online jitter; beats flow into beat_out.
- 1fps-look fix: fx glslTOPs have NO inputs, so TD marked them clean after one
  render and ignored uniform updates (no re-render). fx_tick now calls
  g.cook(force=True) per scene per frame -> scenes re-render at TD fps.
  (Reading out1 via numpyArray on an unwatched nullTOP shows stale data -
  null caches; read the fx glsl node itself, or trust the live chain.)
- Speed defaults raised ~3x for bar-locked scenes (flujo 0.6, aurora 0.75,
  plasma 1.0, marea 1.0, espiral 1.0, caleidoscopio 1.2 cycles-or-turns/bar)
  both live and in fx909 defgen. Lluvia/titileo are time-driven (were fine).
- VJ app auto controls: AUTO button now shows a dwell stepper (-/+ 2 bars,
  cmd 'autovj_dwell' -> auto_vj Minbars) and the last decision text; state
  includes 'auto_dwell' (both http_cb and ui_stream - keep in sync).

## Smooth musical clock (2026-11-18)
- Scenes no longer step on beats: base animation runs on uPulsosS = smooth,
  phase-locked musical clock (beat_count + elapsed_since_last_real_beat *
  bpm/60, computed in fx_tick). Shaders use pulsos/compases/barPhase from it
  -> continuous motion at exact musical rate, re-synced on every real beat.
- Beats remain available as MODULATION only: uBeat/uBeatPhase (discrete) and
  the uArlevel brightness pump (bass). Corazon now uses fract(pulsos) for a
  smooth LUB-DUB envelope instead of the integer storage phase.
- ctx uniforms now: uFxTime,uBeat,uBeatPhase,uBpm,uPulsosS,uBass,uMid,uHigh
  (fx909/builder_dat.txt has the current builder DAT; the builder.py BUILDER
  string was stale during the rollback recovery - prefer builder_dat.txt).

## fx_clock v2 — frame-skip + reopen-independence (2026-11-18)
- Only USED scenes (program, preview, zone feeds) get uniform updates +
  cook(force) per frame; idle scenes don't (their out1 caches, fine).
- selectCHOP .par.top.eval() returns an OP object, not a string — use .path.
- Smooth musical clock guarded: if beat_t is stale (>2s old, e.g. audio_jev
  network not loaded yet on reopen), free-run at tempo from a stored
  (beat, walltime) base instead of exploding to 1e9 (float32 precision froze
  the shaders — this was the "starts only when I visit audio_jev" bug).
- Thumbnails at 0.3s cadence (jpeg encode+disk IO at 0.12s stuttered frames).
- Save-error root cause: beat_send_cb cached its UDP socket in OPERATOR
  STORAGE (A.store('beat_sock', s)) — storage is pickled into the .toe and
  sockets cannot be pickled. Deleting it was futile (re-created every cook).
  FIX: socket cached in the callback MODULE's globals (_sock = [None]) which
  lives per-session but is never saved. RULE: never .store() sockets/threads/
  live objects on operators — use module globals.
- Post-restart frozen-scenes fix: time-gate timestamps stored in operator
  storage (thumb_t etc) persist across TD restarts, but absTime.seconds
  RESETS to 0 — the gate "absTime - stored < interval" went NEGATIVE and
  early-returned forever (thumbs + idle-scene uniform refresh never ran).
  Rule: always treat negative deltas as stale (0 <= dt < interval).
- fx_thumbs now also refreshes the uniforms of the scene it snapshots
  (idle scenes otherwise render stale), and does so even with 0 websocket
  clients (jpeg encode only when clients exist).

## CHOP-driven uniforms (stutter fix, 2026-11-18 late)
- Per Derivative best practice (CHOP exports > expressions > python/frame):
  removed ALL per-frame python uniform writes + cook(force) from fx_tick.
- New drive chain in mediaSwitcher:
  fx_drive_speed (Speed CHOP speed=1) -> uFxTime (small t, resets per TD start)
  fx_pulsos_speed (Speed CHOP, speed EXPR = beat_out bpm/60) + fx_pulsos_offset
  (constantCHOP) -> fx_pulsos (mathCHOP add) -> uPulsosS.
  ar_null bass/mid/high + beat_out_null bpm/beatcount/beatpos bound directly.
- 148 uniform pars across 18 scenes now bound via EXPRESSIONS
  (fx909/bind_chop_uniforms.json re-applies them; the builder resets ctx
  uniforms to constants, so ALWAYS re-run the binder after a scene rebuild!).
- fx_clock v3: python only does fx_sync (1 Hz phase correction of
  fx_pulsos_offset vs real beats, jump if drift>0.25 beats) + fx_thumbs
  (0.3s round robin, cook(force) only the snapshotted scene).
- fx_exec frame loop: fx_sync, fx_thumbs, svc_watch, beat watch - no per-frame
  par writes anywhere.

## DURABLE RULE — node creation & layout (user directive, 2026-11-19)
- VIEWER FLAGS: viewer ON for every node EXCEPT TOPs that are not nulls.
  nullTOPs always viewer ON. The ONLY viewer-off nodes are non-null TOPs.
- LAYOUT: nodes in sequential, logical order (signal flow left-to-right),
  spread out and easily visible — NOT collapsed/stacked in one spot, never
  obstructing other nodes. Apply when creating AND when reorganizing.
- Applied retroactively (2026-11-19): services/auto_vj side by side at
  project level; mediaSwitcher infra row (fx_builder, fx_clock, fx_exec,
  fx_drive chain, thumb_fit at x=1600+, y=1400); audio_jev DAT row; each fx
  scene = fx_glsl -> fx -> out1 left-to-right with viewer on out1 only;
  fx scene COMPs in a 6-column grid below the originals.

## Master overrides (WHITE/STROBE/BLACK) (2026-11-19)
- leds909/ovr_state (constantCHOP, chan1) = mode: 0 normal, 1 white,
  2 blackout, 3 strobe (12 Hz alternation, expression on ovr_switch index).
- Chain: viz_all -> ovr_switch (switchPOP; in0 viz_all, in1 ovr_white,
  in2 ovr_black) -> ovr_out (nullPOP) -> popto1.pop.
  ovr_white/ovr_black = glslPOP compute shaders (TDIndex/TDNumElements/
  TDOut_color; shader DATs ovr_white_glsl/ovr_black_glsl). attributePOP was
  NOT usable (attr count par refuses programmatic growth); pixel-style
  fragColor does NOT compile in glslPOP - use the TDIn/TDOut compute format.
- poptoCHOP .pop repointing via .val is UNRELIABLE mid-run from the bridge
  (one clean test did route white to trimA/LED feed; black unconfirmed from
  the bridge). popViewer select2 now shows ovr_out - VERIFY VISUALLY:
  set ovr_state 1/2/3 and watch the 3D view / LEDs. If the switch does not
  propagate live, alternative = strobe via ovr_state expression directly on
  popto1.pop (mode expression), or wire trims from a nullCHOP after popto1.
- GUI: WHITE (toggle), STROBE (hold, mouse down/up), BLACK (toggle) buttons
  in the SHOW infobar; cmd 'override' value 0-3; state 'ovr' flag.

## CONSOLE GUI + per-scene properties + AUTO v2 (2026-11-19)
- NEW APP: vj_gui/index.html fully replaced by the CONSOLE layout (mockup A,
  design files in vj_gui/design/; legacy app backed up as index_legacy_backup.html).
  Layout: master bar (WHITE/STROBE/BLACK, BPM/genre, AUTO + SLOW/NORM/FAST),
  left PREVIEW/PROGRAM WebRTC monitors + CUT/TAKE + fade slider, center source
  grid with live thumbs + SAFE row, right tabs PROPERTIES / AUTO / ZONES.
- TD protocol additions (http_cb):
  scenepars {i} -> {type:'scenepars', pars:[{n,l,v,min,max}]} (customPars of
    the scene COMP, colors as separate R/G/B pars)
  setpar {i,par,value} (clamped, customPars whitelist)
  auto_mode {0|1|2} -> auto_vj set_mode: dwell presets 32/8/2 bars
  autorules_get/set -> 5-col rules table (match|scenes|cond|colA|colB)
  state += auto_mode (both http_cb._state_msg and ui_stream — keep in sync;
  NOTE: _state_msg had a DUPLICATE definition, deduped).
- auto_vj v2: rules now have cond ('bpm>150' style filters) and base palette
  hex colA/colB — applied to the picked scene's Cola/Colb RGB pars on switch.
  Modes: Automode par 0/1/2 = slow/normal/fast -> Minbars 32/8/2.
- Verified live: props panel renders Fuego's Color A/B pickers + Viveza/
  Altura/Fondo/Audio React sliders from TD; AUTO tab shows 7 editable rules;
  mode buttons set dwell (2/8/32 verified TD-side); app runs at TD webserver
  port 8080.

## RAVE latent modulation (audio pipeline option 3) + LOOKS + keys (2026-11-19)
- jev/rave_service.py: RAVE v1 streaming model (percussion.ts, 71 MB,
  jev/models/rave/) — encoder latents (4 dims, tanh -1..1) + latent velocity
  via OSC /rave/lat,/rave/vel @ ~11 Hz to :7005. Audio fed by beat_send_cb
  FAN-OUT to UDP 7011 (two sockets cannot share 7010 on Windows).
  Gotchas: torch no_grad REQUIRED (in-place cache ops), input shape (1,1,N),
  pip needs scipy<1.13; numpy pinned 1.26 (beat_service shim still fine).
- Launcher: rave_service.py auto-starts (liveness port 7012); watchdog covers.
- TD: oscin1_callbacks stores rave_lat/rave_vel; audio_jev/rave_out scriptCHOP
  (onCook, non-timeslice) exposes lat0-3/vel; fx ctx uniform uRvel bound by
  expression to rave_out['vel']; shader epilogue restored (was lost!):
  col *= clamp(1 + uArlevel*(uBass*1.1 + uRvel*0.9 - 0.18), 0, 2).
  Beatmodel par max=3 ('rave' = online beats + latent modulation).
- LOOKS bank: mediaSwitcher/looks_mod + looks_tbl (name|json snapshot of
  program source + all zone sources). cmds: look_save/look_apply/looks_list
  -> {'type':'looks'}. GUI 4th tab LOOKS with save + GO.
- Keyboard masters in GUI: W=white, S=strobe (hold), Space=blackout,
  T=take, A=auto. Ignored while typing in inputs.

## Live monitors — WebRTC + scene/venue toggle (2026-11-19)
- GUI now initiates webrtc_connect on ws open (retry 4s if no video) and
  binds ALL FOUR TD tracks by ev.track.id ('prog','prev','mprog','mprev' —
  TD labels tracks exactly; do NOT use the offer message's track field).
- Each monitor has SCENE / VENUE toggle (raw scene video vs venue-map
  output). JPEG frame/map fallbacks only show before WebRTC connects.
- http_cb onWebSocketClose now closes the client's webrtc connections
  (rtc_map) — reloads had leaked 14 stale connections.

## Realtime all-scenes grid preview (2026-11-19)
- PREVIEW/PROGRAM monitors verified to carry DIFFERENT streams (fit2=preview
  bus, xfade=program). They look identical right after a TAKE because both
  buses point at the same scene until a new preview is selected — two-bus
  design, not a bug.
- All-scenes live thumbnails: mediaSwitcher/thumb_grid (layoutTOP 6-col grid,
  1080x608, all source out1s; fx_thumbs rewires it when source count changes)
  -> vso_grid -> 5th webrtc track 'grid'. GUI slices the single video into
  per-clip <canvas> tiles via rAF (GRID_COLS=6; tile = col*tw,row*th) — one
  encode/decode, all 34 squares animate at full frame rate. JPEG thumbs
  remain as pre-connect fallback. Gotcha: inserting tuples into the
  webrtc_connect track list broke the for-loop syntax once — tuple must
  close AFTER the added pair.

## RAVE removed from the pipeline (2026-11-20)
- DECISION: RAVE (encoder-only modulation) did not justify its cost at the
  current integration depth (one uRvel term behind a 0-default slider vs a
  whole torch process + extra port + service). Analysis stack = BeatNet
  beats/BPM + FFT bands, unchanged.
- File-side DONE: rave_service.py + model archived to jev/archive_rave/;
  beat_service.py PORT_RAVE note removed.
- TD-side PENDING (TD was closed during removal): run
  leds909/REMOVE_RAVE.py + curl the payload (commands inside) to: drop
  rave from the launcher, kill the process, remove beat_send_cb 7011
  fan-out, set Beatmodel back to 0-2. rave_out CHOP + /rave handlers stay
  (inert, uRvel reads zeros).
- If TD closed WITHOUT saving yesterday: grid preview, rtc cleanup, monitor
  toggles, http_cb cmds etc are RAM-lost — rerun RECOVER + this script.

## Status check 2026-11-20 (incl. crash + recovery path)
- Audit result: reopen had lost only the LAST unsaved items (thumb_grid,
  vso_grid, webrtc grid track). Everything else survived the save.
- RAVE removal COMPLETED in TD (launcher 2 services, beatmodel 0-2,
  beat_send_cb clean single copy). Files archived in jev/archive_rave/.
- APP PORT: 8080 is taken by TD's own CEF debugger + steamwebhelper ->
  webserver1 moved to 9090. App: http://127.0.0.1:9090  (update any
  browser bookmark; VJ_GUI.exe host setting may need 9090 too).
- CRASH: growing layout TOP inputs one-by-one via inputConnectors hung/
- killed TD. RULE: create layout TOPs fresh and use setInputs ONCE.
- RESTORE_TODAY.py (leds909/) re-applies everything RAM-side after a
- crash/reopen: RAVE removal, port 9090, grid track tuple, thumb_grid
  recreated fresh, fx_clock hook, service restart. RUN IT then SAVE.
