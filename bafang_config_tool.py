#!/usr/bin/env python3

"""Single-file Bafang controller backend and command-line tool."""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import ClassVar

import serial


LOG = logging.getLogger("bafang_config_tool")
DEFAULT_BAUDRATE = 1200
DEFAULT_TIMEOUT_SECONDS = 2


def _append_u8_checksum(send_data: bytes) -> bytes:
    """Append modulo-256 checksum for all bytes except the command byte."""
    checksum = sum(send_data[1:]) & 0xFF
    return send_data + bytes([checksum])


def _is_length_and_u8_checksum_correct(read_data: bytes) -> bool:
    """Check frame length and checksum."""
    checksum_correct = (sum(read_data[:-1]) & 0xFF) == int(read_data[-1])
    length_correct = len(read_data) == 1 + 1 + int(read_data[1]) + 1
    return checksum_correct and length_correct


def _decode_ascii(raw: bytes, start: int, length: int) -> str:
    return bytes(raw[start : start + length]).decode("ascii", errors="replace").strip("\x00 ")


def _hex_dump(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


@dataclass(slots=True)
class GeneralControllerData:
    """GEN block (general/controller info) values from Bafang controller."""

    manufacturer: str
    model: str
    hardware_version: str
    firmware_version: str
    nominal_voltage_code: int
    nominal_voltage_str: str
    cut_off_voltage_min: int
    cut_off_voltage_max: int
    max_current_amps: int

    BLOCK_ID: ClassVar[int] = 0x51
    GEN_FRAME_DATA_LEN: ClassVar[int] = 0x10
    SERIAL_CMD_READ_GEN: ClassVar[bytes] = bytes([0x11, BLOCK_ID, 0x04, 0xB0])

    @staticmethod
    def _map_nominal_voltage_data(code: int) -> tuple[str, int, int]:
        if code == 0:
            return "24V", 18, 22
        if code == 1:
            return "36V", 28, 32
        if code == 2:
            return "48V", 38, 43
        if code == 3:
            return "60V", 48, 55
        if code == 4:
            return "24-48V", 18, 43
        return "24-60V", 18, 55

    @classmethod
    def _from_frame(cls, frame: bytes) -> GeneralControllerData:
        if int(frame[0]) != cls.BLOCK_ID:
            raise ValueError(f"Unexpected block id 0x{int(frame[0]):02X}, expected 0x{cls.BLOCK_ID:02X}")
        if int(frame[1]) != cls.GEN_FRAME_DATA_LEN:
            raise ValueError(f"GEN response too short: {int(frame[1])} bytes")
        if not _is_length_and_u8_checksum_correct(frame):
            raise ValueError(f"Invalid frame (length or checksum): {_hex_dump(frame)}")

        nominal_voltage_code = frame[16]
        nominal_voltage_str, cut_off_voltage_min, cut_off_voltage_max = cls._map_nominal_voltage_data(
            nominal_voltage_code
        )

        return cls(
            manufacturer=_decode_ascii(frame, 2, 4),
            model=_decode_ascii(frame, 6, 4),
            hardware_version=f"V{chr(frame[10])}.{chr(frame[11])}",
            firmware_version=f"V{chr(frame[12])}.{chr(frame[13])}.{chr(frame[14])}.{chr(frame[15])}",
            nominal_voltage_code=nominal_voltage_code,
            nominal_voltage_str=nominal_voltage_str,
            cut_off_voltage_min=cut_off_voltage_min,
            cut_off_voltage_max=cut_off_voltage_max,
            max_current_amps=frame[17],
        )

    @classmethod
    def read_from_controller(cls, ser: serial.Serial) -> GeneralControllerData:
        if not ser.is_open:
            raise ValueError("Serial port must be open")

        request = _append_u8_checksum(cls.SERIAL_CMD_READ_GEN)
        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.write(request)
        ser.flush()
        time.sleep(0.2)

        frame = ser.read(3 + cls.GEN_FRAME_DATA_LEN)
        if not frame:
            raise TimeoutError("No response received for GEN request")

        return cls._from_frame(frame)

    def to_json_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json_dict(cls, data: dict) -> GeneralControllerData:
        return cls(**data)

    def to_pretty_string(self) -> str:
        lines = [
            "Bafang Controller General Info",
            "------------------------------",
            f"Block ID:            0x{self.BLOCK_ID:02X}",
            f"Manufacturer:        {self.manufacturer}",
            f"Model:               {self.model}",
            f"Hardware version:    {self.hardware_version}",
            f"Firmware version:    {self.firmware_version}",
            f"Nominal voltage:     {self.nominal_voltage_str}, (code {self.nominal_voltage_code})",
            f"Cut-off voltage:     {self.cut_off_voltage_min}V - {self.cut_off_voltage_max}V",
            f"Max current:         {self.max_current_amps} A",
        ]
        return "\n".join(lines)


@dataclass(slots=True)
class BasicControllerData:
    """BAS block (basic parameters) values from Bafang controller."""

    low_battery_protect: int
    current_limit_amps: int
    assist_current_limits: tuple[int, int, int, int, int, int, int, int, int, int]
    assist_speed_limits: tuple[int, int, int, int, int, int, int, int, int, int]
    wheel_diameter_code: int
    speed_meter_type: int
    speed_meter_signals: int

    BLOCK_ID: ClassVar[int] = 0x52
    BAS_FRAME_DATA_LEN: ClassVar[int] = 0x18
    SERIAL_CMD_READ_BAS: ClassVar[bytes] = bytes([0x11, BLOCK_ID])

    SPEED_METER_TYPE_TO_TEXT: ClassVar[dict[int, str]] = {
        0: "External, Wheel Meter",
        1: "Internal, Motor Meter",
        3: "By Motor Phase",
    }
    BAS_WRITE_STATUS_TEXT: ClassVar[dict[int, str]] = {
        0: "Error: Low Battery Protection out of range.",
        1: "Error: Current Limit out of range.",
        2: "Error: Current Limit for Pedal assist level 0 out of range.",
        3: "Error: Speed Limit for Pedal assist level 0 out of range.",
        4: "Error: Current Limit for Pedal assist level 1 out of range.",
        5: "Error: Speed Limit for Pedal assist level 1 out of range.",
        6: "Error: Current Limit for Pedal assist level 2 out of range.",
        7: "Error: Speed Limit for Pedal assist level 2 out of range.",
        8: "Error: Current Limit for Pedal assist level 3 out of range.",
        9: "Error: Speed Limit for Pedal assist level 3 out of range.",
        10: "Error: Current Limit for Pedal assist level 4 out of range.",
        11: "Error: Speed Limit for Pedal assist level 4 out of range.",
        12: "Error: Current Limit for Pedal assist level 5 out of range.",
        13: "Error: Speed Limit for Pedal assist level 5 out of range.",
        14: "Error: Current Limit for Pedal assist level 6 out of range.",
        15: "Error: Speed Limit for Pedal assist level 6 out of range.",
        16: "Error: Current Limit for Pedal assist level 7 out of range.",
        17: "Error: Speed Limit for Pedal assist level 7 out of range.",
        18: "Error: Current Limit for Pedal assist level 8 out of range.",
        19: "Error: Speed Limit for Pedal assist level 8 out of range.",
        20: "Error: Current Limit for Pedal assist level 9 out of range.",
        21: "Error: Speed Limit for Pedal assist level 9 out of range.",
        22: "Error: Wheel Diameter out of range.",
        23: "Error: Speed Meter Signals out of range.",
        24: "Success: Basic flash write successful.",
    }
    WHEEL_DIAMETER_CODE_TO_TEXT: ClassVar[dict[int, str]] = {
        31: "16 inch", 32: "16 inch",
        33: "17 inch", 34: "17 inch",
        35: "18 inch", 36: "18 inch",
        37: "19 inch", 38: "19 inch",
        39: "20 inch", 40: "20 inch",
        41: "21 inch", 42: "21 inch",
        43: "22 inch", 44: "22 inch",
        45: "23 inch", 46: "23 inch",
        47: "24 inch", 48: "24 inch",
        49: "25 inch", 50: "25 inch",
        51: "26 inch", 52: "26 inch",
        53: "27 inch", 54: "27 inch",
        55: "700C", 56: "28 inch",
        57: "29 inch", 58: "29 inch",
        59: "30 inch", 60: "30 inch",
    }

    @classmethod
    def _from_frame(cls, frame: bytes) -> BasicControllerData:
        if int(frame[0]) != cls.BLOCK_ID:
            raise ValueError(f"Unexpected block id 0x{int(frame[0]):02X}, expected 0x{cls.BLOCK_ID:02X}")
        if int(frame[1]) != cls.BAS_FRAME_DATA_LEN:
            raise ValueError(f"BAS response data length unexpected: {int(frame[1])} bytes")
        if not _is_length_and_u8_checksum_correct(frame):
            raise ValueError(f"Invalid frame (length or checksum): {_hex_dump(frame)}")

        return cls(
            low_battery_protect=frame[2],
            current_limit_amps=frame[3],
            assist_current_limits=(
                frame[4], frame[5], frame[6], frame[7], frame[8],
                frame[9], frame[10], frame[11], frame[12], frame[13],
            ),
            assist_speed_limits=(
                frame[14], frame[15], frame[16], frame[17], frame[18],
                frame[19], frame[20], frame[21], frame[22], frame[23],
            ),
            wheel_diameter_code=frame[24],
            speed_meter_type=int(frame[25]) // 64,
            speed_meter_signals=int(frame[25]) % 64,
        )

    @classmethod
    def read_from_controller(cls, ser: serial.Serial) -> BasicControllerData:
        if not ser.is_open:
            raise ValueError("Serial port must be open")

        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.write(cls.SERIAL_CMD_READ_BAS)
        ser.flush()
        time.sleep(0.2)

        frame = ser.read(3 + cls.BAS_FRAME_DATA_LEN)
        if not frame:
            raise TimeoutError("No response received for BAS request")

        return cls._from_frame(frame)

    def write_to_controller(self, ser: serial.Serial) -> str:
        if not ser.is_open:
            raise ValueError("Serial port must be open")
        if len(self.assist_current_limits) != 10:
            raise ValueError("assist_current_limits must contain exactly 10 values")
        if len(self.assist_speed_limits) != 10:
            raise ValueError("assist_speed_limits must contain exactly 10 values")

        speed_meter_type_raw = self.speed_meter_type
        if speed_meter_type_raw == 2:
            speed_meter_type_raw = 3
        if speed_meter_type_raw not in (0, 1, 3):
            raise ValueError(f"speed_meter_type must be one of 0, 1, 3 (or 2), got {self.speed_meter_type}")
        if not (0 <= self.speed_meter_signals <= 63):
            raise ValueError(f"speed_meter_signals must be in range 0..63, got {self.speed_meter_signals}")

        payload = [
            self.low_battery_protect,
            self.current_limit_amps,
            *self.assist_current_limits,
            *self.assist_speed_limits,
            self.wheel_diameter_code,
            speed_meter_type_raw * 64 + self.speed_meter_signals,
        ]
        for idx, value in enumerate(payload):
            if not (0 <= int(value) <= 255):
                raise ValueError(f"BAS payload byte out of range at index {idx}: {value}")

        request = _append_u8_checksum(bytes([0x16, self.BLOCK_ID, self.BAS_FRAME_DATA_LEN, *payload]))

        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.write(request)
        ser.flush()
        time.sleep(1.0)

        response = ser.read(2)
        if len(response) < 2:
            raise TimeoutError("No response received for BAS write request")
        if int(response[0]) != self.BLOCK_ID:
            raise ValueError(
                f"Unexpected BAS write response block id 0x{int(response[0]):02X}, expected 0x{self.BLOCK_ID:02X}"
            )

        status_code = int(response[1])
        return self.BAS_WRITE_STATUS_TEXT.get(status_code, f"Unknown BAS write status code: {status_code}")

    @classmethod
    def wheel_diameter_text_from_code(cls, code: int) -> str:
        return cls.WHEEL_DIAMETER_CODE_TO_TEXT.get(code, f"raw={code}")

    @classmethod
    def speed_meter_type_text_from_index(cls, index: int) -> str:
        return cls.SPEED_METER_TYPE_TO_TEXT.get(index, f"Unknown ({index})")

    def to_json_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json_dict(cls, data: dict) -> BasicControllerData:
        data["assist_current_limits"] = tuple(data["assist_current_limits"])
        data["assist_speed_limits"] = tuple(data["assist_speed_limits"])
        return cls(**data)

    def to_pretty_string(self) -> str:
        current_limits = ", ".join(str(value) for value in self.assist_current_limits)
        speed_limits = ", ".join(str(value) for value in self.assist_speed_limits)
        lines = [
            "Bafang Basic Parameters",
            "-----------------------",
            f"Block ID:              0x{self.BLOCK_ID:02X}",
            f"Low battery protect:   {self.low_battery_protect} V",
            f"Current limit:         {self.current_limit_amps} A",
            f"Assist current [%]:    [{current_limits}]",
            f"Assist speed [%]:      [{speed_limits}]",
            f"Wheel diameter:        {self.wheel_diameter_text_from_code(self.wheel_diameter_code)} (raw {self.wheel_diameter_code})",
            f"Speed meter type:      {self.speed_meter_type_text_from_index(self.speed_meter_type)} (raw {self.speed_meter_type})",
            f"Speed meter signals:   {self.speed_meter_signals}",
        ]
        return "\n".join(lines)


@dataclass(slots=True)
class PedalAssistControllerData:
    """PAS block (pedal assist parameters) values from Bafang controller."""

    pedal_sensor_type: int
    designated_assist: int
    speed_limit: int
    start_current_pct: int
    slow_start_mode: int
    start_degree: int
    work_mode: int
    stop_delay: int
    current_decay: int
    stop_decay: int
    keep_current_pct: int

    BLOCK_ID: ClassVar[int] = 0x53
    PAS_FRAME_DATA_LEN: ClassVar[int] = 0x0B
    SERIAL_CMD_READ_PAS: ClassVar[bytes] = bytes([0x11, 0x53])

    PEDAL_SENSOR_TYPE_TO_TEXT: ClassVar[dict[int, str]] = {
        0: "None",
        1: "DH-Sensor-12",
        2: "BB-Sensor-32",
        3: "DoubleSignal-24",
    }
    PAS_WRITE_STATUS_TEXT: ClassVar[dict[int, str]] = {
        0: "Error: Pedal Sensor Type error.",
        1: "Error: Designated Assist Level error.",
        2: "Error: Speed Limit error.",
        3: "Error: Start Current out of range.",
        4: "Error: Slow-start Mode error.",
        5: "Error: Start Degree out of range.",
        6: "Error: Work Mode error.",
        7: "Error: Stop Delay out of range.",
        8: "Error: Current Decay out of range.",
        9: "Error: Stop Decay out of range.",
        10: "Error: Keep Current out of range.",
        11: "Success: Pedal Assist flash write successful.",
    }

    @classmethod
    def _from_frame(cls, frame: bytes) -> PedalAssistControllerData:
        if int(frame[0]) != cls.BLOCK_ID:
            raise ValueError(f"Unexpected block id 0x{int(frame[0]):02X}, expected 0x{cls.BLOCK_ID:02X}")
        if int(frame[1]) != cls.PAS_FRAME_DATA_LEN:
            raise ValueError(f"PAS response data length unexpected: {int(frame[1])} bytes")
        if not _is_length_and_u8_checksum_correct(frame):
            raise ValueError(f"Invalid frame (length or checksum): {_hex_dump(frame)}")

        return cls(
            pedal_sensor_type=frame[2],
            designated_assist=frame[3],
            speed_limit=frame[4],
            start_current_pct=frame[5],
            slow_start_mode=frame[6],
            start_degree=frame[7],
            work_mode=frame[8],
            stop_delay=frame[9],
            current_decay=frame[10],
            stop_decay=frame[11],
            keep_current_pct=frame[12],
        )

    @classmethod
    def read_from_controller(cls, ser: serial.Serial) -> PedalAssistControllerData:
        if not ser.is_open:
            raise ValueError("Serial port must be open")

        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.write(cls.SERIAL_CMD_READ_PAS)
        ser.flush()
        time.sleep(0.2)

        frame = ser.read(3 + cls.PAS_FRAME_DATA_LEN)
        if not frame:
            raise TimeoutError("No response received for PAS request")

        return cls._from_frame(frame)

    @classmethod
    def pedal_sensor_text_from_type(cls, code: int) -> str:
        return cls.PEDAL_SENSOR_TYPE_TO_TEXT.get(code, f"Unknown ({code})")

    @staticmethod
    def _fmt_by_display(raw: int, unit: str = "") -> str:
        return "By Display's Command" if raw == 255 else f"{raw}{unit}"

    @staticmethod
    def _fmt_work_mode(raw: int) -> str:
        return "Undetermined" if raw == 255 else f"{raw} RPM"

    def write_to_controller(self, ser: serial.Serial) -> str:
        if not ser.is_open:
            raise ValueError("Serial port must be open")
        if not (0 <= self.pedal_sensor_type <= 3):
            raise ValueError(f"pedal_sensor_type must be 0-3, got {self.pedal_sensor_type}")
        if not (self.designated_assist == 255 or 0 <= self.designated_assist <= 9):
            raise ValueError(f"designated_assist must be 0-9 or 255, got {self.designated_assist}")
        if not (self.speed_limit == 255 or 15 <= self.speed_limit <= 40):
            raise ValueError(f"speed_limit must be 15-40 or 255, got {self.speed_limit}")
        if not (1 <= self.start_current_pct <= 20):
            raise ValueError(f"start_current_pct must be 1-20, got {self.start_current_pct}")
        if not (1 <= self.slow_start_mode <= 8):
            raise ValueError(f"slow_start_mode must be 1-8, got {self.slow_start_mode}")
        if not (1 <= self.start_degree <= 100):
            raise ValueError(f"start_degree must be 1-100, got {self.start_degree}")
        if not (self.work_mode == 255 or 10 <= self.work_mode <= 80):
            raise ValueError(f"work_mode must be 10-80 or 255, got {self.work_mode}")

        payload = [
            self.pedal_sensor_type,
            self.designated_assist,
            self.speed_limit,
            self.start_current_pct,
            self.slow_start_mode,
            self.start_degree,
            self.work_mode,
            self.stop_delay,
            self.current_decay,
            self.stop_decay,
            self.keep_current_pct,
        ]
        for idx, value in enumerate(payload):
            if not (0 <= int(value) <= 255):
                raise ValueError(f"PAS payload byte out of range at index {idx}: {value}")

        request = _append_u8_checksum(bytes([0x16, self.BLOCK_ID, self.PAS_FRAME_DATA_LEN, *payload]))

        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.write(request)
        ser.flush()
        time.sleep(1.0)

        response = ser.read(2)
        if len(response) < 2:
            raise TimeoutError("No response received for PAS write request")
        if int(response[0]) != self.BLOCK_ID:
            raise ValueError(
                f"Unexpected PAS write response block id 0x{int(response[0]):02X}, expected 0x{self.BLOCK_ID:02X}"
            )

        status_code = int(response[1])
        return self.PAS_WRITE_STATUS_TEXT.get(status_code, f"Unknown PAS write status code: {status_code}")

    def to_json_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json_dict(cls, data: dict) -> PedalAssistControllerData:
        return cls(**data)

    def to_pretty_string(self) -> str:
        lines = [
            "Bafang Pedal Assist Parameters",
            "------------------------------",
            f"Block ID:              0x{self.BLOCK_ID:02X}",
            f"Pedal sensor type:     {self.pedal_sensor_text_from_type(self.pedal_sensor_type)} (raw {self.pedal_sensor_type})",
            f"Designated assist:     {self._fmt_by_display(self.designated_assist)}",
            f"Speed limit:           {self._fmt_by_display(self.speed_limit, ' km/h')}",
            f"Start current:         {self.start_current_pct} %",
            f"Slow start mode:       {self.slow_start_mode}",
            f"Start degree:          {self.start_degree} deg",
            f"Work mode:             {self._fmt_work_mode(self.work_mode)}",
            f"Stop delay:            {self.stop_delay}",
            f"Current decay:         {self.current_decay}",
            f"Stop decay:            {self.stop_decay}",
            f"Keep current:          {self.keep_current_pct} %",
        ]
        return "\n".join(lines)


@dataclass(slots=True)
class ThrottleControllerData:
    """THR block (throttle handle parameters) values from Bafang controller."""

    start_voltage: int
    end_voltage: int
    mode: int
    assist_level: int
    speed_limit: int
    start_current_pct: int

    BLOCK_ID: ClassVar[int] = 0x54
    THR_FRAME_DATA_LEN: ClassVar[int] = 0x06
    SERIAL_CMD_READ_THR: ClassVar[bytes] = bytes([0x11, 0x54])

    MODE_TO_TEXT: ClassVar[dict[int, str]] = {
        0: "Speed",
        1: "Current",
    }
    THR_WRITE_STATUS_TEXT: ClassVar[dict[int, str]] = {
        0: "Error: Start Voltage out of range.",
        1: "Error: End Voltage out of range.",
        2: "Error: Mode error.",
        3: "Error: Designated Assist error.",
        4: "Error: Speed Limit error.",
        5: "Error: Start Current out of range.",
        6: "Success: Throttle Handle flash write successful.",
    }

    @classmethod
    def _from_frame(cls, frame: bytes) -> ThrottleControllerData:
        if int(frame[0]) != cls.BLOCK_ID:
            raise ValueError(f"Unexpected block id 0x{int(frame[0]):02X}, expected 0x{cls.BLOCK_ID:02X}")
        if int(frame[1]) != cls.THR_FRAME_DATA_LEN:
            raise ValueError(f"THR response data length unexpected: {int(frame[1])} bytes")
        if not _is_length_and_u8_checksum_correct(frame):
            raise ValueError(f"Invalid frame (length or checksum): {_hex_dump(frame)}")

        return cls(
            start_voltage=frame[2],
            end_voltage=frame[3],
            mode=frame[4],
            assist_level=frame[5],
            speed_limit=frame[6],
            start_current_pct=frame[7],
        )

    @classmethod
    def read_from_controller(cls, ser: serial.Serial) -> ThrottleControllerData:
        if not ser.is_open:
            raise ValueError("Serial port must be open")

        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.write(cls.SERIAL_CMD_READ_THR)
        ser.flush()
        time.sleep(0.2)

        frame = ser.read(3 + cls.THR_FRAME_DATA_LEN)
        if not frame:
            raise TimeoutError("No response received for THR request")

        return cls._from_frame(frame)

    @classmethod
    def mode_text_from_code(cls, code: int) -> str:
        return cls.MODE_TO_TEXT.get(code, f"Unknown ({code})")

    @staticmethod
    def _fmt_by_display(raw: int, unit: str = "") -> str:
        return "By Display's Command" if raw == 255 else f"{raw}{unit}"

    def write_to_controller(self, ser: serial.Serial) -> str:
        if not ser.is_open:
            raise ValueError("Serial port must be open")
        if not (0 <= self.start_voltage <= 255):
            raise ValueError(f"start_voltage must be 0-255, got {self.start_voltage}")
        if not (0 <= self.end_voltage <= 255):
            raise ValueError(f"end_voltage must be 0-255, got {self.end_voltage}")
        if not (0 <= self.mode <= 1):
            raise ValueError(f"mode must be 0-1, got {self.mode}")
        if not (self.assist_level == 255 or 0 <= self.assist_level <= 9):
            raise ValueError(f"assist_level must be 0-9 or 255, got {self.assist_level}")
        if not (self.speed_limit == 255 or 15 <= self.speed_limit <= 40):
            raise ValueError(f"speed_limit must be 15-40 or 255, got {self.speed_limit}")
        if not (0 <= self.start_current_pct <= 255):
            raise ValueError(f"start_current_pct must be 0-255, got {self.start_current_pct}")

        payload = [
            self.start_voltage,
            self.end_voltage,
            self.mode,
            self.assist_level,
            self.speed_limit,
            self.start_current_pct,
        ]
        for idx, value in enumerate(payload):
            if not (0 <= int(value) <= 255):
                raise ValueError(f"THR payload byte out of range at index {idx}: {value}")

        request = _append_u8_checksum(bytes([0x16, self.BLOCK_ID, self.THR_FRAME_DATA_LEN, *payload]))

        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.write(request)
        ser.flush()
        time.sleep(1.0)

        response = ser.read(2)
        if len(response) < 2:
            raise TimeoutError("No response received for THR write request")
        if int(response[0]) != self.BLOCK_ID:
            raise ValueError(
                f"Unexpected THR write response block id 0x{int(response[0]):02X}, expected 0x{self.BLOCK_ID:02X}"
            )

        status_code = int(response[1])
        return self.THR_WRITE_STATUS_TEXT.get(status_code, f"Unknown THR write status code: {status_code}")

    def to_json_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json_dict(cls, data: dict) -> ThrottleControllerData:
        return cls(**data)

    def to_pretty_string(self) -> str:
        lines = [
            "Bafang Throttle Parameters",
            "--------------------------",
            f"Block ID:              0x{self.BLOCK_ID:02X}",
            f"Start voltage:         {self.start_voltage / 10:.1f} V (raw {self.start_voltage})",
            f"End voltage:           {self.end_voltage / 10:.1f} V (raw {self.end_voltage})",
            f"Mode:                  {self.mode_text_from_code(self.mode)}",
            f"Assist level:          {self._fmt_by_display(self.assist_level)}",
            f"Speed limit:           {self._fmt_by_display(self.speed_limit, ' km/h')}",
            f"Start current:         {self.start_current_pct} %",
        ]
        return "\n".join(lines)


def save_profile(
    path: Path | str,
    gen: GeneralControllerData,
    bas: BasicControllerData,
    pas: PedalAssistControllerData,
    thr: ThrottleControllerData,
) -> None:
    """Save parameter blocks to a single human-readable JSON file."""
    data = {
        "general": gen.to_json_dict(),
        "basic": bas.to_json_dict(),
        "pedal_assist": pas.to_json_dict(),
        "throttle": thr.to_json_dict(),
    }
    with open(path, "w", encoding="utf-8") as file_handle:
        json.dump(data, file_handle, indent=2)


def load_profile(
    path: Path | str,
) -> tuple[GeneralControllerData, BasicControllerData, PedalAssistControllerData, ThrottleControllerData]:
    """Load parameter blocks from a JSON file created by save_profile."""
    with open(path, encoding="utf-8") as file_handle:
        data = json.load(file_handle)
    return (
        GeneralControllerData.from_json_dict(data["general"]),
        BasicControllerData.from_json_dict(data["basic"]),
        PedalAssistControllerData.from_json_dict(data["pedal_assist"]),
        ThrottleControllerData.from_json_dict(data["throttle"]),
    )


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )


def read_all_from_controller(
    ser: serial.Serial,
) -> tuple[GeneralControllerData, BasicControllerData, PedalAssistControllerData, ThrottleControllerData]:
    LOG.debug("Reading GEN block")
    gen_data = GeneralControllerData.read_from_controller(ser)
    LOG.debug("Reading BAS block")
    bas_data = BasicControllerData.read_from_controller(ser)
    LOG.debug("Reading PAS block")
    pas_data = PedalAssistControllerData.read_from_controller(ser)
    LOG.debug("Reading THR block")
    thr_data = ThrottleControllerData.read_from_controller(ser)
    return gen_data, bas_data, pas_data, thr_data


def write_all_to_controller(
    ser: serial.Serial,
    bas_data: BasicControllerData,
    pas_data: PedalAssistControllerData,
    thr_data: ThrottleControllerData,
) -> tuple[str, str, str]:
    LOG.debug("Writing BAS block")
    bas_status = bas_data.write_to_controller(ser)
    LOG.debug(f"BAS write status: {bas_status}")
    LOG.debug("Writing PAS block")
    pas_status = pas_data.write_to_controller(ser)
    LOG.debug(f"PAS write status: {pas_status}")
    LOG.debug("Writing THR block")
    thr_status = thr_data.write_to_controller(ser)
    LOG.debug(f"THR write status: {thr_status}")
    return bas_status, pas_status, thr_status


def pretty_print_all(
    gen_data: GeneralControllerData,
    bas_data: BasicControllerData,
    pas_data: PedalAssistControllerData,
    thr_data: ThrottleControllerData,
) -> None:
    print(gen_data.to_pretty_string())
    print()
    print(bas_data.to_pretty_string())
    print()
    print(pas_data.to_pretty_string())
    print()
    print(thr_data.to_pretty_string())
    print()


def _open_serial(serial_interface: str) -> serial.Serial:
    LOG.debug("Opening serial interface %s", serial_interface)
    return serial.Serial(port=serial_interface, baudrate=DEFAULT_BAUDRATE, timeout=DEFAULT_TIMEOUT_SECONDS)


def cmd_read(args: argparse.Namespace) -> int:
    output_path = Path(args.json_file)
    with _open_serial(args.serial_interface) as ser:
        gen_data, bas_data, pas_data, thr_data = read_all_from_controller(ser)
    save_profile(output_path, gen_data, bas_data, pas_data, thr_data)
    LOG.info("Saved controller parameters to %s", output_path)
    return 0


def cmd_write(args: argparse.Namespace) -> int:
    input_path = Path(args.json_file)
    _, bas_data, pas_data, thr_data = load_profile(input_path)
    LOG.info("Loaded controller parameters from %s", input_path)

    with _open_serial(args.serial_interface) as ser:
        bas_status, pas_status, thr_status = write_all_to_controller(ser, bas_data, pas_data, thr_data)

    LOG.info("BAS write status: %s", bas_status)
    LOG.info("PAS write status: %s", pas_status)
    LOG.info("THR write status: %s", thr_status)
    return 0


def cmd_print(args: argparse.Namespace) -> int:
    with _open_serial(args.serial_interface) as ser:
        gen_data, bas_data, pas_data, thr_data = read_all_from_controller(ser)
    pretty_print_all(gen_data, bas_data, pas_data, thr_data)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read, write, or print Bafang controller parameters.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    read_parser = subparsers.add_parser(
        "read",
        help="Read controller parameters and save them to a JSON file.",
    )
    read_parser.add_argument("serial_interface", help="Serial interface such as /dev/ttyUSB0 or COM3.")
    read_parser.add_argument("json_file", help="Output JSON file path.")
    read_parser.set_defaults(func=cmd_read)

    write_parser = subparsers.add_parser(
        "write",
        help="Load parameters from a JSON file and write them to the controller.",
    )
    write_parser.add_argument("serial_interface", help="Serial interface such as /dev/ttyUSB0 or COM3.")
    write_parser.add_argument("json_file", help="Input JSON file path.")
    write_parser.set_defaults(func=cmd_write)

    print_parser = subparsers.add_parser(
        "print",
        help="Read controller parameters and print them in a human-readable form.",
    )
    print_parser.add_argument("serial_interface", help="Serial interface such as /dev/ttyUSB0 or COM3.")
    print_parser.set_defaults(func=cmd_print)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())