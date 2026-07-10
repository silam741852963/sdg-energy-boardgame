from dataclasses import dataclass, field
import random
from typing import List

from .strategies import (
    LaunchStrategy,
    SingleLaunch,
    SpreadLaunch,
    MulticolorSpreadLaunch,
    BurstStrategy,
    SphericalBurst,
    PalmBurst,
    ConeBurst,
)
from .behaviors import (
    UpdateBehavior,
    DrawBehavior,
    SwimBehavior,
    SpinBehavior,
    WaterfallBehavior,
    CrackleBehavior,
    FlickerBehavior,
    TrailBehavior,
)


@dataclass
class FireworkSpec:
    name: str
    particle_count: int
    base_color: str
    variant: int
    speed_variance: float
    radius: float
    gravity_mod: float
    drag: float
    life_span: int
    burst: bool = True
    pistil: bool = False
    split: bool = False
    multicolor: int = 1
    intensity: float = 1.0
    colors: List[str] = field(default_factory=list)
    pistil_color: str = ""

    launch_strategy: LaunchStrategy = field(default_factory=SingleLaunch)
    burst_strategy: BurstStrategy = field(default_factory=SphericalBurst)
    update_behaviors: List[UpdateBehavior] = field(default_factory=list)
    draw_behaviors: List[DrawBehavior] = field(default_factory=list)

    @property
    def has_trails(self):
        return any(isinstance(b, TrailBehavior) for b in self.draw_behaviors)

    @has_trails.setter
    def has_trails(self, value):
        has = self.has_trails
        if value and not has:
            self.draw_behaviors.append(TrailBehavior())
        elif not value and has:
            self.draw_behaviors = [
                b for b in self.draw_behaviors if not isinstance(b, TrailBehavior)
            ]

    @property
    def flicker(self):
        return any(isinstance(b, FlickerBehavior) for b in self.draw_behaviors)

    @flicker.setter
    def flicker(self, value):
        has = self.flicker
        if value and not has:
            self.draw_behaviors.append(FlickerBehavior())
        elif not value and has:
            self.draw_behaviors = [
                b for b in self.draw_behaviors if not isinstance(b, FlickerBehavior)
            ]

    @property
    def crackle(self):
        return any(isinstance(b, CrackleBehavior) for b in self.draw_behaviors)

    @crackle.setter
    def crackle(self, value):
        has = self.crackle
        if value and not has:
            self.draw_behaviors.append(CrackleBehavior())
        elif not value and has:
            self.draw_behaviors = [
                b for b in self.draw_behaviors if not isinstance(b, CrackleBehavior)
            ]

    @property
    def swim(self):
        return any(isinstance(b, SwimBehavior) for b in self.update_behaviors)

    @swim.setter
    def swim(self, value):
        has = self.swim
        if value and not has:
            self.update_behaviors.append(SwimBehavior())
        elif not value and has:
            self.update_behaviors = [
                b for b in self.update_behaviors if not isinstance(b, SwimBehavior)
            ]

    @property
    def spin(self):
        return any(isinstance(b, SpinBehavior) for b in self.update_behaviors)

    @spin.setter
    def spin(self, value):
        has = self.spin
        if value and not has:
            self.update_behaviors.append(SpinBehavior())
        elif not value and has:
            self.update_behaviors = [
                b for b in self.update_behaviors if not isinstance(b, SpinBehavior)
            ]

    @property
    def waterfall(self):
        return any(isinstance(b, WaterfallBehavior) for b in self.update_behaviors)

    @waterfall.setter
    def waterfall(self, value):
        has = self.waterfall
        if value and not has:
            self.update_behaviors.append(WaterfallBehavior())
        elif not value and has:
            self.update_behaviors = [
                b for b in self.update_behaviors if not isinstance(b, WaterfallBehavior)
            ]

    @property
    def palm_tail(self):
        for b in self.draw_behaviors:
            if isinstance(b, TrailBehavior):
                return b.palm_tail
        return False

    @palm_tail.setter
    def palm_tail(self, value):
        for b in self.draw_behaviors:
            if isinstance(b, TrailBehavior):
                b.palm_tail = value

    @property
    def glitter(self):
        for b in self.draw_behaviors:
            if isinstance(b, TrailBehavior):
                return b.glitter
        return False

    @glitter.setter
    def glitter(self, value):
        for b in self.draw_behaviors:
            if isinstance(b, TrailBehavior):
                b.glitter = value


from .config import FIREWORK_TYPES, COLORS


def generate_spec(fw_type: str) -> FireworkSpec:
    color = random.choice(COLORS)
    variant = random.choice([0, 1])

    # Sometimes have 2 or more colors (35% chance of 2 or 3 colors)
    multicolor = 1
    if random.random() < 0.35:
        multicolor = random.choice([2, 3])

    # Improved base default spec: more particles, slightly larger radius for better glow
    spec = FireworkSpec(
        name=fw_type,
        particle_count=random.randint(100, 150),
        base_color=color,
        variant=variant,
        speed_variance=7.5,
        radius=1.2,
        gravity_mod=0.5,
        drag=0.05,
        life_span=80,
        multicolor=multicolor,
    )

    if fw_type == "Brocade":
        # Brocade: massive, dense, long-lived shimmering trails
        spec.particle_count = 300
        spec.gravity_mod = 0.4
        spec.drag = 0.06
        spec.life_span = 140
        spec.speed_variance = 10.0
        spec.radius = 1.5
        spec.draw_behaviors.append(
            TrailBehavior(palm_tail=True, glitter=True, trail_len=8)
        )
    elif fw_type == "Chrysanthemum":
        # Chrysanthemum: extremely high density, big spread, and new long trails!
        spec.particle_count = 500
        spec.speed_variance = 22.0
        spec.drag = 0.15
        spec.gravity_mod = 0.05
        spec.life_span = 100
        spec.radius = 1.2
        spec.draw_behaviors.append(TrailBehavior(trail_len=8))
    elif fw_type == "Comet":
        # Comet: single bright arcing tail, thicker and brighter
        spec.burst = False
        spec.particle_count = 150
        spec.life_span = 150
        spec.gravity_mod = 0.1
        spec.drag = 0.01
        spec.variant = 1
        spec.radius = 1.5
        spec.intensity = 2.0
        spec.launch_strategy = SpreadLaunch()
        spec.draw_behaviors.append(TrailBehavior(palm_tail=True, trail_len=8))
    elif fw_type == "Crossette":
        # Crossette: splits into double the shooting stars
        spec.particle_count = 40
        spec.split = True
        spec.speed_variance = 8.0
        spec.drag = 0.04
        spec.gravity_mod = 0.2
        spec.life_span = 50
        spec.radius = 1.5
        spec.draw_behaviors.append(TrailBehavior(trail_len=6))
    elif fw_type == "Pearls":
        # Pearls: fountain of 180 multi-color pearls with beautiful trails!
        spec.burst = False
        spec.particle_count = 180
        spec.life_span = 180
        spec.radius = 1.5
        spec.intensity = 1.5
        spec.multicolor = len(COLORS)
        spec.launch_strategy = MulticolorSpreadLaunch()
        spec.draw_behaviors.append(TrailBehavior(trail_len=10))
    elif fw_type == "Dragon Eggs":
        # Dragon Eggs: massive wall of popping white crackles
        spec.particle_count = 250
        spec.speed_variance = 11.0
        spec.drag = 0.06
        spec.life_span = 130
        spec.radius = 2.0
        spec.intensity = 2.5
        spec.draw_behaviors.append(CrackleBehavior())
        spec.draw_behaviors.append(TrailBehavior(glitter=True, trail_len=5))
    elif fw_type == "Waterfall":
        # Waterfall: dense cascading curtain of glowing fire falling down (enlarged and enhanced)
        spec.particle_count = 450
        spec.gravity_mod = 1.2
        spec.drag = 0.08
        spec.speed_variance = 16.0
        spec.life_span = 200
        spec.radius = 2.2
        spec.update_behaviors.append(WaterfallBehavior())
        spec.draw_behaviors.append(TrailBehavior(trail_len=12))
    elif fw_type == "Flying Fish":
        # Flying Fish: more fish swarming energetically
        spec.particle_count = 120
        spec.speed_variance = 8.0
        spec.drag = 0.04
        spec.gravity_mod = 0.05
        spec.radius = 1.5
        spec.life_span = 45
        spec.update_behaviors.append(SwimBehavior())
        spec.draw_behaviors.append(TrailBehavior(trail_len=6))
    elif fw_type == "Palm Tree":
        # Palm Tree: thicker trunk and branches, super bright
        spec.particle_count = 28
        spec.speed_variance = 7.5
        spec.drag = 0.05
        spec.life_span = 70
        spec.gravity_mod = 1.0
        spec.radius = 2.0
        spec.intensity = 2.5
        spec.burst_strategy = PalmBurst()
        spec.draw_behaviors.append(TrailBehavior(palm_tail=True, trail_len=8))
    elif fw_type == "Peony":
        # Peony: spherical color shell, denser with beautiful trails
        spec.particle_count = 350
        spec.speed_variance = 18.0
        spec.drag = 0.12
        spec.gravity_mod = 0.05
        spec.radius = 1.0
        spec.life_span = 100
        spec.burst_strategy = SphericalBurst(speed_min=1.2, add_shell_velocity=False)
        spec.draw_behaviors.append(TrailBehavior(trail_len=6))
    elif fw_type == "Pistil":
        # Pistil: nested outer ring and core shell with trails
        spec.particle_count = 250
        spec.pistil = True
        spec.speed_variance = 9.0
        spec.drag = 0.06
        spec.life_span = 100
        spec.radius = 1.2
        spec.multicolor = 1
        spec.draw_behaviors.append(TrailBehavior(trail_len=5))
    elif fw_type == "Rising Tail":
        # Rising Tail: bright upward cone of fire
        spec.particle_count = 80
        spec.speed_variance = 6.0
        spec.drag = 0.04
        spec.gravity_mod = 0.8
        spec.radius = 1.5
        spec.intensity = 2.5
        spec.life_span = 120
        spec.burst_strategy = ConeBurst()
        spec.draw_behaviors.append(TrailBehavior(palm_tail=True, trail_len=15))
    elif fw_type == "Strobe":
        # Strobe: blinking stars that leave small trails
        spec.particle_count = 200
        spec.speed_variance = 8.0
        spec.drag = 0.04
        spec.gravity_mod = 0.1
        spec.life_span = 140
        spec.radius = 1.5
        spec.draw_behaviors.append(TrailBehavior(trail_len=4))
        spec.draw_behaviors.append(FlickerBehavior())
    elif fw_type == "Tourbillion":
        # Tourbillion: wild spinning spirals of light
        spec.particle_count = 120
        spec.speed_variance = 8.0
        spec.drag = 0.04
        spec.radius = 1.5
        spec.life_span = 100
        spec.update_behaviors.append(SpinBehavior())
        spec.draw_behaviors.append(TrailBehavior(trail_len=8))
    elif fw_type == "Heart":
        # Heart: Custom heart-shaped explosion
        from .strategies import HeartBurst
        spec.particle_count = 200
        spec.speed_variance = 11.0
        spec.drag = 0.08
        spec.gravity_mod = 0.08
        spec.life_span = 120
        spec.radius = 1.6
        spec.intensity = 2.0
        spec.burst_strategy = HeartBurst(add_shell_velocity=False)
        spec.draw_behaviors.append(TrailBehavior(trail_len=6))
    elif fw_type == "Heart_Brocade":
        # Heart Brocade: heart-shaped explosion with long shimmering trails
        from .strategies import HeartBurst
        spec.particle_count = 250
        spec.speed_variance = 10.0
        spec.drag = 0.06
        spec.gravity_mod = 0.4
        spec.life_span = 140
        spec.radius = 1.8
        spec.intensity = 2.5
        spec.burst_strategy = HeartBurst(add_shell_velocity=False)
        spec.draw_behaviors.append(TrailBehavior(palm_tail=True, glitter=True, trail_len=8))
    elif fw_type == "Heart_Strobe":
        # Heart Strobe: heart-shaped explosion with flickering strobe particles
        from .strategies import HeartBurst
        spec.particle_count = 200
        spec.speed_variance = 12.0
        spec.drag = 0.08
        spec.gravity_mod = 0.08
        spec.life_span = 140
        spec.radius = 1.5
        spec.intensity = 2.0
        spec.burst_strategy = HeartBurst(add_shell_velocity=False)
        spec.draw_behaviors.append(TrailBehavior(trail_len=4))
        spec.draw_behaviors.append(FlickerBehavior())
    elif fw_type == "Heart_Crackle":
        # Heart Crackle: heart-shaped explosion with crackling dragon eggs behavior
        from .strategies import HeartBurst
        spec.particle_count = 200
        spec.speed_variance = 11.0
        spec.drag = 0.08
        spec.gravity_mod = 0.08
        spec.life_span = 130
        spec.radius = 1.8
        spec.intensity = 2.2
        spec.burst_strategy = HeartBurst(add_shell_velocity=False)
        spec.draw_behaviors.append(CrackleBehavior())
        spec.draw_behaviors.append(TrailBehavior(glitter=True, trail_len=5))
    elif fw_type == "Orange_Fruit":
        # Orange Fruit: spherical burst with dense bright orange outer shell and green core (leaf/stem)
        spec.particle_count = 200
        spec.speed_variance = 9.0
        spec.drag = 0.05
        spec.gravity_mod = 0.1
        spec.life_span = 120
        spec.radius = 1.6
        spec.intensity = 2.0
        spec.base_color = "orange"
        spec.colors = ["orange"]
        spec.pistil = True
        spec.pistil_color = "green"
        spec.draw_behaviors.append(TrailBehavior(trail_len=5))
    elif fw_type == "Willow":
        # Willow: dense falling willow branches with long golden tails
        spec.particle_count = 180
        spec.speed_variance = 8.0
        spec.gravity_mod = 0.2
        spec.drag = 0.02
        spec.life_span = 250
        spec.radius = 1.5
        spec.draw_behaviors.append(TrailBehavior(trail_len=20))

    return spec


def get_random_preset():
    return generate_spec(random.choice(FIREWORK_TYPES))


def serialize_spec(spec: FireworkSpec) -> dict:
    return {
        "name": spec.name,
        "particle_count": spec.particle_count,
        "base_color": spec.base_color,
        "variant": spec.variant,
        "speed_variance": spec.speed_variance,
        "radius": spec.radius,
        "gravity_mod": spec.gravity_mod,
        "drag": spec.drag,
        "life_span": spec.life_span,
        "burst": spec.burst,
        "pistil": spec.pistil,
        "split": spec.split,
        "multicolor": spec.multicolor,
        "intensity": spec.intensity,
        "has_trails": spec.has_trails,
        "flicker": spec.flicker,
        "crackle": spec.crackle,
        "swim": spec.swim,
        "spin": spec.spin,
        "waterfall": spec.waterfall,
        "palm_tail": spec.palm_tail,
        "glitter": spec.glitter,
        "colors": spec.colors,
        "pistil_color": spec.pistil_color
    }


def deserialize_spec(d: dict) -> FireworkSpec:
    spec = FireworkSpec(
        name=d.get("name", "Peony"),
        particle_count=d.get("particle_count", 150),
        base_color=d.get("base_color", "silver"),
        variant=d.get("variant", 0),
        speed_variance=d.get("speed_variance", 7.5),
        radius=d.get("radius", 1.2),
        gravity_mod=d.get("gravity_mod", 0.5),
        drag=d.get("drag", 0.05),
        life_span=d.get("life_span", 80),
        burst=d.get("burst", True),
        pistil=d.get("pistil", False),
        split=d.get("split", False),
        multicolor=d.get("multicolor", 1),
        intensity=d.get("intensity", 1.0),
        colors=d.get("colors", []),
        pistil_color=d.get("pistil_color", "")
    )
    spec.has_trails = d.get("has_trails", False)
    spec.flicker = d.get("flicker", False)
    spec.crackle = d.get("crackle", False)
    spec.swim = d.get("swim", False)
    spec.spin = d.get("spin", False)
    spec.waterfall = d.get("waterfall", False)
    spec.palm_tail = d.get("palm_tail", False)
    spec.glitter = d.get("glitter", False)
    
    # Restore burst strategy
    if spec.name == "Rising Tail":
        from .strategies import ConeBurst
        spec.burst_strategy = ConeBurst()
    elif spec.name == "Palm Tree":
        from .strategies import PalmBurst
        spec.burst_strategy = PalmBurst()
    elif spec.name in ("Heart", "Heart_Brocade", "Heart_Strobe", "Heart_Crackle"):
        from .strategies import HeartBurst
        spec.burst_strategy = HeartBurst(add_shell_velocity=False)
    else:
        from .strategies import SphericalBurst
        spec.burst_strategy = SphericalBurst(speed_min=1.2, add_shell_velocity=False) if spec.name == "Peony" else SphericalBurst()
        
    return spec


def save_spec_to_file(spec: FireworkSpec, filepath: str):
    import os
    import json
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(serialize_spec(spec), f, indent=4)


def load_spec_from_file(filepath: str) -> FireworkSpec:
    import json
    with open(filepath, "r") as f:
        return deserialize_spec(json.load(f))

