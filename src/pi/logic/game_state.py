import time
from typing import List
from config import MAX_ENERGY_GAUGE
from .models import PlayerSession, RankingEntry


class GameState:
    def __init__(self):
        self.current_session: PlayerSession | None = None
        self.rankings: List[RankingEntry] = []

    def start_new_session(self, player_name: str):
        self.current_session = PlayerSession(player_name=player_name)
        self.current_session.start_time = time.time()

    def add_energy(self, gen_type, amount: float):
        if not self.current_session or self.current_session.completed:
            return

        self.current_session.energy_levels[gen_type] += amount

        if self.current_session.total_energy >= MAX_ENERGY_GAUGE:
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
