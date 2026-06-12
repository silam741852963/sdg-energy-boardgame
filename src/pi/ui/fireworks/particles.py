import pyxel
import math
import random
import collections
from .physics import project_3d_to_2d
from .config import COLOR_MAP
from .config import COLORS
from .lighting import draw_baked_particle
from .behaviors import TrailBehavior

class Particle:
    _pool = []
    
    @classmethod
    def create(cls, x, y, z, vx, vy, vz, spec, is_shell=False, is_inner=False):
        if cls._pool:
            p = cls._pool.pop()
            p._init_state(x, y, z, vx, vy, vz, spec, is_shell, is_inner)
            return p
        else:
            p = cls.__new__(cls)
            p._init_state(x, y, z, vx, vy, vz, spec, is_shell, is_inner)
            return p

    def _init_state(self, x, y, z, vx, vy, vz, spec, is_shell=False, is_inner=False):
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
        self.spin_angle = random.uniform(0, math.pi * 2)

        self.particle_color = spec.base_color

        if spec.name == "Flying Fish" and not is_shell:
            self.particle_color = random.choice(["silver", spec.base_color])
        elif getattr(spec, "multicolor", 1) > 1 and not is_shell:
            pool = random.sample(COLORS, min(spec.multicolor, len(COLORS)))
            self.particle_color = random.choice(pool)

        self.flicker_offset = random.randint(0, 60)
        self.px, self.py, self.factor = project_3d_to_2d(self.x, self.y, self.z)
        
        self.update_behaviors = [] if is_shell else spec.update_behaviors
        
        if is_shell and spec.burst:
            if spec.name in ["Rising Tail", "Palm Tree"]:
                self.draw_behaviors = [TrailBehavior(palm_tail=True, trail_len=8)]
            else:
                self.draw_behaviors = [TrailBehavior(trail_len=5)]
        else:
            self.draw_behaviors = spec.draw_behaviors

        # --- HOISTED CALCULATIONS ---
        self.trail_len = 0
        for b in self.draw_behaviors:
            if isinstance(b, TrailBehavior):
                self.trail_len = b.trail_len
                break
                
        if self.is_shell and self.trail_len == 0:
            self.trail_len = 5
            
        self.is_palm_tail_shell = self.is_shell and any(isinstance(b, TrailBehavior) and b.palm_tail for b in self.draw_behaviors)
        
        self.history = collections.deque(maxlen=self.trail_len if self.trail_len > 0 else 1)

    def update(self):
        if not self.active:
            return
        self.age += 1

        if not (self.is_shell and self.spec.burst):
            if self.age > self.life:
                self.active = False
                return

        if self.trail_len > 0:
            self.history.append((self.px, self.py, self.factor))

        for behavior in self.update_behaviors:
            behavior.update(self)

        self.vy += self.gravity
        self.vx *= 1 - self.drag
        self.vy *= 1 - self.drag
        self.vz *= 1 - self.drag

        self.x += self.vx
        self.y += self.vy
        self.z += self.vz

        self.px, self.py, self.factor = project_3d_to_2d(self.x, self.y, self.z)

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

        if self.factor <= 0:
            return

        for behavior in self.draw_behaviors:
            if behavior.pre_draw(self):
                return

        color = 121 if self.is_palm_tail_shell else self.get_shade(self.factor)

        if self.spec.name != "Willow" or self.is_shell:
            draw_baked_particle(self.px, self.py, color, self.factor, intensity, self.spec.radius)

        for behavior in self.draw_behaviors:
            behavior.post_draw(self)
