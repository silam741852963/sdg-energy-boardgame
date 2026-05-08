import asyncio
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from config import CLEANBOOST_MACS, ENERGY_PER_BEACON
from logic.game_state import GameState


class BLEReceiver:
    def __init__(self, game_state: GameState):
        self.game_state = game_state

    def detection_callback(
        self, device: BLEDevice, advertisement_data: AdvertisementData
    ):
        # Triggered every time a BLE beacon is detected
        mac = device.address
        if mac in CLEANBOOST_MACS:
            gen_type = CLEANBOOST_MACS[mac]
            # Emit event to game state
            self.game_state.add_energy(gen_type, ENERGY_PER_BEACON)

    async def start_scanning(self):
        scanner = BleakScanner(self.detection_callback)
        await scanner.start()
        try:
            # Keep the scanner running infinitely
            while True:
                await asyncio.sleep(1.0)
        finally:
            await scanner.stop()
