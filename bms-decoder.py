import sys
import asyncio
import threading
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QTextEdit, QLineEdit
from bleak import BleakScanner, BleakClient
import struct

# Global Variables
BMS_MAC_ADDRESS = None  # Will be set after scanning
SERVICE_UUID = "0000FFE0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000FFE1-0000-1000-8000-00805f9b34fb"

COMMANDS = {
    "Read Home Data": "01 03 01 01 00 13 54 3B",
    "Set System Voltage": "01 06 00 10",  # Placeholder
    "Set Battery Type": "01 06 00 20"  # Placeholder
}

def decode_bms_response(hex_response):
    """
    Decodes a Modbus RTU response from the BMS device.
    """
    try:
        response_bytes = bytes.fromhex(hex_response)
        
        if len(response_bytes) < 10:
            return "Invalid response length"
        
        battery_voltage_raw = int.from_bytes(response_bytes[5:7], byteorder="big")  # Read 2 bytes
        controller_temperature_raw = response_bytes[11]  # 33 -> Controller temp
        battery_temperature_raw = response_bytes[12]  # 19 -> Battery temp
        
        return (f"Battery Voltage: {battery_voltage_raw} (Raw)\n"
                f"Controller Temperature: {controller_temperature_raw} (Raw)\n"
                f"Battery Temperature: {battery_temperature_raw} (Raw)")
    except Exception as e:
        return f"Error decoding response: {str(e)}"

class BluetoothBMSGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Bluetooth BMS Tool")
        self.setGeometry(200, 200, 400, 400)

        self.layout = QVBoxLayout()

        self.scan_button = QPushButton("Scan for Bluetooth Devices", self)
        self.scan_button.clicked.connect(self.scan_devices)
        self.layout.addWidget(self.scan_button)

        self.device_label = QLabel("No device selected", self)
        self.layout.addWidget(self.device_label)

        self.send_button = QPushButton("Request Home Data", self)
        self.send_button.clicked.connect(self.send_command)
        self.layout.addWidget(self.send_button)
        
        self.voltage_input = QLineEdit(self)
        self.voltage_input.setPlaceholderText("Enter System Voltage")
        self.layout.addWidget(self.voltage_input)
        
        self.set_voltage_button = QPushButton("Set System Voltage", self)
        self.set_voltage_button.clicked.connect(self.set_system_voltage)
        self.layout.addWidget(self.set_voltage_button)
        
        self.battery_type_input = QLineEdit(self)
        self.battery_type_input.setPlaceholderText("Enter Battery Type")
        self.layout.addWidget(self.battery_type_input)
        
        self.set_battery_button = QPushButton("Set Battery Type", self)
        self.set_battery_button.clicked.connect(self.set_battery_type)
        self.layout.addWidget(self.set_battery_button)
        
        self.response_area = QTextEdit(self)
        self.response_area.setReadOnly(True)
        self.layout.addWidget(self.response_area)

        self.setLayout(self.layout)

    def scan_devices(self):
        scan_thread = threading.Thread(target=asyncio.run, args=(self.scan_devices_async(),))
        scan_thread.start()

    async def scan_devices_async(self):
        global BMS_MAC_ADDRESS
        self.device_label.setText("Scanning...")
        devices = await BleakScanner.discover()
        for device in devices:
            if device.name and ("BMS" in device.name or "MPPT" in device.name):
                BMS_MAC_ADDRESS = device.address
                self.device_label.setText(f"Selected Device: {BMS_MAC_ADDRESS}")
                return
        self.device_label.setText("No BMS found")

    def send_command(self):
        command_thread = threading.Thread(target=asyncio.run, args=(self.send_command_async(),))
        command_thread.start()

    async def send_command_async(self):
        if not BMS_MAC_ADDRESS:
            self.response_area.setText("No device selected. Scan first.")
            return
        
        command_hex = COMMANDS["Read Home Data"]
        command_bytes = bytes.fromhex(command_hex)

        async with BleakClient(BMS_MAC_ADDRESS) as client:
            if await client.is_connected():
                self.response_area.append(f"Connected to {BMS_MAC_ADDRESS}")
                await client.start_notify(CHARACTERISTIC_UUID, self.notification_handler)  # Enable notifications
                await client.write_gatt_char(CHARACTERISTIC_UUID, command_bytes)
                self.response_area.append(f"Sent: {command_hex}")
                await asyncio.sleep(5)
                await client.stop_notify(CHARACTERISTIC_UUID)

    async def notification_handler(self, sender, data):
        hex_data = data.hex()
        self.response_area.append(f"Received: {hex_data}")
        decoded_response = decode_bms_response(hex_data)
        self.response_area.append(decoded_response)

    def set_system_voltage(self):
        voltage = self.voltage_input.text()
        command_hex = COMMANDS["Set System Voltage"] + voltage.zfill(4)
        command_thread = threading.Thread(target=asyncio.run, args=(self.send_custom_command(command_hex),))
        command_thread.start()

    def set_battery_type(self):
        battery_type = self.battery_type_input.text()
        command_hex = COMMANDS["Set Battery Type"] + battery_type.zfill(4)
        command_thread = threading.Thread(target=asyncio.run, args=(self.send_custom_command(command_hex),))
        command_thread.start()

    async def send_custom_command(self, command_hex):
        if not BMS_MAC_ADDRESS:
            self.response_area.setText("No device selected. Scan first.")
            return
        command_bytes = bytes.fromhex(command_hex)
        async with BleakClient(BMS_MAC_ADDRESS) as client:
            if await client.is_connected():
                self.response_area.append(f"Sending: {command_hex}")
                await client.write_gatt_char(CHARACTERISTIC_UUID, command_bytes)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BluetoothBMSGUI()
    window.show()
    sys.exit(app.exec())
