from dataclasses import dataclass
import random
import os


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
    multicolor: int = 1
    intensity: float = 1.0


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

COLORS = [
    "red",
    "orange",
    "gold",
    "yellow",
    "lime",
    "green",
    "cyan",
    "blue",
    "indigo",
    "violet",
    "magenta",
    "pink",
]

# --- RESTORED: Drone ASCII Color Mapping ---
ASCII_COLOR_MAP = {
    "R": "red",
    "O": "orange",
    "G": "gold",
    "Y": "yellow",
    "L": "lime",
    "E": "green",
    "C": "cyan",
    "B": "blue",
    "I": "indigo",
    "V": "violet",
    "M": "magenta",
    "P": "pink",
    "W": "silver",
}


def load_drone_pattern(filename="pattern.txt"):
    """Reads the ASCII text file safely relative to the execution directory."""
    filepath = os.path.join(os.getcwd(), filename)

    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            # We strip the newline characters but KEEP the spaces!
            return [line.rstrip("\r\n") for line in f.readlines()]
    else:
        print(f"WARNING: Could not find {filepath}. Using fallback pattern.")
        return ["  W W W  ", " W W W W ", "  W W W  "]


def generate_spec(fw_type: str) -> FireworkSpec:
    color = random.choice(COLORS)
    variant = random.choice([0, 1])

    spec = FireworkSpec(
        name=fw_type,
        particle_count=random.randint(60, 90),
        base_color=color,
        variant=variant,
        speed_variance=7.0,
        radius=1.0,
        gravity_mod=0.5,
        drag=0.03,
        has_trails=False,
        life_span=80,
    )

    if fw_type == "Brocade":
        spec.particle_count = 150
        spec.has_trails = True
        spec.palm_tail = True
        spec.glitter = True
        spec.gravity_mod = 0.4
        spec.drag = 0.03
        spec.life_span = 140
        spec.speed_variance = 9.0
    elif fw_type == "Chrysanthemum":
        spec.particle_count = 350
        spec.has_trails = True
        spec.speed_variance = 22.0
        spec.drag = 0.15
        spec.gravity_mod = 0.05
        spec.life_span = 80
    elif fw_type == "Comet":
        spec.burst = False
        spec.life_span = 100
        spec.gravity_mod = 0.1
        spec.drag = 0.01
        spec.variant = 1
        spec.radius = 2.0
        spec.has_trails = True
        spec.palm_tail = True
    elif fw_type == "Crossette":
        spec.particle_count = 18
        spec.has_trails = True
        spec.split = True
        spec.speed_variance = 5.0
        spec.drag = 0.01
        spec.gravity_mod = 0.2
        spec.life_span = 40
    elif fw_type == "Pearls":
        spec.burst = False
        spec.has_trails = False
        spec.life_span = 120
        spec.radius = 3.0
        spec.intensity = 2.0
        spec.multicolor = len(COLORS)
    elif fw_type == "Dragon Eggs":
        spec.particle_count = 120
        spec.crackle = True
        spec.speed_variance = 7.0
        spec.life_span = 130
    elif fw_type == "Waterfall":
        spec.particle_count = 150
        spec.waterfall = True
        spec.has_trails = True
        spec.gravity_mod = 1.2
        spec.drag = 0.10
        spec.speed_variance = 12.0
        spec.life_span = 180
    elif fw_type == "Flying Fish":
        spec.particle_count = 60
        spec.swim = True
        spec.has_trails = True
        spec.speed_variance = 5.0
        spec.drag = 0.04
        spec.gravity_mod = 0.05
        spec.radius = 1.5
        spec.life_span = 30
    elif fw_type == "Palm Tree":
        spec.particle_count = 12
        spec.palm_tail = True
        spec.has_trails = True
        spec.speed_variance = 7.0
        spec.drag = 0.02
        spec.life_span = 70
        spec.gravity_mod = 1
        spec.radius = 3
    elif fw_type == "Peony":
        spec.particle_count = 200
        spec.has_trails = False
        spec.speed_variance = 18.0
        spec.drag = 0.12
        spec.gravity_mod = 0.05
        spec.radius = 0.5
        spec.life_span = 100
    elif fw_type == "Pistil":
        spec.particle_count = 150
        spec.pistil = True
        spec.speed_variance = 5.0
        spec.life_span = 100
        spec.multicolor = 1
    elif fw_type == "Rising Tail":
        spec.palm_tail = True
        spec.particle_count = 40
        spec.speed_variance = 5.0
        spec.drag = 0.005
        spec.gravity_mod = 0.8
        spec.radius = 2.0
        spec.life_span = 120
        spec.has_trails = True
    elif fw_type == "Strobe":
        spec.particle_count = 100
        spec.flicker = True
        spec.speed_variance = 4.0
        spec.gravity_mod = 0.1
        spec.life_span = 140
    elif fw_type == "Tourbillion":
        spec.particle_count = 50
        spec.spin = True
        spec.has_trails = True
        spec.speed_variance = 6.0
        spec.drag = 0.02
        spec.life_span = 100
    elif fw_type == "Willow":
        spec.particle_count = 120
        spec.has_trails = True
        spec.speed_variance = 10.0
        spec.gravity_mod = 0.2
        spec.drag = 0.01
        spec.life_span = 220

    return spec


def get_random_preset():
    return generate_spec(random.choice(FIREWORK_TYPES))
