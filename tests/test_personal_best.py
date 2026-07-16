import unittest
from types import SimpleNamespace

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

        state.update_player_name("Charlie")

        entries = state.rankings[GeneratorType.WIND]
        self.assertEqual({entry.player_name for entry in entries}, {"Alice", "Bob", "Charlie"})
        self.assertIs(entries[0], current)
        self.assertIn(alice, entries)
        self.assertIn(bob, entries)

    def test_better_same_player_replaces_only_their_old_best(self):
        alice = RankingEntry("Alice", 20.0, GeneratorType.SOLAR)
        bob = RankingEntry("Bob", 15.0, GeneratorType.SOLAR)
        current = RankingEntry("Player 3", 12.0, GeneratorType.SOLAR)
        state = self.make_state([alice, bob], current)

        state.update_player_name("Alice")

        entries = state.rankings[GeneratorType.SOLAR]
        self.assertEqual([(entry.player_name, entry.time_taken) for entry in entries], [("Alice", 12.0), ("Bob", 15.0)])
        self.assertIs(state.current_ranking_entry, current)

    def test_worse_same_player_keeps_old_best_and_other_players(self):
        alice = RankingEntry("Alice", 10.0, GeneratorType.COIL)
        bob = RankingEntry("Bob", 15.0, GeneratorType.COIL)
        current = RankingEntry("Player 3", 20.0, GeneratorType.COIL)
        state = self.make_state([alice, bob], current)

        state.update_player_name("alice")

        entries = state.rankings[GeneratorType.COIL]
        self.assertEqual([(entry.player_name, entry.time_taken) for entry in entries], [("Alice", 10.0), ("Bob", 15.0)])
        self.assertIsNone(state.current_ranking_entry)


if __name__ == "__main__":
    unittest.main()
