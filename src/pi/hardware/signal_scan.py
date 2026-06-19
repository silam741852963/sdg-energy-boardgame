import asyncio
from bleak import BleakScanner


CLEANBOOST_DEVICES = {
    "D9:44:B0:92:D4:E0": "CleanBoost 03-02860 (Minor: 2860)",
    "EA:32:68:B2:7F:C1": "CleanBoost 03-02728 (Minor: 2728)",
    "FC:19:F9:E9:EE:7D": "CleanBoost 03-02859 (Minor: 2859)",
    "F7:7D:0B:41:39:A8": "CleanBoost 03-02526 (Minor: 2526)",
}


def detection_callback(device, advertisement_data):
    mac = device.address.upper()
    if mac in CLEANBOOST_DEVICES:
        name = CLEANBOOST_DEVICES[mac]
        rssi = advertisement_data.rssi
        print(
            f"Found {name} | Address: {device.address} | RSSI: {rssi} dBm"
        )


async def run_scanner():
    # The scanner will run until the program is interrupted
    scanner = BleakScanner(detection_callback)

    print("Starting continuous scan... Press Ctrl+C to stop.")
    await scanner.start()

    try:
        # Keep the event loop running
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\nStopping scan...")
    finally:
        await scanner.stop()


if __name__ == "__main__":
    asyncio.run(run_scanner())
