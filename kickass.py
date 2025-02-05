import asyncio
from bleak import BleakClient

# Replace with your BMS Bluetooth MAC address
# BMS_MAC_ADDRESS = "C8:47:80:53:44:85"  # Change to actual BMS MAC address A4:C1:38:AF:32:0D
BMS_MAC_ADDRESS = "C8:47:80:53:44:85"

# Replace with actual UUIDs from your BMS using a BLE scanner
SERVICE_UUID = "0000FFE0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000FFE1-0000-1000-8000-00805f9b34fb"

# Modbus RTU Command to Read Home Data
HOME_DATA_CMD = bytes.fromhex("01 03 01 01 00 13 54 3B")

async def send_command_async():
    async with BleakClient(BMS_MAC_ADDRESS) as client:
        if await client.is_connected():
            print(f"Connected to BMS: {BMS_MAC_ADDRESS}")

            # Enable Notifications for Receiving Data
            def notification_handler(sender, data):
                print(f"Received: {data.hex()}")

            await client.start_notify(CHARACTERISTIC_UUID, notification_handler)

            # Send Command
            print(f"Sending Command: {HOME_DATA_CMD.hex()}")
            await client.write_gatt_char(CHARACTERISTIC_UUID, HOME_DATA_CMD)

            # Wait for response
            await asyncio.sleep(5)  # Wait to receive data
            
            await client.stop_notify(CHARACTERISTIC_UUID)

        else:
            print("Failed to connect to BMS.")

# ✅ Fix: Run inside an existing event loop
try:
    loop = asyncio.get_running_loop()  # Check if an event loop is already running
    task = loop.create_task(send_command_async())  # Run the task without blocking
except RuntimeError:  # If no event loop is running, create one
    asyncio.run(send_command_async())
