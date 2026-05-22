import pyxel
import math
from .physics import project_3d_to_2d
from .config import SCREEN_HEIGHT


class LightingSystem:
    def __init__(self):
        self.sky_flash_timer = 0
        self.sky_flash_color = 0
        self.active_explosions = []

    def trigger_sky_flash(self, color_idx: int):
        self.sky_flash_color = color_idx
        self.sky_flash_timer = 3

    def add_ground_reflection(self, x: float, z: float, max_age: int, color_idx: int):
        self.active_explosions.append([x, z, 0, max_age, color_idx])

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
        # Pushed horizon down further for 1080p
        horizon_y = (SCREEN_HEIGHT / 2) + 200

        for exp_x, exp_z, age, max_age, color in self.active_explosions:
            if age < max_age * 0.6:
                rx, ry, factor = project_3d_to_2d(exp_x, SCREEN_HEIGHT / 2, exp_z)
                if factor > 0:
                    intensity = 1.0 - (age / (max_age * 0.6))
                    # Greatly increased reflection size for 1080p
                    width = int(150 * factor * intensity)
                    height = int(30 * factor * intensity)
                    if width > 0 and height > 0:
                        pyxel.elli(
                            rx - width / 2,
                            horizon_y + (ry - horizon_y) * 0.3,
                            width,
                            height,
                            color,
                        )


def bake_particle_sprites():
    """
    Pre-renders large 32x32 dithered glowing orbs.
    Because a single Image Bank can only hold 64 sprites of this size,
    we split the 71 colors across Bank 0 and Bank 1.
    """
    pyxel.images[0].rect(0, 0, 256, 256, 0)
    pyxel.images[1].rect(0, 0, 256, 256, 0)

    sprites_per_row = 8

    for color_idx in range(1, 72):
        # Colors 1-63 go to Bank 0, Colors 64-71 go to Bank 1
        bank = 0 if color_idx < 64 else 1
        local_idx = color_idx % 64

        ix = (local_idx % sprites_per_row) * 32
        iy = (local_idx // sprites_per_row) * 32

        for dy in range(32):
            for dx in range(32):
                dist = math.sqrt((dx - 15.5) ** 2 + (dy - 15.5) ** 2)
                draw_pixel = False

                if dist <= 3.0:
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

                if draw_pixel:
                    pyxel.images[bank].pset(ix + dx, iy + dy, color_idx)


def draw_baked_particle(px, py, color_idx, factor):
    if color_idx == 0:
        return

    if factor < 0.4:
        pyxel.pset(px, py, color_idx)
    else:
        bank = 0 if color_idx < 64 else 1
        local_idx = color_idx % 64
        sprites_per_row = 8

        ix = (local_idx % sprites_per_row) * 32
        iy = (local_idx // sprites_per_row) * 32

        # blt uses the 'bank' variable to pull from the correct VRAM memory
        pyxel.blt(px - 16, py - 16, bank, ix, iy, 32, 32, 0)
