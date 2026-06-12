import asyncio
from gpiozero import Button
from config import GeneratorType, ENERGY_PER_BEACON
from logic.game_state import GameState

GPIO_PINS = {
    GeneratorType.WIND: 17,
    GeneratorType.SOLAR: 27,
    GeneratorType.PIEZO: 22,
    GeneratorType.COIL: 23,
}


class WireReceiver:
    def __init__(self, game_state: GameState):
        self.game_state = game_state
        self.loop = asyncio.get_event_loop()
        self.inputs = []

    def _on_pin_activated(self, gen_type: GeneratorType):
        # gpiozero triggers callbacks in a background thread.
        # We must use call_soon_threadsafe to safely update the asyncio game state.
        self.loop.call_soon_threadsafe(
            self.game_state.set_active_generator, gen_type
        )

    def _on_pin_deactivated(self, gen_type: GeneratorType):
        # Optional: handle if the user turns the dial to an intermediate state
        pass

    async def start_listening(self):
        """Initializes GPIO pins and listens for digital HIGH state."""

        for gen_type, pin in GPIO_PINS.items():
            # Create a closure so the callback remembers which generator triggered it
            def make_activated_callback(g_type=gen_type):
                return lambda: self._on_pin_activated(g_type)

            def make_deactivated_callback(g_type=gen_type):
                return lambda: self._on_pin_deactivated(g_type)

            # pull_up=False: The pin normally reads LOW (0V).
            # bounce_time=0.1: Ignores rapid signal noise for 100ms.
            digital_input = Button(pin, pull_up=False, bounce_time=0.1)

            # when_pressed triggers when the pin receives 3.3V (HIGH)
            digital_input.when_pressed = make_activated_callback()
            digital_input.when_released = make_deactivated_callback()
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
