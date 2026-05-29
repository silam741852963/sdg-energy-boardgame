import pyxel
import random
import math
import copy
from .config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    CUSTOM_PALETTE,
    FULLSCREEN,
    COLOR_MAP,
    SCALE_X,
    SCALE_Y,
)
from .physics import calculate_launch_velocity
from .models import get_random_preset, COLORS, load_drone_pattern, ASCII_COLOR_MAP
from .particles import Particle, Drone
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
        self.drones = []

        self.lighting = LightingSystem()
        self.gui = ControlPanel()

    def launch_drones(self):
        pattern = load_drone_pattern("pattern.txt")
        if not pattern:
            return

        spacing = self.gui.drone_spacing * SCALE_X
        height = len(pattern)
        width = max(len(row) for row in pattern)

        start_x = -(width * spacing) / 2
        start_y = self.gui.drone_altitude * SCALE_Y

        for row_idx, row in enumerate(pattern):
            for col_idx, char in enumerate(row):
                char = char.upper()
                if char in ASCII_COLOR_MAP:
                    tx = start_x + (col_idx * spacing)
                    ty = start_y + (row_idx * spacing)

                    self.drones.append(
                        Drone(
                            target_x=tx,
                            target_y=ty,
                            target_z=0,
                            color_name=ASCII_COLOR_MAP[char],
                            radius=self.gui.drone_radius,
                            intensity=self.gui.drone_intensity,
                        )
                    )

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

        if spec.name in ["Comet", "Pearls"]:
            if spec.name == "Comet":
                num_shells = 7
                spread_width = 30.0
                for i in range(num_shells):
                    offset = -(spread_width / 2) + (
                        i * (spread_width / (num_shells - 1))
                    )
                    off_vx = vx + offset
                    off_vy = vy - (10.0 - abs(offset) * 0.5)
                    off_vz = vz
                    shell = Particle(
                        sx, sy, sz, off_vx, off_vy, off_vz, spec, is_shell=True
                    )
                    self.shells.append(shell)
            elif spec.name == "Pearls":
                num_shells = 7
                spread_width = 12.0

                mixed_colors = (
                    random.sample(COLORS, min(spec.multicolor, len(COLORS)))
                    if spec.multicolor > 1
                    else [spec.base_color]
                )

                for i in range(num_shells):
                    offset = -(spread_width / 2) + (
                        i * (spread_width / (num_shells - 1))
                    )
                    off_vx = vx + offset
                    off_vy = vy - 4.0
                    off_vz = vz

                    p_spec = copy.copy(spec)
                    p_spec.base_color = mixed_colors[i % len(mixed_colors)]

                    shell = Particle(
                        sx, sy, sz, off_vx, off_vy, off_vz, p_spec, is_shell=True
                    )
                    shell.particle_color = p_spec.base_color
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
                if spec.name == "Palm Tree":
                    phi = random.uniform(math.pi * 0.8, math.pi * 2.2)
                elif spec.name == "Rising Tail":
                    phi = random.uniform(1.2 * math.pi, 1.8 * math.pi)
                else:
                    phi = random.uniform(0, math.pi * 2)

                if spec.name == "Rising Tail":
                    costheta = random.uniform(-0.6, 0.6)
                else:
                    costheta = random.uniform(-1, 1)

                theta = math.acos(costheta)

                if spec.name == "Peony":
                    speed = (
                        random.uniform(
                            spec.speed_variance * 1.2, spec.speed_variance * 1.6
                        )
                        * speed_mult
                    )
                else:
                    speed = (
                        random.uniform(
                            spec.speed_variance * 0.8, spec.speed_variance * 1.6
                        )
                        * speed_mult
                    )

                pvx = speed * math.sin(theta) * math.cos(phi)
                pvy = speed * math.sin(theta) * math.sin(phi)
                pvz = speed * math.cos(theta)

                if spec.name == "Rising Tail":
                    mag = math.sqrt(
                        shell.launch_vx**2 + shell.launch_vy**2 + shell.launch_vz**2
                    )
                    if mag > 0:
                        nx = shell.launch_vx / mag
                        ny = shell.launch_vy / mag
                        nz = shell.launch_vz / mag

                        pvx = (pvx * 0.2) + (nx * speed * 1.5)
                        pvy = (pvy * 0.2) + (ny * speed * 1.5)
                        pvz = (pvz * 0.2) + (nz * speed * 1.5)

                elif spec.name != "Peony":
                    pvx += shell.vx * 0.2
                    pvy += shell.vy * 0.2
                    pvz += shell.vz * 0.2
                    pvy -= random.uniform(0.5, 2.0)

                p = Particle(
                    shell.x, shell.y, shell.z, pvx, pvy, pvz, spec, is_inner=is_inner
                )

                if spec.name == "Pistil" and is_inner:
                    p.flicker = True

                p.particle_color = random.choice(color_pool)
                self.particles.append(p)

    def update(self):
        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()

        gui_captured_mouse = self.gui.update()

        # --- KEYBOARD SHORTCUTS ---
        if pyxel.btnp(pyxel.KEY_D):
            self.launch_drones()
        if pyxel.btnp(pyxel.KEY_C):
            for d in self.drones:
                d.clear()

        # --- GUI BUTTON SIGNALS ---
        if self.gui.trigger_drones:
            self.gui.trigger_drones = False
            self.launch_drones()

        if self.gui.clear_drones:
            self.gui.clear_drones = False
            for d in self.drones:
                d.clear()

        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and not gui_captured_mouse:
            if self.gui.visible:
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
                random.randint(int(400 * SCALE_X), SCREEN_WIDTH - int(400 * SCALE_X)),
                random.randint(int(400 * SCALE_Y), int(700 * SCALE_Y)),
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
                    self.particles.append(new_p)

        self.particles = [p for p in self.particles if p.active]

        for d in self.drones:
            d.update()

        # Clean up dead drones
        self.drones = [d for d in self.drones if d.active]

    def draw(self):
        self.lighting.draw_background()
        self.lighting.draw_reflections()

        for s in self.shells:
            s.draw(intensity=s.get_intensity())
        for p in self.particles:
            p.draw(intensity=p.get_intensity())

        for d in self.drones:
            d.draw()

        self.gui.draw()


def run():
    app = FireworkEngine()
    pyxel.run(app.update, app.draw)


if __name__ == "__main__":
    run()
