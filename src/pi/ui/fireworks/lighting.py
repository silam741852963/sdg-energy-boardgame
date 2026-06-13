from .physics import project_3d_to_2d
from .config import SCREEN_HEIGHT, SCALE_X, SCALE_Y
from . import palette

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

    def draw_background(self, renderer):
        if self.sky_flash_timer > 0:
            c = palette.get_color(self.sky_flash_color)
        else:
            c = (0.0, 0.0, 0.0)
        
        # Clear with background color (sky flash)
        renderer.clear((c[0], c[1], c[2], 1.0))

    def draw_reflections(self, renderer):
        horizon_y = (SCREEN_HEIGHT / 2) + int(200 * SCALE_Y)

        for exp_x, exp_z, age, max_age, color, radius_mod in self.active_explosions:
            if age < max_age * 0.6:
                rx, ry, factor = project_3d_to_2d(exp_x, SCREEN_HEIGHT / 2, exp_z)
                if factor > 0:
                    intensity = 1.0 - (age / (max_age * 0.6))
                    width = int(150 * SCALE_X * factor * intensity * radius_mod)
                    height = int(30 * SCALE_Y * factor * intensity * radius_mod)

                    if width > 0 and height > 0:
                        c = palette.get_color(color)
                        # Render ground reflections as blended ellipses on the ground
                        renderer.draw_ellipse(
                            rx - width / 2,
                            horizon_y + (ry - horizon_y) * 0.3,
                            width,
                            height,
                            (c[0], c[1], c[2], intensity * 0.4)
                        )
