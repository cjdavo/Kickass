"""Module to support Jikong Smart BMS."""

import asyncio
from collections.abc import Callable
from typing import Final
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str
from custom_components.bms_ble.const import (
    ATTR_BALANCE_CUR,
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLE_CHRG,
    ATTR_CYCLES,
    ATTR_DELTA_VOLTAGE,
    ATTR_POWER,
    ATTR_RUNTIME,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    KEY_CELL_COUNT,
    KEY_CELL_VOLTAGE,
    KEY_TEMP_VALUE,
)
from .basebms import BaseBMS, BMSsample, crc_sum

class BMS(BaseBMS):
    """Jikong Smart BMS class implementation with real-time data retrieval."""

    HEAD_RSP: Final = bytes([0x01, 0x03, 0x00, 0x0A])  # Response header
    HEAD_CMD: Final = bytes([0x01, 0x03, 0x01, 0x01])  # Command header
    BT_MODULE_MSG: Final = bytes([0x41, 0x54, 0x0D, 0x0A])  # AT command filter
    TYPE_POS: Final[int] = 4
    INFO_LEN: Final[int] = 300
    
    _FIELDS: Final[list[tuple[str, int, int, bool, Callable[[int], int | float]]]] = (
        [  # Protocol: JK02_32S; JK02_24S has offset -32
            (ATTR_VOLTAGE, 150, 4, False, lambda x: float(x * 0.251)),
            (ATTR_CURRENT, 158, 4, True, lambda x: float(x * 0.0147)),
            (ATTR_BATTERY_LEVEL, 173, 1, False, lambda x: x),
            (ATTR_CYCLE_CHRG, 174, 4, False, lambda x: float(x * 0.1154)),
            (ATTR_CYCLES, 182, 4, False, lambda x: x),
            (ATTR_TEMPERATURE, 180, 2, False, lambda x: float(x * 0.0078)),
        ]
    )
    
    def __init__(self, ble_device: BLEDevice, reconnect: bool = False) -> None:
        """Initialize private BMS members."""
        super().__init__(__name__, ble_device, reconnect)
        self._data_final: bytearray = bytearray()
        self._char_write_handle: int = -1
        self._bms_info: dict[str, str] = {}
        self._prot_offset: int = 0
        self._valid_reply: int = 0x02

    async def _async_update(self) -> BMSsample:
        """Retrieve real-time battery status information."""
        if not self._data_event.is_set() or self._data_final[4] != 0x02:
            self._log.debug("Requesting battery info...")
            await self._await_reply(
                data=BMS._cmd(b"\x96"), char=self._char_write_handle
            )

        data: BMSsample = self._decode_data(self._data_final, self._prot_offset)
        data.update(BMS._temp_sensors(self._data_final, self._prot_offset))
        data.update(BMS._cell_voltages(self._data_final, int(data[KEY_CELL_COUNT])))

        return data
    
    @staticmethod
    def _cmd(cmd: bytes, value: list[int] | None = None) -> bytes:
        """Assemble a Jikong BMS command."""
        value = [] if value is None else value
        assert len(value) <= 13
        frame = bytes([*BMS.HEAD_CMD, cmd[0]])
        frame += bytes([len(value), *value])
        frame += bytes([0] * (13 - len(value)))
        frame += bytes([crc_sum(frame)])
        return frame

    @staticmethod
    def _decode_data(data: bytearray, offs: int) -> BMSsample:
        """Decode battery management system status."""
        return (
            {
                KEY_CELL_COUNT: int.from_bytes(
                    data[70 + (offs >> 1) : 74 + (offs >> 1)], byteorder="little"
                ).bit_count()
            }
            | {
                ATTR_DELTA_VOLTAGE: int.from_bytes(
                    data[76 + (offs >> 1) : 78 + (offs >> 1)], byteorder="little"
                )
                / 1000
            }
            | {
                key: func(
                    int.from_bytes(
                        data[idx + offs : idx + offs + size],
                        byteorder="little",
                        signed=sign,
                    )
                )
                for key, idx, size, sign, func in BMS._FIELDS
            }
        )
