import time
from typing import List
from config import MAX_ENERGY_GAUGE, GeneratorType
from .models import PlayerSession, RankingEntry


class GameState:
    def __init__(self):
        self.current_session: PlayerSession | None = None
        self.rankings: List[RankingEntry] = []
        self.active_generator: GeneratorType | None = None
        self.last_activity_time = time.time()
        self.last_drain_time = time.time()
        self.mock_paused = False

        # Explicit tracker for when each gauge last INCREASED its value
        self._last_gauge_values = {}
        self._last_increase_time = {}
        self.session_count = 0

    def start_new_session(self, player_name: str | None = None):
        self.session_count += 1
        name = player_name if player_name else f"Student {self.session_count}"
        self.current_session = PlayerSession(player_name=name)
        self.current_session.start_time = time.time()
        for gen in GeneratorType:
            self._last_gauge_values[gen] = 0.0
            self._last_increase_time[gen] = time.time()

    def set_active_generator(self, gen_type: GeneratorType | None):
        if self.active_generator != gen_type:
            self.active_generator = gen_type
            self.last_activity_time = time.time()

    def check_inactivity(self):
        current_time = time.time()
        dt = current_time - self.last_drain_time
        self.last_drain_time = current_time

        # 60s inactivity returns to default None (Ablic)
        if (
            self.active_generator is not None
            and (current_time - self.last_activity_time) > 60.0
        ):
            self.active_generator = None

        # Auto drain each gauge after 30s of no increase
        if not self.current_session:
            return

        for gen in GeneratorType:
            current_val = self.current_session.energy_levels.get(gen, 0.0)
            last_known = self._last_gauge_values.get(gen, 0.0)

            if current_val > last_known:
                # Value went up — reset the 30s inactivity clock for this gauge
                self._last_increase_time[gen] = current_time
                self._last_gauge_values[gen] = current_val
            elif current_val < last_known:
                # Value went down (already draining or was drained externally) — just track it
                self._last_gauge_values[gen] = current_val
            # else: value unchanged — do nothing with _last_gauge_values

            # Only drain if gauge is above 0 AND the inactivity timer has started AND 30s have passed
            if gen in self._last_increase_time and current_val > 0.0:
                idle_secs = current_time - self._last_increase_time[gen]
                if idle_secs > 30.0:
                    new_val = max(0.0, current_val - (5.0 * dt))
                    self.current_session.energy_levels[gen] = new_val
                    self._last_gauge_values[gen] = new_val

    def add_energy(self, gen_type, amount: float):
        if not self.current_session:
            return

        # Ensure we only fill if this signal matches the active generator, OR we just fill the active generator
        # Assume we fill the active generator if a clean boost signal comes in
        if self.active_generator is None:
            return

        if self.current_session.completed:
            return

        self.last_activity_time = time.time()
        self.current_session.last_energy_time[self.active_generator] = time.time()

        # Fill the currently selected generator
        self.current_session.energy_levels[self.active_generator] += amount

        # Check if any single gauge has reached the max
        if not self.current_session.completed:
            if any(
                level >= MAX_ENERGY_GAUGE
                for level in self.current_session.energy_levels.values()
            ):
                self.current_session.completed = True
                self.current_session.end_time = time.time()
                self._save_ranking()

    def _save_ranking(self):
        time_taken = self.current_session.end_time - self.current_session.start_time
        entry = RankingEntry(self.current_session.player_name, time_taken)
        self.rankings.append(entry)
        # Sort by fastest time
        self.rankings.sort(key=lambda x: x.time_taken)

    def get_elapsed_time(self) -> float:
        if not self.current_session:
            return 0.0
        if self.current_session.completed:
            return self.current_session.end_time - self.current_session.start_time
        return time.time() - self.current_session.start_time
