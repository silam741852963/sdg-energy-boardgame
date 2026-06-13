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
        
        for ev in original_events:
            events.append(ev)
            if is_main_show:
                # Spawn 1 extra clone event for each event (doubling the show density)
                for _ in range(1):
                    clone = ev.copy()
                    clone["time"] = max(0.0, ev.get("time", 0.0) + random.uniform(-0.4, 0.4))
                    clone["x"] = max(100, min(1820, ev.get("x", 960) + random.randint(-200, 200)))
                    clone["y"] = max(100, min(900, ev.get("y", 600) + random.randint(-120, 120)))
                    # 40% chance to cycle to a new random color for more variety
                    if random.random() < 0.4:
                        clone["color"] = random.choice(COLORS)
                    events.append(clone)
            
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
