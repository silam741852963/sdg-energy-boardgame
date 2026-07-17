import unittest
import json
import math
import tempfile
from types import SimpleNamespace
from pathlib import Path

from pi.config import GeneratorType
from pi.logic.game_state import GameState
from pi.logic.models import RankingEntry


class PersonalBestTests(unittest.TestCase):
    def make_state(self, entries, current):
        state = GameState.__new__(GameState)
        state.current_session = SimpleNamespace(player_name="Temporary")
        state.current_ranking_entry = current
        state.rankings = {generator: [] for generator in GeneratorType}
        state.rankings[current.generator_type] = [*entries, current]
        state.save_rankings = lambda: None
        return state

    def test_faster_different_player_does_not_remove_existing_player(self):
        alice = RankingEntry("Alice", 20.0, GeneratorType.WIND)
        bob = RankingEntry("Bob", 25.0, GeneratorType.WIND)
        current = RankingEntry("Player 3", 10.0, GeneratorType.WIND)
        state = self.make_state([alice, bob], current)

        result = state.update_player_name("Charlie")

        entries = state.rankings[GeneratorType.WIND]
        self.assertEqual({entry.player_name for entry in entries}, {"Alice", "Bob", "Charlie"})
        self.assertIs(entries[0], current)
        self.assertIn(alice, entries)
        self.assertIn(bob, entries)
        self.assertTrue(result.is_first_result)
        self.assertEqual(result.final_rank, 1)

    def test_better_same_player_replaces_only_their_old_best(self):
        alice = RankingEntry("Alice", 20.0, GeneratorType.SOLAR)
        bob = RankingEntry("Bob", 15.0, GeneratorType.SOLAR)
        current = RankingEntry("Player 3", 12.0, GeneratorType.SOLAR)
        state = self.make_state([alice, bob], current)

        result = state.update_player_name("Alice")

        entries = state.rankings[GeneratorType.SOLAR]
        self.assertEqual([(entry.player_name, entry.time_taken) for entry in entries], [("Alice", 12.0), ("Bob", 15.0)])
        self.assertIs(state.current_ranking_entry, current)
        self.assertTrue(result.is_personal_best)
        self.assertEqual(result.previous_best, 20.0)
        self.assertEqual(result.improvement, 8.0)

    def test_worse_same_player_keeps_old_best_and_other_players(self):
        alice = RankingEntry("Alice", 10.0, GeneratorType.COIL, timestamp=100.0)
        bob = RankingEntry("Bob", 15.0, GeneratorType.COIL)
        current = RankingEntry("Player 3", 20.0, GeneratorType.COIL, timestamp=200.0)
        state = self.make_state([alice, bob], current)

        result = state.update_player_name("  alice  ")

        entries = state.rankings[GeneratorType.COIL]
        self.assertEqual([(entry.player_name, entry.time_taken) for entry in entries], [("Alice", 10.0), ("Bob", 15.0)])
        self.assertIsNone(state.current_ranking_entry)
        self.assertEqual(result.run_time, 20.0)
        self.assertEqual(result.difference_from_best, 10.0)
        self.assertFalse(result.kept_run)
        self.assertEqual(result.final_rank, 1)
        self.assertIs(state.last_ranking_result, result)
        self.assertEqual(entries[0].timestamp, 200.0)

    def test_name_normalization_merges_whitespace_and_case(self):
        alice = RankingEntry("Alice Smith", 20.0, GeneratorType.PIEZO)
        current = RankingEntry("Player 4", 18.0, GeneratorType.PIEZO)
        state = self.make_state([alice], current)

        result = state.update_player_name("  ALICE   SMITH  ")

        self.assertTrue(result.is_personal_best)
        self.assertEqual(result.player_name, "ALICE SMITH")
        self.assertEqual(len(state.rankings[GeneratorType.PIEZO]), 1)

    def test_equal_time_reports_match_without_duplicate(self):
        alice = RankingEntry("Alice", 12.0, GeneratorType.SOLAR)
        current = RankingEntry("Player 5", 12.0, GeneratorType.SOLAR)
        state = self.make_state([alice], current)

        result = state.update_player_name("Alice")

        self.assertFalse(result.is_personal_best)
        self.assertEqual(result.difference_from_best, 0.0)
        self.assertFalse(result.kept_run)
        self.assertEqual(len(state.rankings[GeneratorType.SOLAR]), 1)

    def test_personal_best_lookup_can_exclude_provisional_run(self):
        alice = RankingEntry("Alice", 14.0, GeneratorType.WIND)
        current = RankingEntry("Alice", 10.0, GeneratorType.WIND)
        state = self.make_state([alice], current)

        self.assertEqual(
            state.get_personal_best(" alice ", GeneratorType.WIND), 10.0
        )
        self.assertEqual(
            state.get_personal_best(
                " alice ", GeneratorType.WIND, exclude_current=True
            ),
            14.0,
        )

    def test_loading_filters_invalid_times_and_keeps_one_best_per_player(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "leaderboard.json"
            path.write_text(
                json.dumps(
                    {
                        "WIND": [
                            {"player_name": " Alice ", "time_taken": 15.0, "timestamp": 30.0},
                            {"player_name": "alice", "time_taken": 12.0, "timestamp": 20.0},
                            {"player_name": "Bob", "time_taken": -1.0},
                            {"player_name": "Eve", "time_taken": math.nan},
                            {"player_name": None, "time_taken": True},
                        ]
                    }
                )
            )
            state = GameState.__new__(GameState)
            state._get_leaderboard_filepath = lambda: str(path)

            state.load_rankings()

        entries = state.rankings[GeneratorType.WIND]
        self.assertEqual(
            [(entry.player_name, entry.time_taken) for entry in entries],
            [("alice", 12.0)],
        )
        self.assertEqual(entries[0].timestamp, 30.0)


if __name__ == "__main__":
    unittest.main()
