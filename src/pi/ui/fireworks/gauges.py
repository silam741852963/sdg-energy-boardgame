import pyxel
from .config import SCREEN_WIDTH, SCREEN_HEIGHT, SCALE_X, SCALE_Y
from config import GeneratorType, MAX_ENERGY_GAUGE

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
            GeneratorType.COIL: 71     # Blue (or Red, let's use Blue)
        }
        
        # Current animated state per generator: {gen: {"x": 0, "scale": 1.0, "alpha": 1.0}}
        self.state = {}
        for gen in self.generators:
            self.state[gen] = {"y": SCREEN_HEIGHT / 2, "scale": 0.5, "dim": True}

        self.char_cache = {}

    def get_char_pixels(self, char, color):
        cache_key = (char, color)
        if cache_key not in self.char_cache:
            pyxel.images[2].rect(0, 0, 4, 6, 0)
            pyxel.images[2].text(0, 0, char, color)
            pixels = []
            for j in range(6):
                for i in range(4):
                    if pyxel.images[2].pget(i, j) == color:
                        pixels.append((i, j))
            self.char_cache[cache_key] = pixels
        return self.char_cache[cache_key]

    def draw_text_scaled(self, x, y, text, color, scale):
        scale = max(1, int(scale))
        for idx, char in enumerate(text):
            char_pixels = self.get_char_pixels(char, color)
            char_x = x + idx * 4 * scale
            for dx, dy in char_pixels:
                pyxel.rect(
                    char_x + dx * scale,
                    y + dy * scale,
                    scale,
                    scale,
                    color,
                )

    def update(self):
        if not self.game_state:
            return

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
            
            # Vertical cylinder math:
            # Active is at dist=0 -> center y.
            # dist = 1 -> bottom (unselected), dist = -1 -> top (unselected)
            # dist = 2 or -2 -> hidden behind
            
            # Keep all 3 cleanly on the screen
            base_y = SCREEN_HEIGHT - (110 * SCALE_Y)
            target_y = base_y + (dist * 75 * SCALE_Y)
            
            # Hide the 4th one (dist == 2 or -2)
            if abs(dist) >= 2:
                target_scale = 0.0
            else:
                target_scale = 1.0 if dist == 0 else 0.5
                
            target_dim = dist != 0
            
            self.state[gen]["y"] += (target_y - self.state[gen]["y"]) * 0.1
            self.state[gen]["scale"] += (target_scale - self.state[gen]["scale"]) * 0.1
            self.state[gen]["dim"] = target_dim

    def draw(self):
        if not self.game_state or not self.game_state.current_session:
            return
            
        levels = self.game_state.current_session.energy_levels
        
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
                
                border_col = 123 if st["dim"] else 121
                fill_col = self.colors[gen]
                
                # Draw outer glow / shadow
                if not st["dim"]:
                    pyxel.rectb(int(x-1), int(y-1), int(w+2), int(h+2), fill_col)
                
                # Draw border
                pyxel.rectb(int(x), int(y), int(w), int(h), border_col)
                pyxel.rect(int(x+1), int(y+1), int(w-2), int(h-2), 0) # clear background
                
                # Draw fill
                fill_pct = min(1.0, levels.get(gen, 0.0) / MAX_ENERGY_GAUGE)
                if fill_pct > 0:
                    pyxel.rect(int(x + 2), int(y + 2), int((w - 4) * fill_pct), int(h - 4), fill_col)
                
                # Draw label
                text = f"{gen.name} - {int(fill_pct*100)}%"
                text_col = 122 if st["dim"] else 7
                
                # Draw text above the gauge (significantly larger)
                text_scale = st["scale"] * 3.0
                self.draw_text_scaled(x + 10 * SCALE_X, y - 25 * SCALE_Y * st["scale"], text, text_col, text_scale)
