import pyxel
import random
import math
import copy
from .config import SCREEN_WIDTH, SCREEN_HEIGHT, CUSTOM_PALETTE, FULLSCREEN, COLOR_MAP
from .physics import calculate_launch_velocity
from .models import get_random_preset
from .particles import Particle
from .lighting import LightingSystem, bake_particle_sprites
from .gui import ControlPanel


class FireworkEngine:
    def __init__(self):
        pyxel.init(SCREEN_WIDTH, SCREEN_HEIGHT, fps=60, title="3D Fireworks")

        if FULLSCREEN:
            pyxel.fullscreen(True)

        pyxel.colors[: len(CUSTOM_PALETTE)] = CUSTOM_PALETTE
        bake_particle_sprites()
        pyxel.mouse(True)

        self.particles = []
        self.shells = []
        self.lighting = LightingSystem()
        self.gui = ControlPanel()

    def launch(self, target_px, target_py, forced_spec=None):
        tx = target_px - (SCREEN_WIDTH / 2)
        clamped_py = max(350, min(target_py, SCREEN_HEIGHT - 300))
        ty = clamped_py - (SCREEN_HEIGHT / 2)
        tz = random.uniform(-100, 100)

        sx = random.uniform(-600, 600)
        sy = SCREEN_HEIGHT / 2
        sz = random.uniform(-100, 100)

        gravity = 0.5
        vx, vy, vz = calculate_launch_velocity((sx, sy, sz), (tx, ty, tz), gravity)

        spec = forced_spec if forced_spec else get_random_preset()

        if spec.name in ["Comet", "Pearls"]:
            num_shells = random.randint(8, 15)
            for _ in range(num_shells):
                off_vx = vx + random.uniform(-3.0, 3.0)
                off_vy = vy + random.uniform(-4.0, 0.0)
                off_vz = vz + random.uniform(-3.0, 3.0)
                shell = Particle(
                    sx, sy, sz, off_vx, off_vy, off_vz, spec, is_shell=True
                )
                self.shells.append(shell)
        else:
            shell = Particle(sx, sy, sz, vx, vy, vz, spec, is_shell=True)
            self.shells.append(shell)

    def explode(self, shell):
        spec = shell.spec
        if not spec.burst:
            return

        if spec.base_color != "silver":
            darkest_shade_idx = COLOR_MAP[spec.base_color] + (spec.variant * 5) + 4
            self.lighting.trigger_sky_flash(darkest_shade_idx)

        self.lighting.add_ground_reflection(
            shell.x, shell.z, spec.life_span, self.lighting.sky_flash_color
        )

        layers = [False]
        if spec.pistil:
            layers.append(True)

        for is_inner in layers:
            count = spec.particle_count // 2 if is_inner else spec.particle_count
            speed_mult = 0.4 if is_inner else 1.0

            for _ in range(count):
                phi = random.uniform(0, math.pi * 2)
                costheta = random.uniform(-1, 1)
                theta = math.acos(costheta)

                speed = (
                    random.uniform(spec.speed_variance * 1.5, spec.speed_variance * 2.5)
                    * speed_mult
                )
                pvx = speed * math.sin(theta) * math.cos(phi)
                pvy = speed * math.sin(theta) * math.sin(phi)
                pvz = speed * math.cos(theta)

                pvx += shell.vx * 0.2
                pvy += shell.vy * 0.2
                pvz += shell.vz * 0.2
                pvy -= random.uniform(1.0, 3.0)

                p = Particle(
                    shell.x, shell.y, shell.z, pvx, pvy, pvz, spec, is_inner=is_inner
                )
                self.particles.append(p)

    def update(self):
        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()

        gui_captured_mouse = self.gui.update()

        # Update Launch Logic to pass the customized spec
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and not gui_captured_mouse:
            if self.gui.visible:
                # We use the exactly tuned spec from the GUI laboratory
                custom_spec = copy.copy(self.gui.spec)
                self.launch(pyxel.mouse_x, pyxel.mouse_y, forced_spec=custom_spec)
            else:
                self.launch(pyxel.mouse_x, pyxel.mouse_y)

        if (
            not self.gui.visible
            and len(self.shells) == 0
            and len(self.particles) == 0
            and random.random() < 0.05
        ):
            self.launch(
                random.randint(400, SCREEN_WIDTH - 400),
                random.randint(400, 700),
            )

        self.lighting.update()

        for shell in self.shells:
            shell.update()
            if shell.vy >= 0 and shell.active:
                if shell.spec.burst:
                    self.explode(shell)
                    shell.active = False

        self.shells = [s for s in self.shells if s.active]

        for p in self.particles:
            p.update()
            if p.spec.split and p.age == int(p.life * 0.5) and p.active:
                p.active = False
                for i in range(4):
                    angle = i * (math.pi / 2)
                    nvx = p.vx + math.cos(angle) * 15
                    nvy = p.vy + math.sin(angle) * 15
                    new_p = Particle(p.x, p.y, p.z, nvx, nvy, p.vz, p.spec)
                    new_p.spec.split = False
                    self.particles.append(new_p)

        self.particles = [p for p in self.particles if p.active]

    def draw(self):
        self.lighting.draw_background()
        self.lighting.draw_reflections()

        for s in self.shells:
            s.draw()
        for p in self.particles:
            p.draw()

        self.gui.draw()


def run():
    app = FireworkEngine()
    pyxel.run(app.update, app.draw)


if __name__ == "__main__":
    run()
