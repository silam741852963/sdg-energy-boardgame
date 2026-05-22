from dataclasses import dataclass
import random


@dataclass
class FireworkSpec:
    name: str
    particle_count: int
    base_color: str
    variant: int
    speed_variance: float
    gravity_mod: float
    drag: float
    has_trails: bool
    life_span: int
    flicker: bool = False
    swim: bool = False
    split: bool = False
    crackle: bool = False
    burst: bool = True
    pistil: bool = False
    spin: bool = False
    waterfall: bool = False
    palm_tail: bool = False
    glitter: bool = False


FIREWORK_TYPES = [
    "Brocade",
    "Chrysanthemum",
    "Comet",
    "Crossette",
    "Pearls",
    "Dragon Eggs",
    "Waterfall",
    "Flying Fish",
    "Palm Tree",
    "Peony",
    "Pistil",
    "Rising Tail",
    "Strobe",
    "Tourbillion",
    "Willow",
]

COLORS = ["red", "orange", "yellow", "green", "blue", "indigo", "violet"]


def generate_spec(fw_type: str) -> FireworkSpec:
    color = random.choice(COLORS)
    variant = random.choice([0, 1])

    # Baseline defaults
    spec = FireworkSpec(
        name=fw_type,
        particle_count=random.randint(60, 90),
        base_color=color,
        variant=variant,
        speed_variance=10.0,
        gravity_mod=0.6,
        drag=0.04,
        has_trails=False,
        life_span=60,
    )

    if fw_type == "Brocade":
        spec.particle_count = 150
        spec.has_trails = True
        spec.palm_tail = True
        spec.glitter = True
        spec.gravity_mod = 0.5
        spec.drag = 0.04
        spec.life_span = 120
        spec.speed_variance = 14.0
    elif fw_type == "Chrysanthemum":
        spec.particle_count = 350  # Increased for massive density
        spec.has_trails = True
        spec.speed_variance = 40.0  # Explodes outward with brutal force
        spec.drag = 0.20  # Slams on the brakes harder
        spec.gravity_mod = (
            0.05  # Almost zero gravity to keep the perfect spherical shape
        )
        spec.life_span = 90
    elif fw_type == "Comet":
        spec.burst = False
        spec.has_trails = True
        spec.palm_tail = True  # Gives the comet the thick, bright trail from the GIF
        spec.life_span = 140
    elif fw_type == "Crossette":
        spec.particle_count = (
            8  # Less is more! Fewer particles make the cross splits distinct
        )
        spec.has_trails = True
        spec.split = True
        spec.speed_variance = 2.0  # Shoots out very fast and straight
        spec.drag = 0.01  # Minimal drag before the split
        spec.gravity_mod = 0.2  # Slight droop
        spec.life_span = 70
    elif fw_type == "Pearls":
        spec.burst = False
        spec.has_trails = False
        spec.life_span = 100
    elif fw_type == "Dragon Eggs":
        spec.particle_count = 100
        spec.crackle = True
        spec.speed_variance = 15.0
        spec.life_span = 110
    elif fw_type == "Waterfall":
        spec.particle_count = 120
        spec.waterfall = True
        spec.has_trails = True
        spec.gravity_mod = -0.1
        spec.drag = 0.15
        spec.speed_variance = 20.0
        spec.life_span = 160
    elif fw_type == "Flying Fish":
        spec.particle_count = 40
        spec.swim = True
        spec.has_trails = True
        spec.speed_variance = 8.0
        spec.drag = 0.08
        spec.life_span = 100
    elif fw_type == "Palm Tree":
        spec.particle_count = 20
        spec.palm_tail = True
        spec.has_trails = True
        spec.speed_variance = 18.0
        spec.drag = 0.01
        spec.gravity_mod = 0.8
        spec.life_span = 100
    elif fw_type == "Peony":
        spec.particle_count = 120
        spec.speed_variance = 12.0
        spec.life_span = 70
    elif fw_type == "Pistil":
        spec.particle_count = 150
        spec.pistil = True
        spec.speed_variance = 14.0
        spec.life_span = 80
    elif fw_type == "Rising Tail":
        spec.palm_tail = True
        spec.particle_count = 80
        spec.speed_variance = 10.0
        spec.life_span = 70
    elif fw_type == "Strobe":
        spec.particle_count = 100
        spec.flicker = True
        spec.speed_variance = 10.0
        spec.gravity_mod = 0.2
        spec.life_span = 120
    elif fw_type == "Tourbillion":
        spec.particle_count = 50
        spec.spin = True
        spec.has_trails = True
        spec.speed_variance = 8.0
        spec.drag = 0.02
        spec.life_span = 90
    elif fw_type == "Willow":
        spec.particle_count = 120
        spec.has_trails = True
        spec.speed_variance = 15.0
        spec.gravity_mod = 0.2
        spec.drag = 0.01
        spec.life_span = 200

    return spec


def get_random_preset():
    return generate_spec(random.choice(FIREWORK_TYPES))
