import asyncio
from gpiozero import PWMOutputDevice

class PWMController:
    def __init__(self, pin=2, frequency=1000):
        """
        Creates a PWM output on the specified GPIO pin.
        Note: The Raspberry Pi uses 3.3V logic. External hardware
        is required to step this up to 5V.
        """
        self.pin = pin
        self.frequency = frequency
        self.pwm = None

    async def start(self):
        # Initialize PWM on the given pin with the target frequency
        self.pwm = PWMOutputDevice(self.pin, frequency=self.frequency)
        # Set to 50% duty cycle for a standard square wave
        self.pwm.value = 0.5
        
        try:
            while True:
                await asyncio.sleep(1.0)
        finally:
            if self.pwm:
                self.pwm.close()
