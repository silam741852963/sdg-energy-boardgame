from dataclasses import dataclass
from enum import Enum, auto
import math
from pathlib import Path
import random

import numpy as np
import pygame

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
    CRASH = auto()
    REVEAL = auto()
    CHARGING = auto()
    IGNITION = auto()
    ASCENT = auto()
    DEPARTURE = auto()
    RECORD_HOLD = auto()
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

# Nonlinear pre-launch buildup: the first cell whispers, the third announces.
CHARGE_CUE_LEVELS = {
    1: {
        "shake": 0.22,
        "rate": 2.4,
        "life": 28,
        "size": 4.8,
        "intensity": 0.40,
        "speed": 1.35,
    },
    2: {
        "shake": 0.88,
        "rate": 9.0,
        "life": 39,
        "size": 7.4,
        "intensity": 0.62,
        "speed": 2.10,
    },
    3: {
        "shake": 2.05,
        "rate": 21.0,
        "life": 52,
        "size": 11.0,
        "intensity": 0.88,
        "speed": 2.95,
    },
}


class RocketScene:
    CRASH_SECONDS = 10.8
    # Keep the exterior approach near 1.5 seconds while giving the cockpit
    # sequence substantially more room to breathe.
    CRASH_ZOOM_PROGRESS = 0.14
    CRASH_IMPACT_PROGRESS = 0.90
    REVEAL_SECONDS = 3.6
    REVEAL_RETURN_SECONDS = 2.0
    REVEAL_CAMERA_TRAVEL = 1050.0 * SCALE_Y
    DEPARTURE_SECONDS = 1.8
    RETURN_SECONDS = 5.6
    STAR_STREAK_START = 0.60
    ROCKET_ESCAPE_START = 0.84
    ROCKET_ESCAPE_END = 0.92
    BLACK_FADE_START = 0.93
    BLACK_FADE_END = 0.99
    EARTH_RETURN_FOCUS_HOLD_SECONDS = 0.75
    EARTH_RETURN_ZOOM_SECONDS = 2.0
    EARTH_RETURN_FADE_SECONDS = 0.625
    EARTH_RETURN_STAR_SECONDS = 2.75
    EARTH_RETURN_STAR_ANGLE = math.radians(8.0)
    EARTH_RETURN_TRAIL_SEGMENTS = 5
    EARTH_SPIN_RADIANS_PER_SECOND = 0.13
    EARTH_IDLE_LATITUDE = math.radians(8.0)
    # Ōmagari, Daisen, Akita (39°27′11.1″ N, 140°28′31.6″ E).
    OMAGARI_LONGITUDE = math.radians(140.475444)
    OMAGARI_LATITUDE = math.radians(39.453083)
    EARTH_ASSET_PATH = (
        Path(__file__).resolve().parents[4]
        / "resource"
        / "images"
        / "earth-blue-marble-global.jpg"
    )

    def __init__(self, firework_manager, audio):
        self.firework_manager = firework_manager
        self.audio = audio
        self.phase = MissionPhase.ATTRACT
        self.scene_progress = 0.0
        self.phase_elapsed = 0.0
        self.intro_elapsed = 0.0
        self._earth_return_zoom = 0.0
        self._earth_return_fade = 0.0
        self._earth_return_stars = 0.0
        self._earth_return_focus_hold = 0.0
        self._star_field_angle = 0.0
        self._earth_return_star_origin_angle = 0.0
        self._crash_start_angle = 0.0
        self._crash_start_longitude = 0.0
        self._crash_target_longitude = None
        self._intro_played = False
        self._logo_hidden_for_reveal = False
        self.launch_tier = None
        self.launch_generators = ()
        self.reserved_generators = ()
        self.rocket_offset_y = 0.0
        self.camera_y = 0.0
        self._return_camera_start = 0.0
        self._return_rocket_start = 0.0
        self.emission_scale = 1.0
        self._slow_seconds = 0.0
        self._fast_seconds = 0.0
        self._emission_accumulator = 0.0
        self._prelaunch_emission_accumulator = 0.0
        self._cell_message = None
        self._cell_message_time = 0.0
        self._shockwave_age = None
        self._rng = random.Random(1427)
        self._sky_rng = random.Random(2849)
        self._stars = self._build_stars()
        self._comet = None
        # Guarantee an early pass so the ambient effect is visible after boot.
        self._comet_wait = self._sky_rng.uniform(1.5, 4.0)
        self._cosmic_events = []
        self._skyscrapers = self._build_city_layer(78, 168, 190, 445, 4181)
        self._homes = self._build_city_layer(132, 238, 105, 235, 6113)
        self._ground_marks = self._build_ground_marks()
        self._grass = self._build_grass()
        self._city_asset_data = {
            False: self._build_city_asset(self._skyscrapers, near=False),
            True: self._build_city_asset(self._homes, near=True),
        }
        self._city_textures = {}
        self._earth_texture = None

    @property
    def drone_y_offset(self):
        if self.phase is MissionPhase.RECORD_HOLD or (
            self.phase is MissionPhase.RETURN and self._return_camera_start > 0.0
        ):
            # Keep the Ablic mark out of the upward launch wipe. It belongs to
            # the Earth attract screen after the stage has fully reset.
            return -1550.0 * SCALE_Y
        if self.phase is MissionPhase.CRASH:
            exit_progress = self._ease(
                min(1.0, self.crash_progress / self.CRASH_ZOOM_PROGRESS)
            )
            return (270.0 - 1550.0 * exit_progress) * SCALE_Y
        if self.phase is MissionPhase.REVEAL and self._logo_hidden_for_reveal:
            return -1280.0 * SCALE_Y
        eased = self._ease(self.scene_progress)
        intro_offset = (0.0 if self._intro_played else 270.0) * SCALE_Y
        return intro_offset * (1.0 - eased) - 1250.0 * SCALE_Y * eased

    @property
    def scene_alpha(self):
        if self.phase is MissionPhase.RETURN and self._return_camera_start > 0.0:
            return 1.0
        return self._ease(self.scene_progress)

    @property
    def intro_alpha(self):
        if self._intro_played:
            return 0.0
        if self.phase in (MissionPhase.ATTRACT, MissionPhase.CRASH):
            return 1.0
        return 0.0

    @property
    def transition_black_alpha(self):
        if self.phase is MissionPhase.RETURN and self._return_camera_start > 0.0:
            return self._ease(
                min(
                    1.0,
                    max(
                        0.0,
                        (1.0 - self.scene_progress - self.BLACK_FADE_START)
                        / (self.BLACK_FADE_END - self.BLACK_FADE_START),
                    ),
                )
            )
        if self.phase is MissionPhase.ATTRACT and self._earth_return_fade > 0.0:
            return self._ease(self._earth_return_fade)
        return 0.0

    def draw_transition_fade(self, renderer):
        alpha = self.transition_black_alpha
        if alpha <= 0.001:
            return
        renderer.set_blend_mode("alpha")
        renderer.draw_rect(
            0.0,
            0.0,
            SCREEN_WIDTH,
            SCREEN_HEIGHT,
            (0.0, 0.0, 0.0, alpha),
            fill=True,
        )

    @property
    def firework_y_offset(self):
        """Fireworks occupy the depth plane between both city layers."""
        return self.camera_y * 0.31

    def screen_shake(self):
        if self.phase is MissionPhase.CRASH:
            progress = self.crash_progress
            impact = self.CRASH_IMPACT_PROGRESS
            if progress < impact:
                return 0.0, 0.0
            strength = math.sin(
                min(1.0, (progress - impact) / (1.0 - impact)) * math.pi
            )
            amount = 13.0 * strength
            return self._rng.uniform(-amount, amount), self._rng.uniform(
                -amount, amount
            )
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
            pronounced_blink = self._sky_rng.random() < 0.22
            stars.append(
                (
                    self._rng.uniform(0, SCREEN_WIDTH),
                    self._rng.uniform(0, SCREEN_HEIGHT),
                    self._rng.uniform(2.0, 5.5),
                    self._rng.uniform(0.35, 0.9),
                    depth,
                    self._rng.uniform(0, math.tau),
                    self._sky_rng.uniform(0.045, 0.105),
                    self._sky_rng.uniform(0.75, 1.30)
                    if pronounced_blink
                    else self._sky_rng.uniform(0.16, 0.34),
                )
            )
        return stars

    def _update_comet(self, dt):
        if self._comet is None:
            launch_active = self.phase in (
                MissionPhase.IGNITION,
                MissionPhase.ASCENT,
                MissionPhase.DEPARTURE,
                MissionPhase.RECORD_HOLD,
                MissionPhase.RETURN,
            )
            self._comet_wait -= dt * (2.2 if launch_active else 1.0)
            if self._comet_wait > 0.0:
                return
            self._spawn_comet(launch_boost=launch_active)
            return

        comet = self._comet
        comet["age"] += dt
        comet["x"] += comet["vx"] * dt
        comet["y"] += comet["vy"] * dt
        outside = (
            comet["x"] < -180.0 * SCALE_X
            or comet["x"] > SCREEN_WIDTH + 180.0 * SCALE_X
            or comet["y"] > SCREEN_HEIGHT * 0.72
        )
        if comet["age"] >= comet["duration"] or outside:
            self._comet = None
            if self.phase in (
                MissionPhase.IGNITION,
                MissionPhase.ASCENT,
                MissionPhase.DEPARTURE,
            ):
                self._comet_wait = self._sky_rng.uniform(2.5, 5.0)
            else:
                self._comet_wait = self._sky_rng.uniform(8.0, 14.0)

    def _spawn_comet(self, launch_boost=False):
        direction = self._sky_rng.choice((-1.0, 1.0))
        # Launch comets cover the same path in half the former time.
        speed_scale = 2.56 if launch_boost else 1.0
        speed = self._sky_rng.uniform(390.0, 520.0) * SCALE_X * speed_scale
        self._comet = {
            "x": -90.0 * SCALE_X if direction > 0.0 else SCREEN_WIDTH + 90.0 * SCALE_X,
            "y": self._sky_rng.uniform(70.0, 310.0) * SCALE_Y,
            "vx": speed * direction,
            "vy": self._sky_rng.uniform(65.0, 125.0)
            * SCALE_Y
            * (2.0 if launch_boost else 1.0),
            "age": 0.0,
            "duration": self._sky_rng.uniform(1.9, 2.6)
            if launch_boost
            else self._sky_rng.uniform(3.8, 5.2),
            "boost": 1.55 if launch_boost else 1.0,
        }

    def _trigger_liftoff_cosmos(self):
        if self._comet is None:
            self._spawn_comet(launch_boost=True)
        else:
            self._comet["boost"] = max(1.55, self._comet.get("boost", 1.0))

        meteor_streaks = []
        direction = self._sky_rng.choice((-1.0, 1.0))
        for index in range(5):
            meteor_streaks.append(
                (
                    self._sky_rng.uniform(120.0, SCREEN_WIDTH - 120.0),
                    self._sky_rng.uniform(60.0, 330.0) * SCALE_Y,
                    direction * self._sky_rng.uniform(600.0, 940.0) * SCALE_X,
                    self._sky_rng.uniform(180.0, 340.0) * SCALE_Y,
                    index * self._sky_rng.uniform(0.06, 0.12),
                )
            )
        self._cosmic_events = [
            {
                "kind": "meteor_shower",
                "age": 0.0,
                "duration": 1.4,
                "streaks": tuple(meteor_streaks),
            },
            {
                "kind": "constellation_pulse",
                "age": 0.0,
                "duration": 1.7,
                "x": self._sky_rng.uniform(480.0, SCREEN_WIDTH - 480.0),
                "y": self._sky_rng.uniform(170.0, 390.0) * SCALE_Y,
                "phases": tuple(
                    self._sky_rng.uniform(0.0, math.tau) for _ in range(30)
                ),
            },
        ]

    def _update_cosmic_events(self, dt):
        for event in self._cosmic_events:
            event["age"] += dt
        self._cosmic_events = [
            event for event in self._cosmic_events if event["age"] < event["duration"]
        ]

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
            if (
                near
                and x < SCREEN_WIDTH / 2 + 310 * SCALE_X
                and x + width > SCREEN_WIDTH / 2 - 310 * SCALE_X
            ):
                continue
            y = asset_height - height
            base = self._facade_base(near, variation)
            base_rgb = tuple(int(channel * 255) for channel in base)
            edge_base = (39, 25, 32) if near else (19, 35, 62)
            rect(x, y, width, height, base_rgb)
            rect(x, y, width, max(2, 2 * SCALE_Y), edge_base)
            rect(x, y, max(2, 2 * SCALE_X), height, edge_base)
            rect(
                x + width - max(2, 2 * SCALE_X),
                y,
                max(2, 2 * SCALE_X),
                height,
                edge_base,
            )

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
                rect(
                    x + width * 0.28,
                    y - 18 * SCALE_Y,
                    width * 0.44,
                    18 * SCALE_Y,
                    base_rgb,
                )
            elif roof == "antenna":
                antenna_x = x + width * 0.5
                antenna_h = (28 + variation * 36) * SCALE_Y
                rect(
                    antenna_x, y - antenna_h, max(1, 2 * SCALE_X), antenna_h, edge_base
                )

        return asset_width, asset_height, canvas.tobytes()

    def _ensure_city_texture(self, renderer, near):
        texture = self._city_textures.get(near)
        if texture is None:
            width, height, data = self._city_asset_data.pop(near)
            texture = renderer.create_static_texture(width, height, data)
            self._city_textures[near] = (texture, width, height)
        return self._city_textures[near]

    def _ensure_earth_texture(self, renderer):
        if self._earth_texture is None:
            surface = pygame.image.load(str(self.EARTH_ASSET_PATH))
            width, height = surface.get_size()
            rgba = pygame.image.tobytes(surface, "RGBA", False)
            texture = renderer.create_static_texture(
                width,
                height,
                rgba,
                smooth=True,
                wrap_x=True,
            )
            self._earth_texture = (texture, width, height)
        return self._earth_texture

    def reset(self):
        returning_from_launch = self._return_camera_start > 0.0
        return_intro_elapsed = self.intro_elapsed
        self.phase = MissionPhase.ATTRACT
        self.scene_progress = 0.0
        self.phase_elapsed = 0.0
        self.intro_elapsed = return_intro_elapsed if returning_from_launch else 0.0
        self._earth_return_zoom = 1.0 if returning_from_launch else 0.0
        self._earth_return_fade = 1.0 if returning_from_launch else 0.0
        self._earth_return_stars = 1.0 if returning_from_launch else 0.0
        self._earth_return_focus_hold = (
            self.EARTH_RETURN_FOCUS_HOLD_SECONDS if returning_from_launch else 0.0
        )
        self._earth_return_star_origin_angle = self._star_field_angle
        self._crash_start_angle = 0.0
        self._crash_start_longitude = 0.0
        self._crash_target_longitude = None
        self._intro_played = False
        self._logo_hidden_for_reveal = False
        self.launch_tier = None
        self.launch_generators = ()
        self.reserved_generators = ()
        self.rocket_offset_y = 0.0
        self.camera_y = 0.0
        self._return_camera_start = 0.0
        self._return_rocket_start = 0.0
        self._emission_accumulator = 0.0
        self._prelaunch_emission_accumulator = 0.0
        self._cell_message = None
        self._cell_message_time = 0.0
        self._shockwave_age = None
        self._cosmic_events.clear()
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
        self._return_rocket_start = 0.0
        self._shockwave_age = None
        self._cosmic_events.clear()
        self.audio.start_rocket_thrust(count)

    def update(self, snapshot, dt, fps=60.0):
        actions = SceneActions()
        dt = min(0.1, max(0.0, dt))
        self._update_adaptive_density(fps, dt)
        self._update_comet(dt)
        self._update_cosmic_events(dt)
        if self._cell_message_time > 0.0:
            self._cell_message_time = max(0.0, self._cell_message_time - dt)

        self.reserved_generators = tuple(
            generator
            for generator in snapshot.selected_generators
            if generator in snapshot.filled_generators
        )

        has_selection = bool(snapshot.selected_generators)
        if self.phase in (
            MissionPhase.ATTRACT,
            MissionPhase.CRASH,
            MissionPhase.RECORD_HOLD,
            MissionPhase.RETURN,
        ):
            self.intro_elapsed += dt

        if self.phase is MissionPhase.ATTRACT:
            self._earth_return_fade = max(
                0.0, self._earth_return_fade - dt / self.EARTH_RETURN_FADE_SECONDS
            )
            if self._earth_return_fade <= 0.0:
                if self._earth_return_focus_hold > 0.0:
                    self._earth_return_focus_hold = max(
                        0.0, self._earth_return_focus_hold - dt
                    )
                else:
                    self._earth_return_zoom = max(
                        0.0,
                        self._earth_return_zoom - dt / self.EARTH_RETURN_ZOOM_SECONDS,
                    )
                self._earth_return_stars = max(
                    0.0,
                    self._earth_return_stars - dt / self.EARTH_RETURN_STAR_SECONDS,
                )
                self._star_field_angle = (
                    self._earth_return_star_origin_angle
                    + self.EARTH_RETURN_STAR_ANGLE
                    * (1.0 - self._earth_return_stars**2.0)
                )
            if snapshot.launch_committed:
                actions.reset_requested = True
            elif has_selection:
                if self._intro_played:
                    self._logo_hidden_for_reveal = False
                    self.phase = MissionPhase.REVEAL
                else:
                    self._crash_start_angle = self._intro_orbit_angle()
                    self._crash_start_longitude = self._earth_idle_longitude()
                    self._crash_target_longitude = self._forward_target_longitude(
                        self._crash_start_longitude
                    )
                    self.phase = MissionPhase.CRASH
                    self.phase_elapsed = 0.0
        elif self.phase is MissionPhase.CRASH:
            self.phase_elapsed += dt
            if self.phase_elapsed >= self.CRASH_SECONDS:
                self._intro_played = True
                self._logo_hidden_for_reveal = True
                self.phase = MissionPhase.REVEAL
                self.phase_elapsed = 0.0
        elif self.phase is MissionPhase.REVEAL:
            if not has_selection:
                self.phase = MissionPhase.RETURN
            else:
                self.scene_progress = min(
                    1.0, self.scene_progress + dt / self.REVEAL_SECONDS
                )
                if self.scene_progress >= 1.0:
                    self.phase = MissionPhase.CHARGING
        elif self.phase is MissionPhase.CHARGING and not has_selection:
            self.phase = MissionPhase.RETURN
        elif self.phase is MissionPhase.RETURN:
            if has_selection and not snapshot.launch_committed:
                self.phase = MissionPhase.REVEAL
            else:
                return_seconds = (
                    self.RETURN_SECONDS
                    if snapshot.launch_committed
                    else self.REVEAL_RETURN_SECONDS
                )
                self.scene_progress = max(
                    0.0, self.scene_progress - dt / return_seconds
                )
                # Keep the post-launch exit moving upward.  The old return
                # eased camera_y back toward zero, producing a noticeable
                # downward dip before the Earth intro was restored.
                if snapshot.launch_committed:
                    exit_linear = 1.0 - self.scene_progress
                    # Match the record-hold cruise on the first frame, then
                    # accelerate the camera and rocket together. Their summed
                    # screen position stays fixed until the deliberate escape.
                    camera_travel = (
                        420.0 * SCALE_Y * self.RETURN_SECONDS * exit_linear
                        + SCREEN_HEIGHT * 40.0 * exit_linear**2.8
                    )
                    self.camera_y = self._return_camera_start + camera_travel
                    escape_progress = self._ease(
                        min(
                            1.0,
                            max(
                                0.0,
                                (exit_linear - self.ROCKET_ESCAPE_START)
                                / (self.ROCKET_ESCAPE_END - self.ROCKET_ESCAPE_START),
                            ),
                        )
                    )
                    self.rocket_offset_y = (
                        self._return_rocket_start
                        - camera_travel
                        - SCREEN_HEIGHT * 2.4 * escape_progress
                    )
                    if exit_linear < self.BLACK_FADE_START:
                        self._emit_exhaust(dt, grounded=False)
                else:
                    self.camera_y = self._return_camera_start * self._ease(
                        self.scene_progress
                    )
                if self.scene_progress <= 0.0:
                    self.phase = MissionPhase.ATTRACT
                    self.camera_y = 0.0
                    self._logo_hidden_for_reveal = False
                    if snapshot.launch_committed:
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
                self._trigger_liftoff_cosmos()
        elif self.phase is MissionPhase.ASCENT:
            self.phase_elapsed += dt
            progress = min(1.0, self.phase_elapsed / self.launch_tier.ascent_seconds)
            self.rocket_offset_y = -((progress**2.15) * (SCREEN_HEIGHT * 3.0))
            desired_follow = max(0.0, -self.rocket_offset_y - 105 * SCALE_Y)
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
            self.rocket_offset_y = -(SCREEN_HEIGHT * (3.0 + (progress**1.35) * 1.6))
            desired_follow = max(0.0, -self.rocket_offset_y - 105 * SCALE_Y)
            self.camera_y = desired_follow
            self._emit_exhaust(dt, grounded=False)
            if progress >= 1.0:
                self.phase = MissionPhase.RECORD_HOLD
                actions.launch_completed = True
        elif self.phase is MissionPhase.RECORD_HOLD:
            self.phase_elapsed += dt
            self._advance_record_hold(dt)

        return actions

    def sustain_record_hold(self, dt, fps=60.0):
        """Keep the centered rocket alive while ranking input owns the UI."""
        if self.phase is not MissionPhase.RECORD_HOLD:
            return
        dt = min(0.1, max(0.0, dt))
        self._update_adaptive_density(fps, dt)
        self._update_comet(dt)
        self._update_cosmic_events(dt)
        self.phase_elapsed += dt
        self.intro_elapsed += dt
        self._advance_record_hold(dt)

    def _advance_record_hold(self, dt):
        cruise_distance = 420.0 * SCALE_Y * dt
        self.rocket_offset_y -= cruise_distance
        self.camera_y += cruise_distance
        self._emit_exhaust(dt, grounded=False)

    def release_record_hold(self):
        """Begin the accelerating escape after ranking UI is dismissed."""
        if self.phase is not MissionPhase.RECORD_HOLD:
            return
        self.phase = MissionPhase.RETURN
        self.phase_elapsed = 0.0
        self.scene_progress = 1.0
        self._return_camera_start = self.camera_y
        self._return_rocket_start = self.rocket_offset_y

    @property
    def crash_progress(self):
        if self.phase is not MissionPhase.CRASH:
            return 0.0
        return min(1.0, self.phase_elapsed / self.CRASH_SECONDS)

    def _intro_orbit_angle(self):
        return -0.28 + self.intro_elapsed * 0.46

    def _earth_idle_longitude(self):
        return (
            math.radians(-105.0)
            + self.intro_elapsed * self.EARTH_SPIN_RADIANS_PER_SECOND
        )

    @staticmethod
    def _lerp_angle(start, end, amount):
        delta = (end - start + math.pi) % math.tau - math.pi
        return start + delta * amount

    def _forward_target_longitude(self, start):
        target = self.OMAGARI_LONGITUDE
        minimum = start + self.CRASH_SECONDS * self.EARTH_SPIN_RADIANS_PER_SECOND + 0.35
        while target < minimum:
            target += math.tau
        return target

    @staticmethod
    def _intro_earth_geometry():
        width = 660.0 * SCALE_X
        height = 660.0 * SCALE_Y
        center_x = SCREEN_WIDTH / 2
        center_y = 365.0 * SCALE_Y
        return center_x, center_y, width, height

    def _earth_return_screen_center(self):
        """Earth center after applying the active rocket-focused camera zoom."""
        center_x, center_y, _, _ = self._intro_earth_geometry()
        if self._earth_return_zoom <= 0.0:
            return center_x, center_y
        pose = self._intro_rocket_pose()
        zoom_progress = 1.0 - self._earth_return_zoom
        eased_zoom = self._ease(zoom_progress)
        zoom = 3.8 - 2.8 * eased_zoom
        target_x = SCREEN_WIDTH / 2
        target_y = 360.0 * SCALE_Y
        rocket_x = target_x + (pose[0] - target_x) * eased_zoom
        rocket_y = target_y + (pose[1] - target_y) * eased_zoom
        return (
            rocket_x + (center_x - pose[0]) * zoom,
            rocket_y + (center_y - pose[1]) * zoom,
        )

    def _intro_orbit_position(self, angle):
        center_x, center_y, _, _ = self._intro_earth_geometry()
        return (
            center_x + math.cos(angle) * 445.0 * SCALE_X,
            center_y + math.sin(angle) * 270.0 * SCALE_Y,
        )

    def _intro_rocket_pose(self):
        angle = (
            self._crash_start_angle
            if self.phase is MissionPhase.CRASH
            else self._intro_orbit_angle()
        )
        x, y = self._intro_orbit_position(angle)
        return x, y, -math.sin(angle) * SCALE_X, math.cos(angle) * SCALE_Y

    def _draw_intro_rocket(self, renderer, pose, alpha, visual_scale=1.0):
        x, y, dx, dy = pose
        length = max(0.001, math.hypot(dx, dy))
        forward_x, forward_y = dx / length, dy / length
        side_x, side_y = -forward_y, forward_x
        scale = min(SCALE_X, SCALE_Y) * visual_scale

        rects = []
        body = (
            (18.0, 7.0, (1.0, 0.92, 0.82, alpha)),
            (10.0, 10.0, (0.96, 0.12, 0.12, alpha)),
            (1.0, 12.0, (0.98, 0.98, 0.94, alpha)),
            (-9.0, 12.0, (0.96, 0.12, 0.12, alpha)),
            (-19.0, 10.0, (0.98, 0.98, 0.94, alpha)),
        )
        for along, size, color in body:
            px = x + forward_x * along * scale
            py = y + forward_y * along * scale
            rects.append(
                (
                    px - size * scale / 2,
                    py - size * scale / 2,
                    size * scale,
                    size * scale,
                    *color,
                )
            )
        for side in (-1.0, 1.0):
            px = x - forward_x * 14.0 * scale + side_x * side * 10.0 * scale
            py = y - forward_y * 14.0 * scale + side_y * side * 10.0 * scale
            rects.append(
                (
                    px - 4.5 * scale,
                    py - 4.5 * scale,
                    9.0 * scale,
                    9.0 * scale,
                    0.96,
                    0.12,
                    0.12,
                    alpha,
                )
            )
        renderer.set_blend_mode("alpha")
        renderer.draw_colored_rects(rects)

        plume = []
        renderer.set_blend_mode("additive")
        for index in range(7):
            distance = (27.0 + index * 7.0) * scale
            jitter = math.sin(self.intro_elapsed * 13.0 + index * 1.7) * 2.5 * scale
            px = x - forward_x * distance + side_x * jitter
            py = y - forward_y * distance + side_y * jitter
            fade = (1.0 - index / 8.0) * alpha
            plume.append(
                (
                    px,
                    py,
                    (16.0 - index * 1.25) * scale,
                    1.0,
                    0.31 + index * 0.035,
                    0.03,
                    fade,
                )
            )
        renderer.draw_particles(plume)

    def _draw_earth(
        self, renderer, center_x, center_y, width, height, longitude, latitude, alpha
    ):
        texture, _, _ = self._ensure_earth_texture(renderer)
        renderer.set_blend_mode("alpha")
        renderer.draw_earth_globe(
            texture,
            center_x - width / 2,
            center_y - height / 2,
            width,
            height,
            longitude,
            latitude,
            alpha,
        )

    def _draw_orbit_intro(self, renderer, alpha):
        pose = self._intro_rocket_pose()
        center_x, center_y, earth_width, earth_height = self._intro_earth_geometry()
        longitude = self._earth_idle_longitude()
        rocket_scale = 1.0

        if self.phase is MissionPhase.CRASH:
            zoom_progress = self._ease(
                min(1.0, self.crash_progress / self.CRASH_ZOOM_PROGRESS)
            )
            zoom = 1.0 + zoom_progress * 3.8
            target_x = SCREEN_WIDTH / 2
            target_y = 360.0 * SCALE_Y
            center_x = target_x + (center_x - pose[0]) * zoom
            center_y = target_y + (center_y - pose[1]) * zoom
            earth_width *= zoom
            earth_height *= zoom
            pose = (target_x, target_y, pose[2], pose[3])
            rocket_scale += zoom_progress * 3.4
            longitude = (
                self._crash_start_longitude
                + self.phase_elapsed * self.EARTH_SPIN_RADIANS_PER_SECOND
            )
        elif self._earth_return_zoom > 0.0:
            # Re-enter from the departing rocket, then rapidly widen to the
            # normal Earth framing instead of cutting to a static wide shot.
            zoom_progress = 1.0 - self._earth_return_zoom
            eased_zoom = self._ease(zoom_progress)
            zoom = 3.8 - 2.8 * eased_zoom
            target_x = SCREEN_WIDTH / 2
            target_y = 360.0 * SCALE_Y
            orbit_x, orbit_y = pose[0], pose[1]
            rocket_x = target_x + (orbit_x - target_x) * eased_zoom
            rocket_y = target_y + (orbit_y - target_y) * eased_zoom
            center_x = rocket_x + (center_x - orbit_x) * zoom
            center_y = rocket_y + (center_y - orbit_y) * zoom
            earth_width *= zoom
            earth_height *= zoom
            pose = (rocket_x, rocket_y, pose[2], pose[3])
            rocket_scale = 1.0 + (zoom - 1.0) * 1.15

        rocket_behind = pose[1] < center_y and self.phase is not MissionPhase.CRASH
        if rocket_behind:
            self._draw_intro_rocket(renderer, pose, alpha * 0.78, rocket_scale)
        self._draw_earth(
            renderer,
            center_x,
            center_y,
            earth_width,
            earth_height,
            longitude,
            self.EARTH_IDLE_LATITUDE,
            alpha,
        )
        if not rocket_behind:
            self._draw_intro_rocket(renderer, pose, alpha, rocket_scale)

    def _cockpit_progress(self):
        start = self.CRASH_ZOOM_PROGRESS * 0.78
        return self._ease(
            min(1.0, max(0.0, (self.crash_progress - start) / (1.0 - start)))
        )

    def _cockpit_earth_orientation(self, cockpit_progress):
        spinning_longitude = (
            self._crash_start_longitude
            + self.phase_elapsed * self.EARTH_SPIN_RADIANS_PER_SECOND
        )
        omagari_lock = self._ease(min(1.0, max(0.0, (cockpit_progress - 0.24) / 0.66)))
        target_longitude = self._crash_target_longitude
        if target_longitude is None:
            target_longitude = self._forward_target_longitude(
                self._crash_start_longitude
            )
        longitude = (
            spinning_longitude + (target_longitude - spinning_longitude) * omagari_lock
        )
        latitude = (
            self.EARTH_IDLE_LATITUDE
            + (self.OMAGARI_LATITUDE - self.EARTH_IDLE_LATITUDE) * omagari_lock
        )
        return longitude, latitude, omagari_lock

    def _draw_cockpit_ui(self, renderer, pixel_font, progress, omagari_lock, alpha):
        sx = SCALE_X
        sy = SCALE_Y
        window_left = 225.0 * sx
        window_right = 1695.0 * sx
        window_top = 52.0 * sy
        window_bottom = 760.0 * sy
        frame = (0.035, 0.055, 0.080, 0.98 * alpha)
        frame_edge = (0.16, 0.24, 0.31, 0.95 * alpha)
        console = (0.025, 0.036, 0.052, 0.99 * alpha)
        renderer.set_blend_mode("alpha")
        renderer.draw_colored_rects(
            [
                (0, 0, SCREEN_WIDTH, window_top, *frame),
                (0, window_top, window_left, window_bottom - window_top, *frame),
                (
                    window_right,
                    window_top,
                    SCREEN_WIDTH - window_right,
                    window_bottom - window_top,
                    *frame,
                ),
                (
                    0,
                    window_bottom,
                    SCREEN_WIDTH,
                    SCREEN_HEIGHT - window_bottom,
                    *console,
                ),
                (
                    window_left - 18 * sx,
                    window_top,
                    18 * sx,
                    window_bottom - window_top,
                    *frame_edge,
                ),
                (
                    window_right,
                    window_top,
                    18 * sx,
                    window_bottom - window_top,
                    *frame_edge,
                ),
                (
                    window_left,
                    window_top,
                    window_right - window_left,
                    14 * sy,
                    *frame_edge,
                ),
                (
                    window_left,
                    window_bottom - 18 * sy,
                    window_right - window_left,
                    18 * sy,
                    *frame_edge,
                ),
            ]
        )

        target_x = SCREEN_WIDTH / 2
        target_y = 365.0 * sy
        reticle = (1.0, 0.31, 0.12, (0.45 + omagari_lock * 0.50) * alpha)
        gap = 24.0 * sx
        arm = 68.0 * sx
        renderer.draw_colored_lines(
            [
                (target_x - arm, target_y, target_x - gap, target_y, *reticle),
                (target_x + gap, target_y, target_x + arm, target_y, *reticle),
                (
                    target_x,
                    target_y - arm * sy / sx,
                    target_x,
                    target_y - gap * sy / sx,
                    *reticle,
                ),
                (
                    target_x,
                    target_y + gap * sy / sx,
                    target_x,
                    target_y + arm * sy / sx,
                    *reticle,
                ),
            ]
        )

        pulse = 0.68 + 0.32 * math.sin(self.phase_elapsed * 12.0)
        red = (1.0, 0.12, 0.08, pulse * alpha)
        cell_count = 4
        bar_y = 875.0 * sy
        bar_width = 92.0 * sx
        spacing = 112.0 * sx
        bar_x = (SCREEN_WIDTH - (bar_width + (cell_count - 1) * spacing)) / 2.0
        for index in range(cell_count):
            renderer.draw_rect(
                bar_x + index * 112.0 * sx,
                bar_y,
                bar_width,
                34.0 * sy,
                (0.20, 0.035, 0.035, 0.92 * alpha),
                fill=True,
            )
            renderer.draw_rect(
                bar_x + index * 112.0 * sx,
                bar_y,
                bar_width,
                34.0 * sy,
                red,
                fill=False,
            )

        if pixel_font is not None:
            renderer.draw_pixel_text(
                SCREEN_WIDTH / 2,
                808.0 * sy,
                "SOT-KUN EMERGENCY TERMINAL",
                pixel_font,
                5,
                (0.66, 0.80, 0.90, 0.94 * alpha),
                centered=True,
            )
            renderer.draw_pixel_text(
                SCREEN_WIDTH / 2,
                935.0 * sy,
                "ENERGY 0%  -  POWER FAILURE",
                pixel_font,
                6,
                red,
                centered=True,
            )
            if omagari_lock > 0.56:
                renderer.draw_pixel_text(
                    target_x,
                    target_y + 92.0 * sy,
                    "OMAGARI, AKITA  39.4531 N  140.4754 E",
                    pixel_font,
                    4,
                    (1.0, 0.62, 0.22, omagari_lock * alpha),
                    centered=True,
                )

    def _draw_intro_impact(self, renderer, alpha):
        progress = self.crash_progress
        if progress < self.CRASH_IMPACT_PROGRESS:
            return
        age = min(
            1.0,
            (progress - self.CRASH_IMPACT_PROGRESS)
            / (1.0 - self.CRASH_IMPACT_PROGRESS),
        )
        x = SCREEN_WIDTH / 2
        y = 365.0 * SCALE_Y
        renderer.set_blend_mode("additive")
        renderer.draw_circle(
            x,
            y,
            (30.0 + age * 190.0) * SCALE_X,
            (1.0, 0.46, 0.08, (1.0 - age) * alpha * 0.74),
        )
        renderer.draw_circle(
            x,
            y,
            (13.0 + age * 82.0) * SCALE_X,
            (1.0, 0.96, 0.82, (1.0 - age) * alpha),
        )
        particles = []
        for index in range(42):
            angle = index * math.tau / 42.0 + 0.35
            distance = age * (55.0 + (index % 8) * 22.0) * SCALE_X
            particles.append(
                (
                    x + math.cos(angle) * distance,
                    y + math.sin(angle) * distance * 0.72,
                    (18.0 - age * 7.0) * SCALE_X,
                    1.0,
                    0.42 + (index % 3) * 0.18,
                    0.08,
                    (1.0 - age) * alpha,
                )
            )
        renderer.draw_particles(particles)

    def _draw_cockpit_intro(self, renderer, pixel_font, alpha):
        progress = self._cockpit_progress()
        if progress <= 0.001:
            return
        longitude, latitude, omagari_lock = self._cockpit_earth_orientation(progress)
        earth_size = (590.0 + (progress**2.05) * 1730.0) * min(SCALE_X, SCALE_Y)
        self._draw_earth(
            renderer,
            SCREEN_WIDTH / 2,
            365.0 * SCALE_Y,
            earth_size,
            earth_size,
            longitude,
            latitude,
            progress * alpha,
        )
        self._draw_cockpit_ui(
            renderer,
            pixel_font,
            progress,
            omagari_lock,
            progress * alpha,
        )
        self._draw_intro_impact(renderer, alpha)

    def draw_intro(self, renderer, pixel_font=None):
        alpha = self.intro_alpha
        if alpha <= 0.001:
            return

        if self.phase is MissionPhase.CRASH:
            orbit_fade = 1.0 - self._ease(
                min(
                    1.0,
                    max(
                        0.0,
                        (self.crash_progress - self.CRASH_ZOOM_PROGRESS * 0.78)
                        / (self.CRASH_ZOOM_PROGRESS * 0.22),
                    ),
                )
            )
            if orbit_fade > 0.001:
                self._draw_orbit_intro(renderer, alpha * orbit_fade)
            self._draw_cockpit_intro(renderer, pixel_font, alpha)
        else:
            self._draw_orbit_intro(renderer, alpha)
        renderer.set_blend_mode("additive")

    def charge_shake(self, frame_count):
        """Return a body-only tremble that grows with reserved charge."""
        count = len(self.reserved_generators)
        if self.phase is not MissionPhase.CHARGING or count < 1:
            return 0.0, 0.0
        amount = CHARGE_CUE_LEVELS[min(3, count)]["shake"]
        return (
            math.sin(frame_count * 0.71) * amount * SCALE_X,
            math.sin(frame_count * 0.93 + 0.8) * amount * 0.34 * SCALE_Y,
        )

    def _emit_prelaunch_vent(self, dt):
        """Leak low-energy charge particles from the full nozzle width."""
        charge_count = len(self.reserved_generators)
        cue = CHARGE_CUE_LEVELS[min(3, charge_count)]
        self._prelaunch_emission_accumulator += cue["rate"] * dt
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
            [
                805 * SCALE_Y + self._rng.uniform(-2.0, 4.0) * SCALE_Y
                for _ in range(count)
            ],
            dtype=np.float32,
        )
        vx = np.array(
            [self._rng.uniform(-0.75, 0.75) for _ in range(count)],
            dtype=np.float32,
        )
        vy = np.array(
            [self._rng.uniform(0.65, cue["speed"]) for _ in range(count)],
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
            life=cue["life"],
            size=cue["size"],
            gravity=0.018,
            drag=0.045,
            trail_len=1,
            intensity=cue["intensity"],
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

    def _rocket_screen_offset_y(self):
        """Single flight transform shared by the rocket and its exhaust."""
        successful_escape = (
            self.phase is MissionPhase.RETURN and self._return_camera_start > 0.0
        )
        reveal_offset = (
            0.0
            if successful_escape
            else (1.0 - self._ease(self.scene_progress)) * self.REVEAL_CAMERA_TRAVEL
        )
        return reveal_offset + self.rocket_offset_y + self.camera_y

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
        exhaust_y = 805 * SCALE_Y + self._rocket_screen_offset_y()
        spread = 1.7 + tier.plume_layers * 0.8
        tail_half_width = (24 + tier.plume_layers * 5) * SCALE_X
        exhaust_x = np.array(
            [
                rocket_x + self._rng.uniform(-tail_half_width, tail_half_width)
                for _ in range(count)
            ],
            dtype=np.float32,
        )
        exhaust_origin_y = np.array(
            [exhaust_y + self._rng.uniform(-3.0, 5.0) * SCALE_Y for _ in range(count)],
            dtype=np.float32,
        )
        vx = np.array(
            [self._rng.uniform(-spread, spread) for _ in range(count)], dtype=np.float32
        )
        base_vy = 2.5 if grounded else 5.0 + tier.plume_layers
        vy = np.array(
            [self._rng.uniform(base_vy * 0.65, base_vy * 1.35) for _ in range(count)],
            dtype=np.float32,
        )
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
            [
                self._rng.uniform(-spread * 1.4, spread * 1.4)
                for _ in range(smoke_count)
            ],
            dtype=np.float32,
        )
        smoke_vy = np.array(
            [self._rng.uniform(0.4, 2.0) for _ in range(smoke_count)],
            dtype=np.float32,
        )
        smoke_x = np.array(
            [
                rocket_x + self._rng.uniform(-tail_half_width, tail_half_width)
                for _ in range(smoke_count)
            ],
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

    def launch_cosmos_strength(self):
        if self.phase is MissionPhase.IGNITION and self.launch_tier:
            progress = min(1.0, self.phase_elapsed / self.launch_tier.ignition_seconds)
            return self._ease(progress) * 0.62
        if self.phase is MissionPhase.ASCENT:
            return 1.0
        if self.phase is MissionPhase.DEPARTURE:
            progress = min(1.0, self.phase_elapsed / self.DEPARTURE_SECONDS)
            return max(0.25, 1.0 - progress * 0.62)
        if self.phase is MissionPhase.RECORD_HOLD:
            return 0.42
        if self.phase is MissionPhase.RETURN and self._return_camera_start > 0.0:
            return 0.42 + (1.0 - self.scene_progress) * 0.58
        return 0.0

    def draw_stars(self, renderer, frame_count):
        rows = []
        streaks = []
        camera_shift = self._ease(self.scene_progress) * 280.0 * SCALE_Y
        launch_activity = self.launch_cosmos_strength()
        earth_star_strength = (
            self._earth_return_stars if self.phase is MissionPhase.ATTRACT else 0.0
        )
        earth_star_angle = self._star_field_angle
        # Keep the field nearly stationary; the luminous curved trails carry
        # the orbital motion without making the whole view feel like it spins.
        orbit_cos = math.cos(earth_star_angle)
        orbit_sin = math.sin(earth_star_angle)
        orbit_center_x, orbit_center_y = self._earth_return_screen_center()
        successful_return = (
            self.phase is MissionPhase.RETURN and self._return_camera_start > 0.0
        )
        return_progress = (
            max(0.0, 1.0 - self.scene_progress) if successful_return else 0.0
        )
        streak_progress = min(
            1.0,
            max(
                0.0,
                (return_progress - self.STAR_STREAK_START)
                / (self.ROCKET_ESCAPE_END - self.STAR_STREAK_START),
            ),
        )
        for x, y, size, alpha, depth, phase, blink_speed, blink_strength in self._stars:
            draw_y = (
                y - camera_shift * depth + self.camera_y * depth * 0.055
            ) % SCREEN_HEIGHT
            draw_x = x
            if abs(earth_star_angle) > 0.0001:
                relative_x = x - orbit_center_x
                relative_y = draw_y - orbit_center_y
                draw_x = (
                    orbit_center_x + relative_x * orbit_cos - relative_y * orbit_sin
                )
                draw_y = (
                    orbit_center_y + relative_x * orbit_sin + relative_y * orbit_cos
                )
            activity_speed = blink_speed * (1.0 + launch_activity * 2.4)
            wave = 0.5 + 0.5 * math.sin(frame_count * activity_speed + phase)
            blink = wave ** (6.0 - launch_activity * 2.5)
            reactive_flash = launch_activity * (0.22 + depth * 0.34) * blink
            twinkle = alpha * (
                0.58 + 0.20 * wave + blink_strength * blink + reactive_flash
            )
            blink_size = size * (
                1.0 + blink_strength * blink * 0.68 + reactive_flash * 0.72
            )
            rows.append(
                (draw_x, draw_y, blink_size, 0.68, 0.78, 1.0, min(1.0, twinkle))
            )
            if earth_star_strength > 0.01:
                radial_x = draw_x - orbit_center_x
                radial_y = draw_y - orbit_center_y
                # Remaining motion is also normalized angular velocity for the
                # quadratic ease-out, so trails naturally contract as the sky
                # settles around Earth.
                trail_velocity = earth_star_strength
                arc_angle = 0.28 * trail_velocity**1.10 * (0.82 + depth * 0.34)
                previous_x = draw_x
                previous_y = draw_y
                for segment in range(1, self.EARTH_RETURN_TRAIL_SEGMENTS + 1):
                    segment_angle = (
                        -arc_angle * segment / self.EARTH_RETURN_TRAIL_SEGMENTS
                    )
                    segment_cos = math.cos(segment_angle)
                    segment_sin = math.sin(segment_angle)
                    tail_x = (
                        orbit_center_x + radial_x * segment_cos - radial_y * segment_sin
                    )
                    tail_y = (
                        orbit_center_y + radial_x * segment_sin + radial_y * segment_cos
                    )
                    segment_fade = 1.0 - (segment - 1) / (
                        self.EARTH_RETURN_TRAIL_SEGMENTS + 1.0
                    )
                    streaks.append(
                        (
                            tail_x,
                            tail_y,
                            previous_x,
                            previous_y,
                            0.70,
                            0.88,
                            1.0,
                            min(
                                0.96,
                                alpha
                                * trail_velocity**0.85
                                * segment_fade
                                * (0.64 + depth * 0.56),
                            ),
                        )
                    )
                    previous_x = tail_x
                    previous_y = tail_y
            if streak_progress > 0.0:
                speed = streak_progress**2.0
                trail_length = (12.0 + speed * 900.0) * depth * SCALE_Y
                streak_alpha = min(
                    0.92,
                    alpha * (0.18 + depth * 0.62) * speed * 1.45,
                )
                streaks.append(
                    (
                        draw_x,
                        draw_y - trail_length,
                        draw_x,
                        draw_y,
                        0.58,
                        0.78,
                        1.0,
                        streak_alpha,
                    )
                )

        for event in self._cosmic_events:
            if event["kind"] == "meteor_shower":
                for start_x, start_y, vx, vy, delay in event["streaks"]:
                    local_age = event["age"] - delay
                    if local_age < 0.0 or local_age > 1.65:
                        continue
                    progress = local_age / 1.65
                    envelope = math.sin(math.pi * progress)
                    head_x = start_x + vx * local_age
                    head_y = start_y + vy * local_age
                    speed = max(1.0, math.hypot(vx, vy))
                    trail_x = vx / speed
                    trail_y = vy / speed
                    for index in range(10, 0, -1):
                        strength = (1.0 - index / 11.0) ** 1.25
                        distance = index * 12.0 * SCALE_X
                        rows.append(
                            (
                                head_x - trail_x * distance,
                                head_y - trail_y * distance,
                                (2.0 + strength * 5.5) * SCALE_X,
                                0.58,
                                0.76,
                                1.0,
                                envelope * strength * 0.72,
                            )
                        )
                    rows.append(
                        (head_x, head_y, 9.0 * SCALE_X, 0.94, 0.98, 1.0, envelope)
                    )
            elif event["kind"] == "constellation_pulse":
                progress = min(1.0, event["age"] / event["duration"])
                envelope = math.sin(math.pi * progress)
                radius = (34.0 + self._ease(progress) * 330.0) * SCALE_X
                for index, phase in enumerate(event["phases"]):
                    local_radius = radius * (0.68 + 0.32 * math.sin(phase * 1.7) ** 2)
                    angle = phase + event["age"] * (0.10 + index % 3 * 0.018)
                    x = event["x"] + math.cos(angle) * local_radius
                    y = event["y"] + math.sin(angle) * local_radius * 0.48
                    pulse = 0.64 + 0.36 * math.sin(frame_count * 0.18 + phase)
                    color = (0.72, 0.62, 1.0) if index % 3 else (0.48, 0.86, 1.0)
                    rows.append(
                        (
                            x,
                            y,
                            (3.0 + pulse * 5.0) * SCALE_X,
                            *color,
                            envelope * pulse * 0.76,
                        )
                    )
        if self._comet is not None:
            comet = self._comet
            boost = comet.get("boost", 1.0)
            speed = math.hypot(comet["vx"], comet["vy"])
            trail_x = comet["vx"] / speed
            trail_y = comet["vy"] / speed
            fade_in = min(1.0, comet["age"] / 0.35)
            fade_out = min(1.0, (comet["duration"] - comet["age"]) / 0.55)
            comet_alpha = max(0.0, min(fade_in, fade_out))
            trail_count = int(16 * boost)
            for index in range(trail_count, 0, -1):
                distance = index * 13.0 * SCALE_X
                strength = (1.0 - index / (trail_count + 1.0)) ** 1.35
                rows.append(
                    (
                        comet["x"] - trail_x * distance,
                        comet["y"] - trail_y * distance,
                        (2.5 + strength * 7.0 * boost) * SCALE_X,
                        0.52,
                        0.76,
                        1.0,
                        comet_alpha * strength * min(1.0, 0.68 * boost),
                    )
                )
            rows.append(
                (
                    comet["x"],
                    comet["y"],
                    12.0 * SCALE_X * boost,
                    0.92,
                    0.98,
                    1.0,
                    comet_alpha,
                )
            )
        renderer.set_blend_mode("additive")
        if streaks:
            renderer.draw_colored_lines(streaks)
        renderer.draw_particles(np.asarray(rows, dtype=np.float32))

    def grass_propulsion_strength(self):
        """Rocket wash applied to nearby grass, normalized to liftoff peak."""
        if self.phase is MissionPhase.CHARGING:
            return {1: 0.07, 2: 0.16, 3: 0.30}.get(
                min(3, len(self.reserved_generators)), 0.0
            )
        if self.phase is MissionPhase.IGNITION and self.launch_tier:
            progress = min(1.0, self.phase_elapsed / self.launch_tier.ignition_seconds)
            return 0.30 + self._ease(progress) * 0.58
        if self.phase is MissionPhase.ASCENT and self.launch_tier:
            progress = min(1.0, self.phase_elapsed / self.launch_tier.ascent_seconds)
            return max(0.0, 1.0 - progress / 0.65)
        return 0.0

    def grass_propulsion_profile(self):
        """Strength, reach, edge force, flutter rate, and peak bend."""
        strength = self.grass_propulsion_strength()
        if self.phase is MissionPhase.CHARGING:
            return strength, 2400 * SCALE_X, 0.0, 1.04, 168 * SCALE_X
        if self.phase is MissionPhase.IGNITION and self.launch_tier:
            progress = min(1.0, self.phase_elapsed / self.launch_tier.ignition_seconds)
            build = self._ease(progress)
            return (
                strength,
                (2400 + 2800 * build) * SCALE_X,
                0.14 * build,
                1.16 + 0.28 * build,
                (192 + 32 * build) * SCALE_X,
            )
        if self.phase is MissionPhase.ASCENT and self.launch_tier:
            # At liftoff every visible cluster receives a meaningful impulse;
            # strength then fades while the coverage remains screen-wide.
            return strength, SCREEN_WIDTH * 3.20, 0.34, 1.64, 248 * SCALE_X
        return 0.0, 2400 * SCALE_X, 0.0, 1.04, 168 * SCALE_X

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
        resumed_reveal = (
            self.phase is MissionPhase.REVEAL and not self._logo_hidden_for_reveal
        )
        attract_alpha = (
            0.78
            if self._intro_played
            and (
                self.phase in (MissionPhase.ATTRACT, MissionPhase.RETURN)
                or resumed_reveal
            )
            and not (
                self.phase is MissionPhase.RETURN and self._return_camera_start > 0.0
            )
            else 0.0
        )
        alpha = max(self.scene_alpha, attract_alpha)
        if alpha <= 0.001:
            return
        eased_scene = self._ease(self.scene_progress)
        firework_lights = (
            firework_lights if firework_lights is not None else np.empty((0, 8))
        )
        base_y = (
            820 * SCALE_Y
            + (1.0 - eased_scene) * (SCREEN_HEIGHT - 820 * SCALE_Y)
            + self.camera_y * 0.20
        )
        ground_y = (
            820 * SCALE_Y
            + (1.0 - eased_scene) * self.REVEAL_CAMERA_TRAVEL
            + self.camera_y
        )

        # Vertical parallax makes the foreground ground descend faster than the
        # skyline. Extend the far city's foundation through that interval so
        # the residential layer can pass without exposing a strip of sky.
        if renderer is not None:
            foundation_top = max(0.0, base_y - SCALE_Y)
            foundation_bottom = min(float(SCREEN_HEIGHT), ground_y + SCALE_Y)
            if foundation_bottom > foundation_top:
                renderer.set_blend_mode("alpha")
                renderer.draw_rect(
                    0,
                    foundation_top,
                    SCREEN_WIDTH,
                    foundation_bottom - foundation_top,
                    (0.018, 0.034, 0.061, alpha),
                    fill=True,
                )
        self._draw_city_layer(
            renderer,
            self._skyscrapers,
            base_y=base_y,
            parallax_x=self.camera_y * 0.006,
            alpha=alpha,
            lights=firework_lights,
            near=False,
        )

    def draw_world(
        self, renderer, frame_count, firework_lights=None, launch_lights=None
    ):
        alpha = self.scene_alpha
        firework_lights = (
            firework_lights if firework_lights is not None else np.empty((0, 8))
        )
        launch_lights = launch_lights if launch_lights is not None else np.empty((0, 8))
        eased_scene = self._ease(self.scene_progress)
        reveal_offset = (1.0 - eased_scene) * self.REVEAL_CAMERA_TRAVEL
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
        self._draw_ground(
            renderer, ground_y, frame_count, alpha, firework_lights, launch_lights
        )
        self._draw_launch_base(
            renderer, ground_y, alpha, firework_lights, launch_lights
        )

        rocket_y = self._rocket_screen_offset_y()
        shake_x, shake_y = self.charge_shake(frame_count)
        if self.phase is MissionPhase.IGNITION and self.launch_tier:
            build = min(1.0, self.phase_elapsed / self.launch_tier.ignition_seconds)
            amount = self.launch_tier.shake * build
            shake_x = self._rng.uniform(-amount, amount)
            shake_y = self._rng.uniform(-amount * 0.45, amount * 0.45)
        if self.phase is not MissionPhase.RETURN:
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

    def draw_rocket_foreground(
        self,
        renderer,
        frame_count,
        firework_lights=None,
        launch_lights=None,
    ):
        """Keep the rocket body in front of its exhaust particle layer."""
        if self.phase not in (
            MissionPhase.RECORD_HOLD,
            MissionPhase.RETURN,
        ):
            return
        alpha = self.scene_alpha
        if alpha <= 0.001:
            return
        firework_lights = (
            firework_lights if firework_lights is not None else np.empty((0, 8))
        )
        launch_lights = launch_lights if launch_lights is not None else np.empty((0, 8))
        rocket_y = self._rocket_screen_offset_y()
        shake_x = 0.0
        shake_y = 0.0
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

    def _draw_city_layer(
        self, renderer, buildings, base_y, parallax_x, alpha, lights, near
    ):
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
        for (
            source_x,
            width,
            height,
            cols,
            rows,
            lit_windows,
            roof,
            variation,
        ) in buildings:
            x = source_x
            y = base_y - height
            if y > SCREEN_HEIGHT or base_y < 0.0:
                continue
            if (
                near
                and x < SCREEN_WIDTH / 2 + 310 * SCALE_X
                and x + width > SCREEN_WIDTH / 2 - 310 * SCALE_X
            ):
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
                light_lines.append(
                    (x + width, y, x + width, y + height, *light, alpha * 0.24)
                )
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

    def _draw_ground(
        self, renderer, ground_y, frame_count, alpha, firework_lights, launch_lights
    ):
        if ground_y >= SCREEN_HEIGHT:
            return
        renderer.draw_rect(
            0,
            ground_y,
            SCREEN_WIDTH,
            SCREEN_HEIGHT - ground_y,
            (0.025, 0.022, 0.026, alpha),
            fill=True,
        )
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
            light = tuple(
                min(1.0, launch[channel] + fire[channel] * 0.22) for channel in range(3)
            )
            surface = self._lit((0.022, 0.055, 0.035), light, 0.34)
            soil = self._lit((0.025, 0.022, 0.026), light, 0.19)
            ground_rects.append(
                (
                    x,
                    ground_y,
                    segment_width + 1.0,
                    SCREEN_HEIGHT - ground_y,
                    *soil,
                    alpha,
                )
            )
            ground_rects.append(
                (x, ground_y, segment_width + 1.0, 18 * SCALE_Y, *surface, alpha)
            )

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
            local = tuple(
                min(1.0, launch[channel] + fire[channel] * 0.20) for channel in range(3)
            )
            color = self._lit(bases[shade], local, 0.25)
            ground_rects.append(
                (x, y, width, max(2.0, 3 * SCALE_Y), *color, alpha * 0.72)
            )
        renderer.draw_colored_rects(ground_rects)
        renderer.draw_line(
            0,
            ground_y + 20 * SCALE_Y,
            SCREEN_WIDTH,
            ground_y + 20 * SCALE_Y,
            (0.08, 0.10, 0.075, alpha * 0.72),
        )

        if ground_y < -60 * SCALE_Y:
            return
        blade_geometry = []
        (
            propulsion,
            propulsion_radius,
            minimum_falloff,
            flutter_rate,
            peak_bend,
        ) = self.grass_propulsion_profile()
        rocket_x = SCREEN_WIDTH / 2
        for center, phase, speed, gust_response, blades in self._grass:
            cluster_gust = 0.58 + 0.42 * math.sin(
                frame_count * 0.013 * speed + phase * 0.43
            )
            slow_push = math.sin(frame_count * 0.021 + phase) * 1.8 * SCALE_X
            distance_from_rocket = abs(center - rocket_x)
            propulsion_falloff = max(
                minimum_falloff,
                max(0.0, 1.0 - distance_from_rocket / propulsion_radius) ** 1.45,
            )
            outward = -1.0 if center < rocket_x else 1.0
            propulsion_flutter = 0.76 + 0.24 * math.sin(
                frame_count * flutter_rate * speed + phase
            )
            rocket_push = (
                outward
                * propulsion
                * propulsion_falloff
                * propulsion_flutter
                * peak_bend
            )
            for offset, height, blade_phase, amplitude in blades:
                x = center + offset
                if ground_y - height > SCREEN_HEIGHT:
                    continue
                ripple = math.sin(frame_count * 0.052 * speed + phase + blade_phase)
                height_response = min(1.0, height / (28 * SCALE_Y))
                sway = (
                    ripple * amplitude * (0.56 + cluster_gust * gust_response)
                    + slow_push
                    + rocket_push * height_response
                )
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
            local = tuple(
                min(1.0, launch[channel] + fire[channel] * 0.30) for channel in range(3)
            )
            base_green = (0.064, 0.19 + blade_phase * 0.035, 0.088)
            color = (*self._lit(base_green, local, 0.62), alpha)
            grass_lines.append((x, base_y, mid_x, mid_y, *color))
            grass_lines.append((mid_x, mid_y, tip_x, tip_y, *color))
        renderer.draw_colored_lines(grass_lines)

    def _draw_launch_base(
        self, renderer, ground_y, alpha, firework_lights, launch_lights
    ):
        if ground_y > SCREEN_HEIGHT + 90 * SCALE_Y or ground_y < -130 * SCALE_Y:
            return
        cx = SCREEN_WIDTH / 2
        fire = self._sample_light(cx, ground_y - 25 * SCALE_Y, firework_lights)
        launch = self._sample_light(cx, ground_y - 25 * SCALE_Y, launch_lights)
        light = tuple(
            min(1.0, launch[channel] + fire[channel] * 0.24) for channel in range(3)
        )
        steel = self._lit((0.105, 0.13, 0.15), light, 0.35)
        edge = self._lit((0.28, 0.32, 0.34), light, 0.45)

        renderer.set_blend_mode("alpha")
        renderer.draw_rect(
            cx - 220 * SCALE_X,
            ground_y - 10 * SCALE_Y,
            440 * SCALE_X,
            24 * SCALE_Y,
            (*steel, alpha),
            fill=True,
        )
        renderer.draw_rect(
            cx - 180 * SCALE_X,
            ground_y - 24 * SCALE_Y,
            360 * SCALE_X,
            16 * SCALE_Y,
            (*edge, alpha),
            fill=True,
        )
        renderer.draw_rect(
            cx - 68 * SCALE_X,
            ground_y - 27 * SCALE_Y,
            136 * SCALE_X,
            24 * SCALE_Y,
            (0.008, 0.009, 0.012, alpha),
            fill=True,
        )
        renderer.draw_rect(
            cx - 220 * SCALE_X,
            ground_y - 10 * SCALE_Y,
            440 * SCALE_X,
            24 * SCALE_Y,
            (*edge, alpha * 0.9),
            fill=False,
        )

        for side in (-1, 1):
            support_x = cx + side * 112 * SCALE_X
            renderer.draw_rect(
                support_x - 8 * SCALE_X,
                ground_y - 82 * SCALE_Y,
                16 * SCALE_X,
                72 * SCALE_Y,
                (*steel, alpha),
                fill=True,
            )
            renderer.draw_rect(
                support_x - 8 * SCALE_X,
                ground_y - 82 * SCALE_Y,
                16 * SCALE_X,
                72 * SCALE_Y,
                (*edge, alpha * 0.85),
                fill=False,
            )
            renderer.draw_line(
                support_x,
                ground_y - 67 * SCALE_Y,
                cx + side * 56 * SCALE_X,
                ground_y - 47 * SCALE_Y,
                (*edge, alpha),
            )

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
            (
                cx - 3 * block,
                top + 10 * block,
                6 * block,
                3 * block,
                (0.88, 0.91, 0.94),
            ),
            (
                cx - 5 * block,
                top + 9 * block,
                2 * block,
                4 * block,
                (0.90, 0.045, 0.035),
            ),
            (
                cx + 3 * block,
                top + 9 * block,
                2 * block,
                4 * block,
                (0.90, 0.045, 0.035),
            ),
            (
                cx - 1.5 * block,
                top + 13 * block,
                3 * block,
                1.45 * block,
                (0.12, 0.13, 0.145),
            ),
        )
        renderer.set_blend_mode("alpha")
        panel_points = [
            (x + width / 2, y + height / 2) for x, y, width, height, base in panels
        ]
        panel_fire = self._sample_lights(panel_points, firework_lights)
        panel_launch = self._sample_lights(panel_points, launch_lights)
        for (x, y, width, height, base), fire, launch in zip(
            panels,
            panel_fire,
            panel_launch,
        ):
            diffuse = tuple(
                min(1.0, launch[channel] + fire[channel] * 0.12) for channel in range(3)
            )
            rim = tuple(
                min(1.0, launch[channel] + fire[channel] * 0.62) for channel in range(3)
            )
            color = self._lit(base, diffuse, 0.50)
            edge = self._lit((0.24, 0.27, 0.30), rim, 0.62)
            renderer.draw_rect(x, y, width, height, (*color, alpha), fill=True)
            renderer.draw_rect(x, y, width, height, (*edge, alpha * 0.85), fill=False)

        # Offset plates, seams, and rivets give the red-and-white block rocket material
        # without turning it into a character or changing its silhouette.
        seam_fire = self._sample_light(cx, top + 8 * block, firework_lights)
        seam_launch = self._sample_light(cx, top + 8 * block, launch_lights)
        seam_light = tuple(
            min(1.0, seam_launch[channel] + seam_fire[channel] * 0.38)
            for channel in range(3)
        )
        seam = (*self._lit((0.25, 0.28, 0.31), seam_light, 0.8), alpha * 0.82)
        renderer.draw_line(cx, top + 3 * block, cx, top + 13 * block, seam)
        renderer.draw_line(
            cx - 3 * block, top + 6 * block, cx + 3 * block, top + 6 * block, seam
        )
        renderer.draw_line(
            cx - 3 * block, top + 10 * block, cx + 3 * block, top + 10 * block, seam
        )
        accent_fire = self._sample_light(cx, top + 7.6 * block, firework_lights)
        accent_launch = self._sample_light(cx, top + 7.6 * block, launch_lights)
        accent_light = tuple(
            min(1.0, accent_launch[channel] + accent_fire[channel] * 0.20)
            for channel in range(3)
        )
        accent = self._lit((0.92, 0.045, 0.035), accent_light, 0.42)
        renderer.draw_rect(
            cx - 3 * block,
            top + 7.45 * block,
            6 * block,
            0.42 * block,
            (*accent, alpha),
            fill=True,
        )
        rivet = self._lit((0.42, 0.46, 0.50), seam_light, 1.0)
        for dx in (-2.45, 2.45):
            for row in (4.0, 7.5, 11.5):
                renderer.draw_rect(
                    cx + dx * block - 2 * SCALE_X,
                    top + row * block,
                    4 * SCALE_X,
                    4 * SCALE_Y,
                    (*rivet, alpha),
                    fill=True,
                )

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
        if not self.launch_tier or self.phase not in (
            MissionPhase.IGNITION,
            MissionPhase.ASCENT,
        ):
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
        if self.phase in (
            MissionPhase.ATTRACT,
            MissionPhase.CRASH,
            MissionPhase.REVEAL,
            MissionPhase.RECORD_HOLD,
            MissionPhase.RETURN,
        ):
            return None
        if self.phase is MissionPhase.IGNITION:
            return "ALL CELLS READY!", "HOLD ON, SOT-KUN. IT IS TIME TO GO HOME!"
        if self.phase in (MissionPhase.ASCENT, MissionPhase.DEPARTURE):
            return "LIFT OFF!", "HAVE A SAFE TRIP HOME, SOT-KUN!"
        if self._cell_message_time > 0.0 and self._cell_message is not None:
            name = (
                "CRANK"
                if self._cell_message is GeneratorType.HAND_CRANK
                else self._cell_message.name
            )
            return (
                f"{name} CELL READY!",
                "GREAT JOB! SOT-KUN IS ONE STEP CLOSER TO HOME.",
            )
        if snapshot.launch_ready:
            cell_count = len(snapshot.filled_generators)
            seconds = max(1, math.ceil(snapshot.launch_wait_remaining))
            return (
                f"{cell_count} CELLS READY! LAUNCH IN {seconds}",
                f"HELP SOT-KUN FIND ENERGY SOURCE {cell_count + 1}.",
            )
        selected = snapshot.selected_generators
        if len(selected) == 1:
            level = snapshot.energy_levels.get(selected[0], 0.0)
            if level >= MAX_ENERGY_GAUGE:
                return (
                    "CELL ENERGY RESERVED!",
                    "HELP SOT-KUN MOVE TO ANOTHER ENERGY SOURCE.",
                )
            return "POWER UP THE ENERGY CELL!", "SOT-KUN'S TRIP HOME STARTS WITH YOU."
        return (
            "POWER UP THE ACTIVE CELL!",
            "EACH FULL CELL KEEPS ITS ENERGY WHEN SOT-KUN MOVES.",
        )

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
        renderer.draw_pixel_text(
            SCREEN_WIDTH / 2 + 4,
            primary_y + 4,
            primary,
            pixel_font,
            8,
            (0.0, 0.0, 0.0, 0.72),
            centered=True,
        )
        renderer.draw_pixel_text(
            SCREEN_WIDTH / 2,
            primary_y,
            primary,
            pixel_font,
            8,
            (1.0, 0.92, 0.45, 1.0),
            centered=True,
        )
        renderer.draw_pixel_text(
            SCREEN_WIDTH / 2 + 3,
            secondary_y + 3,
            secondary,
            pixel_font,
            4,
            (0.0, 0.0, 0.0, 0.7),
            centered=True,
        )
        renderer.draw_pixel_text(
            SCREEN_WIDTH / 2,
            secondary_y,
            secondary,
            pixel_font,
            4,
            (0.78, 0.88, 1.0, 0.95),
            centered=True,
        )
        renderer.set_blend_mode("additive")
