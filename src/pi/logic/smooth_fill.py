import time
from ..config import GeneratorType

class SmoothFiller:
    def __init__(self, game_state):
        self.game_state = game_state
        # List of active fill operations
        # Each is a dict: {"gen": GeneratorType, "total": float, "added": float, "duration": float, "start": float}
        self.active_fills = []

    def add_fill_request(self, gen_type: GeneratorType, amount: float, duration: float = 0.3):
        self.active_fills.append({
            "gen": gen_type,
            "total": amount,
            "added": 0.0,
            "duration": duration,
            "start": time.time()
        })

    def cancel_fills_for_generator(self, gen_type: GeneratorType):
        self.active_fills = [fill for fill in self.active_fills if fill["gen"] != gen_type]

    def update(self):
        if not self.game_state or not self.game_state.current_session:
            self.active_fills.clear()
            return

        session = self.game_state.current_session
        if session.completed or session.launch_committed:
            self.active_fills.clear()
            return

        current_time = time.time()
        new_active_fills = []

        for fill in self.active_fills:
            gen = fill["gen"]
            total = fill["total"]
            added = fill["added"]
            duration = fill["duration"]
            start_time = fill["start"]

            remaining = total - added
            elapsed = current_time - start_time
            
            if elapsed >= duration or remaining <= 0.0:
                to_add = remaining
                is_done = True
            else:
                target_accum = min(total, total * (elapsed / duration))
                to_add = max(0.0, target_accum - added)
                is_done = (elapsed >= duration)

            if to_add > 0.0:
                self.game_state._apply_energy_delta_locked(gen, to_add)
                fill["added"] += to_add

            if not is_done and not session.completed and not session.launch_committed:
                new_active_fills.append(fill)

        self.active_fills = new_active_fills
