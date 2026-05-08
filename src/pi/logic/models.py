from dataclasses import dataclass, field
from typing import Dict
from config import GeneratorType


@dataclass
class PlayerSession:
    player_name: str
    energy_levels: Dict[GeneratorType, float] = field(default_factory=dict)
    start_time: float = 0.0
    end_time: float = 0.0
    completed: bool = False

    def __post_init__(self):
        for gen_type in GeneratorType:
            self.energy_levels[gen_type] = 0.0

    @property
    def total_energy(self) -> float:
        return sum(self.energy_levels.values())


@dataclass
class RankingEntry:
    player_name: str
    time_taken: float
