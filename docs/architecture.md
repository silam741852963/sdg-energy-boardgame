# Architecture

## Deployment baseline

The target and tested hardware is a **Raspberry Pi 5 with 2 GB of RAM**. The
application renders internally at 1920×1080, limits the main loop to 60 FPS, and
requires a hardware-accelerated OpenGL 3.3 core context. There is no CPU/Pygame
rendering fallback; startup rejects llvmpipe, softpipe, swrast, and other software
renderer strings.

The Python package requires Python 3.10 or newer. Direct dependencies are pinned
in `pyproject.toml`: Bleak, gpiozero/colorzero, dbus-fast, ModernGL/glcontext,
NumPy, pygame-ce, and Rich. `requirements.txt` is a deployment snapshot that
also contains transitive dependencies.

## Process and threading model

```text
CleanBoost BLE ──> BLEReceiver ───────┐
                                      ├──> locked GameState ──> GameSnapshot
Hall sensors ────> WireReceiver ──────┘                         │
PWM output ──────> PWMController                                 v
                                           FireworkEngine / RocketScene
                                              │ ModernGL renderer
                                              ├ particles / lights / Earth
                                              ├ battery / city / drones / text
                                              └ Pygame audio and input
```

`pi.main` parses the debug mode, creates `GameState`, and starts a daemon thread
with a dedicated asyncio event loop. That loop owns BLE scanning and, when Hall
hardware is enabled, GPIO callbacks and PWM. Pygame window management, ModernGL,
simulation updates, keyboard input, and drawing remain on the main thread.

`GameState` protects receiver writes, smooth fills, snapshots, ranking changes,
and mission events with an `RLock`. `WireReceiver` transfers gpiozero callbacks
to its asyncio loop with `call_soon_threadsafe()`. Only the render loop advances
smooth fills and launch countdowns through `check_inactivity()`, avoiding a
second competing simulation clock.

## Hardware adapters

`BLEReceiver` uses Bleak. Advertisements from the four exact MAC addresses in
`pi.config.CLEANBOOST_MACS` map to `GeneratorType`; unknown addresses are
ignored. With `CLEANBOOST_TEST_MODE = True`, generator-specific fill values are
used: Wind 20, Solar 10, Hand Crank 5.1, and Coil 5.1 units per accepted beacon.

`WireReceiver` owns four gpiozero `Button` inputs:

| Generator | BCM GPIO |
| --- | ---: |
| Wind | 17 |
| Solar | 27 |
| Hand Crank | 22 |
| Coil | 23 |

The current configuration uses internal pull-ups, a 50 ms debounce interval,
and `is_pressed == True` as the detected state. Every edge rescans all four
inputs and submits the full active set to `GameState`.

`PWMController` creates a gpiozero `PWMOutputDevice` on BCM GPIO 2 at 1 kHz and
sets it to 50% duty cycle. It starts only with real Hall input. If gpiozero
cannot establish a pin factory, `pi.main` switches Hall input to mock mode and
does not start PWM.

`MockReceiver` only keeps the mock BLE task alive. Keyboard handling in
`FireworkEngine` provides deterministic mock Hall and energy events; it does not
generate random energy.

## Mission state model

`GameState` is authoritative for battery ordering and gameplay:

- `active_sensors` is the physical/current Hall set.
- `selected_generators` is the ordered battery: completed cells remain reserved,
  while the movable selector can append a new cell.
- Leaving an unfinished cell resets its energy and timing. Leaving a full cell
  preserves it.
- Energy is accepted only for a selected generator. It never drains and there is
  no selection timeout.
- CleanBoost additions use `SmoothFiller` over 0.3 seconds. Immediate mock fills
  and smooth fills converge on the same locked energy transition.
- Crossing 100% once emits `CELL_FILLED` and records that cell's elapsed time.
- Two or three completely full selected cells start the configurable eight-second
  continuation deadline. Selecting a new unfinished cell cancels the deadline;
  filling it starts a new one. Four full cells commit immediately.
- Commitment atomically copies the ordered cells to `launch_generators`, locks
  further battery/energy changes, records the charge end time, and emits
  `LAUNCH_COMMITTED` after the last fill event.
- Physical sensor presence continues to be tracked during the animation.
- Sensors held across the automatic reset are disarmed until their next low
  state. Newly presented sensors remain immediately eligible.

The renderer reads immutable `GameSnapshot` objects and consumes ordered
`MissionEvent` objects. Gauge animation and visual completion never determine
gameplay state.

## Presentation state machine

`RocketScene` currently has nine phases:

1. `ATTRACT` — rotating textured Earth, star field, and the start of the opening
   approach; after a completed mission this is also the restored idle state.
2. `CRASH` — Earth zoom toward Ōmagari followed by a staged cockpit
   power-failure, alarm, target-lock, and impact sequence.
3. `REVEAL` — transition from the Ablic/logo view down to the night city and
   grounded rocket after the first valid selection.
4. `CHARGING` — ordered battery cells, mission messages, rocket ports, charge
   cues, city, grass, comets, and generator-specific completion shows.
5. `IGNITION` — tiered ground shake, plume, sparks, lighting, and rocket wash.
6. `ASCENT` — accelerating rocket with camera tracking, boosted sky events,
   fireworks, exhaust, dust, and shake.
7. `DEPARTURE` — 3.6 seconds of tracked follow-through and gradual camera
   release.
8. `RECORD_HOLD` — frozen high-altitude scene beneath name entry and leaderboard
   overlays.
9. `RETURN` — reverses the scene, transitions through the Earth/star return, and
   requests a fresh mission once the restored attract state is ready.

Two-, three-, and four-cell launch tiers use 4+8, 5+10, and 6+12 seconds of
ignition plus ascent, respectively, followed by the shared departure. Larger
tiers increase emission rate, plume layers, fireworks, source-color variety,
dust, audio intensity, and screen shake. The two-cell tier is already the full
spectacle baseline.

`GaugeManager` animates insertion, removal, and reflow in a centered,
double-bordered battery. Cell colors are Wind cyan, Solar yellow, Hand Crank
orange, and Coil lime. `PixelFont` supplies production mission lettering from a
code-defined 5×5 bitmap alphabet. Pygame system fonts are still used by editor,
debug, name-entry, and leaderboard UI.

The rocket exposes four recessed ports in battery order. One completed cell
produces a small pulse, micro-tremble, and sparse nozzle leak; the second and
third cue profiles increase nonlinearly. These effects share the foreground
particle and lighting path.

## Rendering and performance budgets

`FireworkManager` owns a 10,000-slot NumPy `ParticleSystem`. Firework shells,
trails, rocket flame, smoke, sparks, scene effects, stars, and comet effects use
the ModernGL rendering pipeline. Particle heads remain visible at peaks;
decorative trail history is capped at 4,000 GPU instances, and head glow scales
down only above 3,200 simultaneous heads.

The renderer samples at most 12 firework heads and eight exhaust heads as light
probes. Fireworks light city, rocket, grass, and ground. Exhaust probes are
limited to the rocket and foreground. Fireworks occupy a world-anchored plane
between the far and near city layers so camera movement gives them intermediate
parallax.

Static far-city and residential geometry is rasterized once into GPU textures;
dynamic light overlays remain separate. Grass segments, ground marks, and city
washes are batched. Material-light queries are vectorized with NumPy. The Earth
asset is projected and lit on a tessellated GPU sphere from its equirectangular
texture; the opening targets Ōmagari at 39.453083 N, 140.475444 E.

Fireworks use an independent high-luminance palette and additive blending.
Invalid/black color indices resolve to white. Burst centers add a broad white
bloom and crisp core. Four generator scripts contain six events over 3.15
seconds, while `launch.json` contains eight events over four seconds. Concurrent
shows are allowed; a full pool safely drops new particles.

The adaptive Pi budget monitors measured FPS. One sustained second below 55 FPS
reduces decorative rocket emission in 10% steps down to 50%. Three sustained
seconds above 58 FPS restore it gradually. Game state, timers, rocket motion,
messages, and authored firework timing are not degraded.

## Audio

`AudioSystem` loads the ambient Ogg loop and prerecorded firework WAV variants.
It synthesizes interface, Hall selection/removal, fill, launch, thrust, return,
and cockpit samples once during startup. Cockpit audio includes zoom, power
failure, a looping alarm, target lock, and impact. Runtime playback reuses these
samples and dedicated channels rather than allocating audio arrays per frame.

## Rankings and persistence

Rankings are enabled by default. At departure completion, the engine enters
`RECORD_HOLD`, accepts or skips a player name, and shows results for the exact
ordered loadout. Total time ends at launch commitment; per-cell timing spans
each cell's active filling interval.

`leaderboard.json` uses schema version 2 with ordered generators, total time,
timestamp, and per-cell durations. Version 1 grouped and flat leaderboard forms
load as preserved one-cell legacy records. Player names are normalized
case-insensitively and stored in `players_database.json` for suggestions.
Provisional results are committed only after confirmation.

Both JSON stores use atomic replacement. Parse failures mark the corresponding
store unsafe and prevent a later empty state from overwriting recoverable data.
Diagnostics append to `clean_boost_test.log` and `hall_ic_debug.log` in the
repository/deployment root.

## Resources

Runtime resources are resolved from the source location rather than the caller's
working directory:

- `resource/audio/` — ambient loop and firework recordings
- `resource/images/` — NASA-derived 2048×1024 Earth map
- `resource/firework-scripts/` — timed cell and launch shows
- `resource/firework-settings/` — reusable firework definitions
- `resource/drone-pattern/` — metadata plus ASCII formations

Deploy `src/` and `resource/` together. The process user needs access to
Bluetooth, GPIO, the graphical display, audio, and write permission in the
deployment root for rankings and logs.

## Validation

Non-graphical checks:

```bash
python -m compileall -q src
PYTHONPATH=src python -c 'import pi.main; import pi.logic.game_state'
```

Optional local tests (the repository intentionally ignores `tests/`):

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Interactive mock check:

```bash
./run.sh --debug
```

The production validation baseline is the tested Raspberry Pi 5 2 GB system at
1920×1080. Hardware checks should exercise all four BLE mappings, all four Hall
inputs, PWM output, audio channels, ranking persistence, the complete opening
and return cutscenes, and sustained hardware-accelerated rendering.
