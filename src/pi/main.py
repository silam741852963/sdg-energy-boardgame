import asyncio
from logic.game_state import GameState
from ui.cli_render import CLIRenderer

# Toggle this to False when you deploy to the actual Raspberry Pi 5
USE_MOCK_HARDWARE = True

# Dynamically import the correct receiver
if USE_MOCK_HARDWARE:
    from hardware.receiver_mock import MockReceiver as Receiver
else:
    from hardware.receiver_ble import BLEReceiver as Receiver


async def main():
    # 1. Initialize State
    state = GameState()

    # Start a test session immediately
    state.start_new_session("Test Student")

    # 2. Initialize Subsystems
    receiver = Receiver(state)
    ui_renderer = CLIRenderer(state)

    # 3. Run concurrently
    try:
        await asyncio.gather(receiver.start_scanning(), ui_renderer.render_loop())
    except KeyboardInterrupt:
        print("\nExiting CleanBoost Dashboard...")


if __name__ == "__main__":
    asyncio.run(main())
