import os
import json
import math
import random
from .config import SCALE_X, SCALE_Y, COLOR_MAP
from .physics import project_3d_to_2d
from . import palette

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
        self.activated = False

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
        self.activated = False

        self.speed = random.uniform(0.02, 0.024)

    def clear(self):
        if not self.clearing:
            self.clearing = True

            self.tx += random.uniform(-200, 200)
            self.ty -= random.uniform(1500, 2500)
            self.tz += random.uniform(-100, 100)

            self.speed = random.uniform(0.003, 0.01)

    def update(self, frame_count):
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
                if self.activated:
                    self.x += math.sin(frame_count * 0.15 + self.wobble_offset) * 0.6
                    self.y += math.cos(frame_count * 0.12 + self.wobble_offset) * 0.6 - 0.5
                else:
                    self.x += math.sin(frame_count * 0.05 + self.wobble_offset) * 0.3
                    self.y += math.cos(frame_count * 0.04 + self.wobble_offset) * 0.3
        else:
            self.intensity *= 0.99

            if self.intensity < 0.02 or self.y < -1500:
                self.active = False

    def gather_instances(self, instance_data, frame_count):
        if not self.active:
            return
        px, py, factor = project_3d_to_2d(self.x, self.y, self.z)
        if factor <= 0:
            return

        # Determine if we should pulse the glow
        draw_intensity = self.intensity
        if self.activated:
            draw_intensity *= (1.5 + 0.5 * math.sin(frame_count * 0.2 + self.wobble_offset))

        # Balance visual sizes between glowing and non-glowing drones
        size_factor = 21.0 if self.activated else 19.0
        min_size = 7.0 if self.activated else 6.5

        # Compress the radius range to narrow size difference visually (e.g. 1.0 -> 1.5, 4.5 -> 2.55)
        visual_radius = 1.5 + (self.radius - 1.0) * 0.3

        if self.color_blend < 1.0:
            c1_idx = COLOR_MAP.get(self.prev_color, 121)
            c1 = palette.get_color(c1_idx)
            size1 = max(min_size, factor * visual_radius * size_factor)
            alpha1 = draw_intensity * (1.0 - self.color_blend)
            instance_data.append((px, py, size1, c1[0], c1[1], c1[2], alpha1))

            c2_idx = COLOR_MAP.get(self.target_color, 121)
            c2 = palette.get_color(c2_idx)
            size2 = max(min_size, factor * visual_radius * size_factor)
            alpha2 = draw_intensity * self.color_blend
            instance_data.append((px, py, size2, c2[0], c2[1], c2[2], alpha2))
        else:
            color_idx = COLOR_MAP.get(self.target_color, 121)
            c = palette.get_color(color_idx)
            size = max(min_size, factor * visual_radius * size_factor)
            instance_data.append((px, py, size, c[0], c[1], c[2], draw_intensity))


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
                lines = [line.rstrip("\r\n") for line in file.readlines()]
                
                config = {}
                grid = lines
                
                try:
                    split_idx = lines.index("===")
                    json_str = "\n".join(lines[:split_idx])
                    config = json.loads(json_str)
                    grid = lines[split_idx+1:]
                except ValueError:
                    pass
                except json.JSONDecodeError as e:
                    print(f"WARNING: Invalid JSON frontmatter in {f}: {e}")
                    pass

                name = "".join(filter(lambda x: not x.isdigit(), f))
                name = name.replace(".txt", "").replace("-", " ").strip().title()
                self.patterns.append({"name": name, "grid": grid, "config": config})

        print(f"Loaded {len(self.patterns)} drone patterns.")

    def _get_target_coords(self, grid, config, default_spacing, default_altitude):
        coords = []
        
        spacing = config.get("spacing", default_spacing)
        altitude = config.get("altitude", default_altitude)
        legend = config.get("legend", {})

        # --- NEW: Find the True Bounding Box to guarantee perfect centering ---
        min_c = float("inf")
        max_c = 0
        for row in grid:
            first_char = -1
            last_char = -1
            for col_idx, char in enumerate(row):
                if char in legend or char.upper() in ASCII_COLOR_MAP:
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
                if char in legend or char.upper() in ASCII_COLOR_MAP:
                    # Offset by min_c so the visual pattern starts exactly at start_x
                    tx = start_x + ((col_idx - min_c) * h_spacing)
                    ty = start_y + (row_idx * v_spacing)
                    
                    props = {}
                    if char in legend:
                        props = legend[char]
                    else:
                        props = {"color": ASCII_COLOR_MAP[char.upper()]}
                        
                    coords.append({
                        "x": tx,
                        "y": ty,
                        "z": props.get("z", 0),
                        "color": props.get("color", "silver"),
                        "radius": props.get("radius", None),
                        "intensity": props.get("intensity", None)
                    })

        return coords

    def transition_to_pattern(self, index, gui, audio=None, override_color=None):
        if not self.patterns:
            return
        if index < 0 or index >= len(self.patterns):
            return

        if self.current_index == -1 and audio:
            audio.play_music("ablic-theme.wav")

        self.current_index = index
        target_coords = self._get_target_coords(
            self.patterns[index]["grid"],
            self.patterns[index].get("config", {}),
            gui.drone_spacing * SCALE_X,
            gui.drone_altitude,
        )

        available_drones = [d for d in self.drones if not d.clearing and d.active]

        for i, target in enumerate(target_coords):
            tx, ty, tz = target["x"], target["y"], target["z"]
            c_name = override_color if override_color is not None else target["color"]
            radius = target["radius"] if target["radius"] is not None else gui.drone_radius
            intensity = target["intensity"] if target["intensity"] is not None else gui.drone_intensity
            
            if i < len(available_drones):
                available_drones[i].transition_to(
                    tx, ty, tz, c_name, radius, intensity
                )
            else:
                new_drone = Drone(
                    tx,
                    ty,
                    tz,
                    c_name,
                    radius,
                    intensity,
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

    def update(self, frame_count, fill_pct=0.0):
        # The Ablic logo (index 0) should be fully colored from the beginning
        if self.current_index == 0:
            fill_pct = 1.0
            
        # Determine activation threshold based on x coordinates
        if self.drones and fill_pct > 0.0:
            min_tx = float('inf')
            max_tx = float('-inf')
            for d in self.drones:
                if not d.clearing and d.active:
                    if d.tx < min_tx:
                        min_tx = d.tx
                    if d.tx > max_tx:
                        max_tx = d.tx
            
            if min_tx != float('inf'):
                threshold_x = min_tx + (max_tx - min_tx) * fill_pct
                for d in self.drones:
                    if not d.clearing and d.active:
                        d.activated = d.tx <= threshold_x

        # Update drones and cull dead ones in-place
        alive_count = 0
        for d in self.drones:
            d.update(frame_count)
            if d.active:
                self.drones[alive_count] = d
                alive_count += 1
        del self.drones[alive_count:]

    def draw(self, renderer, font, frame_count):
        instance_data = []
        for d in self.drones:
            d.gather_instances(instance_data, frame_count)
        renderer.draw_particles(instance_data)

        if self.current_index != -1 and self.patterns:
            name = self.patterns[self.current_index]["name"]
            c = palette.get_color(121)
            renderer.draw_text(int(20 * SCALE_X), int(20 * SCALE_Y), f"DRONE SHOW: {name}", font, c)
