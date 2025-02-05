import sys
import asyncio
import threading
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QTextEdit, QLineEdit
from bleak import BleakScanner, BleakClient
import struct

# Global Variables
BMS_MAC_ADDRESS = None  # Will be set after scanning.  C8:47:80:53:44:85
SERVICE_UUID = "0000FFE0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000FFE1-0000-1000-8000-00805f9b34fb"
SERVICE1_UUID = "00001800-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC10_UUID = "00002A00-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC10_UUID = "00002A01-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC10_UUID = "00002A02-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC10_UUID = "00002A04-0000-1000-8000-00805f9b34fb"
CLIENT_CHARACTERISTIC_CONFIG  = "00002902-0000-1000-8000-00805f9b34fb"



COMMANDS = {
    "Read Home Data": "01 03 01 01 00 13 54 3B",
    "Set System Voltage": "01 06 00 10",  # Placeholder
    "Set Battery Type": "01 06 00 20",  # Placeholder
    "CHART_TODAY": "01 03 04 00 00 05 84 F9",
    "NEW_CHART_TODAY": "01 03 04 00 00 05", # from decompiler
    "Clear_historical_data": "01 79 FF FF FF FF 9D 94",
    "Forced_CHECK": "01 06 01 21 01 FF 99 EC",
    "Restore_Factory_Settings": "01 78 FF FF FF FF A0 54",
    "Read_SETTINGS": "01 03 02 01 00 11 E4 7E 15 C0",
    "Forced_CHECK" : "01 06 01 21 01 FF 99 EC",
    "Forced_CHECK1_CLOSE" : "01 06 01 20 00 00 89 FC",
    "Forced_CHECK1_OPEN" : "01 06 01 20 00 01 48 3C",
    "Forced_CHECK3_CLOSE" : "01 06 01 21 FF 00 99 CC",
    "Forced_CHECK3_OPEN" : "01 06 01 21 FF 01 58 0C",
    "Forced_Load_Short" : "01 03 01 21 00 01 D5 FC",
    "MODE_SIZE" : "01 03 00 0B 00 01 F5 C8",
    "OVERDATA" : "01 03 01 01 00 11 D5 FA",
    "SETTING_RETURN" : "01 10 02 00 00 15 00 7E",
    "SETTING_RETURN2" : "01 10 03 00 00 0C C0 48",
    "TODAY_DATA" : "01 03 04 00 00 05"
   
 }
 # Format of the Commands
# 01 → Device Address (Master ID 01)
# 03 → Function Code (03 = Read Holding Registers)
# 00 0A → Starting Register Address (0A = Register 10)
# 00 0B → Number of Registers to Read (11 registers)
# 24 0F → CRC Checksum


# The response is formatted using the Modbus RTU protocol
# ,which follows this general structure:
# Field	Size (bytes)	Description
# Device ID	1 byte	Identifies the device (usually 0x01)
# Function Code	1 byte	0x03 (Read Holding Registers)
# Byte Count	1 byte	Number of bytes in the data payload
# Data	N bytes	Actual sensor or system data
# CRC Checksum	2 bytes	Error-checking value

# Received Response
# 01 03
# 26 00 64 01 0C 0C 82 03
# 5A 33 19 00
# 00 00 00 00 03 (14-18) order 14,17,18,15,16
# F2 03 91 0B 26 00 00 00 02 00 00 00 01 00 00 26 1D 00 00 00 00 86 DC

# if (str.startsWith("01 03 04")) {
#          if (str.equals("01 03 04 00 00 05 " + Utils.getCRC(Command.TODAY_DATA))) {
#             this.mHomeFragment.setTodayData(strArr);}
# if (str.startsWith("01 10 02 02 00 10 20")) {
#            this.mSettingFragment.sucess();}



# Breakdown of the Response:
# Field	Value (Hex)	Description
# Device ID	01	Device address (01)
# Function Code	03	Read Holding Registers (03)
# Byte Count	26 (38 bytes)	Number of data bytes
# Data	00 64 ... 00 00 00 00	Sensor data (Parsed below)
# CRC Checksum	86 DC	Error-checking value

# Possible Parameter Mapping
# Index (Bytes)	Value (Hex)	Converted Value	Possible Meaning
# 00 64	100     (dec)	Voltage (10.0V?)	ratio 10?
# 01 0C	268     (dec)	Current (2.68A?)	
# 0C 82	3202    (dec)	Temperature (32.02°C?)	multiply by 1.8 and add 32
# 03 5A	858     (dec)	Charge Power (85.8W?)	
# 33 19	13081   (dec)	Total Energy?	
# 00 00 00 00	0	Empty/Reserved	
# 00 03	3       (dec)	Device Status	
# F2 03	Unknown	Unknown Parameter	
# 91 0B	4491    (dec)	Load Power?	
# 26 00	Unknown	Unknown	
# 00 00	0	Empty	
# 02 00	2	Status Flag?	
# 00 00	0	Empty	
# 00 01	1	Relay State (ON?)	
# 00 00	0	Empty	
# 26 1D	9757    (dec)	Battery Capacity?	
# 00 00 00 00	0	    Empty/Reserved	
# success message "01 10 02 02 00 10 20"

# 01 03 26 
# 00 64 conversion 100
# 01 0f conversion 271
# 00 00 00 00
# 17 conversion 23 controller temperature
# 19 conversion 25 battery temperature
# 00 00 00
# 00 00 00 00 00 00 00 00 00 00 00 00 00 
# 00 00 00 01 00 00 1a f7 00 00 00 00 06 d4

def decode_bms_response(hex_response):
    """
    Decodes a Modbus RTU response from the BMS device.
    """
    try:
        response_bytes = bytes.fromhex(hex_response)
        
        if len(response_bytes) < 23:
            return "Invalid response length"
        
        battery_voltage_raw = int.from_bytes(response_bytes[5:7], byteorder="big")
        battery_current_raw = int.from_bytes(response_bytes[5:7], byteorder="big")
        battery_temperature_raw = response_bytes[12]
        charge_power_raw = int.from_bytes(response_bytes[9:11], byteorder="big")
        controller_temperature_raw = response_bytes[11]
        
        battery_voltage = battery_voltage_raw * 1
        battery_current = battery_current_raw * 1
        battery_temperature = battery_temperature_raw * 1
        charge_power = charge_power_raw * 1
        controller_temperature = controller_temperature_raw
        
        return (f"Battery Voltage: {battery_voltage:.2f}V\n"
                f"Battery Current: {battery_current:.2f}A\n"
                f"Battery Temperature: {battery_temperature:.2f}°C\n"
                f"Charge Power: {charge_power:.2f}W\n"
                f"Controller Temperature: {controller_temperature}°C\n"
                f"Battery Voltage_raw: {battery_voltage_raw:.2f}V\n"
                f"Battery Current_raw: {battery_current_raw:.2f}A\n"
                f"Battery Temperature_raw: {battery_temperature_raw:.2f}°C\n"
                f"Charge Power_raw: {charge_power_raw:.2f}W\n"
                f"Controller Temperature_raw: {controller_temperature_raw}°C")
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
            print(f"Device: {device.name} - {device.address}")
            if device.name and ("BMS" in device.name or "MPPT" in device.name):
                BMS_MAC_ADDRESS = device.address
                self.device_label.setText(f"Selected Device: {BMS_MAC_ADDRESS}")

                async with BleakClient(BMS_MAC_ADDRESS) as client:
                    if await client.is_connected():
                        services = await client.get_services()
                        for service in services:
                            print(f"Service: {service.uuid}")
                            for char in service.characteristics:
                                print(f"  Characteristic: {char.uuid} - {char.properties}")
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
                await client.start_notify(CHARACTERISTIC_UUID, self.notification_handler)  # ✅ Start notifications
                await client.write_gatt_char(CHARACTERISTIC_UUID, command_bytes)
                self.response_area.append(f"Sent: {command_hex}")

                await asyncio.sleep(5)  # ✅ Allow time for response
                await client.stop_notify(CHARACTERISTIC_UUID)
                
    async def notification_handler(self, sender, data):
        """Handles incoming BLE notifications."""
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