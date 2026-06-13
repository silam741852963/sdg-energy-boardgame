import asyncio
import threading
from logic.game_state import GameState
from ui.fireworks.engine import FireworkEngine

USE_MOCK_HARDWARE = True

# Dynamically import the correct receiver
if USE_MOCK_HARDWARE:
    from hardware.receiver_mock import MockReceiver as Receiver
else:
    from hardware.receiver_ble import BLEReceiver as Receiver
    from hardware.receiver_wire import WireReceiver
    from hardware.pwm_out import PWMController

async def async_main(state: GameState):
    # Initialize Receivers
    receivers = []
    
    # BLE Clean Boost receiver
    ble_receiver = Receiver(state)
    receivers.append(ble_receiver.start_scanning())
    
    if not USE_MOCK_HARDWARE:
        # Hardware GPIO receiver (Hall effect selection pins)
        wire_receiver = WireReceiver(state)
        receivers.append(wire_receiver.start_listening())
        
        # 1KHz PWM output on GPIO 2
        pwm_controller = PWMController(pin=2, frequency=1000)
        receivers.append(pwm_controller.start())
        
    try:
        await asyncio.gather(*receivers)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Async logic error: {e}")

def run_asyncio_thread(state: GameState):
    # Set up a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(async_main(state))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

def main():
    # 1. Initialize State
    state = GameState()

    # Start a test session immediately
    state.start_new_session()

    # 2. Start Asyncio Logic in a Background Thread
    bg_thread = threading.Thread(target=run_asyncio_thread, args=(state,), daemon=True)
    bg_thread.start()

    # 3. Start ModernGL Engine in the Main Thread
    # Inject the game state into the engine so it can render UI/Gauges
    app = FireworkEngine(state, is_mock=USE_MOCK_HARDWARE)
    app.run()

if __name__ == "__main__":
    main()
