# Pro VJ software research — findings that shaped the console

Comparative study of Resolume Arena, MadMapper, and TouchDesigner show rigs
(MadMapper scenes/cues, Resolume clip/layer/deck + Advanced Output,
CuryCue-style programmer/executor), plus operator habits from forums.

## The three metaphors
- **Resolume** — clip/layer/deck grid. Columns fire whole looks; layers hold
  content faded up/down; decks are swappable banks; Advanced Output keeps
  physical mapping fully separate from content.
- **MadMapper** — scenes + partial-state cues that merge; surfaces and groups
  are first-class (one fader drives many fixtures).
- **TD shows** — roll-your-own cue engines with a programmer→executor
  (preview→take) separation. Our crossfade-takeover switching is this.

## Adopted in the 909 console
1. LOOKS bank (Resolume columns / MM cues): one tap recalls program + zones.
2. Zones as a routing layer decoupled from sources; routing stored in looks.
3. SAFE row (operator habit: bottom pads = always-recoverable looks).
4. PGM/PST hardened: CUT + TAKE (beat-synced take pending), SCENE/VENUE
   monitors (preview the mapped result, not just the clip).
5. AUTO pilot with modes (dwell presets), genre buckets + conditions
   (bpm>…) + per-bucket base palettes — Resolume Autopilot as the template,
   manual always wins.
6. Master overrides TD-side (white/strobe/blackout survive browser death).
7. Live thumbnails on everything (Resolume's signature) — implemented as a
   single composite WebRTC grid sliced client-side.
8. Per-scene property panels (unique pars: color, speed, react…).

## Deliberately deferred
- Layer/clip mixing per zone with solo/bypass rows (Deck concept B).
- Text/media sources and deck paging.
- OSC wildcard API for hardware controllers (APC40…).
- GUI-disconnect watchdog auto-blackout.

Sources: resolume.com/support (Autopilot, Advanced Output, MIDI, FFT),
docs.madmapper.com (Live Performance, Scenes & Cues), derivative.ca,
forum.derivative.ca, r/vjing, github.com/netzzy/CuryCue (2025-2026).
