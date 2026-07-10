import time
import os
import json
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
        self.drain_paused = False

        # Explicit tracker for when each gauge last INCREASED its value
        self._last_gauge_values = {}
        self._last_increase_time = {}
        self.session_count = 0
        self.clean_boost_signals = []

        # Multi-sensor active states (Hall-IC)
        self.active_sensors = []
        
        # Konami sequence history (track transitions)
        self.dial_sequence = []
        self.trigger_konami_combo = False
        self.trigger_reset_combo = False
        self.trigger_love_combo = False
        
        # Simon Says Mode state
        self.simon_says_active = False
        self.simon_says_target = None
        self.simon_says_step = 0
        self.simon_says_sequence = []
        self.simon_says_last_target_time = 0.0

    def start_new_session(self, player_name: str | None = None):
        self.session_count += 1
        name = player_name if player_name else f"Student {self.session_count}"
        self.current_session = PlayerSession(player_name=name)
        self.current_session.start_time = 0.0
        self.current_ranking_entry = None
        for gen in GeneratorType:
            self._last_gauge_values[gen] = 0.0
            self._last_increase_time[gen] = time.time()

    def set_active_generator(self, gen_type: GeneratorType | None):
        if gen_type is not None and self.current_session and self.current_session.start_time == 0.0:
            self.current_session.start_time = time.time()

        if self.active_generator != gen_type:
            self.active_generator = gen_type
            self.last_activity_time = time.time()
            if not self.active_sensors:
                self.active_sensors = [gen_type] if gen_type else []

    def set_active_sensors(self, sensors: List[GeneratorType]):
        current_time = time.time()
        self.active_sensors = sensors
        
        new_active = sensors[0] if sensors else None
        
        # Track dialing sequence for Konami and Overdrive Mode
        if new_active is not None:
            if not self.dial_sequence or self.dial_sequence[-1][0] != new_active or (current_time - self.dial_sequence[-1][1] > 0.05):
                self.dial_sequence.append((new_active, current_time))
                self.dial_sequence = self.dial_sequence[-15:]
                
                # Check for Konami code: WIND -> SOLAR -> PIEZO -> COIL
                deduped = []
                for item, t in self.dial_sequence:
                    if not deduped or deduped[-1] != item:
                        deduped.append(item)
                
                if len(deduped) >= 4 and deduped[-4:] == [
                    GeneratorType.WIND,
                    GeneratorType.SOLAR,
                    GeneratorType.PIEZO,
                    GeneratorType.COIL,
                ]:
                    if len(self.dial_sequence) >= 4 and (self.dial_sequence[-1][1] - self.dial_sequence[-4][1] <= 5.0):
                        self.trigger_konami_combo = True
                
                # Check for Reset combo sequence: COIL -> PIEZO -> SOLAR -> WIND in rapid succession
                if len(deduped) >= 4 and deduped[-4:] == [
                    GeneratorType.COIL,
                    GeneratorType.PIEZO,
                    GeneratorType.SOLAR,
                    GeneratorType.WIND,
                ]:
                    if len(self.dial_sequence) >= 4 and (self.dial_sequence[-1][1] - self.dial_sequence[-4][1] <= 5.0):
                        self.trigger_reset_combo = True

                # Check for Love combo sequence: SOLAR -> WIND -> SOLAR -> WIND -> PIEZO -> PIEZO in rapid succession (within 7.0 seconds)
                types_seq = [item[0] for item in self.dial_sequence]
                if len(types_seq) >= 6 and types_seq[-6:] == [
                    GeneratorType.SOLAR,
                    GeneratorType.WIND,
                    GeneratorType.SOLAR,
                    GeneratorType.WIND,
                    GeneratorType.PIEZO,
                    GeneratorType.PIEZO,
                ]:
                    if len(self.dial_sequence) >= 6 and (self.dial_sequence[-1][1] - self.dial_sequence[-6][1] <= 7.0):
                        self.trigger_love_combo = True
                
        self.set_active_generator(new_active)

    def check_inactivity(self):
        current_time = time.time()
        dt = current_time - self.last_drain_time
        self.last_drain_time = current_time

        if self.drain_paused:
            # While draining is paused, keep the timers fresh relative to current_time
            # so that no time elapsed is accumulated towards the 55s inactivity limit.
            for gen in GeneratorType:
                self._last_increase_time[gen] = current_time
                if self.current_session:
                    self._last_gauge_values[gen] = self.current_session.energy_levels.get(gen, 0.0)
            return

        # 60s inactivity returns to default None (Ablic)
        if (
            self.active_generator is not None
            and (current_time - self.last_activity_time) > 60.0
        ):
            self.active_generator = None

        # Auto drain each gauge after 55s of no increase
        if not self.current_session:
            return

        for gen in GeneratorType:
            current_val = self.current_session.energy_levels.get(gen, 0.0)
            last_known = self._last_gauge_values.get(gen, 0.0)

            if current_val > last_known:
                # Value went up — reset the 55s inactivity clock for this gauge
                self._last_increase_time[gen] = current_time
                self._last_gauge_values[gen] = current_val
            elif current_val < last_known:
                # Value went down (already draining or was drained externally) — just track it
                self._last_gauge_values[gen] = current_val
            # else: value unchanged — do nothing with _last_gauge_values

            # Only drain if gauge is above 0 AND the inactivity timer has started AND 55s have passed
            if gen in self._last_increase_time and current_val > 0.0:
                idle_secs = current_time - self._last_increase_time[gen]
                if idle_secs > 55.0:
                    new_val = max(0.0, current_val - (5.0 * dt))
                    self.current_session.energy_levels[gen] = new_val
                    self._last_gauge_values[gen] = new_val

    def force_immediate_drain(self, gen_type):
        self._last_increase_time[gen_type] = time.time() - 100.0

    def add_energy(self, gen_type, amount: float, is_clean_boost: bool = False):
        if not self.current_session:
            return

        # Prevent filling any gauge if the generator is not the currently active selection
        if self.active_generator is None or self.active_generator != gen_type:
            return

        from config import CLEANBOOST_TEST_MODE, ENERGY_PER_BEACON_BY_TYPE

        # In test mode, only clean boost signals can add energy
        if CLEANBOOST_TEST_MODE and not is_clean_boost:
            return

        # Determine the amount of energy to add
        if CLEANBOOST_TEST_MODE:
            from config import ENERGY_PER_BEACON
            if amount != ENERGY_PER_BEACON:
                fill_amount = amount
            else:
                fill_amount = ENERGY_PER_BEACON_BY_TYPE.get(gen_type, amount)
        else:
            fill_amount = amount

        if self.current_session.completed:
            return

        # Log clean boost signals in test mode
        if CLEANBOOST_TEST_MODE and is_clean_boost:
            self._log_clean_boost_signal(gen_type, fill_amount)

        self.last_activity_time = time.time()

        # In test mode, fill the received gen_type's gauge. 
        # In normal mode, fill the currently selected active generator's gauge.
        target_gen = gen_type if CLEANBOOST_TEST_MODE else self.active_generator
        if target_gen is None:
            return

        self.current_session.last_energy_time[target_gen] = time.time()
        self.current_session.energy_levels[target_gen] += fill_amount

        # Check if any single gauge has reached the max
        if not self.current_session.completed:
            if any(
                level >= MAX_ENERGY_GAUGE
                for level in self.current_session.energy_levels.values()
            ):
                self.current_session.completed = True
                self.current_session.end_time = time.time()
                self._save_ranking()
                if CLEANBOOST_TEST_MODE:
                    self._write_statistics_log()

    def _log_clean_boost_signal(self, gen_type, fill_amount):
        self.clean_boost_signals.append({
            "time": time.time(),
            "gen_type": gen_type,
            "amount": fill_amount,
            "active_gen": self.active_generator
        })
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
        lines.append(f"Generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Total Elapsed Time: {elapsed:.2f} seconds")
        lines.append(f"Total Signals Received: {total_signals}")
        lines.append("")
        lines.append("--- STATISTICS BY GENERATOR TYPE ---")
        lines.append("")
        
        from config import GeneratorType
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
                    intervals.append(sigs[i]["time"] - sigs[i-1]["time"])
                    
                if intervals:
                    avg_int = sum(intervals) / len(intervals)
                    min_int = min(intervals)
                    max_int = max(intervals)
                    # Std dev
                    variance = sum((x - avg_int) ** 2 for x in intervals) / len(intervals)
                    std_dev = math.sqrt(variance)
                    
                    freq = 1.0 / avg_int if avg_int > 0 else 0.0
                    lines.append(f"  Beacon Frequency: {freq:.2f} Hz (average {avg_int:.2f}s between beacons)")
                    lines.append(f"  Interval Min/Max/StdDev: {min_int:.2f}s / {max_int:.2f}s / {std_dev:.2f}s")
                    
                    # Suggested filling amounts
                    for target_sec in [15, 30, 45]:
                        expected_beacons = target_sec * freq
                        if expected_beacons > 0:
                            sugg_fill = 100.0 / expected_beacons
                            lines.append(f"    To fill 100.0 in {target_sec}s ({expected_beacons:.1f} beacons): {sugg_fill:.2f} per beacon")
                else:
                    lines.append("  Beacon Frequency: N/A (Only 1 signal received)")
            else:
                lines.append("  No signals received for this generator type.")
            lines.append("")
            
        lines.append("============================================================")
        lines.append("CHRONOLOGICAL SIGNAL LOG")
        lines.append("============================================================")
        
        for sig in self.clean_boost_signals:
            sig_time_str = datetime.datetime.fromtimestamp(sig["time"]).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            lines.append(f"[{sig_time_str}] Received {sig['gen_type'].name} (amount={sig['amount']}) | Active Generator: {sig['active_gen'].name if sig['active_gen'] else 'None'}")
            
        with open(filepath, "w") as f:
            f.write("\n".join(lines) + "\n")

    def _save_ranking(self):
        time_taken = self.current_session.end_time - self.current_session.start_time
        self.current_ranking_entry = RankingEntry(self.current_session.player_name, time_taken)
        self.rankings.append(self.current_ranking_entry)
        # Sort by fastest time
        self.rankings.sort(key=lambda x: x.time_taken)

    def get_elapsed_time(self) -> float:
        if not self.current_session:
            return 0.0
        if self.current_session.start_time == 0.0:
            return 0.0
        if self.current_session.completed:
            return self.current_session.end_time - self.current_session.start_time
        return time.time() - self.current_session.start_time

    def update_player_name(self, name: str):
        if self.current_session:
            self.current_session.player_name = name
            if self.current_ranking_entry:
                self.current_ranking_entry.player_name = name
                # Re-sort rankings
                self.rankings.sort(key=lambda x: x.time_taken)

    def _get_players_filepath(self) -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
        return os.path.join(root_dir, "players_database.json")

    def load_player_base(self) -> List[str]:
        filepath = self._get_players_filepath()
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading player base: {e}")
        return []

    def save_player_base(self, players: List[str]):
        filepath = self._get_players_filepath()
        try:
            with open(filepath, "w") as f:
                json.dump(players, f, indent=4)
        except Exception as e:
            print(f"Error saving player base: {e}")

    def add_player_to_base(self, name: str):
        if not name or name.strip() == "":
            return
        name = name.strip()
        players = self.load_player_base()
        if not any(p.lower() == name.lower() for p in players):
            players.append(name)
            self.save_player_base(players)
