"""A varied firework show for the hidden Hall sequence."""

import json
import os
import random

from .config import COLORS
from .models import generate_spec
from .strategies import SingleLaunch
from ...config import GeneratorType


class BirthdayFireworkShow:
    LAUNCH_INTERVAL = (0.55, 0.95)
    # The smaller caps protect the particle pool from splitting and long trails.
    COUNT_RANGES = {
        "Brocade": (360, 520),
        "Chrysanthemum": (500, 640),
        "Comet": (125, 180),
        "Crossette": (65, 100),
        "Dragon Eggs": (300, 420),
        "Palm Tree": (55, 90),
        "Peony": (410, 560),
        "Pistil": (280, 390),
        "Strobe": (260, 370),
        "Tourbillion": (170, 260),
        "Waterfall": (450, 580),
        "Willow": (220, 310),
    }
    PALETTES = (
        ("gold", "sakura", "silver"),
        ("cyan", "blue", "silver"),
        ("orange", "red", "gold"),
        ("lime", "yellow", "cyan"),
        ("magenta", "pink", "sakura"),
    )

    def __init__(self, firework_manager, rng=None):
        self.firework_manager = firework_manager
        self.rng = rng or random.Random()
        root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
        )
        settings_path = os.path.join(
            root, "resource", "firework-settings", "custom.json"
        )
        with open(settings_path, "r", encoding="utf-8") as file:
            self.settings = json.load(file)
        self.active = False
        self._next_launch_at = 0.0
        self._type_bag = []
        self._wave_count = 0

    def start(self, now):
        if self.active:
            return
        self.active = True
        self._wave_count = 0
        self._launch_wave()
        self._next_launch_at = now + self.rng.uniform(*self.LAUNCH_INTERVAL)

    def update(self, now):
        if not self.active or now < self._next_launch_at:
            return
        self._launch_wave()
        self._next_launch_at = now + self.rng.uniform(*self.LAUNCH_INTERVAL)

    def stop(self):
        # Existing shells and particles retain their normal lifetimes.
        self.active = False

    def _next_type(self):
        if not self._type_bag:
            self._type_bag = list(self.COUNT_RANGES)
            self.rng.shuffle(self._type_bag)
        return self._type_bag.pop()

    def _make_spec(self, firework_type):
        spec = generate_spec(firework_type)
        settings = self.settings
        low, high = self.COUNT_RANGES[firework_type]
        count_scale = max(0.5, min(1.5, settings["particle_count"] / 300))
        spec.particle_count = min(
            high, max(low, int(self.rng.randint(low, high) * count_scale))
        )
        spec.radius = min(
            3.2, max(spec.radius, settings["radius"]) * self.rng.uniform(1.1, 1.65)
        )
        spec.life_span = min(
            240,
            int(max(spec.life_span, settings["life_span"]) * self.rng.uniform(0.9, 1.2)),
        )
        spec.speed_variance = min(
            28.0,
            max(spec.speed_variance, settings["speed_variance"])
            * self.rng.uniform(1.05, 1.4),
        )
        spec.gravity_mod = max(
            0.02,
            min(1.5, spec.gravity_mod * self.rng.uniform(0.75, 1.25)),
        )
        spec.drag = min(0.18, spec.drag * self.rng.uniform(0.75, 1.2))
        spec.intensity = min(
            3.0,
            max(spec.intensity, settings["intensity"])
            * self.rng.uniform(1.1, 1.5),
        )
        palette = self.rng.choice(self.PALETTES)
        spec.colors = self.rng.sample(palette, self.rng.randint(2, len(palette)))
        spec.base_color = spec.colors[0]
        spec.multicolor = len(spec.colors)
        spec.variant = self.rng.randrange(2)
        spec.has_trails = bool(settings.get("has_trails", True))
        spec.glitter = self.rng.random() < 0.6
        spec.flicker = spec.flicker or self.rng.random() < 0.18
        spec.crackle = spec.crackle or self.rng.random() < 0.18
        if firework_type in ("Brocade", "Peony", "Pistil"):
            spec.pistil = spec.pistil or self.rng.random() < 0.3
            if spec.pistil:
                spec.pistil_color = "silver"
        return spec

    def _launch_wave(self):
        # A mirrored pair starts each fifth wave; the rest vary across the sky.
        pair = self._wave_count % 5 == 0
        x = self.rng.randint(470, 780)
        positions = (x, 1920 - x) if pair else (self.rng.randint(430, 1490),)
        for target_x in positions:
            spec = self._make_spec(self._next_type())
            self.firework_manager.launch(
                target_x,
                self.rng.randint(365, 510),
                forced_spec=spec,
            )
        self._wave_count += 1


class SuperFireworkShow(BirthdayFireworkShow):
    """All visual and motion flags enabled, with counts capped for splitting."""

    LAUNCH_INTERVAL = (1.15, 1.6)
    COUNT_RANGES = {
        "Brocade": (90, 120),
        "Chrysanthemum": (95, 130),
        "Dragon Eggs": (95, 125),
        "Peony": (95, 130),
        "Pistil": (90, 120),
        "Strobe": (100, 130),
        "Tourbillion": (85, 115),
    }

    def _make_spec(self, firework_type):
        spec = super()._make_spec(firework_type)
        spec.burst = True
        spec.pistil = True
        spec.split = True
        spec.has_trails = True
        spec.flicker = True
        spec.crackle = True
        spec.swim = True
        spec.spin = True
        spec.waterfall = True
        spec.palm_tail = True
        spec.glitter = True
        spec.colors = [*COLORS, "silver"]
        spec.base_color = self.rng.choice(spec.colors)
        spec.multicolor = len(spec.colors)
        spec.variant = 1
        spec.pistil_color = "silver"
        spec.launch_strategy = SingleLaunch()
        spec.intensity = min(3.0, max(2.2, spec.intensity))
        spec.life_span = min(150, spec.life_span)
        return spec


class PairFireworkShow(BirthdayFireworkShow):
    """Six distinct palettes, type sets, and formations for Hall pairs."""

    S = GeneratorType.SOLAR
    W = GeneratorType.WIND
    C = GeneratorType.COIL
    H = GeneratorType.HAND_CRANK
    STYLES = {
        frozenset((S, W)): {
            "types": ("Peony", "Chrysanthemum"),
            "palette": ("gold", "yellow", "cyan", "silver"),
            "waves": (((540, 390), (1380, 390)), ((720, 430), (1200, 430))),
            "interval": (1.1, 1.45),
        },
        frozenset((S, C)): {
            "types": ("Tourbillion", "Crossette"),
            "palette": ("gold", "violet", "magenta", "silver"),
            "waves": (((760, 380),), ((960, 445),), ((1160, 380),)),
            "interval": (0.75, 1.05),
        },
        frozenset((S, H)): {
            "types": ("Palm Tree", "Brocade"),
            "palette": ("orange", "gold", "sakura", "yellow"),
            "waves": (((540, 450),), ((960, 365),), ((1380, 450),)),
            "interval": (0.8, 1.1),
        },
        frozenset((W, C)): {
            "types": ("Waterfall", "Willow"),
            "palette": ("cyan", "blue", "indigo", "silver"),
            "waves": (((520, 365), (960, 365), (1400, 365)),),
            "interval": (2.0, 2.4),
        },
        frozenset((W, H)): {
            "types": ("Crossette", "Strobe"),
            "palette": ("lime", "cyan", "green", "silver"),
            "waves": (((490, 400), (1430, 470)), ((1430, 400), (490, 470))),
            "interval": (1.15, 1.5),
        },
        frozenset((C, H)): {
            "types": ("Dragon Eggs", "Pistil"),
            "palette": ("magenta", "pink", "red", "gold"),
            "waves": (((960, 365),), ((780, 435), (1140, 435))),
            "interval": (1.2, 1.55),
        },
    }

    def __init__(self, firework_manager, pair, rng=None):
        super().__init__(firework_manager, rng)
        self.style = self.STYLES[frozenset(pair)]
        self.COUNT_RANGES = {
            name: BirthdayFireworkShow.COUNT_RANGES[name]
            for name in self.style["types"]
        }
        self.PALETTES = (self.style["palette"],)
        self.LAUNCH_INTERVAL = self.style["interval"]

    def _launch_wave(self):
        wave = self.style["waves"][self._wave_count % len(self.style["waves"])]
        for x, y in wave:
            self.firework_manager.launch(
                x + self.rng.randint(-24, 24),
                y + self.rng.randint(-18, 18),
                forced_spec=self._make_spec(self._next_type()),
            )
        self._wave_count += 1


class CellCelebration(BirthdayFireworkShow):
    """Short generator-specific show when a battery cell first reaches 100%."""

    STYLES = {
        GeneratorType.SOLAR: {
            "types": ("Comet", "Peony", "Strobe"),
            "palette": ("yellow", "gold", "orange", "silver"),
            "waves": (
                ((670, 425), (1250, 425)),
                ((850, 365), (1070, 365)),
                ((960, 405),),
            ),
            "interval": (0.72, 0.92),
            "duration": 3.25,
            "scale": 0.52,
        },
        GeneratorType.WIND: {
            "types": ("Crossette", "Willow", "Chrysanthemum"),
            "palette": ("cyan", "blue", "indigo", "silver"),
            "waves": (
                ((550, 385),),
                ((800, 430),),
                ((1110, 370),),
                ((1390, 425),),
            ),
            "interval": (0.55, 0.75),
            "duration": 3.15,
            "scale": 0.58,
        },
        GeneratorType.COIL: {
            "types": ("Tourbillion", "Dragon Eggs", "Crossette"),
            "palette": ("lime", "green", "magenta", "silver"),
            "waves": (
                ((960, 355),),
                ((740, 425), (1180, 425)),
                ((960, 390),),
            ),
            "interval": (0.7, 0.9),
            "duration": 3.3,
            "scale": 0.5,
        },
        GeneratorType.HAND_CRANK: {
            "types": ("Palm Tree", "Brocade", "Pistil"),
            "palette": ("orange", "gold", "red", "sakura"),
            "waves": (
                ((540, 425),),
                ((960, 365),),
                ((1380, 425),),
                ((720, 395), (1200, 395)),
            ),
            "interval": (0.65, 0.85),
            "duration": 3.25,
            "scale": 0.54,
        },
    }

    def __init__(self, firework_manager, generator, rng=None):
        super().__init__(firework_manager, rng)
        self.style = self.STYLES[generator]
        self.COUNT_RANGES = {
            name: BirthdayFireworkShow.COUNT_RANGES[name]
            for name in self.style["types"]
        }
        self.PALETTES = (self.style["palette"],)
        self.LAUNCH_INTERVAL = self.style["interval"]

    def start(self, now):
        self._type_bag.clear()
        self._end_at = now + self.style["duration"]
        super().start(now)

    def update(self, now):
        if self.active and now >= self._end_at:
            self.stop()
        else:
            super().update(now)

    def _make_spec(self, firework_type):
        spec = super()._make_spec(firework_type)
        spec.particle_count = max(1, int(spec.particle_count * self.style["scale"]))
        return spec

    def _launch_wave(self):
        wave = self.style["waves"][self._wave_count % len(self.style["waves"])]
        for x, y in wave:
            self.firework_manager.launch(
                x + self.rng.randint(-24, 24),
                y + self.rng.randint(-20, 20),
                forced_spec=self._make_spec(self._next_type()),
            )
        self._wave_count += 1


class LaunchCelebration(BirthdayFireworkShow):
    """Finite, varied celebration scaled to the completed battery loadout."""

    TIERS = {
        2: {
            "types": ("Comet", "Brocade", "Peony", "Palm Tree"),
            "palette": ("gold", "cyan", "orange", "silver"),
            "waves": (
                ((470, 450), (1450, 450)),
                ((730, 365), (1190, 365)),
                ((960, 410),),
            ),
            "interval": (0.65, 0.9),
            "duration": 3.8,
            "scale": 0.78,
        },
        3: {
            "types": ("Comet", "Crossette", "Dragon Eggs", "Strobe", "Pistil"),
            "palette": ("lime", "magenta", "cyan", "gold", "silver"),
            "waves": (
                ((430, 430), (1490, 430)),
                ((650, 370), (1270, 370)),
                ((960, 345),),
            ),
            "interval": (0.55, 0.8),
            "duration": 4.6,
            "scale": 0.9,
        },
        4: {
            "types": ("Comet", "Chrysanthemum", "Waterfall", "Willow", "Peony"),
            "palette": ("gold", "pink", "cyan", "lime", "blue", "silver"),
            "waves": (
                ((390, 430), (1530, 430)),
                ((660, 360), (1260, 360)),
                ((960, 340),),
                ((510, 385), (960, 345), (1410, 385)),
            ),
            "interval": (0.65, 0.9),
            "duration": 5.4,
            "scale": 1.0,
        },
    }

    def start(self, now, cell_count):
        self.stop()
        self.style = self.TIERS[min(4, max(2, cell_count))]
        self.COUNT_RANGES = {
            name: BirthdayFireworkShow.COUNT_RANGES[name]
            for name in self.style["types"]
        }
        self.PALETTES = (self.style["palette"],)
        self.LAUNCH_INTERVAL = self.style["interval"]
        self._type_bag.clear()
        self._end_at = now + self.style["duration"]
        super().start(now)

    def update(self, now):
        if self.active and now >= self._end_at:
            self.stop()
        else:
            super().update(now)

    def _make_spec(self, firework_type):
        spec = super()._make_spec(firework_type)
        spec.particle_count = max(
            1, int(spec.particle_count * self.style["scale"])
        )
        spec.intensity = min(3.0, spec.intensity * (0.9 + self.style["scale"] * 0.2))
        return spec

    def _launch_wave(self):
        wave = self.style["waves"][self._wave_count % len(self.style["waves"])]
        for x, y in wave:
            self.firework_manager.launch(
                x + self.rng.randint(-40, 40),
                y + self.rng.randint(-22, 22),
                forced_spec=self._make_spec(self._next_type()),
            )
        self._wave_count += 1
