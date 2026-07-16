import asyncio
import threading
import argparse
from .logic.game_state import GameState
from .ui.fireworks.engine import FireworkEngine

async def async_main(state: GameState, mock_ble: bool, mock_hall: bool):
    receivers = []
    
    # 1. BLE Clean Boost receiver
    if mock_ble:
        from .hardware.receiver_mock import MockReceiver
        ble_receiver = MockReceiver(state)
        receivers.append(ble_receiver.start_scanning())
    else:
        from .hardware.receiver_ble import BLEReceiver
        ble_receiver = BLEReceiver(state)
        receivers.append(ble_receiver.start_scanning())
    
    # 2. Hardware GPIO receiver (Hall effect selection pins)
    if not mock_hall:
        from .hardware.receiver_wire import WireReceiver
        from .hardware.pwm_out import PWMController
        
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

def run_asyncio_thread(state: GameState, mock_ble: bool, mock_hall: bool):
    # Set up a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(async_main(state, mock_ble, mock_hall))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

def main():
    # Parse command line arguments for the 4 modes
    parser = argparse.ArgumentParser(description="SDG Energy Boardgame Main Script")
    parser.add_argument(
        '--debug',
        nargs='?',
        const='all',
        choices=['ble', 'hall-ic', 'all'],
        help="Run in debug mode. Option: 'ble', 'hall-ic', or 'all' (default if --debug is set)"
    )
    args = parser.parse_args()

    mock_ble = False
    mock_hall = False

    if args.debug == 'all':
        mock_ble = True
        mock_hall = True
        print("[INIT] Debug mode: BOTH BLE and Hall-IC mocked.")
    elif args.debug == 'ble':
        mock_ble = True
        mock_hall = False
        print("[INIT] Debug mode: BLE mocked, Hall-IC real.")
    elif args.debug == 'hall-ic':
        mock_ble = False
        mock_hall = True
        print("[INIT] Debug mode: BLE real, Hall-IC mocked.")
    else:
        mock_ble = False
        mock_hall = False
        print("[INIT] Non-debug mode: BOTH BLE and Hall-IC real.")

    # Graceful check for gpiozero/RPi.GPIO if running real Hall-IC
    if not mock_hall:
        try:
            from gpiozero import Device
            Device.ensure_pin_factory()
        except Exception as e:
            print(f"[WARNING] gpiozero/RPi.GPIO not fully functional ({e}). Forcing mock Hall-IC mode.")
            mock_hall = True

    # 1. Initialize State
    state = GameState()

    # Start a test session immediately
    state.start_new_session()

    # 2. Start Asyncio Logic in a Background Thread
    bg_thread = threading.Thread(
        target=run_asyncio_thread,
        args=(state, mock_ble, mock_hall),
        daemon=True
    )
    bg_thread.start()

    # 3. Start ModernGL Engine in the Main Thread
    # Inject the resolved mock flags
    app = FireworkEngine(state, mock_ble=mock_ble, mock_hall=mock_hall)
    app.run()

if __name__ == "__main__":
    main()
