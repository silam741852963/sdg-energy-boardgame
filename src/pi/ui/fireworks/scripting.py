import json
import os
import time

from .models import generate_spec


class ScriptManager:
    def __init__(self, firework_manager):
        self.firework_manager = firework_manager
        self.active_scripts = []

    def play_sequence(
        self,
        json_path: str,
        variation: int = 0,
        count_scale: float = 1.0,
        intensity_scale: float = 1.0,
        life_scale: float = 1.0,
    ):
        if not os.path.exists(json_path):
            print(f"Script not found: {json_path}")
            return
        with open(json_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        events = []
        for event in data.get("events", []):
            varied = event.copy()
            # Cell celebrations may mirror their geometry, but always retain the
            # generator's authored palette and cadence.
            if variation == 1 and "x" in varied:
                varied["x"] = 1920 - varied["x"]
            if "particle_count" in varied:
                varied["particle_count"] = max(
                    1,
                    int(varied["particle_count"] * count_scale),
                )
            if "intensity" in varied:
                varied["intensity"] *= intensity_scale
            if "life_span" in varied:
                varied["life_span"] = max(1, int(varied["life_span"] * life_scale))
            events.append(varied)
        self.active_scripts.append(
            {
                "filename": os.path.basename(json_path).lower(),
                "events": sorted(events, key=lambda event: event.get("time", 0.0)),
                "start_time": time.time(),
                "index": 0,
            }
        )

    def update(self):
        current_time = time.time()
        for script in self.active_scripts[:]:
            events = script["events"]
            index = script["index"]
            while index < len(events):
                event = events[index]
                if current_time - script["start_time"] < event.get("time", 0.0):
                    break
                spec = generate_spec(event.get("type", "Peony"))
                for key in (
                    "particle_count",
                    "radius",
                    "gravity_mod",
                    "drag",
                    "life_span",
                    "multicolor",
                    "intensity",
                    "speed_variance",
                ):
                    if key in event:
                        setattr(spec, key, event[key])
                if "color" in event:
                    spec.base_color = event["color"]
                    spec.colors = [event["color"]]
                elif "colors" in event:
                    spec.colors = event["colors"]
                    if spec.colors:
                        spec.base_color = spec.colors[0]
                self.firework_manager.launch(
                    event.get("x", 960),
                    event.get("y", 480),
                    forced_spec=spec,
                )
                index += 1
            script["index"] = index
            if index >= len(events):
                self.active_scripts.remove(script)
