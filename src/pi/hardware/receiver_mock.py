import asyncio
import random
from config import GeneratorType, ENERGY_PER_BEACON
from logic.game_state import GameState


class MockReceiver:
    def __init__(self, game_state: GameState):
        self.game_state = game_state

    async def start_scanning(self):
        """Simulates receiving CleanBoost beacons randomly over time."""
        generator_types = list(GeneratorType)

        while True:
            # Simulate a random delay between beacon signals (0.1 to 0.8 seconds)
            await asyncio.sleep(random.uniform(0.1, 0.8))

            # Randomly select which generator "fired"
            gen_type = random.choice(generator_types)

            # Send the event to the logic layer
            self.game_state.add_energy(gen_type, ENERGY_PER_BEACON)
