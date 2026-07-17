from dataclasses import dataclass, field
from typing import Dict
from ..config import GeneratorType
import time


@dataclass
class PlayerSession:
    player_name: str
    energy_levels: Dict[GeneratorType, float] = field(default_factory=dict)
    last_energy_time: Dict[GeneratorType, float] = field(default_factory=dict)
    start_time: float = 0.0
    end_time: float = 0.0
    completed: bool = False

    def __post_init__(self):
        for gen_type in GeneratorType:
            self.energy_levels[gen_type] = 0.0
            self.last_energy_time[gen_type] = time.time()

    @property
    def total_energy(self) -> float:
        return sum(self.energy_levels.values())


@dataclass
class RankingEntry:
    player_name: str
    time_taken: float
    generator_type: GeneratorType
    timestamp: float = 0.0


@dataclass(frozen=True)
class RankingResult:
    player_name: str
    run_time: float
    previous_best: float | None
    final_rank: int | None
    kept_run: bool

    @property
    def is_first_result(self) -> bool:
        return self.previous_best is None

    @property
    def is_personal_best(self) -> bool:
        return self.previous_best is not None and self.run_time < self.previous_best

    @property
    def improvement(self) -> float:
        if not self.is_personal_best:
            return 0.0
        return self.previous_best - self.run_time

    @property
    def difference_from_best(self) -> float:
        if self.previous_best is None:
            return 0.0
        return max(0.0, self.run_time - self.previous_best)
