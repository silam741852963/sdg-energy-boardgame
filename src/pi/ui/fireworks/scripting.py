import json
import os
import time
from .models import generate_spec

class ScriptManager:
    def __init__(self, firework_manager, action_handler=None):
        self.firework_manager = firework_manager
        self.action_handler = action_handler
        self.active_scripts = [] # List of {"events": [...], "start_time": float, "index": int}

    def play_sequence(self, json_path: str, variation: int = 0):
        if not os.path.exists(json_path):
            print(f"Script not found: {json_path}")
            return
            
        with open(json_path, 'r') as f:
            data = json.load(f)
            
        original_events = data.get("events", [])
        events = []
        
        filename = os.path.basename(json_path).lower()
        
        # Keep the authored events intact, then apply one constrained variation.
        # 0 original, 1 mirrored, 2 faster cadence, 3 palette rotation.
        palette_rotation = {
            "red": "gold", "orange": "pink", "gold": "cyan",
            "yellow": "magenta", "lime": "cyan", "green": "gold",
            "cyan": "violet", "blue": "pink", "indigo": "gold",
            "violet": "cyan", "magenta": "orange", "pink": "yellow",
            "silver": "gold",
        }
        for ev in original_events:
            varied = ev.copy()
            if variation == 1 and "x" in varied:
                varied["x"] = 1920 - varied["x"]
            elif variation == 2:
                varied["time"] = round(varied.get("time", 0.0) * 0.88, 3)
            elif variation == 3:
                if "color" in varied:
                    varied["color"] = palette_rotation.get(varied["color"], varied["color"])
                if "colors" in varied:
                    varied["colors"] = [palette_rotation.get(c, c) for c in varied["colors"]]
            events.append(varied)

        # Sort events by time
        events = sorted(events, key=lambda e: e.get("time", 0.0))
        
        self.active_scripts.append({
            "filename": filename,
            "variation": variation,
            "events": events,
            "start_time": time.time(),
            "index": 0
        })

    def update(self, love_mode_active=False):
        current_time = time.time()
        import random
        
        for script in self.active_scripts[:]:
            events = script["events"]
            start_time = script["start_time"]
            idx = script["index"]
            
            # Play all events whose time has passed
            while idx < len(events):
                ev = events[idx]
                if current_time - start_time >= ev["time"]:
                    if "action" in ev:
                        if self.action_handler:
                            self.action_handler(ev["action"], ev)
                        idx += 1
                        continue
                    # Trigger this event
                    fw_type = ev.get("type", "Peony")
                    if love_mode_active:
                        if not fw_type.startswith("Heart") and fw_type != "Orange_Fruit":
                            if fw_type in ("Brocade", "Willow"):
                                fw_type = "Heart_Brocade"
                            elif fw_type in ("Strobe", "Pearls"):
                                fw_type = "Heart_Strobe"
                            elif fw_type in ("Dragon Eggs", "Crossette"):
                                fw_type = "Heart_Crackle"
                            else:
                                fw_type = "Heart"
                                
                    spec = generate_spec(fw_type)
                    
                    # Apply custom parameters from the script event to give the firework more personality
                    for key in ["particle_count", "radius", "gravity_mod", "drag", "life_span", "multicolor", "intensity", "speed_variance"]:
                        if key in ev:
                            setattr(spec, key, ev[key])
                    
                    if love_mode_active:
                        filename = os.path.basename(script.get("filename", "")).lower() if "filename" in script else ""
                        # Fallback check if filename is not directly stored in script dict
                        if not filename and "events" in script:
                            # We can also check active script paths or set filename during play_sequence
                            filename = getattr(self, "_current_playing_filename", "")
                        
                        is_schneider_show = "schneider" in filename
                        if is_schneider_show and fw_type != "Orange_Fruit":
                            spec.base_color = "red"
                            spec.colors = ["red"]
                        elif fw_type == "Orange_Fruit":
                            # Maintain the natural orange fruit specs
                            spec.base_color = "orange"
                            spec.colors = ["orange"]
                        else:
                            colors_list = ["pink", "magenta", "red", "gold"]
                            fw_color = random.choice(colors_list)
                            spec.base_color = fw_color
                            spec.colors = [fw_color]
                    else:
                        if "color" in ev:
                            spec.base_color = ev["color"]
                            spec.colors = [ev["color"]]
                        elif "colors" in ev:
                            spec.colors = ev["colors"]
                            if len(spec.colors) > 0:
                                spec.base_color = spec.colors[0]
                        else:
                            spec.base_color = "red"
                    
                    self.firework_manager.launch(
                        ev.get("x", 960),
                        ev.get("y", 1080),
                        forced_spec=spec
                    )
                    
                    # Launch an extra heart firework at an offset position for double the hearts!
                    if love_mode_active:
                        colors_list = ["pink", "magenta", "red", "gold"]
                        extra_spec = generate_spec("Heart")
                        
                        filename = os.path.basename(script.get("filename", "")).lower() if "filename" in script else ""
                        if not filename and "events" in script:
                            filename = getattr(self, "_current_playing_filename", "")
                        is_schneider_show = "schneider" in filename
                        if is_schneider_show:
                            extra_color = "red"
                        else:
                            extra_color = random.choice(colors_list)
                            
                        extra_spec.base_color = extra_color
                        extra_spec.colors = [extra_color]
                        self.firework_manager.launch(
                            ev.get("x", 960) + random.randint(-150, 150),
                            ev.get("y", 1080) - random.randint(50, 150),
                            forced_spec=extra_spec
                        )
                        
                    idx += 1
                else:
                    break
                    
            script["index"] = idx
            
            # Remove script if completed
            if idx >= len(events):
                self.active_scripts.remove(script)
