import json
import os
import time
from .models import generate_spec

class ScriptManager:
    def __init__(self, firework_manager):
        self.firework_manager = firework_manager
        self.active_scripts = [] # List of {"events": [...], "start_time": float, "index": int}

    def play_sequence(self, json_path: str):
        if not os.path.exists(json_path):
            print(f"Script not found: {json_path}")
            return
            
        with open(json_path, 'r') as f:
            data = json.load(f)
            
        original_events = data.get("events", [])
        events = []
        
        # Check if this is one of the 4 main shows (wind, solar, piezo, coil)
        filename = os.path.basename(json_path).lower()
        is_main_show = any(name in filename for name in ["wind", "solar", "piezo", "coil"])
        
        from .config import COLORS
        import random
        
        if is_main_show:
            # Generate Choreographed Intro Sequence:
            # 1. Sides to Center (0.0 to 5.0s, spaced 1.0s apart)
            left_x_vals = [100, 272, 444, 616, 788, 960]
            right_x_vals = [1820, 1648, 1476, 1304, 1132, 960]
            colors_in = ["red", "orange", "gold", "lime", "cyan", "blue"]
            colors_out = ["magenta", "pink", "violet", "indigo", "lime", "green"]
            
            for i in range(6):
                t = i * 1.0
                col = colors_in[i % len(colors_in)]
                if i == 5:
                    events.append({"time": t, "type": "Rising Tail", "color": col, "x": 960, "y": 600})
                else:
                    events.append({"time": t, "type": "Rising Tail", "color": col, "x": left_x_vals[i], "y": 600})
                    events.append({"time": t, "type": "Rising Tail", "color": col, "x": right_x_vals[i], "y": 600})
                    
            # 2. Reverse: Center to Sides (8.0 to 13.0s, spaced 1.0s apart)
            for i in range(6):
                t = 8.0 + i * 1.0
                col = colors_out[i % len(colors_out)]
                if i == 0:
                    events.append({"time": t, "type": "Rising Tail", "color": col, "x": 960, "y": 600})
                else:
                    events.append({"time": t, "type": "Rising Tail", "color": col, "x": left_x_vals[5 - i], "y": 600})
                    events.append({"time": t, "type": "Rising Tail", "color": col, "x": right_x_vals[5 - i], "y": 600})
                    
            # 3. Transition burst (6.5s) - crossover pattern
            events.append({"time": 6.5, "type": "Tourbillion", "color": "cyan", "x": 300, "y": 500})
            events.append({"time": 6.5, "type": "Tourbillion", "color": "cyan", "x": 1620, "y": 500})
            events.append({"time": 6.5, "type": "Brocade", "color": "gold", "x": 960, "y": 400})
            
            # Process main show events WITHOUT time shifting
            for ev in original_events:
                original_time = ev.get("time", 0.0)
                shifted_ev = ev.copy()
                shifted_ev["time"] = original_time
                events.append(shifted_ev)
                
                for _ in range(3):
                    clone = ev.copy()
                    clone["time"] = max(0.0, original_time + random.uniform(-0.6, 0.6))
                    clone["x"] = max(100, min(1820, ev.get("x", 960) + random.randint(-250, 250)))
                    clone["y"] = max(100, min(900, ev.get("y", 600) + random.randint(-150, 150)))
                    
                    if random.random() < 0.4:
                        clone["color"] = random.choice(COLORS)
                    if random.random() < 0.5:
                        clone["type"] = random.choice([
                            "Tourbillion", "Flying Fish", "Crossette", 
                            "Dragon Eggs", "Strobe", "Waterfall", "Brocade"
                        ])
                    events.append(clone)
        else:
            # For non-main shows (e.g. success.json), keep original logic
            for ev in original_events:
                events.append(ev)
            
        # Sort events by time
        events = sorted(events, key=lambda e: e.get("time", 0.0))
        
        self.active_scripts.append({
            "events": events,
            "start_time": time.time(),
            "index": 0
        })

    def update(self):
        current_time = time.time()
        
        for script in self.active_scripts[:]:
            events = script["events"]
            start_time = script["start_time"]
            idx = script["index"]
            
            # Play all events whose time has passed
            while idx < len(events):
                ev = events[idx]
                if current_time - start_time >= ev["time"]:
                    # Trigger this event
                    spec = generate_spec(ev.get("type", "Peony"))
                    spec.base_color = ev.get("color", "red")
                    
                    self.firework_manager.launch(
                        ev.get("x", 960),
                        ev.get("y", 1080),
                        forced_spec=spec
                    )
                    idx += 1
                else:
                    break
                    
            script["index"] = idx
            
            # Remove script if completed
            if idx >= len(events):
                self.active_scripts.remove(script)
