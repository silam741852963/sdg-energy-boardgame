import pyxel
import math
import random
from .physics import project_3d_to_2d
from .config import COLOR_MAP
from .lighting import draw_baked_particle


class Particle:
    def __init__(self, x, y, z, vx, vy, vz, spec, is_shell=False, is_inner=False):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.spec = spec
        self.is_shell = is_shell
        self.is_inner = is_inner

        self.gravity = 0.15 * (1.0 if is_shell else spec.gravity_mod)
        self.drag = 0.01 if is_shell else spec.drag
        self.age = 0
        self.life = (
            spec.life_span if is_shell else spec.life_span * random.uniform(0.8, 1.2)
        )

        self.active = True
        self.history = []
        self.spin_angle = random.uniform(0, math.pi * 2)

    def update(self):
        if not self.active:
            return
        self.age += 1

        # BUG FIX 1: Shells meant to explode will NEVER die of old age.
        # They are guaranteed to survive until they reach the apex.
        if not (self.is_shell and self.spec.burst):
            if self.age > self.life:
                self.active = False
                return

        if self.spec.has_trails or self.is_shell:
            self.history.append((self.x, self.y, self.z))
            trail_len = 8 if (self.is_shell and self.spec.palm_tail) else 5
            if self.spec.waterfall:
                trail_len = 12
            if len(self.history) > trail_len:
                self.history.pop(0)

        if self.spec.waterfall and not self.is_shell:
            self.gravity = min(0.3, self.gravity + 0.005)

        if self.spec.swim and not self.is_shell:
            self.vx += random.uniform(-1.5, 1.5)
            self.vz += random.uniform(-1.5, 1.5)

        if self.spec.spin and not self.is_shell:
            self.spin_angle += 0.8
            self.vx += math.cos(self.spin_angle) * 1.5
            self.vz += math.sin(self.spin_angle) * 1.5

        self.vy += self.gravity
        self.vx *= 1 - self.drag
        self.vy *= 1 - self.drag
        self.vz *= 1 - self.drag

        self.x += self.vx
        self.y += self.vy
        self.z += self.vz

    def get_shade(self, factor):
        if self.spec.base_color == "silver":
            return 71

        base = self.spec.base_color
        if self.is_inner:
            base = "silver" if base != "blue" else "red"

        if base == "silver":
            return 71

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

    def draw(self):
        if not self.active:
            return

        px, py, factor = project_3d_to_2d(self.x, self.y, self.z)
        if factor <= 0:
            return

        if self.spec.crackle and not self.is_shell:
            if self.age > self.life * 0.8:
                pyxel.pset(px, py, 71)
                return
            elif self.age > self.life * 0.5:
                return

        if self.spec.flicker and not self.is_shell and pyxel.frame_count % 6 < 3:
            return

        color = (
            71 if (self.is_shell and self.spec.palm_tail) else self.get_shade(factor)
        )

        draw_baked_particle(px, py, color, factor)

        if len(self.history) > 1:
            for i in range(1, len(self.history)):
                hx1, hy1, hz1 = self.history[i - 1]
                hx2, hy2, hz2 = self.history[i]

                px1, py1, factor1 = project_3d_to_2d(hx1, hy1, hz1)
                px2, py2, factor2 = project_3d_to_2d(hx2, hy2, hz2)

                if factor1 > 0 and factor2 > 0:
                    trail_col = self.get_shade(factor1 - 0.3)

                    # Palm tree tails draw extremely thick
                    if self.is_shell and self.spec.palm_tail:
                        pyxel.line(px1, py1, px2, py2, trail_col)
                        pyxel.line(px1 + 1, py1, px2 + 1, py2, trail_col)
                        pyxel.line(px1 - 1, py1, px2 - 1, py2, trail_col)
                    else:
                        pyxel.line(px1, py1, px2, py2, trail_col)
