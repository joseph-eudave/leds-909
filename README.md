# LED 909 — VJ show control for venue 909

Realtime LED show system for the 909 venue: **12,347 LEDs** on **4 WLED/ESP32
controllers** driven via **DDP**, controlled live from a web **VJ console**
running against a **TouchDesigner** backend, with realtime **beat detection**,
**genre/mood analysis**, an **auto-VJ pilot**, and a library of **GLSL scene
generators** ported from a professional VJ codebase.

```
TouchDesigner (show engine)  ←UDP/OSC→  Python sidecars (beat / genre)
        │
        ├─ 18+ generated GLSL scenes (CHOP-driven uniforms, no per-frame python)
        ├─ Zone compositor (per-zone textures, blend modes, venue UV mapping)
        ├─ DDP outputs → 4 WLED controllers
        └─ Webserver :9090 → VJ CONSOLE (browser app, WebRTC monitors)
```

## Quick start (new machine)

### 1. Requirements
- **Windows 10/11**, [TouchDesigner](https://derivative.ca/) (non-commercial OK;
  built & tested on 2025.x builds with the POP family: glslPOP, poptoCHOP…).
- **Python 3.12 (64-bit)** on PATH (`python --version`).

### 2. Install
```bat
cd "C:\path\to\leds 909"
python -m pip install -r requirements.txt
```
> BeatNet pip name varies; if `pip install BeatNet` fails, use
> `pip install git+https://github.com/mjhydri/BeatNet`. The service includes a
> numpy-2 shim, but 1.26.x is pinned for scipy/essentia compatibility.

### 3. Open the show
1. Open **`Leds 909.toe`** in TouchDesigner.
2. The `services` component auto-starts both sidecars 2 s after load
   (START SERVICES / STOP buttons otherwise). Logs & PID files in `jev/`.
3. Open the console: **http://127.0.0.1:9090** (port is 9090 — 8080 is usually
   taken by TD's own CEF debugger).
4. Load a music file into `audio_jev/audiofilein1` (or wire any audio source).

### 4. Optional: rebuild the standalone console exe
```bat
cd vj_gui && build_vj_exe.bat
```
(exe is .gitignored; the browser app is the primary interface.)

## What's where

| Path | Contents |
|---|---|
| `Leds 909.toe` | The full TouchDesigner show file |
| `jev/beat_service.py` | BeatNet realtime beats/BPM → OSC `/beat/*` |
| `jev/brain_service.py` | Jamendo/Essentia genre+mood → OSC `/jevbrain/*` |
| `jev/models/` | ONNX models for genre/mood (tracked) |
| `jev/archive_rave/` | Archived RAVE experiment (not in the live pipeline; model .ts excluded from git — see below) |
| `leds909/fx909/` | **Scene generator**: `programs.json` (18 scene defs + GLSL), `defgen.py`, `builder.py`, uniform binder, recovery scripts |
| `leds909/wled_fx/` | WLED Fire 2012 port (first WLED experiment) |
| `leds909/RECOVER_BUILD.py`, `RESTORE_TODAY.py`, `REMOVE_RAVE.py` | One-shot TD-side restores after crashes/reopens |
| `vj_gui/index.html` | The CONSOLE web app (app itself — served by TD) |
| `vj_gui/design/` | The three layout mockups that were evaluated |
| `docs/HANDOFF.md` | **Living engineering log**: every quirk, decision, recovery procedure — read this first when anything breaks |
| `docs/PRO-VJ-WORKFLOWS.md` | Research: Resolume/MadMapper workflows behind the console design |

### Excluded from git (regenerate/download)
- `vj_gui/VJ_GUI.exe` — rebuilt via `build_vj_exe.bat`
- `jev/archive_rave/models_rave/percussion.ts` (71 MB) — download from
  `https://play.forum.ircam.fr/rave-vst-api/get_model/percussion` if you want
  the archived RAVE experiment back
- TD autosave backups (`Leds 909.NN.toe`), caches, logs

## The VJ console (browser)

- **Master bar**: WHITE / STROBE (hold) / BLACK, BPM + genre, AUTO with
  SLOW/NORM/FAST pilot modes. Keyboard: `W` `S` `Space` `T` `A`.
- **Left**: PREVIEW & PROGRAM WebRTC monitors with SCENE/VENUE toggles,
  CUT / TAKE.
- **Center**: all sources with **live grid previews** (one composite WebRTC
  stream sliced client-side) + SAFE row.
- **Right tabs**: **PROPS** (per-scene unique parameters live from TD),
  **AUTO** (genre buckets, conditions like `bpm>150`, base palettes),
  **LOOKS** (full-rig snapshots: program + all zones), **ZONES**.

## Scene generator

Scenes are **generated**, not hand-placed: `leds909/fx909/defgen.py` writes
`programs.json`, the TD-side `fx_builder` DAT builds the scene COMPs, and the
uniform binder wires time/tempo/audio via CHOP expressions (Derivative's
recommended pattern — no Python in the frame loop). After rebuilding scenes,
**re-run the binder** (`bind_chop_uniforms.json` payload — see HANDOFF).

## Show-time checklist

1. Open TD → open the console → press **AUTO** (or drive manually).
2. Blackout/white are TD-side overrides — they work even if the browser dies.
3. After ANY change made via the API/bridge: **save the .toe** (Ctrl+S).
   Crashes/reopens may need `leds909/RESTORE_TODAY.py` — check HANDOFF.

## License / credits

Internal show tool for venue 909. Third-party: BeatNet (CC-BY-4.0),
Essentia/Jamendo models, 909club program library (internal port),
layout/interaction ideas informed by Resolume Arena & MadMapper research
(see docs). The archived RAVE experiment: acids-ircam/RAVE (IRCAM).
