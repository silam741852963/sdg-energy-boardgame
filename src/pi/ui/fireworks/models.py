from dataclasses import dataclass, field
import random
from typing import List, Any

from .strategies import LaunchStrategy, SingleLaunch, SpreadLaunch, MulticolorSpreadLaunch, BurstStrategy, SphericalBurst, PalmBurst, ConeBurst
from .behaviors import UpdateBehavior, DrawBehavior, SwimBehavior, SpinBehavior, WaterfallBehavior, CrackleBehavior, FlickerBehavior, TrailBehavior


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

    launch_strategy: LaunchStrategy = field(default_factory=SingleLaunch)
    burst_strategy: BurstStrategy = field(default_factory=SphericalBurst)
    update_behaviors: List[UpdateBehavior] = field(default_factory=list)
    draw_behaviors: List[DrawBehavior] = field(default_factory=list)


from .config import FIREWORK_TYPES, COLORS


def generate_spec(fw_type: str) -> FireworkSpec:
    color = random.choice(COLORS)
    variant = random.choice([0, 1])

    spec = FireworkSpec(
        name=fw_type,
        particle_count=random.randint(60, 90),
        base_color=color,
        variant=variant,
        speed_variance=7.5,
        radius=1.0,
        gravity_mod=0.5,
        drag=0.05,
        life_span=80,
    )

    if fw_type == "Brocade":
        spec.particle_count = 150
        spec.gravity_mod = 0.4
        spec.drag = 0.06
        spec.life_span = 140
        spec.speed_variance = 9.0
        spec.draw_behaviors.append(TrailBehavior(palm_tail=True, glitter=True))
    elif fw_type == "Chrysanthemum":
        spec.particle_count = 350
        spec.speed_variance = 22.0
        spec.drag = 0.15
        spec.gravity_mod = 0.05
        spec.life_span = 80
        spec.draw_behaviors.append(TrailBehavior())
    elif fw_type == "Comet":
        spec.burst = False
        spec.life_span = 100
        spec.gravity_mod = 0.1
        spec.drag = 0.01
        spec.variant = 1
        spec.radius = 2.0
        spec.launch_strategy = SpreadLaunch()
        spec.draw_behaviors.append(TrailBehavior(palm_tail=True))
    elif fw_type == "Crossette":
        spec.particle_count = 18
        spec.split = True
        spec.speed_variance = 6.0
        spec.drag = 0.04
        spec.gravity_mod = 0.2
        spec.life_span = 40
        spec.draw_behaviors.append(TrailBehavior())
    elif fw_type == "Pearls":
        spec.burst = False
        spec.life_span = 120
        spec.radius = 3.0
        spec.intensity = 2.0
        spec.multicolor = len(COLORS)
        spec.launch_strategy = MulticolorSpreadLaunch()
    elif fw_type == "Dragon Eggs":
        spec.particle_count = 120
        spec.speed_variance = 9.0
        spec.drag = 0.06
        spec.life_span = 130
        spec.draw_behaviors.append(CrackleBehavior())
    elif fw_type == "Waterfall":
        spec.particle_count = 150
        spec.gravity_mod = 1.2
        spec.drag = 0.08
        spec.speed_variance = 12.0
        spec.life_span = 180
        spec.update_behaviors.append(WaterfallBehavior())
        spec.draw_behaviors.append(TrailBehavior(trail_len=12))
    elif fw_type == "Flying Fish":
        spec.particle_count = 60
        spec.speed_variance = 6.0
        spec.drag = 0.04
        spec.gravity_mod = 0.05
        spec.radius = 1.5
        spec.life_span = 30
        spec.update_behaviors.append(SwimBehavior())
        spec.draw_behaviors.append(TrailBehavior())
    elif fw_type == "Palm Tree":
        spec.particle_count = 12
        spec.speed_variance = 7.5
        spec.drag = 0.05
        spec.life_span = 70
        spec.gravity_mod = 1
        spec.radius = 3
        spec.burst_strategy = PalmBurst()
        spec.draw_behaviors.append(TrailBehavior(palm_tail=True))
    elif fw_type == "Peony":
        spec.particle_count = 200
        spec.speed_variance = 18.0
        spec.drag = 0.12
        spec.gravity_mod = 0.05
        spec.radius = 0.5
        spec.life_span = 100
        spec.burst_strategy = SphericalBurst(speed_min=1.2, add_shell_velocity=False)
    elif fw_type == "Pistil":
        spec.particle_count = 150
        spec.pistil = True
        spec.speed_variance = 9.0
        spec.drag = 0.06
        spec.life_span = 100
        spec.multicolor = 1
    elif fw_type == "Rising Tail":
        spec.particle_count = 40
        spec.speed_variance = 6.0
        spec.drag = 0.04
        spec.gravity_mod = 0.8
        spec.radius = 2.0
        spec.life_span = 120
        spec.burst_strategy = ConeBurst()
        spec.draw_behaviors.append(TrailBehavior(palm_tail=True, trail_len=20))
    elif fw_type == "Strobe":
        spec.particle_count = 100
        spec.speed_variance = 6.0
        spec.drag = 0.04
        spec.gravity_mod = 0.1
        spec.life_span = 140
        spec.draw_behaviors.append(FlickerBehavior())
    elif fw_type == "Tourbillion":
        spec.particle_count = 50
        spec.speed_variance = 6.0
        spec.drag = 0.04
        spec.life_span = 100
        spec.update_behaviors.append(SpinBehavior())
        spec.draw_behaviors.append(TrailBehavior())
    elif fw_type == "Willow":
        spec.particle_count = 120
        spec.speed_variance = 8.0
        spec.gravity_mod = 0.2
        spec.drag = 0.02
        spec.life_span = 220
        spec.draw_behaviors.append(TrailBehavior(trail_len=25))

    return spec


def get_random_preset():
    return generate_spec(random.choice(FIREWORK_TYPES))
