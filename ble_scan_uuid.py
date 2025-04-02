import asyncio
from bleak import BleakScanner, BleakClient

SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

async def check_device(device):
    try:
        async with BleakClient(device.address) as client:
            services = client.services  # Verwendung der `services`-Eigenschaft statt `get_services()`
            for service in services:
                for characteristic in service.characteristics:
                    if characteristic.uuid.lower() == CHARACTERISTIC_UUID.lower():
                        print(f"Gefundenes Gerät mit passender Characteristic: {device.name} ({device.address})")
                        return
    except Exception as e:
        print(f"Fehler bei {device.address}: {e}")

async def main():
    print("Scanne nach BLE-Geräten...")
    devices = await BleakScanner.discover()
    
    for device in devices:
        await check_device(device)

if __name__ == "__main__":
    asyncio.run(main())
