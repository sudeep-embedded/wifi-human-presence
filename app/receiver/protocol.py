"""
Python mirror of firmware/esp32s3/main/include/csi_protocol.h.

CRITICAL: This module's frame layout and CRC algorithm MUST match the C
header exactly. If you change one side, change both, or the parser will
either reject every frame (best case) or silently misparse garbage as
valid CSI (worst case, and much harder to debug).

Frame layout (little-endian):
    [0]     SOF0        0xAA
    [1]     SOF1        0x55
    [2:4]   LEN (u16)   length of PAYLOAD in bytes
    [4:4+LEN]           PAYLOAD
    [4+LEN:6+LEN]       CRC16 (u16) over PAYLOAD only
    [6+LEN]             EOF0  0x55
    [7+LEN]             EOF1  0xAA

PAYLOAD layout (struct.Struct format '<QbB6sBH'):
    timestamp_us : u64
    rssi         : i8
    channel      : u8
    mac          : 6 bytes
    rate         : u8
    csi_len      : u16
    csi_data     : csi_len bytes (int8), follows immediately after
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

SOF = bytes([0xAA, 0x55])
EOF = bytes([0x55, 0xAA])

# timestamp_us(Q=8) rssi(b=1) channel(B=1) mac(6s=6) rate(B=1) csi_len(H=2) = 19 bytes
_HEADER_STRUCT = struct.Struct("<QbB6sBH")
HEADER_LEN = _HEADER_STRUCT.size

MAX_CSI_LEN = 512  # must match CSI_PROTO_MAX_CSI_LEN in csi_protocol.h


class FrameError(ValueError):
    """Raised when raw bytes cannot be parsed into a valid CSIFrame."""


@dataclass(frozen=True)
class CSIFrame:
    """A single parsed, CRC-validated CSI capture."""

    timestamp_us: int
    rssi: int
    channel: int
    mac: str  # colon-separated hex, e.g. "aa:bb:cc:dd:ee:ff"
    rate: int
    csi_len: int
    csi_data: bytes  # raw int8 bytes, alternating (imag, real) per subcarrier


def crc16_ccitt_false(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflect, no xorout.

    Must match csi_protocol_crc16() in csi_protocol.c bit-for-bit.
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def parse_payload(payload: bytes) -> CSIFrame:
    """Parse a validated PAYLOAD slice (header + csi_data) into a CSIFrame.

    Raises FrameError if the payload is too short or csi_len doesn't match
    the actual remaining bytes.
    """
    if len(payload) < HEADER_LEN:
        raise FrameError(
            f"payload too short: {len(payload)} bytes, need at least {HEADER_LEN}"
        )

    timestamp_us, rssi, channel, mac_bytes, rate, csi_len = _HEADER_STRUCT.unpack_from(
        payload, 0
    )

    expected_total = HEADER_LEN + csi_len
    if len(payload) != expected_total:
        raise FrameError(
            f"csi_len mismatch: header says {csi_len} bytes of CSI data, "
            f"payload has {len(payload) - HEADER_LEN} bytes available"
        )
    if csi_len > MAX_CSI_LEN:
        raise FrameError(f"csi_len {csi_len} exceeds MAX_CSI_LEN {MAX_CSI_LEN}")

    csi_data = payload[HEADER_LEN:expected_total]
    mac_str = ":".join(f"{b:02x}" for b in mac_bytes)

    return CSIFrame(
        timestamp_us=timestamp_us,
        rssi=rssi,
        channel=channel,
        mac=mac_str,
        rate=rate,
        csi_len=csi_len,
        csi_data=csi_data,
    )


def build_frame_bytes(frame_payload: bytes) -> bytes:
    """Build a complete wire frame from a raw payload. Used by the synthetic
    generator and by tests -- NOT used on the real receive path (real
    frames arrive pre-built from firmware over the serial port).
    """
    length = len(frame_payload)
    if length > 0xFFFF:
        raise ValueError("payload too large for u16 LEN field")
    crc = crc16_ccitt_false(frame_payload)
    return (
        SOF
        + struct.pack("<H", length)
        + frame_payload
        + struct.pack("<H", crc)
        + EOF
    )
