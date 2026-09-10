# SDG Energy Boardgame

A hardware–software board game for teaching sustainable energy concepts. Players
move Sot-kun, a magnetic selector, between four micro-energy generators and fill
two to four cells in an on-screen battery to launch Sot-kun's rocket home.

The target and tested deployment platform is a **Raspberry Pi 5 with 2 GB of
RAM**, connected to four CleanBoost BLE beacons, four Hall-effect sensors, a PWM
output, a 1920×1080 display, and audio. BLE and Hall input can also be mocked for
development on another Linux computer.

## What the application does

- Supports wind, solar, hand-crank, and coil generators.
- Receives energy from four configured CleanBoost BLE devices.
- Uses four GPIO Hall-effect inputs to follow the movable Sot-kun selector.
- Drives a 1 kHz, 50% duty-cycle PWM square wave while real GPIO is enabled.
- Renders a full-HD Pygame/ModernGL experience with GPU particles, lighting,
  parallax scenery, a cockpit crash introduction, tiered rocket launches, and a
  GPU-rendered Earth return focused on Ōmagari, Akita.
- Stores personal bests by exact battery loadout; rankings are enabled by
  default.
- Supports fully mocked and mixed real/mock input modes.

## Tested platform and requirements

The production configuration has been tested on a **2 GB Raspberry Pi 5** at
1920×1080 and 60 FPS. The renderer requires a hardware-accelerated OpenGL 3.3
core context and deliberately rejects software renderers such as llvmpipe,
softpipe, and swrast.

Software requirements:

- Python 3.10 or newer
- Linux Bluetooth/BlueZ for real BLE input
- Raspberry Pi GPIO support for real Hall sensors and PWM output
- An SDL/Pygame-compatible display and audio device
- The Python packages pinned in `pyproject.toml`

On a minimal Raspberry Pi OS installation, install the OS packages that provide
Bluetooth, Mesa/OpenGL, SDL audio/video, GPIO access, and Python virtual
environments. Package names vary by Raspberry Pi OS release.

## Installation

```bash
git clone <repository-url> sdg-energy-boardgame
cd sdg-energy-boardgame
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

The editable install provides the `sdg-energy-boardgame` command. `pyproject.toml`
is the package definition and direct dependency source; `requirements.txt` is a
pinned deployment snapshot that also includes transitive packages.

## Running

Run with real BLE, Hall sensors, and PWM:

```bash
./run.sh
```

Run without physical input hardware:

```bash
./run.sh --debug
```

The launcher resolves the repository root, prefers `.venv/bin/python`, then
`venv/bin/python`, and finally `python3` on `PATH`. Set `SDG_PYTHON` to select an
explicit interpreter:

```bash
SDG_PYTHON=/opt/sdg/venv/bin/python /opt/sdg-energy-boardgame/run.sh
```

An editable installation also supports:

```bash
sdg-energy-boardgame --debug
python -m pi.main --debug
```

### Input modes

| Command | BLE energy | Hall selection | PWM |
| --- | --- | --- | --- |
| `./run.sh` | Real | Real | Enabled |
| `./run.sh --debug ble` | Mock | Real | Enabled |
| `./run.sh --debug hall-ic` | Real | Mock | Disabled |
| `./run.sh --debug` or `--debug all` | Mock | Mock | Disabled |

If GPIO initialization fails in a real-Hall mode, the application warns and
continues with mocked Hall input; PWM is disabled with it.

Mock controls:

| Key | Action |
| --- | --- |
| `1` / `2` / `3` / `4` | Move Sot-kun to Solar / Wind / Coil / Hand Crank; press the active key again to lift it |
| `Q` / `W` / `E` / `R` | Add energy to Solar / Wind / Coil / Hand Crank when mock BLE is active |
| `0` | Clear the mocked Hall selection |
| `Backspace` | Reset the mission |
| `M` | Toggle performance metrics |
| `F5` | Export the current firework specification in fully mocked mode |
| `Esc` | Close an overlay or quit |

Mock energy is manual and deterministic; it is not generated randomly.
Hall changes and energy input are ignored while a cutscene or ranking screen is
active. Input becomes available only in the settled attract and charging views.

## Hardware configuration

Generator definitions, CleanBoost MAC addresses, energy limits, and per-beacon
fill amounts are in [`src/pi/config.py`](src/pi/config.py).

Default BCM Hall sensor pins:

| Generator | BCM pin |
| --- | ---: |
| Solar | 17 |
| Wind | 27 |
| Coil | 22 |
| Hand Crank | 23 |

Hall inputs currently use gpiozero `Button` objects with internal pull-ups,
50 ms debounce, and active detection through `is_pressed`. Pin mapping and
polarity are defined in
[`receiver_wire.py`](src/pi/hardware/receiver_wire.py).

PWM uses BCM pin 2 at 1 kHz and 50% duty cycle. Raspberry Pi GPIO is 3.3 V;
external level conversion is required for 5 V hardware.

## Mission flow

1. Startup shows a rotating Earth and star field, zooms toward Ōmagari, and
   transitions through a cockpit failure/crash sequence into the Ablic attract
   screen.
2. With no generator selected, Ablic floats over the night city. The first
   comet appears within four seconds; later comets recur after randomized waits.
3. Selecting a Hall sensor reveals the grounded rocket and adds that generator's
   colored cell to the battery. Selection and removal use distinct audio cues.
4. Matching BLE advertisements fill only a currently selected cell. CleanBoost
   fills animate over 0.3 seconds, and energy never drains.
5. Moving Sot-kun away from an unfinished cell removes it and discards its
   partial energy. A 100% cell remains reserved in its original order. Up to four
   cells can be reserved.
6. Filling a cell triggers a generator-colored firework show and lights a
   matching rocket port. Pre-launch shake and exhaust grow nonlinearly with the
   number of completed cells.
7. Two or three full cells start an eight-second continuation countdown. Moving
   to a new unfinished cell cancels it; four full cells commit immediately.
8. On commitment the battery locks. Two-, three-, and four-cell launches use
   progressively longer and richer ignition/ascent tiers, followed by a
   1.8-second departure. Flying, launch fireworks, liftoff sky effects, rocket
   escape, and the subsequent Earth/star transition run at half their former
   durations.
9. The result overlay accepts or skips a player name and shows rankings for the
   exact cell loadout. The return then reverses the scene back to Earth and
   restores a fresh mission. A selector held through reset must be removed and
   presented again.

## Rankings and runtime data

Rankings are enabled by `RANKINGS_ENABLED = True`. Total time stops when launch
is committed, so launch animation length does not affect the result. The game
keeps one personal best per player and exact ordered battery loadout and records
individual cell times.

The application creates these files in the repository/deployment root as needed:

- `leaderboard.json` — schema-versioned rankings; legacy one-generator records
  are accepted on load
- `players_database.json` — normalized player names used for suggestions
- `clean_boost_test.log` — CleanBoost reception diagnostics
- `hall_ic_debug.log` — timestamped GPIO state scans

Leaderboard and player writes are atomic. A parse error disables overwriting of
the affected file to avoid destroying recoverable data. The process user needs
write permission in the deployment root; back up the JSON files if rankings
must survive redeployment.

## Resources

- `resource/audio/` contains the ambient loop and prerecorded firework WAVs.
  Interface, cockpit, selection, and rocket sounds are synthesized once at
  startup.
- `resource/images/` contains the NASA-derived Earth texture used by the opening
  and return cutscenes.
- `resource/firework-scripts/` contains four six-event cell shows and one
  eight-event launch show.
- `resource/firework-settings/` contains reusable firework specifications.
- `resource/drone-pattern/` contains metadata and ASCII drone formations.

Resource paths are resolved relative to the installed source tree. Deploy
`src/` and `resource/` together.

## Development and validation

Run non-graphical checks with the selected environment's Python:

```bash
python -m compileall -q src
PYTHONPATH=src python -c 'import pi.main; import pi.logic.game_state'
```

If a local, untracked `tests/` directory is present, run it with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

The repository intentionally does not track `tests/`. Use `./run.sh --debug` for
an interactive software-input check. Hardware validation covers BLE reception,
GPIO transitions, PWM, audio, and sustained hardware-accelerated 1080p output on
the tested Raspberry Pi 5 2 GB configuration.

For threading, state ownership, render budgets, persistence, and deployment
details, see [`docs/architecture.md`](docs/architecture.md).

## Troubleshooting

- **Software renderer rejected:** enable the Pi's hardware-accelerated Mesa/V3D
  driver and verify that the graphical session exposes OpenGL 3.3 core.
- **No display/OpenGL context:** run inside a graphical session and verify SDL is
  using the intended 1920×1080 display.
- **No BLE events:** enable Bluetooth, check BlueZ permissions, and confirm the
  device addresses match `CLEANBOOST_MACS`.
- **GPIO warning:** check gpiozero's pin factory, BCM wiring, and device
  permissions. The application falls back to mock Hall input.
- **No audio:** verify the SDL audio device before launch.
- **Missing assets:** deploy the complete repository, especially `resource/`
  beside `src/`.
- **Wrong Python:** set `SDG_PYTHON` to the intended virtual-environment Python.

## License

See [`LICENSE`](LICENSE).
