# Architecture

## System overview

The application joins asynchronous hardware input with a synchronous real-time
renderer through one shared `GameState` instance.

```text
CleanBoost BLE ──> BLEReceiver ───────┐
                                      │
Hall sensors ────> WireReceiver ──────┼──> GameState ──> GaugeManager
                                      │         │
Mock BLE ────────> MockReceiver ──────┘         └──────> FireworkEngine
                                                               │
                         audio / particles / lights / drones <--┘
```

`pi.main` owns process startup. It constructs the state, starts an asyncio event
loop in a daemon thread for receivers, and runs Pygame/ModernGL in the main thread,
as required by typical windowing and graphics stacks.

## Package layout

```text
src/pi/
├── main.py                 Process entry point and mode selection
├── config.py               Generator identities, MACs, and balance constants
├── hardware/
│   ├── receiver_ble.py     Bleak advertisement receiver
│   ├── receiver_mock.py    Random development energy source
│   ├── receiver_wire.py    Hall-effect GPIO input
│   ├── pwm_out.py          Continuous hardware PWM output
│   └── signal_scan.py      Standalone BLE diagnostic scanner
├── logic/
│   ├── game_state.py       Game rules, persistence, combinations, session state
│   ├── models.py           Session and ranking data classes
│   └── smooth_fill.py      Time-based gauge interpolation
└── ui/
    ├── cli_render.py       Alternative terminal-oriented rendering primitives
    └── fireworks/          Interactive GPU presentation and simulation
```

The `pi` package uses explicit relative imports internally. It can therefore be
installed normally, invoked with `python -m pi.main`, or loaded with `src` on
`PYTHONPATH` without depending on the caller's working directory.

## Startup lifecycle

1. `main()` parses `--debug [ble|hall-ic|all]`.
2. Real GPIO availability is checked when Hall input was requested. Failure
   downgrades Hall input to mock/disabled mode.
3. A `GameState` and initial `PlayerSession` are created.
4. A background thread creates its own asyncio event loop.
5. BLE/mock scanning and, when enabled, GPIO listening and PWM run as concurrent
   asyncio tasks.
6. The main thread creates `FireworkEngine` and enters its frame loop.
7. Closing the UI terminates the process; receiver tasks are daemon-thread work.

## Domain state and rules

`GameState` is the authoritative model. It contains:

- current session, active generator, and active Hall sensors;
- four energy levels and their last-increase timestamps;
- smooth fill operations;
- per-generator ranking entries and current provisional entry;
- player-name database access;
- inactivity, combination, and Simon Says state;
- test-mode CleanBoost samples.

Only energy matching `active_generator` is accepted. With
`CLEANBOOST_TEST_MODE=True`, only calls marked as CleanBoost input can add energy,
and each generator uses its configured per-beacon amount. Accepted BLE energy is
queued in `SmoothFiller`, which applies it over 0.3 seconds and caps it at
`MAX_ENERGY_GAUGE`.

Completion is triggered when any individual gauge reaches the maximum. The state
records elapsed time, writes a provisional ranking, and lets the UI request or
update the player's name. Existing entries for that player and generator are
replaced only by a faster time.

### Timing rules

- Selecting a generator starts/restarts session timing.
- Changing selection clears the prior unfinished generator gauge.
- After 55 seconds without an increase, a non-zero gauge drains at 5 units/second.
- After 60 seconds without activity, selection returns to neutral.
- Pausing drain refreshes drain timers so paused time is not accumulated.

## Concurrency model

The hardware thread and render thread share `GameState` directly. CPython makes
individual reference and basic container operations memory-safe, but compound
state transitions are not protected by locks. Current writers perform short,
non-blocking operations, and the UI tolerates frame-to-frame changes. Future work
that introduces additional writers, long transactions, or another Python runtime
should add an event queue or explicit synchronization.

GPIO callbacks can originate outside the asyncio loop. `WireReceiver` uses
`loop.call_soon_threadsafe()` to move the complete sensor scan onto its receiver
loop before updating state.

## Hardware adapters

### BLE

`BLEReceiver` uses Bleak's continuous scanner callback. Known device addresses map
to `GeneratorType` in `config.CLEANBOOST_MACS`; unknown advertisements are ignored.
Each accepted advertisement calls `GameState.add_energy(..., is_clean_boost=True)`.

### Hall sensors

`WireReceiver` creates four gpiozero `Button` devices. Both press and release
callbacks rescan every sensor, which supports simultaneous active inputs while
using the first active sensor as the selected generator. Pull direction, active
state, debounce interval, and BCM pins are defined in the module.

### PWM

`PWMController` maintains a 1 kHz, 50%-duty signal on BCM pin 2 until cancellation.
The device is closed in the task's `finally` block.

## Presentation subsystem

`FireworkEngine` coordinates the following components:

- `Renderer`: ModernGL shaders, instanced particles, primitives, and text cache
- `FireworkManager`: shell launch, vectorized particle simulation, and explosion
- `GaugeManager`: visual projection of domain energy and selected generator
- `DroneManager`: parses and animates ASCII formation resources
- `ScriptManager`: schedules JSON firework events against wall-clock time
- `LightingSystem`: sky flashes and ground reflections
- `AudioSystem`: synthesized samples, spatial panning, and generated UI tones
- `ControlPanel`: mouse and keyboard customization UI
- `UltimateFireworkForge`: record presentation, four-input choices, persistent
  colored energy core, and the capped five-instance finale

The simulation uses NumPy arrays for high particle counts and ModernGL instancing
for rendering. `SCREEN_WIDTH`, `SCREEN_HEIGHT`, and `FULLSCREEN` are currently
source configuration in `ui/fireworks/config.py`.

## Resource formats

### Firework scripts

Files under `resource/firework-scripts/` contain an `events` array. Each event has
a `time` in seconds and may specify type, position, colors, particle count,
radius, gravity, drag, lifetime, intensity, and speed variance. `ScriptManager`
sorts events and launches every event whose scheduled time has passed.

Each playback may apply one bounded variation to the source events: original,
horizontal mirroring, 12% faster cadence, or palette rotation. The source JSON is
never modified. Events with an `action` field are routed to the engine rather than
launched as shells. Supported finale actions are:

```json
{"time": 2.0, "action": "begin_ultimate_forge", "duration": 8.0}
{"time": 12.0, "action": "launch_ultimate"}
{"time": 12.0, "action": "launch_custom", "source": "ultimate_firework"}
```

### Ultimate finale state

Forge starts for provisional position one only when generator already had a prior
ranking. First-ever entry is excluded. Returning-player personal best is evaluated
by `update_player_name()` after name confirmation; leaderboard waits for that
finale to finish.

`GameState.update_player_name()` is the authoritative ranking decision. It returns
a `RankingResult` containing run time, prior best, improvement, retained status,
and final personal rank. Names use collapsed whitespace and case-insensitive
identity. Loading removes invalid times and duplicate player records, retaining
each player's fastest result. Ranking and player databases use atomic replacement
to avoid partial JSON writes.

```text
RECORD_REVEAL -> CHOOSE_SHAPE -> CHOOSE_PALETTE -> CHOOSE_EFFECT
              -> LOCK_IN -> LAUNCH -> COMPLETE
```

Only stable transitions into a Hall position count. Choice phases are text-free,
fade four glowing options alongside screen dimming once, then time out after ten
seconds and choose
non-repeating defaults. There is no timing or failure
phase: shape, three-color palette, and effect behavior are always composed within
hard caps of 650 particles per shell, 3.4 radius, and 3.5
intensity. Each choice adds a cyan/yellow/orange/lime generator ring to the core.
Each lock also animates a bright particle head and fading trail from option ring
along energy line into core. Final lock holds rings stationary for 1.6 seconds so
its enlarged impact bloom completes before downward launch movement begins.
The rings and connecting geometry use broad layered alpha halos. After the third
choice, every prompt, container, and dim overlay is removed. The three rings move
downward as their halo and core intensity decay, and the shells launch from that
moving core. Ring bloom also uses `Renderer.draw_particles`, matching firework
glow texture and additive blending. Five identical Ultimate instances leave the
shared ring center and target 10%, 30%, 50%, 70%, and 90% of screen width, ordered
left to right at 0.8-second intervals. Rings use a smooth 11.5-second fade ending
near invisibility. Shape chooses shared altitude; palette and effect selections
apply to every instance. Drones use their normal exit animation when Forge starts,
remain absent during active phases, then use their normal enter animation to
restore saved pattern and uniform override color. The normal authored show is
unobstructed.
The record flow waits 3.5 seconds after show playback begins before fading into
the forge. Its launch phase returns to the normal background immediately, lowers
the selected energy rings to the launch position, then emits five ultra shells
sequentially across the screen.

`--ultimate-debug` forces both inputs to mock mode, pauses mock energy and drain,
and drives the normal-show/forge presentation from dedicated engine timers. It
never completes `PlayerSession`, calls ranking persistence, or updates the player
database. `R` resets only the in-memory preview lifecycle and starts it again.
`--disable-ultimate` bypasses record/script forge activation while retaining normal
production fireworks, leaderboard, and player flow. It cannot be combined with
`--ultimate-debug`.

Forge hero shapes use custom vectorized burst strategies: three-arm parametric
Galaxy, five-point Star, Heart, and Diamond. These change actual particle velocity
geometry; effect selection separately changes launch choreography.

### Firework settings

Files under `resource/firework-settings/` hold custom/easter-egg specifications
loaded by the engine. Code-defined defaults are used if a settings file is absent
or invalid.

### Drone patterns

Drone `.txt` files may begin with JSON metadata, followed by a line containing
`===`, followed by an ASCII grid. Characters map to named colors; whitespace is
empty formation space.

## Persistence and observability

Paths are derived from the source/deployment root rather than the current working
directory.

| File | Writer | Purpose |
| --- | --- | --- |
| `leaderboard.json` | `GameState` | Rankings grouped by generator enum name |
| `players_database.json` | `GameState` | Case-insensitive player suggestions |
| `clean_boost_test.log` | `GameState` | Rewritten statistical signal report |
| `hall_ic_debug.log` | `WireReceiver` | Appended GPIO transition log |

The UI also includes FPS, process CPU, and resident-memory metrics for interactive
diagnostics.

## Deployment

`run.sh` discovers its own directory, chooses an interpreter, prepends `src` to
`PYTHONPATH`, changes to the deployment root, and replaces itself with
`python -m pi.main`. This makes systemd, desktop autostart, SSH, and arbitrary
working directories behave consistently.

A system service should:

- run as a user with Bluetooth, input/GPIO, display, audio, and deployment-write
  permissions;
- set display/audio session variables appropriate to the OS;
- use an absolute `ExecStart=/path/to/repository/run.sh`;
- set `SDG_PYTHON` if the environment is outside `.venv` or `venv`;
- restart on failure and preserve/back up runtime JSON data.

Do not copy only an installed wheel for production: the application expects the
repository-level `resource/` directory. Keep source and resources together, or
introduce package-data installation before adopting wheel-only deployment.

## Known constraints

- There is no automated unit or integration test suite.
- Game configuration is Python source rather than environment/file configuration.
- The shared state has no explicit concurrency synchronization.
- Runtime state is stored beside the application rather than in a configurable
  data directory.
- Fullscreen resolution is source-configured, although the engine queries the
  actual desktop size when opening the window.
- Shutdown relies on daemon-thread termination rather than coordinated receiver
  cancellation.

These are the principal areas to address if the project evolves from a dedicated
installation into a distributable multi-environment application.
