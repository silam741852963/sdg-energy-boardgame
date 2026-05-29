import asyncio
from bleak import BleakScanner


TARGET_MAC = "D9:44:B0:92:D4:E0"


def detection_callback(device, advertisement_data):
    # Case-insensitive comparison is recommended as some backends
    # might return lowercase addresses.
    if device.address.upper() == TARGET_MAC.upper():
        rssi = advertisement_data.rssi
        print(
            f"Target found! Address: {device.address}, RSSI: {rssi}, Name: {device.name}"
        )

        # Optional: Add logic to process the device here
        # For example: print(f"Service Data: {advertisement_data.service_data}")


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
