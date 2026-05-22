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
        spec.particle_count = 150  # Massive spider web
        spec.has_trails = True
        spec.gravity_mod = 0.3  # Floats nicely
        spec.drag = 0.02
        spec.life_span = 120
        spec.speed_variance = 14.0
    elif fw_type == "Chrysanthemum":
        spec.particle_count = 250  # Insane density
        spec.has_trails = True
        spec.speed_variance = 30.0  # Explodes outward with brutal force
        spec.drag = 0.18  # Instantly slams on the brakes to form a perfect sphere
        spec.life_span = 80
    elif fw_type == "Comet":
        spec.burst = False
        spec.has_trails = True
        spec.life_span = 120  # Lives long enough to fall back down
    elif fw_type == "Crossette":
        spec.particle_count = 20
        spec.has_trails = True
        spec.split = True
        spec.speed_variance = 12.0  # Fast moving cores before split
        spec.life_span = 60
    elif fw_type == "Pearls":
        spec.burst = False  # Pearls are multiple-launch, they should not burst!
        spec.has_trails = False
        spec.life_span = 100
    elif fw_type == "Dragon Eggs":
        spec.particle_count = 100
        spec.crackle = True
        spec.speed_variance = 15.0
        spec.life_span = 110  # Extra life to allow for the crackle delay
    elif fw_type == "Waterfall":
        spec.particle_count = 120
        spec.waterfall = True
        spec.has_trails = True
        spec.gravity_mod = -0.1  # Literally hovers at apex before falling
        spec.drag = 0.15
        spec.speed_variance = 20.0
        spec.life_span = 160
    elif fw_type == "Flying Fish":
        spec.particle_count = 40
        spec.swim = True
        spec.has_trails = True
        spec.speed_variance = 8.0  # Slower initial speed so the swimming is obvious
        spec.drag = 0.08
        spec.life_span = 100
    elif fw_type == "Palm Tree":
        spec.particle_count = 20
        spec.palm_tail = True
        spec.has_trails = True
        spec.speed_variance = 18.0  # Fronds shoot out far
        spec.drag = 0.01  # Keeps its momentum
        spec.gravity_mod = 0.8  # Arcs heavily
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
        spec.gravity_mod = 0.2  # Floats while blinking
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
        spec.speed_variance = 15.0  # Soft burst
        spec.gravity_mod = 0.2  # Barely any gravity
        spec.drag = 0.01
        spec.life_span = 200  # Hangs in the sky forever

    return spec


def get_random_preset():
    return generate_spec(random.choice(FIREWORK_TYPES))
