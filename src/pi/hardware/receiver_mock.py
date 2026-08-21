import asyncio
from ..logic.game_state import GameState


class MockReceiver:
    def __init__(self, game_state: GameState):
        self.game_state = game_state

    async def start_scanning(self):
        """Keep the mock receiver alive; keyboard input emits deterministic signals."""
        while True:
            await asyncio.sleep(1.0)
