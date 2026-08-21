import time
import os
import json
import math
import threading
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Dict

from ..config import (
    LAUNCH_CONTINUE_SECONDS,
    MAX_ENERGY_GAUGE,
    RANKINGS_ENABLED,
    GeneratorType,
)
from .models import PlayerSession, RankingEntry, RankingResult
from .smooth_fill import SmoothFiller


class MissionEventKind(Enum):
    CELL_FILLED = auto()
    LAUNCH_COMMITTED = auto()


@dataclass(frozen=True)
class MissionEvent:
    kind: MissionEventKind
    generator: GeneratorType | None = None
    generators: tuple[GeneratorType, ...] = ()


@dataclass(frozen=True)
class GameSnapshot:
    selected_generators: tuple[GeneratorType, ...]
    present_sensors: tuple[GeneratorType, ...]
    energy_levels: Dict[GeneratorType, float]
    filled_generators: frozenset[GeneratorType]
    launch_generators: tuple[GeneratorType, ...]
    launch_ready: bool
    launch_wait_remaining: float
    launch_committed: bool
    completed: bool


class GameState:
    def __init__(
        self,
        rankings_enabled: bool = RANKINGS_ENABLED,
        launch_wait_seconds: float = LAUNCH_CONTINUE_SECONDS,
        mission_clock=None,
    ):
        self._lock = threading.RLock()
        self.current_session: PlayerSession | None = None
        self.rankings: Dict[GeneratorType, List[RankingEntry]] = {gen: [] for gen in GeneratorType}
        self.rankings_enabled = rankings_enabled
        # Compatibility for the dormant ranking implementation. Gameplay must
        # use selected_generators and never collapse the battery to this value.
        self.active_generator: GeneratorType | None = None
        self.selected_generators: list[GeneratorType] = []
        self.active_sensors: list[GeneratorType] = []
        self.filled_generators: set[GeneratorType] = set()
        self._sensor_rearm_blocked: set[GeneratorType] = set()
        self._mission_events: deque[MissionEvent] = deque()
        self.launch_wait_seconds = max(0.0, float(launch_wait_seconds))
        self._mission_clock = mission_clock or time.monotonic
        self._launch_deadline: float | None = None
        self.last_activity_time = time.time()
        self.mock_paused = False
        self.session_count = 0
        self.clean_boost_signals = []
        self.current_ranking_entry: RankingEntry | None = None
        self.last_ranking_result: RankingResult | None = None
        self._rankings_storage_safe = True
        self._players_storage_safe = True

        self.smooth_filler = SmoothFiller(self)
        if self.rankings_enabled:
            self.load_rankings()

    def start_new_session(self, player_name: str | None = None):
        # A completed run is provisional until its player name is confirmed.
        # Never let an abandoned provisional entry leak into the next session.
        if self.current_ranking_entry is not None:
            self.discard_current_ranking()
        self.session_count += 1
        name = self.normalize_player_name(player_name)
        if not name:
            existing_names = {
                self.normalize_player_name(entry.player_name).casefold()
                for entries in self.rankings.values()
                for entry in entries
            }
            name = f"Player {self.session_count}"
            while name.casefold() in existing_names:
                self.session_count += 1
                name = f"Player {self.session_count}"
        self.current_session = PlayerSession(player_name=name)
        self.current_session.start_time = 0.0
        self.current_ranking_entry = None
        self.last_ranking_result = None
        if not hasattr(self, "selected_generators"):
            self.selected_generators = []
        if not hasattr(self, "active_sensors"):
            self.active_sensors = []
        if not hasattr(self, "filled_generators"):
            self.filled_generators = set()
        if not hasattr(self, "_mission_events"):
            self._mission_events = deque()
        if not hasattr(self, "_sensor_rearm_blocked"):
            self._sensor_rearm_blocked = set()
        self.selected_generators.clear()
        self.active_sensors.clear()
        self.filled_generators.clear()
        self._sensor_rearm_blocked.clear()
        self._mission_events.clear()
        self._launch_deadline = None
        self.active_generator = None
        self.smooth_filler.active_fills.clear()

    def set_active_generator(self, gen_type: GeneratorType | None):
        """Legacy single-selector adapter used by old ranking/debug callers."""
        self.set_active_sensors([gen_type] if gen_type else [])

    def set_active_sensors(self, sensors: List[GeneratorType]):
        with self._lock:
            unique = []
            for generator in sensors:
                if isinstance(generator, GeneratorType) and generator not in unique:
                    unique.append(generator)
            self.active_sensors = unique
            self.last_activity_time = time.time()

            # Sensors held through an automatic reset must first go low. This
            # prevents an old battery from selecting itself again while allowing
            # every new Hall edge to respond immediately at the attract screen.
            self._sensor_rearm_blocked.intersection_update(unique)
            eligible = [
                generator
                for generator in unique
                if generator not in self._sensor_rearm_blocked
            ]

            session = self.current_session
            if not session or session.launch_committed:
                return

            # One magnet moves between generators. A completed cell becomes a
            # reserved battery cell and survives removal; an unfinished cell is
            # still cancelled so partially charged energy cannot be banked.
            removed = [
                generator
                for generator in self.selected_generators
                if generator not in eligible
                and generator not in self.filled_generators
            ]
            for generator in removed:
                session.energy_levels[generator] = 0.0
                self.filled_generators.discard(generator)
                self.smooth_filler.cancel_fills_for_generator(generator)

            kept = [
                generator
                for generator in self.selected_generators
                if generator in eligible or generator in self.filled_generators
            ]
            added = [generator for generator in eligible if generator not in kept]
            self.selected_generators = kept + added
            self.active_generator = eligible[0] if eligible else None

            if self.selected_generators and session.start_time == 0.0:
                session.start_time = time.time()
            elif not self.selected_generators:
                session.start_time = 0.0
                for generator in GeneratorType:
                    session.energy_levels[generator] = 0.0
                self.filled_generators.clear()
                self.smooth_filler.active_fills.clear()

            self._evaluate_launch_locked()

    def check_inactivity(self):
        # Engine tick hook: energy never drains and selectors never expire, but
        # a ready battery's visible continuation deadline must advance.
        with self._lock:
            self.smooth_filler.update()
            self._evaluate_launch_locked()

    def force_immediate_drain(self, gen_type):
        # Dormant ranking UI compatibility. Draining is disabled by design.
        return

    def add_energy(
        self, gen_type, amount: float, is_clean_boost: bool = False, smooth: bool = True
    ):
        with self._lock:
            if not self.current_session:
                return
            if (
                gen_type not in self.selected_generators
                or self.current_session.launch_committed
                or self.current_session.completed
            ):
                return

        from ..config import CLEANBOOST_TEST_MODE, ENERGY_PER_BEACON_BY_TYPE

        # In test mode, only clean boost signals can add energy
        if CLEANBOOST_TEST_MODE and not is_clean_boost:
            return

        # Determine the amount of energy to add
        if CLEANBOOST_TEST_MODE:
            from ..config import ENERGY_PER_BEACON

            if amount != ENERGY_PER_BEACON:
                fill_amount = amount
            else:
                fill_amount = ENERGY_PER_BEACON_BY_TYPE.get(gen_type, amount)
        else:
            fill_amount = amount

        with self._lock:
            if (
                not self.current_session
                or gen_type not in self.selected_generators
                or self.current_session.launch_committed
                or self.current_session.completed
            ):
                return
            if CLEANBOOST_TEST_MODE and is_clean_boost:
                self._log_clean_boost_signal(gen_type, fill_amount)

            self.last_activity_time = time.time()
            self.current_session.last_energy_time[gen_type] = time.time()

            if smooth and is_clean_boost:
                self.smooth_filler.add_fill_request(gen_type, fill_amount, duration=0.3)
            else:
                self._apply_energy_delta_locked(gen_type, fill_amount)

    def _apply_energy_delta_locked(self, gen_type: GeneratorType, amount: float):
        session = self.current_session
        if not session or session.launch_committed or gen_type not in self.selected_generators:
            return
        old_value = session.energy_levels.get(gen_type, 0.0)
        new_value = min(MAX_ENERGY_GAUGE, max(0.0, old_value + amount))
        session.energy_levels[gen_type] = new_value
        if old_value < MAX_ENERGY_GAUGE <= new_value:
            self.filled_generators.add(gen_type)
            self._mission_events.append(
                MissionEvent(MissionEventKind.CELL_FILLED, generator=gen_type)
            )
        self._evaluate_launch_locked()

    def _evaluate_launch_locked(self):
        session = self.current_session
        if not session or session.launch_committed:
            return
        selected = tuple(self.selected_generators)
        if len(selected) < 2:
            self._launch_deadline = None
            return
        if not all(
            session.energy_levels.get(generator, 0.0) >= MAX_ENERGY_GAUGE
            for generator in selected
        ):
            self._launch_deadline = None
            return

        if len(selected) >= len(GeneratorType) or self.launch_wait_seconds <= 0.0:
            self._commit_launch_locked(selected)
            return

        now = self._mission_clock()
        if self._launch_deadline is None:
            self._launch_deadline = now + self.launch_wait_seconds
        elif now >= self._launch_deadline:
            self._commit_launch_locked(selected)

    def _commit_launch_locked(self, selected):
        session = self.current_session
        if not session or session.launch_committed:
            return
        self._launch_deadline = None
        session.launch_committed = True
        session.launch_generators = selected
        # Remember only sensors that are physically held at launch. Calls to
        # set_active_sensors() keep intersecting this set, so a release during
        # the animation permanently rearms that input for the next mission.
        self._sensor_rearm_blocked = set(selected).intersection(self.active_sensors)
        self._mission_events.append(
            MissionEvent(MissionEventKind.LAUNCH_COMMITTED, generators=selected)
        )

    def consume_mission_events(self) -> list[MissionEvent]:
        with self._lock:
            events = list(self._mission_events)
            self._mission_events.clear()
            return events

    def snapshot(self) -> GameSnapshot:
        with self._lock:
            session = self.current_session
            launch_ready = bool(
                session
                and not session.launch_committed
                and self._launch_deadline is not None
            )
            launch_wait_remaining = (
                max(0.0, self._launch_deadline - self._mission_clock())
                if launch_ready
                else 0.0
            )
            levels = (
                dict(session.energy_levels)
                if session
                else {generator: 0.0 for generator in GeneratorType}
            )
            return GameSnapshot(
                selected_generators=tuple(self.selected_generators),
                present_sensors=tuple(self.active_sensors),
                energy_levels=levels,
                filled_generators=frozenset(self.filled_generators),
                launch_generators=session.launch_generators if session else (),
                launch_ready=launch_ready,
                launch_wait_remaining=launch_wait_remaining,
                launch_committed=bool(session and session.launch_committed),
                completed=bool(session and session.completed),
            )

    def mark_launch_complete(self):
        with self._lock:
            if not self.current_session or self.current_session.completed:
                return
            self.current_session.completed = True
            self.current_session.end_time = time.time()
            if self.rankings_enabled:
                self._save_ranking()

    def reset_mission(self):
        with self._lock:
            present = list(self.active_sensors)
            session = self.current_session
            if session and session.launch_committed:
                # Launch-time rearm tracking has already observed releases and
                # fresh activations while the animation was running.
                blocked = self._sensor_rearm_blocked.intersection(present)
            else:
                # A manual reset has no launch edge to use as its baseline, so
                # currently held sensors must still be released once.
                blocked = set(present)
            self.start_new_session()
            self._sensor_rearm_blocked = blocked
            # Re-apply the latest physical state. Inputs released and activated
            # during the return animation are selected immediately instead of
            # being swallowed by the reset frame.
            self.set_active_sensors(present)

    def _log_clean_boost_signal(self, gen_type, fill_amount):
        self.clean_boost_signals.append(
            {
                "time": time.time(),
                "gen_type": gen_type,
                "amount": fill_amount,
                "active_gen": self.active_generator,
            }
        )
        self._write_statistics_log()

    def _write_statistics_log(self):
        import datetime
        import math

        import os

        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
        filepath = os.path.join(root_dir, "clean_boost_test.log")

        total_signals = len(self.clean_boost_signals)
        if total_signals == 0:
            return

        start_time = self.clean_boost_signals[0]["time"]
        current_time = time.time()
        elapsed = current_time - start_time

        # Group by type
        by_type = {}
        for sig in self.clean_boost_signals:
            g_type = sig["gen_type"]
            if g_type not in by_type:
                by_type[g_type] = []
            by_type[g_type].append(sig)

        lines = []
        lines.append("============================================================")
        lines.append("CLEAN BOOST SIGNAL TEST MODE STATISTICAL INSIGHTS")
        lines.append("============================================================")
        lines.append(
            f"Generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lines.append(f"Total Elapsed Time: {elapsed:.2f} seconds")
        lines.append(f"Total Signals Received: {total_signals}")
        lines.append("")
        lines.append("--- STATISTICS BY GENERATOR TYPE ---")
        lines.append("")

        from ..config import GeneratorType

        for g_type in GeneratorType:
            sigs = by_type.get(g_type, [])
            count = len(sigs)
            pct = (count / total_signals * 100.0) if total_signals > 0 else 0.0

            lines.append(f"[{g_type.value}]")
            lines.append(f"  Signals Received: {count} ({pct:.1f}%)")

            if count > 0:
                total_energy = sum(s["amount"] for s in sigs)
                lines.append(f"  Total Energy Added: {total_energy:.2f}")

                # Calculate intervals
                intervals = []
                for i in range(1, count):
                    intervals.append(sigs[i]["time"] - sigs[i - 1]["time"])

                if intervals:
                    avg_int = sum(intervals) / len(intervals)
                    min_int = min(intervals)
                    max_int = max(intervals)
                    # Std dev
                    variance = sum((x - avg_int) ** 2 for x in intervals) / len(
                        intervals
                    )
                    std_dev = math.sqrt(variance)

                    freq = 1.0 / avg_int if avg_int > 0 else 0.0
                    lines.append(
                        f"  Beacon Frequency: {freq:.2f} Hz (average {avg_int:.2f}s between beacons)"
                    )
                    lines.append(
                        f"  Interval Min/Max/StdDev: {min_int:.2f}s / {max_int:.2f}s / {std_dev:.2f}s"
                    )

                    # Suggested filling amounts
                    for target_sec in [15, 30, 45]:
                        expected_beacons = target_sec * freq
                        if expected_beacons > 0:
                            sugg_fill = 100.0 / expected_beacons
                            lines.append(
                                f"    To fill 100.0 in {target_sec}s ({expected_beacons:.1f} beacons): {sugg_fill:.2f} per beacon"
                            )
                else:
                    lines.append("  Beacon Frequency: N/A (Only 1 signal received)")
            else:
                lines.append("  No signals received for this generator type.")
            lines.append("")

        lines.append("============================================================")
        lines.append("CHRONOLOGICAL SIGNAL LOG")
        lines.append("============================================================")

        for sig in self.clean_boost_signals:
            sig_time_str = datetime.datetime.fromtimestamp(sig["time"]).strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )[:-3]
            lines.append(
                f"[{sig_time_str}] Received {sig['gen_type'].name} (amount={sig['amount']}) | Active Generator: {sig['active_gen'].name if sig['active_gen'] else 'None'}"
            )

        with open(filepath, "w") as f:
            f.write("\n".join(lines) + "\n")

    def _save_ranking(self):
        if not getattr(self, "rankings_enabled", True):
            return
        if self.current_ranking_entry is not None:
            self.discard_current_ranking()

        # Determine completed generator type by checking which gauge >= MAX_ENERGY_GAUGE
        completed_gen = next(
            (
                gen
                for gen, level in self.current_session.energy_levels.items()
                if level >= MAX_ENERGY_GAUGE
            ),
            None,
        )
        if not completed_gen:
            completed_gen = self.active_generator or GeneratorType.WIND

        time_taken = self.current_session.end_time - self.current_session.start_time
        if not self._valid_elapsed_time(time_taken):
            self.current_ranking_entry = None
            self.last_ranking_result = None
            return

        self.current_ranking_entry = RankingEntry(
            self.normalize_player_name(self.current_session.player_name) or "Player",
            time_taken,
            completed_gen,
            time.time(),
        )
        if completed_gen not in self.rankings:
            self.rankings[completed_gen] = []
        self.rankings[completed_gen].append(self.current_ranking_entry)
        self.rankings[completed_gen].sort(key=lambda x: x.time_taken)
        self.last_ranking_result = None
        # Do not persist generated placeholder names. The provisional entry is
        # visible to the result flow, but is saved only after name confirmation.

    def get_elapsed_time(self) -> float:
        if not self.current_session:
            return 0.0
        if self.current_session.start_time == 0.0:
            return 0.0
        if self.current_session.completed:
            return self.current_session.end_time - self.current_session.start_time
        return time.time() - self.current_session.start_time

    @staticmethod
    def normalize_player_name(name: object) -> str:
        if not isinstance(name, str):
            return ""
        return " ".join(name.strip().split())[:18]

    @staticmethod
    def _valid_elapsed_time(value: object) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value > 0.0
        )

    @staticmethod
    def _clean_timestamp(value: object) -> float:
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0.0
        ):
            return float(value)
        return 0.0

    def get_personal_best(
        self,
        name: str,
        generator: GeneratorType,
        exclude_current: bool = False,
    ) -> float | None:
        key = self.normalize_player_name(name).casefold()
        if not key:
            return None
        matches = [
            entry.time_taken
            for entry in self.rankings.get(generator, [])
            if (not exclude_current or entry is not self.current_ranking_entry)
            and self.normalize_player_name(entry.player_name).casefold() == key
        ]
        return min(matches) if matches else None

    def update_player_name(self, name: str) -> RankingResult | None:
        if not self.current_session:
            return None

        current = self.current_ranking_entry
        if current is None:
            # Confirmation is deliberately idempotent. Once a run has been
            # finalized, another submit cannot rename or remove any score.
            return self.last_ranking_result

        clean_name = self.normalize_player_name(name)
        if not clean_name:
            clean_name = self.normalize_player_name(self.current_session.player_name)
        if not clean_name:
            clean_name = "Player"
        self.current_session.player_name = clean_name

        gen = current.generator_type
        key = clean_name.casefold()
        entries = self.rankings.setdefault(gen, [])

        # Partition by object identity first. Never use list.remove/equality here:
        # only records belonging to confirmed player may be replaced.
        previous_entries = [entry for entry in entries if entry is not current]
        same_player = [
            entry
            for entry in previous_entries
            if self.normalize_player_name(entry.player_name).casefold() == key
        ]
        different_players = [
            entry
            for entry in previous_entries
            if self.normalize_player_name(entry.player_name).casefold() != key
        ]

        previous_best = (
            min(entry.time_taken for entry in same_player) if same_player else None
        )
        current.player_name = clean_name
        personal_best_entry = current
        kept_run = True
        if previous_best is not None:
            best_entry = min(
                [*same_player, current], key=lambda entry: entry.time_taken
            )
            # Keep exactly one personal best for this name. Every differently
            # named player remains untouched, regardless of relative time.
            self.rankings[gen] = [*different_players, best_entry]
            personal_best_entry = best_entry
            kept_run = best_entry is current
            best_entry.timestamp = max(
                [current.timestamp, *(entry.timestamp for entry in same_player)]
            )
        else:
            # New name: rename provisional entry only. No existing player removed.
            self.rankings[gen] = [*previous_entries, current]

        self.rankings[gen].sort(key=lambda entry: entry.time_taken)
        final_rank = next(
            index
            for index, entry in enumerate(self.rankings[gen], start=1)
            if entry is personal_best_entry
        )
        self.last_ranking_result = RankingResult(
            player_name=clean_name,
            run_time=current.time_taken,
            previous_best=previous_best,
            final_rank=final_rank,
            kept_run=kept_run,
        )
        self.save_rankings()
        # From this point onward the score is confirmed, not cancellable. This
        # prevents selector movement while leaving the leaderboard from deleting
        # the finalized result.
        self.current_ranking_entry = None
        return self.last_ranking_result

    def discard_current_ranking(self):
        if self.current_ranking_entry is not None:
            current = self.current_ranking_entry
            gen = current.generator_type
            if gen in self.rankings:
                # Dataclass equality can consider two distinct records equal.
                # Filter by identity so cancellation removes only the pending run.
                self.rankings[gen] = [
                    entry for entry in self.rankings[gen] if entry is not current
                ]
            self.current_ranking_entry = None
        self.last_ranking_result = None

    def _get_leaderboard_filepath(self) -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
        return os.path.join(root_dir, "leaderboard.json")

    def load_rankings(self):
        filepath = self._get_leaderboard_filepath()
        if not os.path.exists(filepath):
            self.rankings = {gen: [] for gen in GeneratorType}
            self._rankings_storage_safe = True
            return

        try:
            with open(filepath, "r", encoding="utf-8") as file:
                data = json.load(file)
            loaded = self._deserialize_rankings(data)
        except Exception as error:
            # Keep any rankings already in memory and block writes. Otherwise a
            # malformed file could be silently replaced by an empty leaderboard.
            self._rankings_storage_safe = False
            print(f"Error loading rankings: {error}")
            return

        self.rankings = loaded
        self.current_ranking_entry = None
        self.last_ranking_result = None
        self._rankings_storage_safe = True

    def _deserialize_rankings(self, data) -> Dict[GeneratorType, List[RankingEntry]]:
        loaded = {gen: [] for gen in GeneratorType}

        if isinstance(data, dict):
            groups = []
            for gen_name, entries in data.items():
                if not isinstance(entries, list):
                    raise ValueError(f"ranking group {gen_name!r} is not a list")
                gen = self._generator_from_name(gen_name)
                if gen is not None:
                    groups.append((gen, entries))
        elif isinstance(data, list):
            # Backward compatibility for the old flat leaderboard format.
            groups = []
            for raw_entry in data:
                if not isinstance(raw_entry, dict):
                    continue
                gen_name = raw_entry.get("generator_type")
                gen = (
                    GeneratorType.WIND
                    if gen_name is None
                    else self._generator_from_name(gen_name)
                )
                if gen is not None:
                    groups.append((gen, [raw_entry]))
        else:
            raise ValueError("leaderboard root must be an object or list")

        for gen, entries in groups:
            for raw_entry in entries:
                if not isinstance(raw_entry, dict):
                    continue
                time_taken = raw_entry.get("time_taken", 0.0)
                if not self._valid_elapsed_time(time_taken):
                    continue
                loaded[gen].append(
                    RankingEntry(
                        player_name=self.normalize_player_name(
                            raw_entry.get("player_name", "Player")
                        )
                        or "Player",
                        time_taken=float(time_taken),
                        generator_type=gen,
                        timestamp=self._clean_timestamp(
                            raw_entry.get("timestamp", 0.0)
                        ),
                    )
                )

        for gen in GeneratorType:
            best_by_player = {}
            for entry in loaded[gen]:
                key = self.normalize_player_name(entry.player_name).casefold()
                previous = best_by_player.get(key)
                if previous is None:
                    best_by_player[key] = entry
                elif entry.time_taken < previous.time_taken:
                    entry.timestamp = max(entry.timestamp, previous.timestamp)
                    best_by_player[key] = entry
                else:
                    previous.timestamp = max(previous.timestamp, entry.timestamp)
            loaded[gen] = sorted(
                best_by_player.values(), key=lambda entry: entry.time_taken
            )

        return loaded

    @staticmethod
    def _generator_from_name(value: object) -> GeneratorType | None:
        if not isinstance(value, str):
            return None
        key = value.casefold()
        if key in {"piezo", "piezoelectric"}:
            return GeneratorType.HAND_CRANK
        return next(
            (
                gen
                for gen in GeneratorType
                if gen.name.casefold() == key or gen.value.casefold() == key
            ),
            None,
        )

    def save_rankings(self):
        if not getattr(self, "_rankings_storage_safe", True):
            print("Refusing to overwrite leaderboard after a load error")
            return False
        filepath = self._get_leaderboard_filepath()
        try:
            data = {}
            for gen, entries in self.rankings.items():
                data[gen.name] = [
                    {
                        "player_name": r.player_name,
                        "time_taken": r.time_taken,
                        "timestamp": getattr(r, "timestamp", 0.0)
                    }
                    for r in entries
                ]
            self._write_json_atomic(filepath, data)
            return True
        except Exception as e:
            print(f"Error saving rankings: {e}")
            return False

    @staticmethod
    def _write_json_atomic(filepath: str, data) -> None:
        temp_path = f"{filepath}.tmp"
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, filepath)

    def _get_players_filepath(self) -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
        return os.path.join(root_dir, "players_database.json")

    def load_player_base(self) -> List[str]:
        filepath = self._get_players_filepath()
        if not os.path.exists(filepath):
            self._players_storage_safe = True
            return []
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, list):
                raise ValueError("player database root must be a list")
            players = []
            seen = set()
            for value in data:
                name = self.normalize_player_name(value)
                key = name.casefold()
                if name and key not in seen:
                    players.append(name)
                    seen.add(key)
            self._players_storage_safe = True
            return players
        except Exception as error:
            self._players_storage_safe = False
            print(f"Error loading player base: {error}")
            return []

    def save_player_base(self, players: List[str]):
        if not getattr(self, "_players_storage_safe", True):
            print("Refusing to overwrite player database after a load error")
            return False
        filepath = self._get_players_filepath()
        try:
            self._write_json_atomic(filepath, players)
            return True
        except Exception as e:
            print(f"Error saving player base: {e}")
            return False

    def add_player_to_base(self, name: str):
        if not name or not self.normalize_player_name(name):
            return
        name = self.normalize_player_name(name)
        players = self.load_player_base()
        if not any(p.casefold() == name.casefold() for p in players):
            players.append(name)
            self.save_player_base(players)
