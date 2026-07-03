import asyncio
from gpiozero import Button
from config import GeneratorType, ENERGY_PER_BEACON
from logic.game_state import GameState

# Pin mapping: BCM GPIO Pin numbers
GPIO_PINS = {
    GeneratorType.WIND: 17,
    GeneratorType.SOLAR: 27,
    GeneratorType.PIEZO: 22,
    GeneratorType.COIL: 23,
}

# Configuration for Hall-IC output type:
# - True: Active-LOW sensor (pulls to GND when magnet detected). Uses internal pull-up.
# - False: Active-HIGH sensor (pulls to 3.3V when magnet detected). Uses internal pull-down.
HALL_IC_PULL_UP = False


class WireReceiver:
    def __init__(self, game_state: GameState):
        self.game_state = game_state
        self.loop = asyncio.get_event_loop()
        self.inputs = []

    def _on_pin_changed(self):
        # Scan all pins to find which generator is active.
        # This handles transitions and intermediate states (where no pin is active) cleanly.
        self.loop.call_soon_threadsafe(self._check_and_update_generator)

    def _check_and_update_generator(self):
        active_gen = None
        for gen_type, device in zip(GPIO_PINS.keys(), self.inputs):
            if device.is_pressed:
                active_gen = gen_type
                break
        
        # Update game state immediately
        if self.game_state.active_generator != active_gen:
            self.game_state.set_active_generator(active_gen)

    async def start_listening(self):
        """Initializes GPIO pins and listens for Hall-IC signals."""

        for gen_type, pin in GPIO_PINS.items():
            # bounce_time=0.05: Ignored rapid signal noise for 50ms for faster response
            digital_input = Button(pin, pull_up=HALL_IC_PULL_UP, bounce_time=0.05)

            # Assign state change callbacks
            digital_input.when_pressed = self._on_pin_changed
            digital_input.when_released = self._on_pin_changed
            self.inputs.append(digital_input)

            # Check initial state
            if digital_input.is_pressed:
                self.game_state.set_active_generator(gen_type)

        # Keep the async task alive so the program doesn't exit
        try:
            while True:
                # Poll inactivity timer
                self.game_state.check_inactivity()
                await asyncio.sleep(1.0)
        finally:
            # Safely release the GPIO pins when the program stops
            for device in self.inputs:
                device.close()
