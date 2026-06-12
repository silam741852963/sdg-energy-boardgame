import pyxel
import math
from .physics import project_3d_to_2d
from .config import SCREEN_HEIGHT, SCALE_X, SCALE_Y


class LightingSystem:
    def __init__(self):
        self.sky_flash_timer = 0
        self.sky_flash_color = 0
        self.active_explosions = []

    def trigger_sky_flash(self, color_idx: int):
        self.sky_flash_color = color_idx
        self.sky_flash_timer = 3

    def add_ground_reflection(
        self, x: float, z: float, max_age: int, color_idx: int, radius_mod: float = 1.0
    ):
        self.active_explosions.append([x, z, 0, max_age, color_idx, radius_mod])

    def update(self):
        if self.sky_flash_timer > 0:
            self.sky_flash_timer -= 1

        for exp in self.active_explosions:
            exp[2] += 1

        self.active_explosions = [
            exp for exp in self.active_explosions if exp[2] < exp[3]
        ]

    def draw_background(self):
        bg_color = self.sky_flash_color if self.sky_flash_timer > 0 else 0
        pyxel.cls(bg_color)

    def draw_reflections(self):
        horizon_y = (SCREEN_HEIGHT / 2) + int(200 * SCALE_Y)

        for exp_x, exp_z, age, max_age, color, radius_mod in self.active_explosions:
            if age < max_age * 0.6:
                rx, ry, factor = project_3d_to_2d(exp_x, SCREEN_HEIGHT / 2, exp_z)
                if factor > 0:
                    intensity = 1.0 - (age / (max_age * 0.6))
                    width = int(150 * SCALE_X * factor * intensity * radius_mod)
                    height = int(30 * SCALE_Y * factor * intensity * radius_mod)

                    if width > 0 and height > 0:
                        pyxel.elli(
                            rx - width / 2,
                            horizon_y + (ry - horizon_y) * 0.3,
                            width,
                            height,
                            color,
                        )


def bake_particle_sprites():
    pyxel.images[0].rect(0, 0, 256, 256, 0)
    pyxel.images[1].rect(0, 0, 256, 256, 0)
    sprites_per_row = 8

    for color_idx in range(1, 122):
        bank = color_idx // 64
        local_idx = color_idx % 64
        ix = (local_idx % sprites_per_row) * 32
        iy = (local_idx // sprites_per_row) * 32

        for dy in range(32):
            for dx in range(32):
                dist = math.sqrt((dx - 15.5) ** 2 + (dy - 15.5) ** 2)
                draw_pixel = False
                use_white_core = False

                if dist <= 1.5:
                    use_white_core = True
                elif dist <= 3.0:
                    draw_pixel = True
                elif dist <= 7.0:
                    if (dx + dy) % 2 == 0:
                        draw_pixel = True
                elif dist <= 11.0:
                    if dx % 2 == 0 and dy % 2 == 0:
                        draw_pixel = True
                elif dist <= 15.0:
                    if (dx + dy) % 4 == 0 and dx % 2 == 0:
                        draw_pixel = True

                if use_white_core:
                    pyxel.images[bank].pset(ix + dx, iy + dy, 121)
                elif draw_pixel:
                    pyxel.images[bank].pset(ix + dx, iy + dy, color_idx)


def draw_baked_particle(px, py, color_idx, factor, intensity=1.0, radius=1.0):
    color_idx = int(color_idx)
    if color_idx == 0:
        return

    if color_idx != 121:
        safe_intensity = max(0.0, min(1.0, intensity))
        shade_drop = int((1.0 - safe_intensity) * 4.0)
        base_color_start = ((color_idx - 1) // 5) * 5 + 1
        max_idx = base_color_start + 4
        color_idx = min(color_idx + shade_drop, max_idx)

    effective_factor = factor * radius
    px, py = int(px), int(py)

    if effective_factor < 0.4 or intensity < 0.3:
        dot_color = 121 if intensity > 0.8 else color_idx
        dot_size = int(radius * factor * 2)
        if dot_size > 1:
            pyxel.circ(px, py, dot_size, dot_color)
        else:
            pyxel.pset(px, py, dot_color)
    else:
        bank = int(color_idx // 64)
        local_idx = int(color_idx % 64)
        sprites_per_row = 8
        ix = (local_idx % sprites_per_row) * 32
        iy = (local_idx // sprites_per_row) * 32

        # VISUAL FIX: Draw a dim, dithered halo to simulate a soft glow drop-off
        # Skip halo for dim/distant particles to save CPU
        if radius > 1.2 and intensity > 0.4 and factor > 0.5:
            # 1. Force the halo to be the absolute darkest shade available
            if color_idx == 121:
                halo_color = 123  # Dark Gray
            else:
                base_color_start = ((color_idx - 1) // 5) * 5 + 1
                halo_color = base_color_start + 4

            glow_size = int(12 * factor * radius)

            # 2. Draw sparse concentric rings (step=6 for performance)
            if halo_color != 121:
                for r in range(6, glow_size + 1, 6):
                    pyxel.circb(px, py, r, halo_color)

        pyxel.blt(px - 16, py - 16, bank, ix, iy, 32, 32, 0)
