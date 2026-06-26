import random
from .config import SCREEN_WIDTH, SCREEN_HEIGHT, SCALE_X, SCALE_Y
from config import GeneratorType, MAX_ENERGY_GAUGE
from . import palette

class GaugeManager:
    def __init__(self, game_state=None):
        self.game_state = game_state
        self.generators = [
            GeneratorType.WIND,
            GeneratorType.SOLAR,
            GeneratorType.PIEZO,
            GeneratorType.COIL
        ]
        
        # Color mapping for gauges matching drones
        self.colors = {
            GeneratorType.WIND: 61,    # Cyan
            GeneratorType.SOLAR: 31,   # Yellow
            GeneratorType.PIEZO: 11,   # Orange
            GeneratorType.COIL: 71     # Blue
        }
        
        # Current animated state per generator: {gen: {"y": 0, "scale": 1.0, "alpha": 1.0}}
        self.state = {}
        for gen in self.generators:
            self.state[gen] = {"y": SCREEN_HEIGHT / 2, "scale": 0.5, "dim": True, "level": 0.0}

    def update(self):
        if not self.game_state:
            return

        # Smoothly animate energy level transitions
        levels = self.game_state.current_session.energy_levels if self.game_state.current_session else {}
        for gen in self.generators:
            target_level = levels.get(gen, 0.0)
            diff = target_level - self.state[gen]["level"]
            if abs(diff) < 0.1:
                self.state[gen]["level"] = target_level
            else:
                self.state[gen]["level"] += diff * 0.1

        active_gen = self.game_state.active_generator
        
        if active_gen is None:
            for gen in self.generators:
                self.state[gen]["scale"] += (0.0 - self.state[gen]["scale"]) * 0.1
            return
            
        active_idx = self.generators.index(active_gen)
        
        for i, gen in enumerate(self.generators):
            dist = i - active_idx
            if dist > 2: dist -= 4
            if dist < -2: dist += 4
            
            base_y = SCREEN_HEIGHT - (110 * SCALE_Y)
            target_y = base_y + (dist * 75 * SCALE_Y)
            
            target_scale = 1.0 if dist == 0 else 0.0
            target_dim = dist != 0
            
            self.state[gen]["y"] += (target_y - self.state[gen]["y"]) * 0.1
            self.state[gen]["scale"] += (target_scale - self.state[gen]["scale"]) * 0.1
            self.state[gen]["dim"] = target_dim

    def draw(self, renderer, fonts, frame_count):
        if not self.game_state or not self.game_state.current_session:
            return
            
        # Set blend mode to alpha for UI layout
        renderer.set_blend_mode("alpha")
        
        # Draw background gauges first, then foreground
        for pass_num in [0, 1]:
            for gen in self.generators:
                st = self.state[gen]
                if st["scale"] < 0.1:
                    continue
                    
                is_foreground = (st["scale"] > 0.8)
                if (pass_num == 0 and is_foreground) or (pass_num == 1 and not is_foreground):
                    continue
                    
                w = 1200 * SCALE_X * st["scale"]
                h = 60 * SCALE_Y * st["scale"]
                
                x = (SCREEN_WIDTH / 2) - (w / 2)
                y = st["y"] - (h / 2)
                
                border_col_idx = 123 if st["dim"] else 121
                fill_col_idx = self.colors[gen]
                
                fill_pct = min(1.0, st["level"] / MAX_ENERGY_GAUGE)

                # Add vibration and flashing effect when full
                is_full = fill_pct >= 1.0
                if is_full:
                    x += random.randint(-3, 3)
                    y += random.randint(-3, 3)
                    if (frame_count % 10) < 5:
                        fill_col_idx = self.colors[gen] + 5  # Use pastel variant of the main color
                        border_col_idx = fill_col_idx

                # Draw outer glow / shadow
                if not st["dim"] or is_full:
                    # Renders a slightly larger outline in main/pastel color
                    outer_col = palette.get_color(fill_col_idx)
                    renderer.draw_rect(x-1, y-1, w+2, h+2, outer_col, fill=False)
                
                # Draw border
                border_col = palette.get_color(border_col_idx)
                renderer.draw_rect(x, y, w, h, border_col, fill=False)
                
                # Clear background (draw black rectangle inside)
                renderer.draw_rect(x+1, y+1, w-2, h-2, (0.0, 0.0, 0.0, 1.0), fill=True)
                
                # Draw fill
                if fill_pct > 0:
                    fill_col = palette.get_color(fill_col_idx)
                    renderer.draw_rect(x + 2, y + 2, (w - 4) * fill_pct, h - 4, fill_col, fill=True)
                
                # Draw label
                text = f"{gen.name} - {int(fill_pct*100)}%"
                text_col_idx = 122 if st["dim"] and not is_full else 121
                if is_full and (frame_count % 10) < 5:
                    text_col_idx = self.colors[gen] + 5 # Flash pastel variant

                text_col = palette.get_color(text_col_idx)
                
                # Select font size based on scale
                if st["scale"] > 0.8:
                    font = fonts["large"]
                    text_y = y - 48 * SCALE_Y
                else:
                    font = fonts["small"]
                    text_y = y - 30 * SCALE_Y
                
                renderer.draw_text(x + 10 * SCALE_X, text_y, text, font, text_col)
                
        # Reset blend mode back to additive for particles
        renderer.set_blend_mode("additive")
