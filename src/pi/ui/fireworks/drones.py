import os
import pyxel
import math
import random
from .config import SCALE_X, SCALE_Y, COLOR_MAP
from .lighting import draw_baked_particle
from .physics import project_3d_to_2d

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


class Drone:
    def __init__(
        self, target_x, target_y, target_z, color_name, radius, intensity, spawn_y=1000
    ):
        self.x = target_x + random.uniform(-150, 150)
        self.y = spawn_y
        self.z = target_z + random.uniform(-50, 50)

        self.tx = target_x
        self.ty = target_y
        self.tz = target_z

        self.prev_color = color_name
        self.target_color = color_name
        self.color_blend = 1.0

        self.radius = radius
        self.intensity = intensity

        self.active = True
        self.clearing = False

        self.speed = random.uniform(0.02, 0.04)
        self.wobble_offset = random.uniform(0, math.pi * 2)

    def transition_to(self, tx, ty, tz, color_name, radius, intensity):
        self.tx = tx
        self.ty = ty
        self.tz = tz

        if self.target_color != color_name:
            self.prev_color = self.target_color
            self.target_color = color_name
            self.color_blend = 0.0

        self.radius = radius
        self.intensity = intensity
        self.clearing = False

        self.speed = random.uniform(0.02, 0.024)

    def clear(self):
        if not self.clearing:
            self.clearing = True

            self.tx += random.uniform(-200, 200)
            self.ty -= random.uniform(1500, 2500)
            self.tz += random.uniform(-100, 100)

            self.speed = random.uniform(0.003, 0.01)

    def update(self):
        if not self.active:
            return

        self.x += (self.tx - self.x) * self.speed
        self.y += (self.ty - self.y) * self.speed
        self.z += (self.tz - self.z) * self.speed

        if self.color_blend < 1.0:
            self.color_blend += 0.02
            if self.color_blend > 1.0:
                self.color_blend = 1.0

        if not self.clearing:
            dist = abs(self.tx - self.x) + abs(self.ty - self.y)
            if dist < 15:
                self.x += math.sin(pyxel.frame_count * 0.05 + self.wobble_offset) * 0.3
                self.y += math.cos(pyxel.frame_count * 0.04 + self.wobble_offset) * 0.3
        else:
            self.intensity *= 0.99

            if self.intensity < 0.02 or self.y < -1500:
                self.active = False

    def draw(self):
        if not self.active:
            return
        px, py, factor = project_3d_to_2d(self.x, self.y, self.z)
        if factor <= 0:
            return

        if self.color_blend < 1.0:
            c1_idx = COLOR_MAP.get(self.prev_color, 121)
            draw_baked_particle(
                px,
                py,
                c1_idx,
                factor,
                self.intensity * (1.0 - self.color_blend),
                self.radius,
            )

            c2_idx = COLOR_MAP.get(self.target_color, 121)
            draw_baked_particle(
                px, py, c2_idx, factor, self.intensity * self.color_blend, self.radius
            )
        else:
            color_idx = COLOR_MAP.get(self.target_color, 121)
            draw_baked_particle(px, py, color_idx, factor, self.intensity, self.radius)


class DroneManager:
    def __init__(self):
        self.drones = []
        self.patterns = []
        self.current_index = -1
        self._load_all_patterns()

    def _load_all_patterns(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
        pattern_dir = os.path.join(root_dir, "resource", "drone-pattern")

        if not os.path.exists(pattern_dir):
            print(f"WARNING: Drone pattern directory not found at {pattern_dir}")
            return

        files = sorted([f for f in os.listdir(pattern_dir) if f.endswith(".txt")])
        for f in files:
            filepath = os.path.join(pattern_dir, f)
            with open(filepath, "r", encoding="utf-8") as file:
                grid = [line.rstrip("\r\n") for line in file.readlines()]
                name = "".join(filter(lambda x: not x.isdigit(), f))
                name = name.replace(".txt", "").replace("-", " ").strip().title()
                self.patterns.append({"name": name, "grid": grid})

        print(f"Loaded {len(self.patterns)} drone patterns.")

    def _get_target_coords(self, grid, spacing, altitude):
        coords = []

        # --- NEW: Find the True Bounding Box to guarantee perfect centering ---
        min_c = float("inf")
        max_c = 0
        for row in grid:
            first_char = -1
            last_char = -1
            for col_idx, char in enumerate(row):
                if char.upper() in ASCII_COLOR_MAP:
                    if first_char == -1:
                        first_char = col_idx
                    last_char = col_idx
            if first_char != -1:
                min_c = min(min_c, first_char)
                max_c = max(max_c, last_char)

        # Failsafe if the text file is entirely empty
        if min_c == float("inf"):
            return coords

        # Calculate width based ONLY on the actual drone boundaries
        width = max_c - min_c
        h_spacing = spacing * 0.5
        v_spacing = spacing
        start_x = -(width * h_spacing) / 2
        start_y = altitude * SCALE_Y

        for row_idx, row in enumerate(grid):
            for col_idx, char in enumerate(row):
                char = char.upper()
                if char in ASCII_COLOR_MAP:
                    # Offset by min_c so the visual pattern starts exactly at start_x
                    tx = start_x + ((col_idx - min_c) * h_spacing)
                    ty = start_y + (row_idx * v_spacing)
                    coords.append((tx, ty, 0, ASCII_COLOR_MAP[char]))

        return coords

    def transition_to_pattern(self, index, gui, audio=None):
        if not self.patterns:
            return
        if index < 0 or index >= len(self.patterns):
            return

        if self.current_index == -1 and audio:
            audio.play_music("ablic-theme.mp3")

        self.current_index = index
        target_coords = self._get_target_coords(
            self.patterns[index]["grid"],
            gui.drone_spacing * SCALE_X,
            gui.drone_altitude,
        )

        available_drones = [d for d in self.drones if not d.clearing and d.active]

        for i, (tx, ty, tz, c_name) in enumerate(target_coords):
            if i < len(available_drones):
                available_drones[i].transition_to(
                    tx, ty, tz, c_name, gui.drone_radius, gui.drone_intensity
                )
            else:
                new_drone = Drone(
                    tx,
                    ty,
                    tz,
                    c_name,
                    gui.drone_radius,
                    gui.drone_intensity,
                    spawn_y=1000,
                )
                self.drones.append(new_drone)

        if len(available_drones) > len(target_coords):
            for i in range(len(target_coords), len(available_drones)):
                available_drones[i].clear()

    def next_pattern(self, gui, audio=None):
        if not self.patterns:
            return
        next_idx = (self.current_index + 1) % len(self.patterns)
        self.transition_to_pattern(next_idx, gui, audio)

    def prev_pattern(self, gui, audio=None):
        if not self.patterns:
            return
        prev_idx = (
            0
            if self.current_index == -1
            else (self.current_index - 1) % len(self.patterns)
        )
        self.transition_to_pattern(prev_idx, gui, audio)

    def clear_all(self, audio=None):
        for d in self.drones:
            d.clear()
        self.current_index = -1
        if audio:
            audio.stop_music()

    def update(self):
        for d in self.drones:
            d.update()
        self.drones = [d for d in self.drones if d.active]

    def draw(self):
        for d in self.drones:
            d.draw()

        if self.current_index != -1 and self.patterns:
            name = self.patterns[self.current_index]["name"]
            pyxel.text(10, 10, f"DRONE SHOW: {name}", 121)
