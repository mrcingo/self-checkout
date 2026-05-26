"""Read UHF RFID tags from a serial-connected reader module."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterator

import serial

FRAME_HEADER = 0xAA
FRAME_END = 0xDD
FRAME_NO_TAG = 0xFF
FRAME_HEADER_SIZE = 5
FRAME_FOOTER_SIZE = 2
DEFAULT_SCAN_TIME = 0x1E
DEFAULT_EPC_HEX_LEN = 16


@dataclass(frozen=True)
class RfidConfig:
    port: str = os.environ.get("RFID_PORT", "/dev/ttyUSB0")
    baudrate: int = int(os.environ.get("RFID_BAUDRATE", "115200"))
    scan_time: int = int(os.environ.get("RFID_SCAN_TIME", str(DEFAULT_SCAN_TIME)), 0)
    epc_hex_len: int = int(os.environ.get("RFID_EPC_HEX_LEN", str(DEFAULT_EPC_HEX_LEN)))
    timeout: float = float(os.environ.get("RFID_SERIAL_TIMEOUT", "1"))


def build_scan_command(scan_time: int = DEFAULT_SCAN_TIME) -> bytes:
    payload = [0x00, 0x27, 0x00, 0x03, 0x22, 0x00, scan_time]
    checksum = sum(payload) & 0xFF
    return bytes([FRAME_HEADER] + payload + [checksum, FRAME_END])


def extract_frame(buffer: bytes) -> tuple[bytes | None, bytes]:
    start = buffer.find(FRAME_HEADER)
    if start == -1 or len(buffer) < start + FRAME_HEADER_SIZE:
        return None, buffer

    payload_length = (buffer[start + 3] << 8) | buffer[start + 4]
    total_length = FRAME_HEADER_SIZE + payload_length + FRAME_FOOTER_SIZE

    if len(buffer) < start + total_length:
        return None, buffer

    frame = buffer[start : start + total_length]
    if frame[-1] != FRAME_END:
        return None, buffer[start + 1 :]

    return frame, buffer[start + total_length :]


def epc_from_frame(
    frame: bytes, *, epc_hex_len: int = DEFAULT_EPC_HEX_LEN
) -> str | None:
    if len(frame) < 15 or frame[2] == FRAME_NO_TAG:
        return None

    raw = frame[3:15].hex().upper()
    if epc_hex_len <= 0 or len(raw) <= epc_hex_len:
        return raw
    return raw[-epc_hex_len:]


def parse_frames(
    buffer: bytes, *, epc_hex_len: int = DEFAULT_EPC_HEX_LEN
) -> tuple[list[str], bytes]:
    tags: list[str] = []
    while True:
        frame, buffer = extract_frame(buffer)
        if frame is None:
            break
        epc = epc_from_frame(frame, epc_hex_len=epc_hex_len)
        if epc and epc not in tags:
            tags.append(epc)
    return tags, buffer


class RfidReader:
    """Serial RFID reader: poll once per scan command, or iterate tag reads."""

    def __init__(self, config: RfidConfig | None = None) -> None:
        self._config = config or RfidConfig()
        self._ser: serial.Serial | None = None
        self._buffer = b""
        self._command = build_scan_command(self._config.scan_time)

    def open(self) -> None:
        self._ser = serial.Serial(
            self._config.port,
            self._config.baudrate,
            timeout=self._config.timeout,
        )
        self._buffer = b""

    def close(self) -> None:
        if self._ser is not None:
            self._ser.close()
            self._ser = None
        self._buffer = b""

    def __enter__(self) -> RfidReader:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def poll(self) -> list[str]:
        """Send one inventory command and return tag EPCs from the response."""
        if self._ser is None:
            raise RuntimeError("RfidReader is not open; call open() or use 'with'.")

        self._ser.write(self._command)
        self._buffer += self._ser.read(self._ser.in_waiting or 64)
        tags, self._buffer = parse_frames(
            self._buffer, epc_hex_len=self._config.epc_hex_len
        )
        return tags

    def iter_tags(self) -> Iterator[str]:
        """Yield each detected tag EPC, scanning continuously."""
        while True:
            for tag in self.poll():
                yield tag


def main() -> None:
    with RfidReader() as reader:
        for tag in reader.iter_tags():
            print(tag)


if __name__ == "__main__":
    main()
