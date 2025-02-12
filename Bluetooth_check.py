from bleak import BleakClient
import asyncio

SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

async def run(address):
    async with BleakClient(address) as client:
        print("Verbunden!")
        while True:
            value = await client.read_gatt_char(CHARACTERISTIC_UUID)
            print("Empfangene Daten:", value.decode())

if __name__ == "__main__":
    address = "64:e8:33:88:5e:e2"  # Ersetze durch die BLE-Adresse deines ESP32-C3
    asyncio.run(run(address))