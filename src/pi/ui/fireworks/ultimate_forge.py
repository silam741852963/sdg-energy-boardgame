"""Record-gated, four-input builder for a custom ultra firework finale."""

from __future__ import annotations

import math
import random
import time
from enum import Enum, auto

from ...config import GeneratorType
from . import palette
from .config import COLOR_MAP, SCALE_X, SCALE_Y, SCREEN_HEIGHT, SCREEN_WIDTH
from .models import generate_spec


class ForgePhase(Enum):
    INACTIVE = auto()
    RECORD_REVEAL = auto()
    CHOOSE_SHAPE = auto()
    CHOOSE_PALETTE = auto()
    CHOOSE_EFFECT = auto()
    LOCK_IN = auto()
    LAUNCH = auto()
    COMPLETE = auto()


GENERATORS = list(GeneratorType)
GEN_COLORS = {
    GeneratorType.WIND: "cyan",
    GeneratorType.SOLAR: "yellow",
    GeneratorType.PIEZO: "orange",
    GeneratorType.COIL: "lime",
}
SHAPES = {
    GeneratorType.WIND: ("GALAXY", "Galaxy"),
    GeneratorType.SOLAR: ("FIVE-POINT STAR", "Star"),
    GeneratorType.PIEZO: ("PULSE HEART", "Heart"),
    GeneratorType.COIL: ("ENERGY DIAMOND", "Diamond"),
}
PALETTES = {
    GeneratorType.WIND: ("SKY CURRENT", ["cyan", "blue", "silver"]),
    GeneratorType.SOLAR: ("SOLAR FLARE", ["gold", "orange", "yellow"]),
    GeneratorType.PIEZO: ("NEON PULSE", ["pink", "magenta", "violet"]),
    GeneratorType.COIL: ("TESLA NIGHT", ["blue", "indigo", "silver"]),
}
EFFECTS = {
    GeneratorType.WIND: "ROTATING TRAILS",
    GeneratorType.SOLAR: "SECONDARY SUNBURST",
    GeneratorType.PIEZO: "CRACKLE ECHOES",
    GeneratorType.COIL: "ORBITAL CHAIN",
}


class UltimateFireworkForge:
    """Small state machine that accepts only transitions between four Hall inputs."""

    REVEAL_SECONDS = 2.3
    CHOICE_SECONDS = 10.0
    PULSE_SECONDS = 1.6
    LAUNCH_SECONDS = 11.5

    def __init__(self, firework_manager, audio, lighting):
        self.firework_manager = firework_manager
        self.audio = audio
        self.lighting = lighting
        self.reset()

    def reset(self):
        self.phase = ForgePhase.INACTIVE
        self.phase_started = 0.0
        self.achievement = "GENERATOR RECORD"
        self.shape_gen = None
        self.palette_gen = None
        self.effect_gen = None
        self.previous_input = None
        self.last_transition_time = 0.0
        self.energy_strength = 0
        self.pending_launches = []
        self.launched = False
        self.launch_origin_y = SCREEN_HEIGHT // 2
        self.visual_started_at = 0.0
        self.selection_pulses = []
        self.choice_locked_at = {
            "shape": None,
            "palette": None,
            "effect": None,
        }

    @property
    def active(self):
        return self.phase not in (ForgePhase.INACTIVE, ForgePhase.COMPLETE)

    @property
    def blocks_show_completion(self):
        return self.active or bool(self.pending_launches)

    def start(self, achievement="GENERATOR RECORD", now=None):
        self.reset()
        self.achievement = achievement
        self.phase = ForgePhase.RECORD_REVEAL
        self.phase_started = now if now is not None else time.time()
        self.visual_started_at = self.phase_started
        self.audio.play_combo_unlock()

    def request_launch(self, now=None):
        """Allow an authored script marker to advance an active forge safely."""
        if self.phase in (ForgePhase.INACTIVE, ForgePhase.COMPLETE):
            return
        launch_time = now if now is not None else time.time()
        self.shape_gen = self.shape_gen or self._default_for_phase()
        self.palette_gen = self.palette_gen or self._default_for_phase()
        self.effect_gen = self.effect_gen or self._default_for_phase()
        for key in self.choice_locked_at:
            if self.choice_locked_at[key] is None:
                self.choice_locked_at[key] = launch_time - self.PULSE_SECONDS
        self.energy_strength = 8
        self._advance(ForgePhase.LAUNCH, launch_time)

    def _advance(self, phase, now):
        self.phase = phase
        self.phase_started = now

    def _stable_transition(self, active_generator, now):
        if active_generator == self.previous_input:
            return None
        self.previous_input = active_generator
        if active_generator is None or now - self.last_transition_time < 0.08:
            return None
        self.last_transition_time = now
        return active_generator

    def update(self, active_generator, now=None):
        now = now if now is not None else time.time()
        self._update_pending_launches(now)
        if self.phase in (ForgePhase.INACTIVE, ForgePhase.COMPLETE):
            return

        elapsed = now - self.phase_started
        transition = self._stable_transition(active_generator, now)

        if self.phase == ForgePhase.RECORD_REVEAL:
            if elapsed >= self.REVEAL_SECONDS:
                self._advance(ForgePhase.CHOOSE_SHAPE, now)
            return

        if self.phase in (
            ForgePhase.CHOOSE_SHAPE,
            ForgePhase.CHOOSE_PALETTE,
            ForgePhase.CHOOSE_EFFECT,
        ):
            if transition is not None:
                self._lock_choice(transition, now)
                return
            if elapsed >= self.CHOICE_SECONDS:
                self._lock_choice(self._default_for_phase(), now)
            return

        if self.phase == ForgePhase.LOCK_IN:
            if elapsed >= self.PULSE_SECONDS:
                self._advance(ForgePhase.LAUNCH, now)
            return

        if self.phase == ForgePhase.LAUNCH:
            travel_progress = min(1.0, elapsed / 2.2)
            self.launch_origin_y = int(
                SCREEN_HEIGHT // 2 + int(300 * SCALE_Y) * travel_progress
            )
            if elapsed >= 2.25 and not self.launched:
                self._launch_ultimate(now)
            if elapsed >= self.LAUNCH_SECONDS:
                self.phase = ForgePhase.COMPLETE

    def _default_for_phase(self):
        # Defaults rotate so an unattended forge remains attractive and varied.
        candidates = GENERATORS[:]
        used = {self.shape_gen, self.palette_gen, self.effect_gen}
        unused = [gen for gen in candidates if gen not in used]
        return random.choice(unused or candidates)

    def _lock_choice(self, generator, now):
        self.audio.play_success_chime()
        self.selection_pulses.append((generator, now))
        if self.phase == ForgePhase.CHOOSE_SHAPE:
            self.shape_gen = generator
            self.choice_locked_at["shape"] = now
            self._advance(ForgePhase.CHOOSE_PALETTE, now)
        elif self.phase == ForgePhase.CHOOSE_PALETTE:
            self.palette_gen = generator
            self.choice_locked_at["palette"] = now
            self._advance(ForgePhase.CHOOSE_EFFECT, now)
        else:
            self.effect_gen = generator
            self.choice_locked_at["effect"] = now
            # Choice determines personality; every player receives the complete
            # high-energy finale without another performance gate.
            self.energy_strength = 8
            self._advance(ForgePhase.LOCK_IN, now)

    def _build_spec(self):
        shape_gen = self.shape_gen or GeneratorType.WIND
        palette_gen = self.palette_gen or GeneratorType.SOLAR
        effect_gen = self.effect_gen or GeneratorType.COIL
        _, fw_type = SHAPES[shape_gen]
        _, colors = PALETTES[palette_gen]
        spec = generate_spec(fw_type)
        spec.base_color = colors[0]
        spec.colors = colors[:]
        spec.multicolor = len(colors)
        boost = min(1.0, self.energy_strength / 8.0)
        spec.particle_count = min(650, int(360 * (1.0 + 0.35 * boost)))
        spec.radius = min(3.4, 2.3 + 0.7 * boost)
        spec.intensity = min(3.5, 2.2 + boost)
        spec.life_span = min(190, int(spec.life_span * (1.15 + 0.25 * boost)))
        spec.speed_variance = min(24.0, spec.speed_variance * (1.15 + 0.2 * boost))
        if effect_gen == GeneratorType.WIND:
            spec.has_trails = True
            spec.spin = True
        elif effect_gen == GeneratorType.SOLAR:
            spec.pistil = True
            spec.pistil_color = "silver"
        elif effect_gen == GeneratorType.PIEZO:
            spec.crackle = True
            spec.flicker = True
        elif effect_gen == GeneratorType.COIL:
            spec.pistil = True
        return spec

    def _launch_ultimate(self, now):
        if self.launched:
            return
        self.launched = True
        self.audio.play_overdrive_unlock()
        self.lighting.trigger_sky_flash(COLOR_MAP.get("silver", 121))
        self._schedule_combination_show(now)

    def _schedule_combination_show(self, now):
        """Schedule exactly five Ultimate shells from left to right."""
        target_y = {
            GeneratorType.WIND: 190,
            GeneratorType.SOLAR: 250,
            GeneratorType.PIEZO: 315,
            GeneratorType.COIL: 225,
        }[self.shape_gen or GeneratorType.WIND]
        self.pending_launches = [
            (
                now + index * 0.8,
                int(SCREEN_WIDTH * fraction),
                target_y,
            )
            for index, fraction in enumerate((0.1, 0.3, 0.5, 0.7, 0.9))
        ]

    def _update_pending_launches(self, now):
        remaining = []
        for launch_time, target_x, target_y in self.pending_launches:
            if now >= launch_time:
                self.firework_manager.launch(
                    target_x,
                    int(target_y * SCALE_Y),
                    forced_spec=self._build_spec(),
                    source_px=SCREEN_WIDTH // 2,
                    source_py=self.launch_origin_y,
                )
            else:
                remaining.append((launch_time, target_x, target_y))
        self.pending_launches = remaining

    def draw(self, renderer, fonts, frame_count):
        if not self.active:
            return
        elapsed = time.time() - self.phase_started
        renderer.set_blend_mode("alpha")
        # The screen returns to the normal show as soon as all three choices lock.
        if self.phase != ForgePhase.LAUNCH:
            dim_alpha = (
                min(0.82, 0.82 * elapsed / self.REVEAL_SECONDS)
                if self.phase == ForgePhase.RECORD_REVEAL
                else 0.84
            )
            renderer.draw_rect(
                0, 0, SCREEN_WIDTH, SCREEN_HEIGHT,
                (0.0, 0.0, 0.03, dim_alpha), fill=True,
            )

        if self.phase == ForgePhase.RECORD_REVEAL:
            self._draw_choices(renderer, fonts, frame_count)
        elif self.phase in (
            ForgePhase.CHOOSE_SHAPE,
            ForgePhase.CHOOSE_PALETTE,
            ForgePhase.CHOOSE_EFFECT,
            ForgePhase.LOCK_IN,
        ):
            self._draw_choices(renderer, fonts, frame_count)
        elif self.phase == ForgePhase.LAUNCH:
            self._draw_launch(renderer, fonts, elapsed)
        renderer.set_blend_mode("additive")

    def _draw_choices(self, renderer, fonts, frame_count):
        positions = [(500, 390), (1420, 390), (500, 735), (1420, 735)]
        current = self.previous_input
        now = time.time()
        # One fade only: starts with dimming during reveal, never resets per choice.
        fade_in = min(1.0, (now - self.visual_started_at) / self.REVEAL_SECONDS)
        for generator, (x, y) in zip(GENERATORS, positions):
            selected = generator == current
            pulse = 1.0 + (0.12 * math.sin(frame_count * 0.18) if selected else 0.0)
            radius = int((132 if selected else 112) * SCALE_Y * pulse)
            color_name = GEN_COLORS[generator]
            rgb = palette.get_color(COLOR_MAP[color_name])
            color = (*rgb, fade_in)
            self._draw_bold_circle(renderer, int(x * SCALE_X), int(y * SCALE_Y), radius, color, thickness=12)
            self._draw_bold_line(renderer, int(x * SCALE_X), int(y * SCALE_Y), SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, (*rgb, 0.5 * fade_in), thickness=6)

        self._draw_energy_core(renderer, frame_count, fade=1.0)
        self._draw_selection_pulses(renderer, positions, now)

    def _draw_selection_pulses(self, renderer, positions, now):
        position_map = dict(zip(GENERATORS, positions))
        alive = []
        particles = []
        for generator, started in self.selection_pulses:
            progress = (now - started) / self.PULSE_SECONDS
            if progress >= 1.0:
                continue
            alive.append((generator, started))
            x, y = position_map[generator]
            sx, sy = x * SCALE_X, y * SCALE_Y
            ex, ey = SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2
            rgb = palette.get_color(COLOR_MAP[GEN_COLORS[generator]])
            # Bright head plus fading trail travels down selected energy line.
            for trail_index in range(34):
                trail_progress = max(0.0, progress - trail_index * 0.012)
                px = sx + (ex - sx) * trail_progress
                py = sy + (ey - sy) * trail_progress
                strength = (1.0 - trail_index / 34.0) * (1.0 - progress * 0.12)
                size = 118.0 - trail_index * 2.0
                # Three overlapping sprites make pulse read as continuous energy.
                particles.extend(
                    [
                        (px, py, size, *rgb, strength),
                        (px - 4 * SCALE_X, py, size * 0.8, *rgb, strength * 0.72),
                        (px + 4 * SCALE_X, py, size * 0.8, *rgb, strength * 0.72),
                    ]
                )
            if progress >= 0.82:
                impact = min(1.0, (progress - 0.82) / 0.18)
                impact_size = 110.0 + impact * 260.0
                particles.append(
                    (ex, ey, impact_size, *rgb, (1.0 - impact) * 0.95)
                )
        self.selection_pulses = alive
        if particles:
            renderer.set_blend_mode("additive")
            renderer.draw_particles(particles)
            renderer.set_blend_mode("alpha")


    def _draw_launch(self, renderer, fonts, elapsed):
        progress = min(1.0, max(0.0, elapsed / self.LAUNCH_SECONDS))
        smooth_fade = 1.0 - (3.0 * progress**2 - 2.0 * progress**3)
        fade = 0.002 + 0.998 * smooth_fade
        travel_progress = min(1.0, elapsed / 2.2)
        center_y = int(SCREEN_HEIGHT // 2 + int(300 * SCALE_Y) * travel_progress)
        self._draw_energy_core(
            renderer, int(time.time() * 60), fade=fade, center_y=center_y
        )

    def _draw_energy_core(self, renderer, frame_count, fade=1.0, center_y=None):
        """Stack one glowing ring per locked choice around the launch origin."""
        choices = [self.shape_gen, self.palette_gen, self.effect_gen]
        locked_times = [
            self.choice_locked_at["shape"],
            self.choice_locked_at["palette"],
            self.choice_locked_at["effect"],
        ]
        now = time.time()
        locked = [
            generator
            for generator, locked_at in zip(choices, locked_times)
            if generator is not None
            and locked_at is not None
            and now - locked_at >= self.PULSE_SECONDS
        ]
        if not locked:
            return
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2 if center_y is None else center_y
        pulse = math.sin(frame_count * 0.12) * 5
        for index, generator in enumerate(locked):
            radius = int((58 + index * 30 + pulse) * SCALE_Y)
            rgb = palette.get_color(COLOR_MAP[GEN_COLORS[generator]])
            color = (*rgb, fade)
            self._draw_bold_circle(
                renderer, cx, cy, radius, color, thickness=max(5, int(14 * fade))
            )
        core_color = palette.get_color(COLOR_MAP[GEN_COLORS[locked[-1]]])
        renderer.draw_circle(
            cx, cy, int(34 * SCALE_Y), (*core_color, 0.28 * fade), fill=True
        )

    @staticmethod
    def _draw_bold_circle(renderer, cx, cy, radius, color, thickness=10):
        """Build dense animated ring from overlapping firework glow sprites."""
        rgb = color[:3]
        alpha = color[3] if len(color) > 3 else 1.0
        particle_ring = []
        now = time.time()
        point_count = max(180, min(360, int(radius * 1.8)))
        # Three close tracks fill ring body. Large overlapping glow sprites fill
        # radial space between adjacent selected rings.
        track_offsets = (-max(8, thickness), 0, max(8, thickness))
        for track_index, track_offset in enumerate(track_offsets):
            track_radius = max(1, radius + track_offset)
            phase_offset = track_index / len(track_offsets)
            for index in range(point_count):
                unit = index / point_count
                angle = (unit + phase_offset / point_count) * math.tau
                wave = 0.5 + 0.5 * math.sin(angle * 4.0 - now * 4.5)
                breathe = 0.88 + 0.14 * math.sin(now * 3.2 + angle * 2.0)
                particle_size = max(48.0, thickness * 4.4) * breathe
                px = cx + math.cos(angle) * track_radius
                py = cy + math.sin(angle) * track_radius
                particle_ring.append(
                    (
                        px, py, particle_size,
                        rgb[0], rgb[1], rgb[2],
                        alpha * (0.48 + wave * 0.42),
                    )
                )
        renderer.set_blend_mode("additive")
        renderer.draw_particles(particle_ring)
        renderer.set_blend_mode("alpha")
        half = max(1, int(thickness / 2))
        glow = max(16, thickness * 3)
        for offset in range(-glow, glow + 1, 3):
            renderer.draw_circle(
                cx, cy, max(1, radius + offset), (*rgb, alpha * 0.16), fill=False
            )
        for offset in range(-half - 4, half + 5, 2):
            renderer.draw_circle(
                cx, cy, max(1, radius + offset), (*rgb, alpha * 0.38), fill=False
            )
        for offset in range(-half, half + 1, 2):
            renderer.draw_circle(
                cx, cy, max(1, radius + offset), (*rgb, alpha), fill=False
            )

    @staticmethod
    def _draw_bold_line(renderer, x1, y1, x2, y2, color, thickness=6):
        """Draw solid line plus animated firework-sprite energy flowing through it."""
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length <= 0:
            return
        nx, ny = -dy / length, dx / length
        half = max(1, int(thickness / 2))
        rgb = color[:3]
        alpha = color[3] if len(color) > 3 else 1.0
        now = time.time()
        particle_line = []
        point_count = max(2, int(length / 3.5))
        for index in range(point_count + 1):
            unit = index / point_count
            wave = 0.5 + 0.5 * math.sin(unit * math.tau * 3.0 - now * 5.5)
            px = x1 + dx * unit
            py = y1 + dy * unit
            particle_line.append(
                (
                    px, py, max(42.0, thickness * 5.0) * (0.9 + wave * 0.2),
                    rgb[0], rgb[1], rgb[2], alpha * (0.42 + wave * 0.48),
                )
            )
        renderer.set_blend_mode("additive")
        renderer.draw_particles(particle_line)
        renderer.set_blend_mode("alpha")
        glow_half = half + 18
        for offset in range(-glow_half, glow_half + 1, 2):
            ox, oy = nx * offset, ny * offset
            renderer.draw_line(
                x1 + ox, y1 + oy, x2 + ox, y2 + oy, (*rgb, alpha * 0.15)
            )
        for offset in range(-half, half + 1):
            ox, oy = nx * offset, ny * offset
            renderer.draw_line(
                x1 + ox, y1 + oy, x2 + ox, y2 + oy, (*rgb, alpha)
            )
