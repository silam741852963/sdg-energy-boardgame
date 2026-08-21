# SDG Energy Boardgame

A hardware–software board game for teaching sustainable energy concepts. Players
move one magnet between micro-energy generators, reserving two to four completed
cells in one on-screen battery to launch Sot-kun's rocket home.

The application targets a 2 GB Raspberry Pi 5 connected to CleanBoost BLE beacons and
Hall-effect sensors, but every input can be mocked for development on another
Linux computer.

## Features

- Wind, solar, hand-crank, and coil generator modes
- BLE energy input from four configured CleanBoost devices
- GPIO Hall-effect selection with automatic GPIO fallback
- Full-HD Pygame and ModernGL interface with GPU particle effects
- A parallax night city, bright red-and-white textured rocket, compact cell fireworks, and particle-lit launch effects
- Retained personal-best code behind a disabled runtime feature flag
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
and continues with mocked Hall input. In mocked Hall mode, keys `1`–`4` move one
virtual magnet between Wind, Solar, Hand Crank, and Coil; pressing the active key
lifts it. In mocked BLE mode, `Q`, `W`, `E`, and `R`
charge those matching cells. `0` clears all mocked Hall selections, `Backspace`
resets, `M` toggles metrics, and `Esc` quits. Mock energy is manual and
deterministic; it is never generated randomly.

## Hardware configuration

Generator definitions, CleanBoost MAC addresses, gauge limits, and fill rates are
in [`src/pi/config.py`](src/pi/config.py).

Default BCM Hall sensor pins:

| Generator | BCM pin |
| --- | ---: |
| Wind | 17 |
| Solar | 27 |
| Hand Crank | 22 |
| Coil | 23 |

The PWM square wave uses BCM pin 2 at 1 kHz and 50% duty cycle. GPIO is 3.3 V;
external level conversion is required for 5 V hardware. Pin mapping and active
polarity are configured in [`receiver_wire.py`](src/pi/hardware/receiver_wire.py).

## Game behavior

1. With no Hall sensors selected, Ablic floats over a procedural star field.
2. The first selected sensor pans down to the grounded rocket and adds its colored
   cell to the battery. Each generator plays a distinct rising confirmation tone;
   removal plays its descending counterpart.
3. Fill that cell to 100%, then move the same magnet to another sensor. A full
   cell remains in the battery with all its energy; leaving an unfinished cell
   removes it and discards only its partial energy. Up to four full cells can be
   reserved in order.
4. Matching CleanBoost advertisements animate into their selected cell over 0.3
   seconds. Energy does not drain.
5. Each cell reaching 100% plays an extended generator-colored firework sequence.
   Four recessed ports on the rocket light in the completed generators' colors.
   The first full cell starts a barely visible micro-tremble and sparse, small
   nozzle leak. The second stage is clearly active, while the third becomes
   dramatically denser, brighter, longer-lived, and more energetic.
6. At two and three full cells, an eight-second on-screen countdown lets the
   player move the magnet to an optional next cell. A new Hall selection cancels
   the countdown immediately. Four full cells launch without another wait.
7. When the countdown expires, the battery atomically locks. Two-cell launches
   use the former four-cell spectacle as their baseline; three- and four-cell
   launches add progressively richer exhaust, fireworks, impact, and shake.
   Their launch animations last approximately 14.2, 17.2, and 20.2 seconds.
8. The camera follows the rocket high above the initial scene, then automatically
   returns to Ablic. The next mission unlocks as soon as the logo returns, with
   the rocket restored to its launch base. A magnet held through reset must be
   removed and presented again; newly presented magnets respond immediately. A
   ready chime confirms that the screen is interactive again.

Rankings are disabled by `RANKINGS_ENABLED = False`: production does not load,
save, or display ranking data. The legacy ranking implementation remains for a
later design.

## Runtime data

The application creates these files in the repository/deployment root as needed:

- `leaderboard.json` — dormant ranking storage when rankings are explicitly enabled
- `players_database.json` — dormant player suggestions when rankings are enabled
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

Run the local regression suite and complete interactive application with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
./run.sh --debug
```

The local `tests/` directory is intentionally ignored by Git. Final GPU, GPIO,
BLE, audio, and sustained 1080p/60 FPS behavior still require validation on the
target Raspberry Pi 5.

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
