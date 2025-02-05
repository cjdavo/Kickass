import sys
import asyncio
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QTextEdit, QComboBox
from bleak import BleakScanner, BleakClient

# Global Variables
BMS_MAC_ADDRESS = None  # Will be set after scanning
SERVICE_UUID = "0000FFE0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000FFE1-0000-1000-8000-00805f9b34fb"


COMMANDS = {
    "Read Home Data": "01 03 01 01 00 13 54 3B"
}

def decode_bms_response(hex_response):
    response_bytes = bytes.fromhex(hex_response)
    battery_voltage_raw = int.from_bytes(response_bytes[3:5], byteorder="big")
    battery_current_raw = int.from_bytes(response_bytes[5:7], byteorder="big")
    battery_temperature_raw = int.from_bytes(response_bytes[7:9], byteorder="big")
    charge_power_raw = int.from_bytes(response_bytes[9:11], byteorder="big")
    controller_temperature_raw = response_bytes[21]
    
    battery_voltage = battery_voltage_raw * 0.251
    battery_current = battery_current_raw * 0.0147
    battery_temperature = battery_temperature_raw * 0.0078
    charge_power = charge_power_raw * 0.1154
    controller_temperature = controller_temperature_raw
    
    return (f"Battery Voltage: {battery_voltage:.2f}V\n"
            f"Battery Current: {battery_current:.2f}A\n"
            f"Battery Temperature: {battery_temperature:.2f}°C\n"
            f"Charge Power: {charge_power:.2f}W\n"
            f"Controller Temperature: {controller_temperature}°C")

class BluetoothBMSGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Bluetooth BMS Tool")
        self.setGeometry(200, 200, 400, 300)

        self.layout = QVBoxLayout()

        self.scan_button = QPushButton("Scan for Bluetooth Devices", self)
        self.scan_button.clicked.connect(self.scan_devices)
        self.layout.addWidget(self.scan_button)

        self.device_label = QLabel("No device selected", self)
        self.layout.addWidget(self.device_label)

        self.send_button = QPushButton("Request Home Data", self)
        self.send_button.clicked.connect(self.send_command)
        self.layout.addWidget(self.send_button)

        self.response_area = QTextEdit(self)
        self.response_area.setReadOnly(True)
        self.layout.addWidget(self.response_area)

        self.setLayout(self.layout)

    async def scan_devices_async(self):
        global BMS_MAC_ADDRESS
        self.device_label.setText("Scanning...")
        devices = await BleakScanner.discover()
        for device in devices:
            if "BMS" in device.name or "MPPT" in device.name:
                BMS_MAC_ADDRESS = device.address
                self.device_label.setText(f"Selected Device: {BMS_MAC_ADDRESS}")
                return
        self.device_label.setText("No BMS found")

    def scan_devices(self):
        asyncio.create_task(self.scan_devices_async())

    async def send_command_async(self):
        if not BMS_MAC_ADDRESS:
            self.response_area.setText("No device selected. Scan first.")
            return
        
        command_hex = COMMANDS["Read Home Data"]
        command_bytes = bytes.fromhex(command_hex)

        async with BleakClient(BMS_MAC_ADDRESS) as client:
            if await client.is_connected():
                self.response_area.append(f"Connected to {BMS_MAC_ADDRESS}")
                await client.write_gatt_char(CHARACTERISTIC_UUID, command_bytes)
                self.response_area.append(f"Sent: {command_hex}")

                def notification_handler(sender, data):
                    hex_data = data.hex()
                    self.response_area.append(f"Received: {hex_data}")
                    decoded_response = decode_bms_response(hex_data)
                    self.response_area.append(decoded_response)
                
                await client.start_notify(CHARACTERISTIC_UUID, notification_handler)
                await asyncio.sleep(5)
                await client.stop_notify(CHARACTERISTIC_UUID)
            else:
                self.response_area.append("Failed to connect.")

    def send_command(self):
        asyncio.create_task(self.send_command_async())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BluetoothBMSGUI()
    window.show()
    sys.exit(app.exec())
