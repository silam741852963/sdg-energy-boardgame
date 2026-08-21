# Architecture

## System overview

The Raspberry Pi application combines asynchronous hardware input with a
synchronous Pygame/ModernGL renderer.

```text
CleanBoost BLE ──> BLEReceiver ───────┐
                                      ├──> locked GameState ──> GameSnapshot
Hall sensors ────> WireReceiver ──────┘                         │
                                                                v
                                       FireworkEngine / RocketScene
                                          │ particles / lights / audio
                                          └ battery / drones / pixel text
```

`pi.main` creates `GameState`, runs BLE/GPIO/PWM asyncio tasks on a daemon
thread, and keeps all window and OpenGL work on the main thread. Receiver writes,
smooth filling, snapshots, and mission events are protected by an `RLock`.
`WireReceiver` moves GPIO callbacks onto its asyncio loop with
`call_soon_threadsafe()`. The render loop is the only owner of simulation ticks;
the receiver loop does not run a competing inactivity update.

## Mission model

`GameState` owns the authoritative ordered battery and energy rules.

- `active_sensors` records the Hall sensors currently selected by Sot-kun.
- `selected_generators` preserves completed cells in order and appends the cell
  under the movable Sot-kun selector on the right.
- Moving Sot-kun away cancels and resets an unfinished cell. A cell that reached
  100% is reserved with its energy intact until launch or mission reset.
- Energy is accepted only when its matching generator is selected.
- There is no energy drain or selection timeout.
- A cell crossing 100% emits one `CELL_FILLED` event.
- At least two cells must be reserved and full. Two and three cells enter an
  eight-second `launch_ready` continuation window; selecting a new unfinished
  cell cancels it, filling that cell starts a fresh window, and four cells bypass
  the wait.
- Countdown expiry atomically records `launch_generators`, locks the battery,
  and emits `LAUNCH_COMMITTED` after the final `CELL_FILLED` event.
- After commitment, physical presence is still tracked while battery changes and
  further energy are ignored.
- The engine creates a new mission as soon as the return transition restores the
  Ablic screen. The rocket scene is reset with it, so the rocket is back on its
  launch base before the next selection.
- Sensors held across that reset remain physically present but are disarmed until
  they first go low. A newly introduced sensor responds immediately; a held one
  responds after its next low/high edge. This prevents a completed battery from
  silently selecting itself again without delaying the next player.

The renderer consumes immutable `GameSnapshot` copies and ordered
`MissionEvent` values, so animated gauges never decide gameplay completion.
`SmoothFiller` and immediate debug fills both call the same internal energy
transition.

## Presentation states

`RocketScene` has seven explicit phases:

1. `ATTRACT` — dark-blue procedural stars, clearly varied blinking, a recurring comet, and the Ablic drone pattern.
2. `REVEAL` — Ablic flies upward while parallax and ground geometry pan down.
3. `CHARGING` — the textured red-and-white block rocket, mission messages, and expanding battery.
4. `IGNITION` — the rocket shakes and emits a grounded tail plume.
5. `ASCENT` — the camera follows the accelerating rocket beyond the initial view while stars intensify and liftoff triggers a boosted comet, meteor shower, and constellation pulse.
6. `DEPARTURE` — a 3.6-second tracked follow-through holds the rocket longer before a late gradual camera release sends it beyond the frame.
7. `RETURN` — after the ranking flow closes, the depth layers reverse and Ablic returns. When the
   logo is restored, gameplay unlocks and the rocket and camera return to their
   initial transforms.

Two-, three-, and four-cell launches use 4+8, 5+10, and 6+12 second
ignition/ascent timings followed by the shared 3.6-second departure. The
two-cell tier matches the former four-cell impact baseline; larger batteries
increase plume layers, firework density and lifetime, source-color
variety, dust, shockwave strength, audio intensity, and screen shake.

`GaugeManager` animates additions, removals, and reflow inside one horizontally
centered, double-bordered battery: Wind cyan, Solar yellow, Hand Crank orange,
and Coil lime. `PixelFont` contains a compact
code-defined bitmap alphabet and renders all production mission text without
Pyxel, another font package, or a system-font dependency. Sot-kun is referenced
only by messages and has no visual character.

The rocket body carries four recessed charge ports ordered by reserved cell.
The first completed cell pulses its source-colored port with only a micro-tremble
and sparse, small nozzle leak. Explicit nonlinear cue profiles make cell two
clearly active and cell three substantially denser, brighter, longer-lived, and
more energetic. These particles use the existing scene-effect pool and
foreground light path.

## Particle, rendering, and audio budgets

`FireworkManager` owns a 10,000-slot NumPy `ParticleSystem`. Firework shells
and rocket flame/smoke/sparks share that pool and the same ModernGL instanced draw
path. Scene effects carry a group flag so mission resets can clear them without
changing the firework API.

The renderer samples at most 12 firework heads and eight exhaust heads as colored
light probes. Firework probes illuminate the material-colored city, rocket,
clustered grass, and ground; launch-effect probes are intentionally limited to
the rocket and foreground. Fireworks occupy a world-anchored depth plane between
the skyscraper and residential layers, so the camera moves them with intermediate
parallax instead of pinning them to the viewport. Far facades receive a soft
front wash, residential facades receive mostly roof/edge backlight, and the
rocket/ground favor local exhaust with weaker firework rim light.

Static skyscraper and residential geometry is rasterized once and uploaded as
two reusable GPU layer assets. The far skyline is anchored to the bottom edge
while the attract screen is visible, then moves to the shared ground horizon
during reveal, so no empty strip opens below the buildings. Per-building light
overlays stay dynamic. Grass
tufts use per-cluster gust phase and response, and all colored blade segments are
submitted in one batched line draw rather than hundreds of individual calls.
Lighting queries for buildings, ground segments, texture marks, grass, and rocket
panels are evaluated in vectorized batches. Ground marks and dynamic city washes
are also submitted as batched colored geometry rather than per-object draw calls.

The four cell JSON scripts contain six dense events over 3.15 seconds, with
long-lived final bursts. Launch commitment also starts an eight-event, four-second
celebration whose count, intensity, and lifetime scale with battery size. Playback may
mirror geometry but never rotates the generator palette. Independent cell shows
may overlap; pool exhaustion safely drops new particles.

Fireworks use a separate luminous render palette. Every authored hue and shade
has a minimum perceived luminance, invalid or black indices become pure white,
and sky flashes use the bright shade of the burst color. Firework drawing owns
its additive blend state so earlier alpha-blended layers cannot darken overlapping
glows. A broad, short-lived white bloom plus a crisp white core fills the apparent
sky cavities at each burst center. Particle intensity
continues to control decay without letting fading RGB turn muddy against the sky.

The engine requires an OpenGL 3.3 core context, rejects llvmpipe/softpipe/swrast,
and has no CPU/Pygame rendering fallback. Particles are instanced, city assets are GPU textures, and animated
grass is submitted as batched colored geometry. NumPy handles simulation and
one-time asset preparation; rasterization, blending, texture compositing, and
particle drawing remain on the GPU.
At celebration peaks every particle head remains visible, while decorative trail
history is deterministically capped at 4,000 GPU instances and glow size scales
down only above 3,200 simultaneous heads to protect fill rate.

The engine targets 1920×1080 at 60 FPS on a 2 GB Raspberry Pi 5. One sustained
second below 55 FPS lowers decorative rocket emissions in 10% steps to a 50%
minimum. Three sustained seconds above 58 FPS restore density gradually. Mission timing, rocket
motion, fireworks, messages, and game rules never degrade.

`AudioSystem` loads existing firework WAVs and synthesizes UI and tier-specific
rocket thrust samples once during startup. Each generator has a distinct rising
Hall-selection tone and descending removal tone. Fill pitch, cell-ready chimes,
launch thrust, explosions, launch completion, and the mission-ready logo cue
cover the remaining player-facing state changes. No audio arrays are allocated
per frame.

Sky stars and the active comet trail share one GPU particle batch. Startup
guarantees a comet within four seconds; later passes wait a randomized 8–14
seconds after the previous pass ends. Ignition accelerates that timer; liftoff
guarantees or boosts a comet and adds a short meteor shower plus expanding
constellation pulse to the same batch. Star blink speed and intensity also rise
through ignition, ascent, and departure. Grass remains clustered;
its ambient gust is combined with a distance-faded outward rocket wash. The wash
uses a second 2× increase to both influence radius and bend/flutter velocity
through charged shaking and ignition. At the ascent transition its radius is
3.2 viewport widths from center and guarantees a strong impulse to every grass
cluster, then falls away as the rocket climbs.

## Hardware and debug adapters

Known BLE addresses map directly to `GeneratorType`; unknown advertisements are
ignored. Four gpiozero `Button` inputs are rescanned together on every edge. The
gameplay path expects one movable Sot-kun selector; each completed generator remains in the
battery when Sot-kun moves to the next Hall sensor.

Mock input is deterministic:

| Key | Action |
| --- | --- |
| 1 / 2 / 3 / 4 | Move Sot-kun to Wind / Solar / Hand Crank / Coil; repeat to lift it |
| Q / W / E / R | Charge the matching selected cell |
| 0 | Clear all mocked Hall selections |
| Backspace | Reset mission |
| M | Toggle performance metrics |
| F5 | Export the current internal firework spec |
| Escape | Quit |

The old quick combination selectors, random mock BLE generation, pause shortcut,
dial sequences, simultaneous-selector effects, all-four overload, and Simon Says
have been removed.

## Rankings and persistence

`RANKINGS_ENABLED` defaults to `True`. When the rocket finishes its departure,
the high-altitude scene pauses under a name-entry overlay before Ablic starts to
return. Confirming a name
saves one personal best per exact loadout (canonical cell kinds plus cell count),
then shows the matching top five. Total time stops when launch is committed, so
the different launch-animation tiers do not affect results. Per-cell times cover
each cell's active filling interval.

`leaderboard.json` uses schema version 2 and stores total time, ordered generator
cells, and an individual duration for every cell. Version 1 grouped and flat
leaderboards still load as preserved one-cell legacy records. The existing
player database, case-insensitive name normalization, auto-fill suggestions,
provisional confirmation, personal-best replacement, atomic writes, and
load-error write protection remain in place.

Runtime diagnostics may still write `clean_boost_test.log` and
`hall_ic_debug.log`. Ranking paths remain `leaderboard.json` and
`players_database.json`; JSON writes are atomic and parse failures block
destructive overwrites.

## Validation and deployment

Use:

```bash
python -m compileall -q src
PYTHONPATH=src python -m unittest discover -s tests -v
./run.sh --debug
```

The local `tests/` directory is ignored by Git. It covers ranking preservation,
ordered selection, reset behavior, smooth and immediate completion, launch
locking, removal-triggered readiness, no-drain behavior, and bounded short
scripts. Real GPIO/BLE, fullscreen OpenGL, audio output, and sustained 1080p
performance must also be checked on the target Raspberry Pi 5.

Deploy `src/` and `resource/` together. The service user needs Bluetooth, GPIO,
display, audio, and log-directory permissions. `run.sh` resolves its own root and
supports `SDG_PYTHON` for systemd or other fixed deployments.
