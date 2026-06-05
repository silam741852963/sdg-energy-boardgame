import pyxel
import math
import random
from .physics import project_3d_to_2d
from .config import COLOR_MAP
from .models import COLORS
from .lighting import draw_baked_particle


class Particle:
    def __init__(self, x, y, z, vx, vy, vz, spec, is_shell=False, is_inner=False):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.launch_vx = vx
        self.launch_vy = vy
        self.launch_vz = vz

        self.spec = spec
        self.is_shell = is_shell
        self.is_inner = is_inner
        self.is_split_child = False
        self.gravity = 0.15 * (1.0 if is_shell else spec.gravity_mod)
        self.drag = 0.01 if is_shell else spec.drag
        self.age = 0
        self.life = (
            spec.life_span if is_shell else spec.life_span * random.uniform(0.8, 1.2)
        )
        self.active = True
        self.history = []
        self.spin_angle = random.uniform(0, math.pi * 2)

        self.particle_color = spec.base_color

        if spec.name == "Flying Fish" and not is_shell:
            self.particle_color = random.choice(["silver", spec.base_color])
        elif getattr(spec, "multicolor", 1) > 1 and not is_shell:
            pool = random.sample(COLORS, min(spec.multicolor, len(COLORS)))
            self.particle_color = random.choice(pool)

        self.flicker_offset = random.randint(0, 60)
        self.flicker = spec.flicker

    def update(self):
        if not self.active:
            return
        self.age += 1

        if not (self.is_shell and self.spec.burst):
            if self.age > self.life:
                self.active = False
                return

        if self.spec.has_trails or self.is_shell:
            self.history.append((self.x, self.y, self.z))
            trail_len = 8 if (self.is_shell and self.spec.palm_tail) else 5

            if self.spec.waterfall:
                trail_len = 12
            if self.spec.name == "Rising Tail" and not self.is_shell:
                trail_len = 20
            if self.spec.name == "Willow" and not self.is_shell:
                trail_len = 25

            if len(self.history) > trail_len:
                self.history.pop(0)

        if self.spec.waterfall and not self.is_shell:
            self.gravity = min(0.3, self.gravity + 0.005)

        if self.spec.swim and not self.is_shell:
            self.vx += random.uniform(-3.0, 3.0)
            self.vz += random.uniform(-3.0, 3.0)
            self.vy += random.uniform(-1.0, 1.0)

        if self.spec.spin and not self.is_shell:
            self.spin_angle += 1.2
            self.vx += math.cos(self.spin_angle) * 2.5
            self.vz += math.sin(self.spin_angle) * 2.5
            self.vy += random.uniform(-0.5, 0.5)

        self.vy += self.gravity
        self.vx *= 1 - self.drag
        self.vy *= 1 - self.drag
        self.vz *= 1 - self.drag

        self.x += self.vx
        self.y += self.vy
        self.z += self.vz

    def get_intensity(self):
        if self.is_shell and self.spec.burst:
            return 1.0 * self.spec.intensity

        remaining = max(0.0, 1.0 - (self.age / self.life))

        if self.spec.name == "Comet":
            val = remaining * 1.5
        elif self.spec.name == "Pearls":
            val = remaining * 3.0
        else:
            val = remaining

        return min(1.0, val) * self.spec.intensity

    def get_shade(self, factor):
        if self.particle_color == "silver":
            return 121

        base = self.particle_color
        if self.is_inner:
            base = "silver" if base != "blue" else "red"

        if base == "silver":
            return 121

        base_idx = COLOR_MAP[base] + (self.spec.variant * 5)

        if factor > 1.2:
            return base_idx
        if factor > 1.0:
            return base_idx + 1
        if factor > 0.8:
            return base_idx + 2
        if factor > 0.6:
            return base_idx + 3
        return base_idx + 4

    def draw(self, intensity=1.0):
        if not self.active:
            return

        px, py, factor = project_3d_to_2d(self.x, self.y, self.z)
        if factor <= 0:
            return

        if self.spec.crackle and not self.is_shell:
            if self.age > self.life * 0.8:
                pyxel.circ(
                    px + random.randint(-3, 3), py + random.randint(-3, 3), 1, 121
                )
                return
            elif self.age > self.life * 0.5:
                return

        if (
            self.flicker
            and not self.is_shell
            and (pyxel.frame_count + self.flicker_offset) % 6 < 3
        ):
            return

        color = (
            121 if (self.is_shell and self.spec.palm_tail) else self.get_shade(factor)
        )

        if self.spec.name != "Willow" or self.is_shell:
            draw_baked_particle(px, py, color, factor, intensity, self.spec.radius)

        if len(self.history) > 1:
            thickness = int(self.spec.radius)

            for i in range(1, len(self.history)):
                hx1, hy1, hz1 = self.history[i - 1]
                hx2, hy2, hz2 = self.history[i]

                px1, py1, factor1 = project_3d_to_2d(hx1, hy1, hz1)
                px2, py2, factor2 = project_3d_to_2d(hx2, hy2, hz2)

                if factor1 > 0 and factor2 > 0:
                    trail_col = self.get_shade(factor1 - 0.3)
                    scatter_radius = thickness + 3

                    if random.random() < 0.6:
                        sx = px1 + random.uniform(-scatter_radius, scatter_radius)
                        sy = py1 + random.uniform(-scatter_radius, scatter_radius)
                        pyxel.pset(int(sx), int(sy), trail_col)

                    if random.random() < 0.15:
                        sx = px1 + random.uniform(
                            -scatter_radius - 2, scatter_radius + 2
                        )
                        sy = py1 + random.uniform(
                            -scatter_radius - 2, scatter_radius + 2
                        )
                        pyxel.pset(int(sx), int(sy), 121)

                    if self.spec.glitter and random.random() < 0.4:
                        pyxel.pset(px1, py1, 121)
                    else:
                        if self.is_shell and self.spec.palm_tail:
                            t_width = thickness + 1
                            for w in range(-t_width, t_width + 1):
                                pyxel.line(px1 + w, py1, px2 + w, py2, trail_col)
                        else:
                            for w in range(-thickness + 1, thickness + 1):
                                pyxel.line(px1 + w, py1, px2 + w, py2, trail_col)
