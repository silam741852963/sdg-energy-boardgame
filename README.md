# SDG Energy Boardgame

A hardware–software board game for teaching sustainable energy concepts. Players
operate one of four micro-energy generators, select it with a physical dial, and
charge its on-screen gauge. Reaching the target starts a GPU-rendered fireworks
and drone show and records the player's completion time.

The application targets a Raspberry Pi 4 connected to CleanBoost BLE beacons and
Hall-effect sensors, but every input can be mocked for development on another
Linux computer.

## Features

- Wind, solar, piezoelectric, and coil generator modes
- BLE energy input from four configured CleanBoost devices
- GPIO Hall-effect selection with automatic GPIO fallback
- Full-HD Pygame and ModernGL interface with GPU particle effects
- Scripted fireworks, drone patterns, positional audio, and easter eggs
- Per-generator leaderboards and player personal-best handling
- Fully mocked or mixed real/mock development modes

## Requirements

- Python 3.10 or newer
- A working OpenGL context (OpenGL 3.3-capable drivers recommended)
- Linux Bluetooth/BlueZ for real BLE operation
- Raspberry Pi GPIO support for real Hall sensors and PWM output
- Audio output supported by SDL/Pygame

On a minimal Raspberry Pi OS installation, system packages for Bluetooth,
OpenGL, SDL, audio, and Python virtual environments may also be required. Their
exact names vary by OS release.

## Installation

Clone the repository and create an isolated environment:

```bash
git clone <repository-url> sdg-energy-boardgame
cd sdg-energy-boardgame
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

`pip install -e .` installs the package, dependencies, and the
`sdg-energy-boardgame` command. The legacy `requirements.txt` remains available
for deployment tooling that consumes pinned requirement files directly.

## Running

For development without physical hardware:

```bash
./run.sh --debug
```

For production with BLE, Hall sensors, and PWM:

```bash
./run.sh
```

The launcher is independent of the current working directory. It looks for
`.venv/bin/python`, then `venv/bin/python`, then `python3` on `PATH`. Override the
interpreter when needed:

```bash
SDG_PYTHON=/opt/sdg/venv/bin/python /opt/sdg-energy-boardgame/run.sh
```

An editable installation also provides:

```bash
sdg-energy-boardgame --debug
python -m pi.main --debug
```

### Input modes

| Command | BLE energy | Hall selection / PWM |
| --- | --- | --- |
| `./run.sh` | Real | Real |
| `./run.sh --debug ble` | Mock | Real |
| `./run.sh --debug hall-ic` | Real | Mock/disabled |
| `./run.sh --debug` or `--debug all` | Mock | Mock/disabled |

If GPIO initialization fails in a real-Hall mode, the application logs a warning
and continues with Hall input disabled. In fully mocked mode, the active generator
can be selected through the graphical controls and BLE signals are generated at
random intervals.

## Hardware configuration

Generator definitions, CleanBoost MAC addresses, gauge limits, and fill rates are
in [`src/pi/config.py`](src/pi/config.py).

Default BCM Hall sensor pins:

| Generator | BCM pin |
| --- | ---: |
| Wind | 17 |
| Solar | 27 |
| Piezoelectric | 22 |
| Coil | 23 |

The PWM square wave uses BCM pin 2 at 1 kHz and 50% duty cycle. GPIO is 3.3 V;
external level conversion is required for 5 V hardware. Pin mapping and active
polarity are configured in [`receiver_wire.py`](src/pi/hardware/receiver_wire.py).

## Game behavior

1. A Hall sensor selects the generator and starts its timer.
2. A matching CleanBoost advertisement adds generator-specific energy.
3. Energy is animated into the gauge over 0.3 seconds.
4. A gauge reaching 100 completes the session and stores a ranking.
5. The UI runs the associated fireworks and drone celebration.

Changing generators clears the previously selected unfinished gauge. A non-zero
gauge begins draining after 55 seconds without an increase, and selection returns
to neutral after 60 seconds without activity.

### Ultimate Firework Forge

An all-time generator record or returning player's personal best starts a short
interactive finale using the same four Hall positions. First-time players do not
trigger it. All-time records are known immediately; personal bests start only
after player confirms existing name. Player chooses shape, palette, and special
effect; every result launches exactly five capped ultra fireworks in sequence
from left to right. Drone patterns animate out when Forge starts, remain absent
during its presentation, then animate back into their saved pattern afterward.
Inactivity selects varied defaults, so no failure state or timing minigame.

In mocked Hall mode, hold number keys `1` through `4` for Wind, Solar, Piezo, and
Coil. Release or move between positions to create distinct input transitions.
Each choice adds a persistent glowing ring to the central launch core using the
generator's consistent color: cyan Wind, yellow Solar, orange Piezo, and lime
Coil. After the third ring forms, the forge interface disappears and the normal
show becomes fully visible. The three rings descend together toward the bottom of
the screen, slowly lose their glow as stored energy is spent, and launch the
complete five-firework sequence from their final position. Rings use the same
additive soft-particle texture as fireworks. All five shells leave the shared ring
center, target 10% through 90% of screen width, and remain 0.8 seconds apart. The
rings smoothly fade to near invisibility across the unchanged launch phase. Shape
controls altitude while palette and effect selections apply to every instance.

Launch the isolated presentation while developing the forge with:

```bash
./run.sh --ultimate-debug
```

This mode mocks hardware, pauses energy generation, plays a normal-show prelude,
then starts the forge. It does not complete a session or write leaderboard/player
data. Press `R` to clear the presentation and replay it. Choice windows are three
seconds and all unattended choices receive safe visual defaults.

Production can keep normal generator shows while disabling forge interaction:

```bash
./run.sh --disable-ultimate
```

Forge selection phases last ten seconds. Configuration is intentionally text-free:
screen dimming and four generator-colored rings/energy lines fade in together once,
without restarting between phases. Each selection sends bright pulse along chosen
line into center core. Custom hero
shapes include three-arm Galaxy, five-point Star, Heart, and Diamond.

Generator scripts receive one constrained variation per run: original, horizontal
mirror, faster cadence, or an authored palette rotation. Script authors may also
schedule `begin_ultimate_forge`, `launch_ultimate`, or `launch_custom` actions;
existing scripts require no changes because record finales start automatically.

## Runtime data

The application creates these files in the repository/deployment root as needed:

- `leaderboard.json` — rankings grouped by generator
- `players_database.json` — saved player-name suggestions
- `clean_boost_test.log` — CleanBoost test statistics
- `hall_ic_debug.log` — timestamped GPIO transitions

The process user must be able to write to that directory. Back up the JSON files
if rankings must survive a redeployment.

## Resources

- `resource/audio/` contains three synthesized WAV variants per exploding firework
  sound role.
- `resource/firework-scripts/` contains timed JSON show definitions.
- `resource/firework-settings/` contains reusable firework specifications.
- `resource/drone-pattern/` contains metadata and ASCII drone formations.

Resource paths are resolved from the installed source location, so launching from
a different working directory is supported. A deployment must retain the
`resource/` directory beside `src/`.

## Development and validation

Compile and import the application without opening a display:

```bash
python -m compileall -q src
PYTHONPATH=src python -c 'import pi.main; import pi.logic.game_state'
```

Run the complete interactive application with `./run.sh --debug`. There is
currently no automated test suite; hardware behavior and the OpenGL presentation
require integration testing on the target installation.

For module responsibilities, threading, state transitions, resource formats, and
deployment notes, see [`docs/architecture.md`](docs/architecture.md).

## Troubleshooting

- **No display/OpenGL context:** run inside a graphical session with current GPU
  drivers; verify SDL is using the intended display.
- **No BLE events:** confirm Bluetooth is enabled, BlueZ permissions are granted,
  and the beacon MAC addresses match `CLEANBOOST_MACS`.
- **GPIO warning:** verify the process is running on a Raspberry Pi with an
  available gpiozero pin factory and sufficient device permissions.
- **No audio:** check the SDL audio device before launch; Pygame initializes audio
  as part of the visual engine.
- **Missing assets:** deploy the whole repository, not only the Python package.
- **Wrong Python:** set `SDG_PYTHON` to the intended virtual-environment Python.

## License

See [`LICENSE`](LICENSE).
