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
used: Solar 10, Wind 20, Coil 5.1, and Hand Crank 5.1 units per accepted beacon.

`WireReceiver` owns four gpiozero `Button` inputs:

| Generator | BCM GPIO |
| --- | ---: |
| Solar | 17 |
| Wind | 27 |
| Coil | 22 |
| Hand Crank | 23 |

The Hall positions follow the canonical presentation order. BLE mappings remain
bound to their configured device addresses independently. The current
configuration uses internal pull-ups, a 50 ms debounce interval,
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
7. `DEPARTURE` — 1.8 seconds of tracked follow-through and gradual camera
   release.
8. `RECORD_HOLD` — frozen high-altitude scene beneath name entry and leaderboard
   overlays.
9. `RETURN` — reverses the scene, transitions through the Earth/star return, and
   requests a fresh mission once the restored attract state is ready.

Two-, three-, and four-cell launch tiers use 2+4, 2.5+5, and 3+6 seconds of
ignition plus ascent, respectively, followed by the shared 1.8-second departure.
The departure, rocket escape, launch firework schedule and lifetime, liftoff
cosmic events, and Earth/star return transition are also halved from their
former durations. Larger
tiers increase emission rate, plume layers, fireworks, source-color variety,
dust, audio intensity, and screen shake. The two-cell tier is already the full
spectacle baseline.

`GaugeManager` animates insertion, removal, and reflow in a centered,
double-bordered battery. Its canonical generator order is Solar, Wind, Coil,
then Hand Crank; cell colors are yellow, cyan, lime, and orange respectively.
`PixelFont` supplies production mission lettering from a
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
seconds, while `launch.json` contains eight events over two seconds. Concurrent
shows are allowed; a full pool safely drops new particles.

The adaptive Pi budget monitors measured FPS. One sustained second below 55 FPS
reduces decorative rocket emission in 10% steps down to 50%. Three sustained
seconds above 58 FPS restore it gradually. Game state, timers, rocket motion,
messages, and authored firework timing are not degraded.

## Implementation hard points

The visual design deliberately combines effects that are expensive on small
hardware: a rotating textured globe, thousands of animated particles, light
that reacts to those particles, and a full-HD presentation. The following table
is a one-slide summary of the main implementation challenges and solutions. The
sections after it document the implementation in detail.

| Hard point | Description | Solution |
| --- | --- | --- |
| **Real-time Earth / リアルタイム地球表現** | Rotate and zoom a textured Earth toward Ōmagari while preserving a convincing spherical shape and lighting. / 地球を滑らかに回転・拡大し、大曲へフォーカスしながら立体感のある光を表現する。 | Build a 96×48 sphere mesh once, retain equirectangular UV coordinates, and perform orientation, texture sampling, diffuse lighting, and rim lighting in GPU shaders. / 96×48分割の球体を一度生成し、正距円筒図法のUVを保持して、向き・テクスチャ・拡散光・リム光をGPUで処理する。 |
| **Large particle system / 大規模パーティクル** | Fireworks, exhaust, smoke, sparks, and trails can rapidly multiply the simulation and draw workload. / 花火、噴射、煙、火花、軌跡によって計算量と描画量が急増する。 | Reuse a fixed 10,000-slot NumPy pool, update active particles in vectorized passes, and render their quads with GPU instancing. Cap decorative trail history at 4,000 instances. / 1万個固定のNumPyプールを再利用し、有効粒子を一括演算してGPUインスタンシングで描画する。装飾用の軌跡は最大4,000個に制限する。 |
| **Particle-driven lighting / パーティクル連動ライティング** | Allow fireworks to illuminate the city, rocket, grass, and ground without evaluating every particle against every object. / 全粒子と全オブジェクトの組み合わせを計算せずに、花火の光を街・ロケット・草・地面へ反映する。 | Select only the brightest 12 firework and eight exhaust probes, calculate point-to-light influence in NumPy batches, and draw batched dynamic overlays over cached scene textures. / 最も明るい花火12個と噴射8個だけを光源にし、NumPyで一括計算して、キャッシュ済み背景へ動的な光レイヤーをまとめて描画する。 |
| **Stable Pi performance / Piでの安定動作** | Keep the full-HD spectacle responsive within the Raspberry Pi 5's CPU, GPU, and 2 GB memory budget. / Raspberry Pi 5のCPU・GPU・2 GBメモリ内でフルHD演出を安定させる。 | Require hardware OpenGL 3.3, cache static work, batch draw calls, bound peak effects, and adapt only decorative rocket emission when measured FPS falls. / OpenGL 3.3のハードウェア描画を必須化し、静的処理のキャッシュ、描画の一括化、ピーク負荷の上限設定、FPSに応じた装飾粒子のみの調整を行う。 |

### Earth construction and flat-map transformation

#### Source texture

`earth-blue-marble-global.jpg` is a 2048×1024 derivative of NASA's Blue
Marble imagery. It is a flat **equirectangular** map: horizontal image position
represents longitude and vertical image position represents latitude. It is not
a photograph of a globe and is not pasted onto a pre-rendered circular image.
The image is loaded lazily, uploaded to one GPU texture, cached, and reused by
both the opening approach and the post-launch return. Horizontal texture repeat
is enabled so the map joins at the ±180-degree longitude seam.

#### Mesh generation

`Renderer._init_buffers()` constructs a unit sphere once when the renderer is
created. The mesh has 96 longitude segments and 48 latitude segments. Including
the duplicate boundary vertices needed for the texture seam and both poles,
this produces:

- `(96 + 1) × (48 + 1) = 4,753` vertices;
- `96 × 48 = 4,608` grid cells;
- two triangles per cell, or 9,216 triangles; and
- three indices per triangle, or 27,648 indices.

For mesh column `column` and row `row`, normalized texture coordinates are:

```text
u = column / 96
v = row / 48
```

The equirectangular coordinates are converted to longitude `lambda` and
latitude `phi`:

```text
lambda = (u - 0.5) * 2*pi       # -180 degrees to +180 degrees
phi    = pi/2 - v*pi            # +90 degrees to -90 degrees
```

Each pair of angles becomes a point `P = (x, y, z)` on a unit sphere:

```text
x = cos(phi) * sin(lambda)
y = sin(phi)
z = cos(phi) * cos(lambda)
```

The original `(u, v)` pair is stored alongside `(x, y, z)`. This association is
the actual "wrapping" operation: a point at a particular longitude and latitude
on the flat map is assigned to the vertex at the same longitude and latitude on
the sphere. The GPU interpolates `(u, v)` across every triangle and uses the
interpolated coordinate to sample the image. No per-frame CPU image warping is
performed.

The important distinction is that **96×48 is the sphere's segmentation, not the
texture resolution**. The sphere uses the full 2048×1024 texture. Increasing the
mesh segmentation makes the silhouette and texture interpolation smoother but
adds vertices; 96×48 is the project's balance between smooth curvature and a
small, static mesh.

#### Choosing the visible location

The renderer does not rebuild or physically rotate the mesh when the camera
target changes. Given a requested center longitude `lambda_c` and latitude
`phi_c`, the CPU calculates three orthonormal view directions:

```text
Center = ( cos(phi_c)*sin(lambda_c),
           sin(phi_c),
           cos(phi_c)*cos(lambda_c) )

East   = ( cos(lambda_c), 0, -sin(lambda_c) )

North  = ( -sin(phi_c)*sin(lambda_c),
            cos(phi_c),
           -sin(phi_c)*cos(lambda_c) )
```

For every sphere vertex, the vertex shader projects its unit-sphere position
onto that basis:

```text
view_x = dot(P, East)
view_y = dot(P, North)
view_z = dot(P, Center)
```

`view_x` and `view_y` locate the vertex inside the globe's screen rectangle:

```text
local_x = 0.5 + view_x * 0.5
local_y = 0.5 - view_y * 0.5
```

The result is an orthographic view of a sphere. `view_z` identifies whether a
fragment faces the viewer; the fragment shader discards fragments for which
`view_z <= 0`. Changing `Center`, `East`, and `North` rotates the visible world
without modifying the vertex buffer. Changing the screen rectangle's width and
height produces the animated zoom.

During the cockpit sequence, `RocketScene` smoothly interpolates from the idle
spin toward Ōmagari, Daisen, Akita at 39.453083° N, 140.475444° E. Angle
interpolation keeps moving forward across wrapped longitudes rather than jumping
at the map seam. The zoom changes the globe's screen-space size and position
relative to the rocket, while the same mesh and texture remain in use.

#### Earth lighting

The fragment shader normalizes the interpolated view-space sphere normal and
computes a diffuse term against the fixed light direction
`normalize(-0.42, 0.34, 0.84)`:

```text
diffuse   = max(0, dot(view_normal, light_direction))
brightness = 0.26 + 0.74 * diffuse
```

The nonzero `0.26` base leaves geographic detail visible on the night side. A
blue rim is added using `(1 - view_normal.z)^2.2`, so it becomes strongest near
the silhouette, and `smoothstep` softens the edge alpha. Texture sampling,
normal interpolation, lighting, back-face removal, and the atmospheric edge are
therefore GPU work. The CPU changes only a few uniforms per frame.

This approach was chosen over calculating inverse trigonometric texture
coordinates for every screen pixel. Longitude and latitude are evaluated once
when the small mesh is created; the rasterizer then performs the interpolation
that it is designed to do efficiently.

### Fixed 10,000-particle pool

#### Data layout and lifecycle

`FireworkManager` creates one `ParticleSystem(10000)`. A particle is not a
separate Python object. Instead, the system uses a structure-of-arrays layout:
`x`, `y`, `z`, velocity, gravity, drag, age, lifetime, intensity, color index,
behavior flags, projection data, and other properties are separate fixed-size
NumPy arrays. Most numeric arrays use 32-bit values, and compact state flags use
Boolean or 8-bit arrays. Three `(10000, 20)` history arrays retain the maximum
20 trail positions per simulation slot.

`free_indices` initially contains every slot. Spawning a particle pops a free
index and writes its initial values into the existing arrays. Expired or faded
particles are marked inactive and their indexes are returned to that list. If a
requested spawn batch does not fit, it is skipped safely rather than growing
the pool.

The pool improves performance in several distinct ways:

1. **Bounded simulation memory.** Core particle storage cannot grow because of
   an unexpectedly dense firework. This is especially important on the 2 GB Pi.
2. **No growing collection of Python particle objects.** Reusing slots avoids
   constructing and destroying thousands of objects and reduces garbage
   collector pressure. Small temporary NumPy arrays are still created for some
   batch operations, so the design does not claim literally zero allocation.
3. **Contiguous batch processing.** Boolean masks select active particles, after
   which age, gravity, drag, velocity, position, intensity, and perspective are
   updated in array operations rather than Python loops over objects.
4. **Predictable worst-case simulation work.** At most 10,000 simulation slots
   can be active. Visual overload degrades by dropping new decorative particles,
   not by exhausting memory or allowing work to grow without limit.

The tradeoff is intentional: when all slots are occupied, a new effect may lose
some particles. Preserving frame pacing and gameplay responsiveness is more
important than preserving every decorative spawn during an exceptional peak.

#### Simulation and perspective

Each update builds masks over the fixed arrays. It increments ages, culls faded
particles, shifts trail history only for particles that have trails, applies
behavior-specific updates, and performs gravity and drag in vectorized passes.
The 3D-to-2D particle projection is:

```text
factor = FOV / (VIEWER_DISTANCE + z)
screen_x = x * factor + SCREEN_WIDTH/2
screen_y = y * factor + SCREEN_HEIGHT/2
```

This inexpensive perspective factor lets one pool support firework depth and
parallax without a separate scene object for each particle.

#### GPU-instanced drawing

Visible particle heads and derived effects are gathered into rows of seven
32-bit floats:

```text
screen_x, screen_y, size, red, green, blue, alpha
```

The initial instance buffer reserves `10000 × 7 × 4 = 280,000` bytes. The
renderer writes the gathered rows to that buffer and makes one instanced draw
using a shared four-vertex glow quad. The vertex shader positions and sizes each
quad; the fragment shader samples a shared glow texture. This replaces a draw
call and geometry setup for every individual particle.

The number of draw instances can exceed the number of simulated particle heads
because trails, glitter, and crackle derive extra quads. The renderer can grow
its instance buffer when required and explicitly releases the replaced GPU
objects. More importantly, decorative trail history is sampled down to at most
4,000 instances. Every live particle head remains visible. When more than 3,200
heads overlap, glow size is reduced by `sqrt(3200 / head_count)` to reduce GPU
fill rate without reducing the number of heads.

Additive blending models fireworks as emitted light and prevents overlapping
glow sprites from producing dark seams. The firework manager explicitly selects
this blend mode before particle drawing so a preceding alpha-blended scene layer
cannot accidentally change the effect.

### Particle-driven scene lighting

A physically complete solution would test every luminous particle against every
building, grass blade, ground mark, and rocket material. That Cartesian product
would be far too expensive, and its cost would be highest at exactly the moment
when the particle system is busiest.

The project instead treats a bounded selection of bright particle heads as
**light probes**:

- candidates must have intensity greater than 0.18;
- candidates are scored by `intensity × max(0.35, radius)`;
- `argpartition` selects the strongest candidates without sorting the entire
  pool;
- at most 12 firework probes and eight rocket/exhaust probes are returned; and
- each probe carries screen position, RGB color, strength, radius, and score.

Firework probes illuminate the city, rocket, grass, and ground. Exhaust probes
are restricted to the rocket and foreground, which prevents a local engine
plume from unrealistically lighting the distant skyline.

Scene materials are sampled in groups. For `P` material points and `L` bounded
light probes, NumPy forms compact `P × L` distance matrices and applies a
quadratic radial falloff:

```text
falloff = max(0, 1 - distance/radius)
weight  = falloff^2 * strength
contribution = light_rgb * weight
```

Nearby heads should read as one luminous firework plume rather than dozens of
independent lamps. Contributions are therefore combined as the strongest
contribution plus 3.5% of their sum, then clipped to the displayable range. This
keeps dense clusters colorful instead of bleaching the scene white.

The batching is significant on the Pi. The previous scalar pattern created
several temporary NumPy arrays for every grass blade, ground mark, or building.
One point/light matrix replaces hundreds of tiny calls per frame. The computed
responses are then emitted as batches of colored rectangles and line segments.

Static and dynamic work are also separated. Far-city and residential facade
geometry, including their fixed windows, is rasterized once into textures. Each
city layer normally needs one textured draw call; only its changing light wash,
roof light, and rim light are rebuilt. Far buildings receive a subdued broad
wash because they face the fireworks, while the near layer receives mostly rim
and roof light because the fireworks sit behind it. This both communicates
depth and avoids redrawing all facade detail every frame.

### Maintaining smooth output on Raspberry Pi 5 with 2 GB

The performance target is a tested Raspberry Pi 5 with 2 GB RAM, a 1920×1080
internal render target, and a main-loop limit of 60 FPS. This is a target and
validation baseline, not a promise that every unrelated Pi configuration or
software driver will deliver identical results.

The renderer requires an OpenGL 3.3 core context and rejects renderer names such
as llvmpipe, softpipe, and swrast. A CPU software rasterizer could technically
produce an image, but it could not sustain this scene at the intended frame
rate. Failing at startup makes a driver/configuration problem visible instead
of silently running the experience at an unusable speed.

The principal safeguards work together:

- **GPU ownership of pixel-heavy work:** textured Earth projection, glow
  sampling, blending, and instanced particle quads execute in shaders.
- **Vectorized CPU work:** NumPy updates particle physics and samples material
  lighting in batches.
- **Bounded peak complexity:** the simulation has 10,000 slots, trail history
  contributes at most 4,000 decorative instances, and lighting uses only 20
  probes in its two source groups.
- **Cached static work:** the Earth texture, sphere buffers, city textures,
  reusable quad geometry, audio samples, and active text textures are reused.
  Text textures not used in the current frame are released to prevent an
  unbounded VRAM cache.
- **Batched scene geometry:** grass lines, ground marks, city washes, and other
  repeated colored primitives are submitted in groups rather than as hundreds
  of individual draw calls.
- **Fill-rate protection:** particle glow sizes shrink only during very dense
  peaks, preserving visible heads while reducing the number of screen pixels
  blended repeatedly.

Finally, `RocketScene._update_adaptive_density()` measures actual FPS and
adjusts only the decorative rocket emission rate:

- after one continuous second below 55 FPS, emission falls by 10 percentage
  points;
- repeated slow intervals can reduce it to a floor of 50%;
- after three continuous seconds above 58 FPS, it recovers by five percentage
  points; and
- the stable 55–58 FPS band resets both timers, preventing rapid oscillation.

This is graceful degradation: the player may see fewer exhaust or decorative
rocket particles under sustained load, but game state, battery rules, timers,
rocket trajectory, authored firework event timing, messages, and input handling
are unchanged. Performance protection therefore cannot alter a result or make
the mission mechanically easier or harder.

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
