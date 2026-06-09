import math
import random
import copy

from .config import SCREEN_WIDTH, SCREEN_HEIGHT, SCALE_X, SCALE_Y, COLOR_MAP, COLORS
from .physics import calculate_launch_velocity
from .models import get_random_preset
from .particles import Particle

class FireworkManager:
    def __init__(self, audio_system, lighting_system):
        self.audio = audio_system
        self.lighting = lighting_system
        self.particles = []
        self.shells = []

    def launch(self, target_px, target_py, forced_spec=None):
        tx = target_px - (SCREEN_WIDTH / 2)
        clamped_py = max(
            int(350 * SCALE_Y), min(target_py, SCREEN_HEIGHT - int(300 * SCALE_Y))
        )
        ty = clamped_py - (SCREEN_HEIGHT / 2)
        tz = random.uniform(-100, 100)

        spec = forced_spec if forced_spec else get_random_preset()

        if spec.name == "Rising Tail":
            sx = tx
            sz = tz
        else:
            sx = random.uniform(-600 * SCALE_X, 600 * SCALE_X)
            sz = random.uniform(-100, 100)

        sy = SCREEN_HEIGHT / 2
        gravity = 0.3
        vx, vy, vz = calculate_launch_velocity((sx, sy, sz), (tx, ty, tz), gravity)

        self.audio.play_launch(sx)
        
        spec.launch_strategy.apply(self, sx, sy, sz, vx, vy, vz, spec)

    def explode(self, shell):
        spec = shell.spec
        if not spec.burst:
            return

        self.audio.play_explosion(spec, shell.x, shell.y)

        if spec.base_color != "silver":
            darkest_shade_idx = COLOR_MAP[spec.base_color] + (spec.variant * 5) + 4
            self.lighting.trigger_sky_flash(darkest_shade_idx)

        self.lighting.add_ground_reflection(
            shell.x,
            shell.z,
            spec.life_span,
            self.lighting.sky_flash_color,
            radius_mod=spec.radius,
        )

        layers = [False]
        if spec.pistil:
            layers.append(True)

        color_pool = [spec.base_color]
        if spec.multicolor > 1:
            color_pool = random.sample(COLORS, min(spec.multicolor, len(COLORS)))

        for is_inner in layers:
            count = spec.particle_count // 2 if is_inner else spec.particle_count
            speed_mult = 0.4 if is_inner else 1.0

            for _ in range(count):
                pvx, pvy, pvz = spec.burst_strategy.get_velocity(shell, speed_mult, spec)

                p = Particle(
                    shell.x, shell.y, shell.z, pvx, pvy, pvz, spec, is_inner=is_inner
                )

                if spec.name == "Pistil" and is_inner:
                    from .behaviors import FlickerBehavior
                    p.draw_behaviors.append(FlickerBehavior())

                p.particle_color = random.choice(color_pool)
                self.particles.append(p)

    def update(self):
        for shell in self.shells:
            shell.update()
            if shell.vy >= 0 and shell.active:
                if shell.spec.burst:
                    self.explode(shell)
                    shell.active = False

        self.shells = [s for s in self.shells if s.active]

        new_particles = []
        for p in self.particles:
            p.update()
            if (
                p.spec.split
                and not p.is_split_child
                and p.age == int(p.life * 0.5)
                and p.active
            ):
                p.active = False
                for i in range(4):
                    angle = i * (math.pi / 2) + (math.pi / 4)

                    nvx = (p.vx * 0.4) + math.cos(angle) * 4
                    nvy = (p.vy * 0.4) + math.sin(angle) * 4
                    nvz = p.vz * 0.4

                    new_p = Particle(p.x, p.y, p.z, nvx, nvy, nvz, p.spec)
                    new_p.is_split_child = True
                    new_p.particle_color = p.particle_color
                    new_p.life = p.life * 0.4
                    new_particles.append(new_p)

        if new_particles:
            self.particles.extend(new_particles)

        self.particles = [p for p in self.particles if p.active]

    def draw(self):
        for s in self.shells:
            s.draw(intensity=s.get_intensity())
        for p in self.particles:
            p.draw(intensity=p.get_intensity())
