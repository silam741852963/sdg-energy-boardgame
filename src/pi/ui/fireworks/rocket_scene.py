from dataclasses import dataclass
from enum import Enum, auto
import math
import random

import numpy as np

from .config import (
    LAUNCH_TIER_TIMINGS,
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    SCALE_X,
    SCALE_Y,
)
from . import palette
from ...config import GeneratorType, MAX_ENERGY_GAUGE


class MissionPhase(Enum):
    ATTRACT = auto()
    REVEAL = auto()
    CHARGING = auto()
    IGNITION = auto()
    ASCENT = auto()
    DEPARTURE = auto()
    RETURN = auto()


@dataclass(frozen=True)
class LaunchTier:
    cells: int
    ignition_seconds: float
    ascent_seconds: float
    emission_rate: float
    shake: float
    plume_layers: int


@dataclass
class SceneActions:
    launch_completed: bool = False
    reset_requested: bool = False


TIERS = {
    # Two cells inherit the former four-cell spectacle. Three and four cells
    # build above that baseline while adaptive density protects Pi fill rate.
    2: LaunchTier(2, *LAUNCH_TIER_TIMINGS[2], 250.0, 14.0, 3),
    3: LaunchTier(3, *LAUNCH_TIER_TIMINGS[3], 330.0, 19.0, 4),
    4: LaunchTier(4, *LAUNCH_TIER_TIMINGS[4], 420.0, 25.0, 5),
}

GENERATOR_PARTICLE_COLORS = {
    GeneratorType.WIND: "cyan",
    GeneratorType.SOLAR: "yellow",
    GeneratorType.HAND_CRANK: "orange",
    GeneratorType.COIL: "lime",
}

GENERATOR_STATUS_COLOR_INDICES = {
    GeneratorType.WIND: 61,
    GeneratorType.SOLAR: 31,
    GeneratorType.HAND_CRANK: 11,
    GeneratorType.COIL: 41,
}


class RocketScene:
    REVEAL_SECONDS = 2.0
    DEPARTURE_SECONDS = 2.2

    def __init__(self, firework_manager, audio):
        self.firework_manager = firework_manager
        self.audio = audio
        self.phase = MissionPhase.ATTRACT
        self.scene_progress = 0.0
        self.phase_elapsed = 0.0
        self.launch_tier = None
        self.launch_generators = ()
        self.reserved_generators = ()
        self.rocket_offset_y = 0.0
        self.camera_y = 0.0
        self._return_camera_start = 0.0
        self.emission_scale = 1.0
        self._slow_seconds = 0.0
        self._fast_seconds = 0.0
        self._emission_accumulator = 0.0
        self._prelaunch_emission_accumulator = 0.0
        self._cell_message = None
        self._cell_message_time = 0.0
        self._shockwave_age = None
        self._rng = random.Random(1427)
        self._stars = self._build_stars()
        self._skyscrapers = self._build_city_layer(78, 168, 190, 445, 4181)
        self._homes = self._build_city_layer(132, 238, 105, 235, 6113)
        self._ground_marks = self._build_ground_marks()
        self._grass = self._build_grass()
        self._city_asset_data = {
            False: self._build_city_asset(self._skyscrapers, near=False),
            True: self._build_city_asset(self._homes, near=True),
        }
        self._city_textures = {}

    @property
    def drone_y_offset(self):
        eased = self._ease(self.scene_progress)
        return -1250.0 * SCALE_Y * eased

    @property
    def scene_alpha(self):
        return self._ease(self.scene_progress)

    @property
    def firework_y_offset(self):
        """Fireworks occupy the depth plane between both city layers."""
        return self.camera_y * 0.31

    def screen_shake(self):
        if not self.launch_tier:
            return 0.0, 0.0
        if self.phase is MissionPhase.IGNITION:
            strength = min(1.0, self.phase_elapsed / self.launch_tier.ignition_seconds)
            amount = self.launch_tier.shake * strength * 0.45
        elif self.phase is MissionPhase.ASCENT:
            amount = self.launch_tier.shake * max(0.0, 1.0 - self.phase_elapsed / 1.4)
        else:
            return 0.0, 0.0
        return self._rng.uniform(-amount, amount), self._rng.uniform(-amount, amount)

    @staticmethod
    def _ease(value):
        value = min(1.0, max(0.0, value))
        return value * value * (3.0 - 2.0 * value)

    def _build_stars(self):
        stars = []
        for _ in range(190):
            depth = self._rng.choice((0.25, 0.45, 0.7))
            stars.append(
                (
                    self._rng.uniform(0, SCREEN_WIDTH),
                    self._rng.uniform(0, SCREEN_HEIGHT),
                    self._rng.uniform(2.0, 5.5),
                    self._rng.uniform(0.35, 0.9),
                    depth,
                    self._rng.uniform(0, math.tau),
                )
            )
        return stars

    @staticmethod
    def _build_city_layer(min_width, max_width, min_height, max_height, seed):
        rng = random.Random(seed)
        buildings = []
        x = -max_width
        while x < SCREEN_WIDTH + max_width:
            width = rng.uniform(min_width, max_width) * SCALE_X
            height = rng.uniform(min_height, max_height) * SCALE_Y
            cols = max(2, int(width / (52 * SCALE_X)))
            rows = max(2, int(height / (58 * SCALE_Y)))
            lit = tuple(rng.random() > 0.37 for _ in range(cols * rows))
            roof = rng.choice(("flat", "step", "antenna"))
            buildings.append((x, width, height, cols, rows, lit, roof, rng.random()))
            x += width + rng.uniform(10, 28) * SCALE_X
        return buildings

    @staticmethod
    def _build_ground_marks():
        rng = random.Random(8309)
        return [
            (
                rng.uniform(0, SCREEN_WIDTH),
                rng.uniform(16, 380) * SCALE_Y,
                rng.uniform(7, 34) * SCALE_X,
                rng.choice((0, 1, 2)),
            )
            for _ in range(150)
        ]

    @staticmethod
    def _build_grass():
        rng = random.Random(9917)
        clusters = []
        for _ in range(38):
            center = rng.uniform(0, SCREEN_WIDTH)
            phase = rng.uniform(0.0, math.tau)
            speed = rng.uniform(0.82, 1.18)
            gust = rng.uniform(0.72, 1.25)
            blades = []
            for _ in range(rng.randint(6, 11)):
                blades.append(
                    (
                        rng.uniform(-28, 28) * SCALE_X,
                        rng.uniform(13, 42) * SCALE_Y,
                        rng.uniform(-0.38, 0.38),
                        rng.uniform(2.5, 8.5) * SCALE_X,
                    )
                )
            clusters.append((center, phase, speed, gust, tuple(blades)))
        return clusters

    @staticmethod
    def _facade_base(near, variation):
        if near:
            colors = (
                (0.092, 0.049, 0.057),
                (0.048, 0.076, 0.068),
                (0.069, 0.051, 0.087),
            )
        else:
            colors = (
                (0.031, 0.058, 0.116),
                (0.052, 0.043, 0.105),
                (0.025, 0.071, 0.100),
            )
        return colors[min(2, int(variation * 3))]

    def _build_city_asset(self, buildings, near):
        """Rasterize static facade geometry once; lighting remains dynamic."""
        asset_height = int((300 if near else 530) * SCALE_Y)
        asset_width = int(SCREEN_WIDTH)
        canvas = np.zeros((asset_height, asset_width, 4), dtype=np.uint8)

        def rect(x, y, width, height, color, alpha=255):
            x0 = max(0, int(round(x)))
            y0 = max(0, int(round(y)))
            x1 = min(asset_width, int(round(x + width)))
            y1 = min(asset_height, int(round(y + height)))
            if x1 <= x0 or y1 <= y0:
                return
            canvas[y0:y1, x0:x1, :3] = np.asarray(color, dtype=np.uint8)
            canvas[y0:y1, x0:x1, 3] = alpha

        for x, width, height, cols, rows, lit_windows, roof, variation in buildings:
            if near and x < SCREEN_WIDTH / 2 + 310 * SCALE_X and x + width > SCREEN_WIDTH / 2 - 310 * SCALE_X:
                continue
            y = asset_height - height
            base = self._facade_base(near, variation)
            base_rgb = tuple(int(channel * 255) for channel in base)
            edge_base = (39, 25, 32) if near else (19, 35, 62)
            rect(x, y, width, height, base_rgb)
            rect(x, y, width, max(2, 2 * SCALE_Y), edge_base)
            rect(x, y, max(2, 2 * SCALE_X), height, edge_base)
            rect(x + width - max(2, 2 * SCALE_X), y, max(2, 2 * SCALE_X), height, edge_base)

            for band in range(1, max(2, int(height / (72 * SCALE_Y)))):
                rect(x, y + band * 72 * SCALE_Y, width, max(1, SCALE_Y), edge_base, 205)

            pad_x = 18 * SCALE_X
            pad_y = 24 * SCALE_Y
            win_w = max(8 * SCALE_X, (width - pad_x * 2) / max(1, cols) * 0.42)
            win_h = 12 * SCALE_Y if near else 10 * SCALE_Y
            step_x = (width - pad_x * 2) / max(1, cols)
            step_y = (height - pad_y * 2) / max(1, rows)
            for row in range(rows):
                for col in range(cols):
                    if not lit_windows[row * cols + col]:
                        continue
                    wx = x + pad_x + col * step_x + (step_x - win_w) / 2
                    wy = y + pad_y + row * step_y
                    rect(wx, wy, win_w, win_h, (208, 137, 26))

            if roof == "step":
                rect(x + width * 0.28, y - 18 * SCALE_Y, width * 0.44, 18 * SCALE_Y, base_rgb)
            elif roof == "antenna":
                antenna_x = x + width * 0.5
                antenna_h = (28 + variation * 36) * SCALE_Y
                rect(antenna_x, y - antenna_h, max(1, 2 * SCALE_X), antenna_h, edge_base)

        return asset_width, asset_height, canvas.tobytes()

    def _ensure_city_texture(self, renderer, near):
        texture = self._city_textures.get(near)
        if texture is None:
            width, height, data = self._city_asset_data.pop(near)
            texture = renderer.create_static_texture(width, height, data)
            self._city_textures[near] = (texture, width, height)
        return self._city_textures[near]

    def reset(self):
        self.phase = MissionPhase.ATTRACT
        self.scene_progress = 0.0
        self.phase_elapsed = 0.0
        self.launch_tier = None
        self.launch_generators = ()
        self.reserved_generators = ()
        self.rocket_offset_y = 0.0
        self.camera_y = 0.0
        self._return_camera_start = 0.0
        self._emission_accumulator = 0.0
        self._prelaunch_emission_accumulator = 0.0
        self._cell_message = None
        self._cell_message_time = 0.0
        self._shockwave_age = None
        self.firework_manager.clear_scene_effects()
        self.audio.stop_rocket_thrust()

    def show_cell_ready(self, generator):
        self._cell_message = generator
        self._cell_message_time = 1.6

    def start_launch(self, generators):
        count = min(4, max(2, len(generators)))
        self.launch_tier = TIERS[count]
        self.launch_generators = tuple(generators)
        self.phase = MissionPhase.IGNITION
        self.phase_elapsed = 0.0
        self.scene_progress = 1.0
        self.rocket_offset_y = 0.0
        self.camera_y = 0.0
        self._return_camera_start = 0.0
        self._shockwave_age = None
        self.audio.start_rocket_thrust(count)

    def update(self, snapshot, dt, fps=60.0):
        actions = SceneActions()
        dt = min(0.1, max(0.0, dt))
        self._update_adaptive_density(fps, dt)
        if self._cell_message_time > 0.0:
            self._cell_message_time = max(0.0, self._cell_message_time - dt)

        self.reserved_generators = tuple(
            generator
            for generator in snapshot.selected_generators
            if generator in snapshot.filled_generators
        )

        has_selection = bool(snapshot.selected_generators)
        if self.phase is MissionPhase.ATTRACT:
            if snapshot.launch_committed:
                actions.reset_requested = True
            elif has_selection:
                self.phase = MissionPhase.REVEAL
        if self.phase is MissionPhase.REVEAL:
            if not has_selection:
                self.phase = MissionPhase.RETURN
            else:
                self.scene_progress = min(1.0, self.scene_progress + dt / self.REVEAL_SECONDS)
                if self.scene_progress >= 1.0:
                    self.phase = MissionPhase.CHARGING
        elif self.phase is MissionPhase.CHARGING and not has_selection:
            self.phase = MissionPhase.RETURN
        elif self.phase is MissionPhase.RETURN:
            if has_selection and not snapshot.launch_committed:
                self.phase = MissionPhase.REVEAL
            else:
                self.scene_progress = max(0.0, self.scene_progress - dt / self.REVEAL_SECONDS)
                self.camera_y = self._return_camera_start * self._ease(self.scene_progress)
                if self.scene_progress <= 0.0:
                    self.phase = MissionPhase.ATTRACT
                    self.camera_y = 0.0
                    actions.reset_requested = True

        if (
            self.phase is MissionPhase.CHARGING
            and len(self.reserved_generators) >= 1
            and not snapshot.launch_committed
        ):
            self._emit_prelaunch_vent(dt)

        if self.phase is MissionPhase.IGNITION:
            self.phase_elapsed += dt
            self._emit_exhaust(dt, grounded=True)
            if self.phase_elapsed >= self.launch_tier.ignition_seconds:
                self.phase = MissionPhase.ASCENT
                self.phase_elapsed = 0.0
                self._shockwave_age = 0.0
        elif self.phase is MissionPhase.ASCENT:
            self.phase_elapsed += dt
            progress = min(1.0, self.phase_elapsed / self.launch_tier.ascent_seconds)
            self.rocket_offset_y = -((progress ** 2.15) * (SCREEN_HEIGHT * 3.0))
            desired_follow = max(0.0, -self.rocket_offset_y - 280 * SCALE_Y)
            self.camera_y = desired_follow
            self._emit_exhaust(dt, grounded=False)
            if self._shockwave_age is not None:
                self._shockwave_age += dt
            if progress >= 1.0:
                self.phase = MissionPhase.DEPARTURE
                self.phase_elapsed = 0.0
        elif self.phase is MissionPhase.DEPARTURE:
            self.phase_elapsed += dt
            progress = min(1.0, self.phase_elapsed / self.DEPARTURE_SECONDS)
            self.rocket_offset_y = -(SCREEN_HEIGHT * (3.0 + (progress ** 1.35) * 1.6))
            desired_follow = max(0.0, -self.rocket_offset_y - 280 * SCALE_Y)
            release = self._ease(max(0.0, (progress - 0.55) / 0.45))
            self.camera_y = desired_follow * (1.0 - 0.32 * release)
            if progress < 0.82:
                self._emit_exhaust(dt, grounded=False)
            if progress >= 1.0:
                self.phase = MissionPhase.RETURN
                self._return_camera_start = self.camera_y
                self.audio.stop_rocket_thrust()
                actions.launch_completed = True

        return actions

    def charge_shake(self, frame_count):
        """Return a body-only tremble that grows with reserved charge."""
        count = len(self.reserved_generators)
        if self.phase is not MissionPhase.CHARGING or count < 1:
            return 0.0, 0.0
        amount = 0.58 + (count - 1) * 0.72
        return (
            math.sin(frame_count * 0.71) * amount * SCALE_X,
            math.sin(frame_count * 0.93 + 0.8) * amount * 0.34 * SCALE_Y,
        )

    def _emit_prelaunch_vent(self, dt):
        """Leak low-energy charge particles from the full nozzle width."""
        charge_count = len(self.reserved_generators)
        rate = 6.0 + (charge_count - 1) * 7.0
        self._prelaunch_emission_accumulator += rate * dt
        count = int(self._prelaunch_emission_accumulator)
        self._prelaunch_emission_accumulator -= count
        if count <= 0:
            return

        rocket_x = SCREEN_WIDTH / 2
        tail_half_width = (19 + charge_count * 3) * SCALE_X
        x = np.array(
            [
                rocket_x + self._rng.uniform(-tail_half_width, tail_half_width)
                for _ in range(count)
            ],
            dtype=np.float32,
        )
        y = np.array(
            [805 * SCALE_Y + self._rng.uniform(-2.0, 4.0) * SCALE_Y for _ in range(count)],
            dtype=np.float32,
        )
        vx = np.array(
            [self._rng.uniform(-0.75, 0.75) for _ in range(count)],
            dtype=np.float32,
        )
        vy = np.array(
            [self._rng.uniform(0.8, 2.1 + charge_count * 0.25) for _ in range(count)],
            dtype=np.float32,
        )
        colors = [
            GENERATOR_PARTICLE_COLORS[generator]
            for generator in self.reserved_generators
        ]
        self.firework_manager.emit_scene_effect(
            screen_x=x,
            screen_y=y,
            vx=vx,
            vy=vy,
            colors=colors,
            count=count,
            life=34 + charge_count * 5,
            size=7.0 + charge_count * 1.4,
            gravity=0.018,
            drag=0.045,
            trail_len=1,
            intensity=0.62 + charge_count * 0.08,
        )

    def _update_adaptive_density(self, fps, dt):
        if fps <= 0.0:
            return
        if fps < 55.0:
            self._slow_seconds += dt
            self._fast_seconds = 0.0
            if self._slow_seconds >= 1.0:
                self.emission_scale = max(0.5, self.emission_scale - 0.1)
                self._slow_seconds = 0.0
        elif fps > 58.0:
            self._fast_seconds += dt
            self._slow_seconds = 0.0
            if self._fast_seconds >= 3.0:
                self.emission_scale = min(1.0, self.emission_scale + 0.05)
                self._fast_seconds = 0.0
        else:
            self._slow_seconds = 0.0
            self._fast_seconds = 0.0

    def _emit_exhaust(self, dt, grounded):
        tier = self.launch_tier
        if tier is None:
            return
        rate = tier.emission_rate * self.emission_scale * (0.45 if grounded else 1.0)
        self._emission_accumulator += rate * dt
        count = int(self._emission_accumulator)
        self._emission_accumulator -= count
        if count <= 0:
            return
        count = min(count, 36)
        rocket_x = SCREEN_WIDTH / 2
        exhaust_y = 805 * SCALE_Y + self.rocket_offset_y + self.camera_y
        spread = 1.7 + tier.plume_layers * 0.8
        tail_half_width = (24 + tier.plume_layers * 5) * SCALE_X
        exhaust_x = np.array(
            [rocket_x + self._rng.uniform(-tail_half_width, tail_half_width) for _ in range(count)],
            dtype=np.float32,
        )
        exhaust_origin_y = np.array(
            [exhaust_y + self._rng.uniform(-3.0, 5.0) * SCALE_Y for _ in range(count)],
            dtype=np.float32,
        )
        vx = np.array([self._rng.uniform(-spread, spread) for _ in range(count)], dtype=np.float32)
        base_vy = 2.5 if grounded else 5.0 + tier.plume_layers
        vy = np.array([self._rng.uniform(base_vy * 0.65, base_vy * 1.35) for _ in range(count)], dtype=np.float32)
        colors = ["gold", "orange", "silver"] + [
            GENERATOR_PARTICLE_COLORS[generator] for generator in self.launch_generators
        ]
        self.firework_manager.emit_scene_effect(
            screen_x=exhaust_x,
            screen_y=exhaust_origin_y,
            vx=vx,
            vy=vy,
            colors=colors,
            count=count,
            life=54 + tier.plume_layers * 12,
            size=14.0 + tier.plume_layers * 3.5,
            gravity=0.025,
            drag=0.025,
            trail_len=3 + tier.plume_layers,
            intensity=1.15,
        )
        smoke_count = max(1, count // 6)
        smoke_vx = np.array(
            [self._rng.uniform(-spread * 1.4, spread * 1.4) for _ in range(smoke_count)],
            dtype=np.float32,
        )
        smoke_vy = np.array(
            [self._rng.uniform(0.4, 2.0) for _ in range(smoke_count)],
            dtype=np.float32,
        )
        smoke_x = np.array(
            [rocket_x + self._rng.uniform(-tail_half_width, tail_half_width) for _ in range(smoke_count)],
            dtype=np.float32,
        )
        self.firework_manager.emit_scene_effect(
            screen_x=smoke_x,
            screen_y=exhaust_y + 6 * SCALE_Y,
            vx=smoke_vx,
            vy=smoke_vy,
            colors=["silver", "blue"],
            count=smoke_count,
            life=105,
            size=22.0 + tier.plume_layers * 3.5,
            gravity=-0.008,
            drag=0.035,
            trail_len=0,
            intensity=0.42,
        )
        if grounded and tier.cells >= 3 and count >= 3:
            dust_count = max(1, count // 8)
            self.firework_manager.emit_scene_effect(
                screen_x=rocket_x,
                screen_y=818 * SCALE_Y,
                vx=np.array(
                    [self._rng.uniform(-6.0, 6.0) for _ in range(dust_count)],
                    dtype=np.float32,
                ),
                vy=np.array(
                    [self._rng.uniform(-1.8, -0.3) for _ in range(dust_count)],
                    dtype=np.float32,
                ),
                colors=["gold", "orange"],
                count=dust_count,
                life=72,
                size=13.0,
                gravity=0.035,
                drag=0.045,
                trail_len=2,
                intensity=0.55,
            )

    def draw_stars(self, renderer, frame_count):
        rows = []
        camera_shift = self._ease(self.scene_progress) * 280.0 * SCALE_Y
        for x, y, size, alpha, depth, phase in self._stars:
            draw_y = (y - camera_shift * depth + self.camera_y * depth * 0.055) % SCREEN_HEIGHT
            twinkle = alpha * (0.82 + 0.18 * math.sin(frame_count * 0.035 + phase))
            rows.append((x, draw_y, size, 0.68, 0.78, 1.0, twinkle))
        renderer.draw_particles(np.asarray(rows, dtype=np.float32))

    @staticmethod
    def _sample_lights(points, sources):
        """Sample many scene points in one NumPy pass.

        The previous scalar helper created several temporary arrays per blade,
        ground mark, and building. On a Pi that meant hundreds of tiny NumPy
        calls per frame, which cost far more than one compact point/light matrix.
        """
        points = np.asarray(points, dtype=np.float32).reshape(-1, 2)
        if not len(points):
            return np.empty((0, 3), dtype=np.float32)
        if sources is None or len(sources) == 0:
            return np.zeros((len(points), 3), dtype=np.float32)
        dx = sources[None, :, 0] - points[:, None, 0]
        dy = sources[None, :, 1] - points[:, None, 1]
        radius = np.maximum(1.0, sources[None, :, 6])
        falloff = np.maximum(0.0, 1.0 - np.sqrt(dx * dx + dy * dy) / radius)
        weights = falloff * falloff * sources[None, :, 5]
        contributions = sources[None, :, 2:5] * weights[:, :, None]
        # Nearby particle heads form one luminous plume, not dozens of lamps.
        # A max-weighted blend keeps a dense cluster from bleaching materials.
        color = np.max(contributions, axis=1) + np.sum(contributions, axis=1) * 0.035
        return np.clip(color, 0.0, 1.0).astype(np.float32, copy=False)

    @classmethod
    def _sample_light(cls, x, y, sources):
        return tuple(cls._sample_lights(((x, y),), sources)[0])

    @staticmethod
    def _lit(base, light, gain=0.45):
        return tuple(min(1.0, base[index] + light[index] * gain) for index in range(3))

    def draw_far_city(self, renderer, firework_lights=None):
        alpha = self.scene_alpha
        eased_scene = self._ease(self.scene_progress)
        firework_lights = firework_lights if firework_lights is not None else np.empty((0, 8))
        self._draw_city_layer(
            renderer,
            self._skyscrapers,
            base_y=(
                820 * SCALE_Y
                + (1.0 - eased_scene) * (SCREEN_HEIGHT - 820 * SCALE_Y)
                + self.camera_y * 0.20
            ),
            parallax_x=self.camera_y * 0.006,
            alpha=0.78 + alpha * 0.22,
            lights=firework_lights,
            near=False,
        )

    def draw_world(self, renderer, frame_count, firework_lights=None, launch_lights=None):
        alpha = self.scene_alpha
        firework_lights = firework_lights if firework_lights is not None else np.empty((0, 8))
        launch_lights = launch_lights if launch_lights is not None else np.empty((0, 8))
        eased_scene = self._ease(self.scene_progress)
        reveal_offset = (1.0 - eased_scene) * 700.0 * SCALE_Y
        if alpha <= 0.0:
            return

        self._draw_city_layer(
            renderer,
            self._homes,
            base_y=820 * SCALE_Y + reveal_offset * 0.79 + self.camera_y * 0.43,
            parallax_x=self.camera_y * 0.014,
            alpha=alpha,
            lights=firework_lights,
            near=True,
        )

        ground_y = 820 * SCALE_Y + reveal_offset + self.camera_y
        renderer.set_blend_mode("alpha")
        self._draw_ground(renderer, ground_y, frame_count, alpha, firework_lights, launch_lights)
        self._draw_launch_base(renderer, ground_y, alpha, firework_lights, launch_lights)

        rocket_y = reveal_offset + self.rocket_offset_y + self.camera_y
        shake_x, shake_y = self.charge_shake(frame_count)
        if self.phase is MissionPhase.IGNITION and self.launch_tier:
            build = min(1.0, self.phase_elapsed / self.launch_tier.ignition_seconds)
            amount = self.launch_tier.shake * build
            shake_x = self._rng.uniform(-amount, amount)
            shake_y = self._rng.uniform(-amount * 0.45, amount * 0.45)
        self._draw_ground_impact(renderer, ground_y, alpha)
        self._draw_rocket(
            renderer,
            rocket_y + shake_y,
            shake_x,
            alpha,
            firework_lights,
            launch_lights,
            frame_count,
        )
        renderer.set_blend_mode("additive")

    def _draw_city_layer(self, renderer, buildings, base_y, parallax_x, alpha, lights, near):
        renderer.set_blend_mode("alpha")
        texture, asset_width, asset_height = self._ensure_city_texture(renderer, near)
        renderer.draw_static_texture(
            texture,
            0,
            base_y - asset_height,
            asset_width,
            asset_height,
            (1.0, 1.0, 1.0, alpha),
        )

        # Static geometry is one textured draw call. Only the bounded dynamic
        # light response is drawn per building.
        renderer.set_blend_mode("additive")
        visible = []
        for source_x, width, height, cols, rows, lit_windows, roof, variation in buildings:
            x = source_x
            y = base_y - height
            if y > SCREEN_HEIGHT or base_y < 0.0:
                continue
            if near and x < SCREEN_WIDTH / 2 + 310 * SCALE_X and x + width > SCREEN_WIDTH / 2 - 310 * SCALE_X:
                continue
            visible.append((x, y, width, height))

        samples = self._sample_lights(
            [(x + width / 2, y + height * 0.45) for x, y, width, height in visible],
            lights,
        )
        light_rects = []
        light_lines = []
        for (x, y, width, height), light_values in zip(visible, samples):
            light = tuple(light_values)
            energy = max(light)
            if energy <= 0.015:
                continue
            if near:
                # Fireworks are behind this layer: mostly rim and roof light,
                # with only a faint bounced wash on the facade.
                light_rects.append((x, y, width, height, *light, alpha * 0.035))
                light_lines.append((x, y, x + width, y, *light, alpha * 0.52))
                light_lines.append((x, y, x, y + height, *light, alpha * 0.24))
                light_lines.append((x + width, y, x + width, y + height, *light, alpha * 0.24))
            else:
                # The far skyline faces the firework plane and receives a broad,
                # subdued color wash.
                light_rects.append((x, y, width, height, *light, alpha * 0.13))
                border = (*light, alpha * 0.18)
                light_lines.extend(
                    (
                        (x, y, x + width, y, *border),
                        (x + width, y, x + width, y + height, *border),
                        (x + width, y + height, x, y + height, *border),
                        (x, y + height, x, y, *border),
                    )
                )
        renderer.draw_colored_rects(light_rects)
        renderer.draw_colored_lines(light_lines)
        renderer.set_blend_mode("alpha")

    def _draw_ground(self, renderer, ground_y, frame_count, alpha, firework_lights, launch_lights):
        if ground_y >= SCREEN_HEIGHT:
            return
        renderer.draw_rect(0, ground_y, SCREEN_WIDTH, SCREEN_HEIGHT - ground_y, (0.025, 0.022, 0.026, alpha), fill=True)
        segment_width = SCREEN_WIDTH / 20.0
        segment_points = [
            (index * segment_width + segment_width / 2, max(ground_y, 0))
            for index in range(20)
        ]
        segment_fire = self._sample_lights(segment_points, firework_lights)
        segment_launch = self._sample_lights(segment_points, launch_lights)
        ground_rects = []
        for index in range(20):
            x = index * segment_width
            fire = segment_fire[index]
            launch = segment_launch[index]
            light = tuple(min(1.0, launch[channel] + fire[channel] * 0.22) for channel in range(3))
            surface = self._lit((0.022, 0.055, 0.035), light, 0.34)
            soil = self._lit((0.025, 0.022, 0.026), light, 0.19)
            ground_rects.append((x, ground_y, segment_width + 1.0, SCREEN_HEIGHT - ground_y, *soil, alpha))
            ground_rects.append((x, ground_y, segment_width + 1.0, 18 * SCALE_Y, *surface, alpha))

        visible_marks = []
        for x, depth, width, shade in self._ground_marks:
            y = ground_y + depth
            if y >= SCREEN_HEIGHT:
                continue
            visible_marks.append((x, y, width, shade))
        mark_points = [(x, y) for x, y, width, shade in visible_marks]
        mark_fire = self._sample_lights(mark_points, firework_lights)
        mark_launch = self._sample_lights(mark_points, launch_lights)
        bases = ((0.06, 0.052, 0.05), (0.035, 0.04, 0.037), (0.075, 0.058, 0.045))
        for (x, y, width, shade), fire, launch in zip(
            visible_marks,
            mark_fire,
            mark_launch,
        ):
            local = tuple(min(1.0, launch[channel] + fire[channel] * 0.20) for channel in range(3))
            color = self._lit(bases[shade], local, 0.25)
            ground_rects.append((x, y, width, max(2.0, 3 * SCALE_Y), *color, alpha * 0.72))
        renderer.draw_colored_rects(ground_rects)
        renderer.draw_line(0, ground_y + 20 * SCALE_Y, SCREEN_WIDTH, ground_y + 20 * SCALE_Y, (0.08, 0.10, 0.075, alpha * 0.72))

        if ground_y < -60 * SCALE_Y:
            return
        blade_geometry = []
        for center, phase, speed, gust_response, blades in self._grass:
            cluster_gust = 0.58 + 0.42 * math.sin(frame_count * 0.013 * speed + phase * 0.43)
            slow_push = math.sin(frame_count * 0.021 + phase) * 1.8 * SCALE_X
            for offset, height, blade_phase, amplitude in blades:
                x = center + offset
                if ground_y - height > SCREEN_HEIGHT:
                    continue
                ripple = math.sin(frame_count * 0.052 * speed + phase + blade_phase)
                sway = ripple * amplitude * (0.56 + cluster_gust * gust_response) + slow_push
                tip_x = x + sway
                mid_x = x + sway * 0.42
                blade_geometry.append(
                    (
                        x,
                        ground_y + 3 * SCALE_Y,
                        mid_x,
                        ground_y - height * 0.50,
                        tip_x,
                        ground_y - height,
                        ground_y - height * 0.65,
                        blade_phase,
                    )
                )
        blade_points = [(row[4], row[6]) for row in blade_geometry]
        blade_fire = self._sample_lights(blade_points, firework_lights)
        blade_launch = self._sample_lights(blade_points, launch_lights)
        grass_lines = []
        for row, fire, launch in zip(blade_geometry, blade_fire, blade_launch):
            x, base_y, mid_x, mid_y, tip_x, tip_y, _, blade_phase = row
            local = tuple(min(1.0, launch[channel] + fire[channel] * 0.30) for channel in range(3))
            base_green = (0.064, 0.19 + blade_phase * 0.035, 0.088)
            color = (*self._lit(base_green, local, 0.62), alpha)
            grass_lines.append((x, base_y, mid_x, mid_y, *color))
            grass_lines.append((mid_x, mid_y, tip_x, tip_y, *color))
        renderer.draw_colored_lines(grass_lines)

    def _draw_launch_base(self, renderer, ground_y, alpha, firework_lights, launch_lights):
        if ground_y > SCREEN_HEIGHT + 90 * SCALE_Y or ground_y < -130 * SCALE_Y:
            return
        cx = SCREEN_WIDTH / 2
        fire = self._sample_light(cx, ground_y - 25 * SCALE_Y, firework_lights)
        launch = self._sample_light(cx, ground_y - 25 * SCALE_Y, launch_lights)
        light = tuple(min(1.0, launch[channel] + fire[channel] * 0.24) for channel in range(3))
        steel = self._lit((0.105, 0.13, 0.15), light, 0.35)
        edge = self._lit((0.28, 0.32, 0.34), light, 0.45)
        hazard = self._lit((0.48, 0.29, 0.055), light, 0.32)

        renderer.set_blend_mode("alpha")
        renderer.draw_rect(cx - 220 * SCALE_X, ground_y - 10 * SCALE_Y, 440 * SCALE_X, 24 * SCALE_Y, (*steel, alpha), fill=True)
        renderer.draw_rect(cx - 180 * SCALE_X, ground_y - 24 * SCALE_Y, 360 * SCALE_X, 16 * SCALE_Y, (*edge, alpha), fill=True)
        renderer.draw_rect(cx - 68 * SCALE_X, ground_y - 27 * SCALE_Y, 136 * SCALE_X, 24 * SCALE_Y, (0.008, 0.009, 0.012, alpha), fill=True)
        renderer.draw_rect(cx - 220 * SCALE_X, ground_y - 10 * SCALE_Y, 440 * SCALE_X, 24 * SCALE_Y, (*edge, alpha * 0.9), fill=False)

        for side in (-1, 1):
            support_x = cx + side * 112 * SCALE_X
            renderer.draw_rect(support_x - 8 * SCALE_X, ground_y - 82 * SCALE_Y, 16 * SCALE_X, 72 * SCALE_Y, (*steel, alpha), fill=True)
            renderer.draw_rect(support_x - 8 * SCALE_X, ground_y - 82 * SCALE_Y, 16 * SCALE_X, 72 * SCALE_Y, (*edge, alpha * 0.85), fill=False)
            renderer.draw_line(
                support_x,
                ground_y - 67 * SCALE_Y,
                cx + side * 56 * SCALE_X,
                ground_y - 47 * SCALE_Y,
                (*edge, alpha),
            )

        stripe_width = 34 * SCALE_X
        for index in range(8):
            if index % 2 == 0:
                x = cx - 176 * SCALE_X + index * stripe_width
                renderer.draw_rect(x, ground_y - 22 * SCALE_Y, stripe_width, 7 * SCALE_Y, (*hazard, alpha), fill=True)

    def _draw_rocket(
        self,
        renderer,
        y_offset,
        x_offset,
        alpha,
        firework_lights,
        launch_lights,
        frame_count,
    ):
        cx = SCREEN_WIDTH / 2 + x_offset
        top = 455 * SCALE_Y + y_offset
        block = 24 * SCALE_X
        panels = (
            (cx - block, top, 2 * block, block, (0.94, 0.055, 0.045)),
            (cx - 2 * block, top + block, 4 * block, 2 * block, (0.96, 0.93, 0.88)),
            (cx - 3 * block, top + 3 * block, 6 * block, 3 * block, (0.92, 0.94, 0.96)),
            (cx - 3 * block, top + 6 * block, 6 * block, 4 * block, (0.98, 0.97, 0.93)),
            (cx - 3 * block, top + 10 * block, 6 * block, 3 * block, (0.88, 0.91, 0.94)),
            (cx - 5 * block, top + 9 * block, 2 * block, 4 * block, (0.90, 0.045, 0.035)),
            (cx + 3 * block, top + 9 * block, 2 * block, 4 * block, (0.90, 0.045, 0.035)),
            (cx - 1.5 * block, top + 13 * block, 3 * block, 1.45 * block, (0.12, 0.13, 0.145)),
        )
        renderer.set_blend_mode("alpha")
        panel_points = [
            (x + width / 2, y + height / 2)
            for x, y, width, height, base in panels
        ]
        panel_fire = self._sample_lights(panel_points, firework_lights)
        panel_launch = self._sample_lights(panel_points, launch_lights)
        for (x, y, width, height, base), fire, launch in zip(
            panels,
            panel_fire,
            panel_launch,
        ):
            diffuse = tuple(min(1.0, launch[channel] + fire[channel] * 0.12) for channel in range(3))
            rim = tuple(min(1.0, launch[channel] + fire[channel] * 0.62) for channel in range(3))
            color = self._lit(base, diffuse, 0.50)
            edge = self._lit((0.24, 0.27, 0.30), rim, 0.62)
            renderer.draw_rect(x, y, width, height, (*color, alpha), fill=True)
            renderer.draw_rect(x, y, width, height, (*edge, alpha * 0.85), fill=False)

        # Offset plates, seams, and rivets give the red-and-white block rocket material
        # without turning it into a character or changing its silhouette.
        seam_fire = self._sample_light(cx, top + 8 * block, firework_lights)
        seam_launch = self._sample_light(cx, top + 8 * block, launch_lights)
        seam_light = tuple(min(1.0, seam_launch[channel] + seam_fire[channel] * 0.38) for channel in range(3))
        seam = (*self._lit((0.25, 0.28, 0.31), seam_light, 0.8), alpha * 0.82)
        renderer.draw_line(cx, top + 3 * block, cx, top + 13 * block, seam)
        renderer.draw_line(cx - 3 * block, top + 6 * block, cx + 3 * block, top + 6 * block, seam)
        renderer.draw_line(cx - 3 * block, top + 10 * block, cx + 3 * block, top + 10 * block, seam)
        accent_fire = self._sample_light(cx, top + 7.6 * block, firework_lights)
        accent_launch = self._sample_light(cx, top + 7.6 * block, launch_lights)
        accent_light = tuple(min(1.0, accent_launch[channel] + accent_fire[channel] * 0.20) for channel in range(3))
        accent = self._lit((0.92, 0.045, 0.035), accent_light, 0.42)
        renderer.draw_rect(cx - 3 * block, top + 7.45 * block, 6 * block, 0.42 * block, (*accent, alpha), fill=True)
        rivet = self._lit((0.42, 0.46, 0.50), seam_light, 1.0)
        for dx in (-2.45, 2.45):
            for row in (4.0, 7.5, 11.5):
                renderer.draw_rect(cx + dx * block - 2 * SCALE_X, top + row * block, 4 * SCALE_X, 4 * SCALE_Y, (*rivet, alpha), fill=True)

        self._draw_charge_ports(renderer, cx, top, block, alpha, frame_count)

    def _draw_charge_ports(self, renderer, cx, top, block, alpha, frame_count):
        """Draw four rocket-mounted indicators for reserved battery cells."""
        port_width = 19 * SCALE_X
        port_height = 13 * SCALE_Y
        gap = 9 * SCALE_X
        total_width = port_width * 4 + gap * 3
        start_x = cx - total_width / 2
        port_y = top + 8.55 * block
        reserved = self.reserved_generators

        for index in range(4):
            x = start_x + index * (port_width + gap)
            renderer.set_blend_mode("alpha")
            renderer.draw_rect(
                x - 3 * SCALE_X,
                port_y - 3 * SCALE_Y,
                port_width + 6 * SCALE_X,
                port_height + 6 * SCALE_Y,
                (0.035, 0.045, 0.06, alpha * 0.95),
                fill=True,
            )
            renderer.draw_rect(
                x,
                port_y,
                port_width,
                port_height,
                (0.08, 0.10, 0.12, alpha),
                fill=True,
            )
            renderer.draw_rect(
                x,
                port_y,
                port_width,
                port_height,
                (0.38, 0.43, 0.48, alpha * 0.72),
                fill=False,
            )
            if index >= len(reserved):
                continue

            color = palette.get_color(GENERATOR_STATUS_COLOR_INDICES[reserved[index]])
            pulse = 0.72 + 0.28 * math.sin(frame_count * 0.12 + index * 0.7)
            # The first filled cell gets an unmistakable calm heartbeat. More
            # cells retain the glow while venting/shake carry the urgency.
            glow_gain = 0.34 if len(reserved) == 1 else 0.24
            renderer.set_blend_mode("additive")
            renderer.draw_rect(
                x - 6 * SCALE_X,
                port_y - 6 * SCALE_Y,
                port_width + 12 * SCALE_X,
                port_height + 12 * SCALE_Y,
                (*color, alpha * pulse * glow_gain),
                fill=True,
            )
            renderer.set_blend_mode("alpha")
            renderer.draw_rect(
                x + 2 * SCALE_X,
                port_y + 2 * SCALE_Y,
                port_width - 4 * SCALE_X,
                port_height - 4 * SCALE_Y,
                (*color, alpha * (0.82 + pulse * 0.18)),
                fill=True,
            )

        renderer.set_blend_mode("alpha")

    def _draw_ground_impact(self, renderer, ground_y, alpha):
        if not self.launch_tier or self.phase not in (MissionPhase.IGNITION, MissionPhase.ASCENT):
            return
        if self.phase is MissionPhase.IGNITION:
            strength = min(1.0, self.phase_elapsed / self.launch_tier.ignition_seconds)
        else:
            strength = max(0.0, 1.0 - self.phase_elapsed / 1.3)
        width = (220 + self.launch_tier.cells * 90) * SCALE_X * strength
        renderer.draw_ellipse(
            SCREEN_WIDTH / 2 - width / 2,
            ground_y - 18 * SCALE_Y,
            width,
            36 * SCALE_Y,
            (1.0, 0.38, 0.04, 0.42 * strength * alpha),
        )
        if self._shockwave_age is not None and self._shockwave_age < 1.2:
            wave = self._shockwave_age / 1.2
            radius = (180 + 520 * wave) * SCALE_X
            renderer.draw_ellipse(
                SCREEN_WIDTH / 2 - radius,
                ground_y - 26 * SCALE_Y,
                radius * 2,
                52 * SCALE_Y,
                (1.0, 0.8, 0.35, (1.0 - wave) * 0.35 * alpha),
            )

    def message(self, snapshot):
        if self.phase in (MissionPhase.ATTRACT, MissionPhase.REVEAL, MissionPhase.RETURN):
            return None
        if self.phase is MissionPhase.IGNITION:
            return "ALL CELLS READY!", "HOLD ON, SOT-KUN. IT IS TIME TO GO HOME!"
        if self.phase in (MissionPhase.ASCENT, MissionPhase.DEPARTURE):
            return "LIFT OFF!", "HAVE A SAFE TRIP HOME, SOT-KUN!"
        if self._cell_message_time > 0.0 and self._cell_message is not None:
            name = "CRANK" if self._cell_message is GeneratorType.HAND_CRANK else self._cell_message.name
            return f"{name} CELL READY!", "GREAT JOB! SOT-KUN IS ONE STEP CLOSER TO HOME."
        if snapshot.launch_ready:
            cell_count = len(snapshot.filled_generators)
            seconds = max(1, math.ceil(snapshot.launch_wait_remaining))
            return (
                f"{cell_count} CELLS READY! LAUNCH IN {seconds}",
                f"MOVE THE MAGNET TO ADD CELL {cell_count + 1}.",
            )
        selected = snapshot.selected_generators
        if len(selected) == 1:
            level = snapshot.energy_levels.get(selected[0], 0.0)
            if level >= MAX_ENERGY_GAUGE:
                return "CELL ENERGY RESERVED!", "MOVE THE MAGNET TO ANOTHER ENERGY SOURCE."
            return "POWER UP THE ENERGY CELL!", "SOT-KUN'S TRIP HOME STARTS WITH YOU."
        return "POWER UP THE ACTIVE CELL!", "EACH FULL CELL KEEPS ITS ENERGY WHEN THE MAGNET MOVES."

    def draw_message(self, renderer, pixel_font, snapshot):
        message = self.message(snapshot)
        if message is None:
            return
        primary, secondary = message
        if self.phase in (MissionPhase.ASCENT, MissionPhase.DEPARTURE):
            primary_y = 58 * SCALE_Y
            secondary_y = 112 * SCALE_Y
        else:
            primary_y = 130 * SCALE_Y
            secondary_y = 205 * SCALE_Y
        renderer.set_blend_mode("alpha")
        renderer.draw_pixel_text(SCREEN_WIDTH / 2 + 4, primary_y + 4, primary, pixel_font, 8, (0.0, 0.0, 0.0, 0.72), centered=True)
        renderer.draw_pixel_text(SCREEN_WIDTH / 2, primary_y, primary, pixel_font, 8, (1.0, 0.92, 0.45, 1.0), centered=True)
        renderer.draw_pixel_text(SCREEN_WIDTH / 2 + 3, secondary_y + 3, secondary, pixel_font, 4, (0.0, 0.0, 0.0, 0.7), centered=True)
        renderer.draw_pixel_text(SCREEN_WIDTH / 2, secondary_y, secondary, pixel_font, 4, (0.78, 0.88, 1.0, 0.95), centered=True)
        renderer.set_blend_mode("additive")
