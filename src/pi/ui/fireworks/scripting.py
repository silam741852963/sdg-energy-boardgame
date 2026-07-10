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
        
        import random
        
        if is_main_show:
            # Determine show-specific theme
            theme = None
            if "wind" in filename:
                theme = {
                    "name": "wind",
                    "main_color": "red",
                    "colors_in": ["red", "pink", "magenta", "orange"],
                    "colors_out": ["pink", "magenta", "orange", "red"],
                    "allowed_types": ["Tourbillion", "Flying Fish", "Comet", "Pearls", "Crossette", "Strobe", "Peony", "Waterfall", "Dragon Eggs", "Palm Tree", "Chrysanthemum", "Brocade", "Pistil", "Willow"]
                }
            elif "solar" in filename:
                theme = {
                    "name": "solar",
                    "main_color": "violet",
                    "colors_in": ["violet", "indigo", "magenta", "blue"],
                    "colors_out": ["indigo", "magenta", "blue", "violet"],
                    "allowed_types": ["Strobe", "Peony", "Chrysanthemum", "Pistil", "Brocade", "Palm Tree", "Waterfall", "Crossette", "Comet", "Pearls", "Flying Fish", "Tourbillion", "Dragon Eggs", "Willow"]
                }
            elif "piezo" in filename:
                theme = {
                    "name": "piezo",
                    "main_color": "blue",
                    "colors_in": ["blue", "cyan", "indigo", "lime"],
                    "colors_out": ["cyan", "indigo", "lime", "blue"],
                    "allowed_types": ["Crossette", "Dragon Eggs", "Strobe", "Peony", "Chrysanthemum", "Palm Tree", "Tourbillion", "Comet", "Pearls", "Flying Fish", "Waterfall", "Brocade", "Pistil", "Willow"]
                }
            elif "coil" in filename:
                theme = {
                    "name": "coil",
                    "main_color": "orange",
                    "colors_in": ["orange", "yellow", "gold", "red"],
                    "colors_out": ["yellow", "gold", "red", "orange"],
                    "allowed_types": ["Brocade", "Waterfall", "Tourbillion", "Comet", "Pearls", "Strobe", "Dragon Eggs", "Crossette", "Peony", "Chrysanthemum", "Palm Tree", "Flying Fish", "Pistil", "Willow"]
                }

            colors_in = theme["colors_in"]
            colors_out = theme["colors_out"]
            main_color = theme["main_color"]
            allowed_types = theme["allowed_types"]

            # Generate Choreographed Intro Sequence:
            # 1. Sides to Center (0.0 to 2.5s, spaced 0.5s apart)
            left_x_vals = [100, 272, 444, 616, 788, 960]
            right_x_vals = [1820, 1648, 1476, 1304, 1132, 960]
            
            for i in range(6):
                t = i * 0.5
                col = colors_in[i % len(colors_in)]
                if i == 5:
                    events.append({"time": t, "type": "Rising Tail", "color": col, "x": 960, "y": 600})
                else:
                    events.append({"time": t, "type": "Rising Tail", "color": col, "x": left_x_vals[i], "y": 600})
                    events.append({"time": t, "type": "Rising Tail", "color": col, "x": right_x_vals[i], "y": 600})
                    
            # 2. Reverse: Center to Sides (4.0 to 6.5s, spaced 0.5s apart)
            for i in range(6):
                t = 4.0 + i * 0.5
                col = colors_out[i % len(colors_out)]
                if i == 0:
                    events.append({"time": t, "type": "Rising Tail", "color": col, "x": 960, "y": 600})
                else:
                    events.append({"time": t, "type": "Rising Tail", "color": col, "x": left_x_vals[5 - i], "y": 600})
                    events.append({"time": t, "type": "Rising Tail", "color": col, "x": right_x_vals[5 - i], "y": 600})
                    
            # 3. Transition burst (3.25s) - crossover pattern
            events.append({"time": 3.25, "type": allowed_types[0], "color": main_color, "x": 300, "y": 500})
            events.append({"time": 3.25, "type": allowed_types[0], "color": main_color, "x": 1620, "y": 500})
            events.append({"time": 3.25, "type": "Brocade" if "Brocade" in allowed_types else "Peony", "color": colors_in[1 % len(colors_in)], "x": 960, "y": 400})
            
            # Process main show events WITHOUT time shifting
            for ev in original_events:
                original_time = ev.get("time", 0.0)
                shifted_ev = ev.copy()
                shifted_ev["time"] = original_time
                events.append(shifted_ev)
                
                # Clone density: create 2 additional clones that are show-specific
                for _ in range(2):
                    clone = ev.copy()
                    clone["time"] = max(0.0, original_time + random.uniform(-0.6, 0.6))
                    clone["x"] = max(100, min(1820, ev.get("x", 960) + random.randint(-250, 250)))
                    clone["y"] = max(100, min(900, ev.get("y", 600) + random.randint(-150, 150)))
                    
                    if random.random() < 0.5:
                        clone["color"] = random.choice(colors_in)
                    
                    if random.random() < 0.6:
                        # In the latter half (time > 15s), give higher probability of Willow clones
                        if original_time > 15.0 and random.random() < 0.75:
                            clone["type"] = "Willow"
                        else:
                            clone["type"] = random.choice(allowed_types)
                    events.append(clone)
        else:
            # For non-main shows (e.g. success.json), keep original logic
            for ev in original_events:
                events.append(ev)
            
        # 1. Scale event times to make the show 20% faster
        for ev in events:
            if "time" in ev:
                ev["time"] = ev["time"] / 1.2

        # 2. Increase the number of firework launches by 10%
        import random
        num_additional = int(round(len(events) * 0.10))
        if num_additional > 0:
            events_to_clone = random.sample(events, num_additional)
            for ev in events_to_clone:
                clone = ev.copy()
                # Apply a small time offset (e.g. -0.4 to 0.4 seconds)
                clone["time"] = max(0.0, ev.get("time", 0.0) + random.uniform(-0.4, 0.4))
                # Apply a small spatial offset
                clone["x"] = max(100, min(1820, ev.get("x", 960) + random.randint(-150, 150)))
                clone["y"] = max(100, min(900, ev.get("y", 600) + random.randint(-100, 100)))
                events.append(clone)

        # Sort events by time
        events = sorted(events, key=lambda e: e.get("time", 0.0))
        
        self.active_scripts.append({
            "filename": filename,
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
                        spec.base_color = ev.get("color", "red")
                    
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

