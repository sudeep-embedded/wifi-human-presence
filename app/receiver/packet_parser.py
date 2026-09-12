"""
Streaming parser for the CSI UART protocol.

Design note: a serial port delivers an arbitrary byte stream with no
guarantee that reads land on frame boundaries. This parser is fed bytes
incrementally (via `feed()`) and internally buffers + state-machines its
way through SOF detection, length-prefixed payload accumulation, CRC
validation, and EOF confirmation -- yielding complete, validated CSIFrame
objects as they become available and silently resynchronizing (byte by
byte) whenever it encounters something that doesn't match the protocol,
rather than getting permanently stuck after one corrupt frame.

Implementation note: the state machine is a single flat loop (not
recursive step calls) specifically because "made progress, buffer state
changed, keep going" (resync after corruption) and "no progress possible,
need more bytes" (partial frame at end of buffer) are different
conditions that both used to collapse to the same return value in an
earlier version of this code -- which silently dropped valid frames that
arrived immediately after a corrupted one in the same feed() call. The
loop below uses `continue` for the former and `return` for the latter to
keep that distinction explicit and testable.
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Iterator

from app.receiver.protocol import (
    EOF,
    HEADER_LEN,
    SOF,
    CSIFrame,
    FrameError,
    crc16_ccitt_false,
    parse_payload,
)

logger = logging.getLogger(__name__)


class _State(Enum):
    SEEK_SOF = auto()
    READ_LEN = auto()
    READ_PAYLOAD = auto()
    READ_CRC = auto()
    READ_EOF = auto()


class PacketParser:
    """Feed raw bytes in, get validated CSIFrame objects out.

    Usage:
        parser = PacketParser()
        for chunk in serial_read_chunks():
            for frame in parser.feed(chunk):
                handle(frame)
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self._state = _State.SEEK_SOF
        self._payload_len = 0
        self._payload = b""
        self._stats_frames_ok = 0
        self._stats_frames_dropped = 0

    @property
    def stats(self) -> dict:
        return {
            "frames_ok": self._stats_frames_ok,
            "frames_dropped": self._stats_frames_dropped,
        }

    def feed(self, data: bytes) -> Iterator[CSIFrame]:
        """Feed newly-received bytes; yields any complete, valid frames
        that can be extracted from the buffer, including multiple frames
        per call and frames following a resync within the same call."""
        self._buf.extend(data)

        while True:
            if self._state == _State.SEEK_SOF:
                idx = self._buf.find(SOF)
                if idx == -1:
                    if len(self._buf) > 1:
                        del self._buf[: len(self._buf) - 1]
                    return
                if idx > 0:
                    logger.debug("Dropping %d bytes of pre-sync garbage", idx)
                    del self._buf[:idx]
                if len(self._buf) < 4:
                    return  # need more bytes for LEN field
                self._state = _State.READ_LEN
                continue

            if self._state == _State.READ_LEN:
                length = self._buf[2] | (self._buf[3] << 8)
                if length == 0 or length > (HEADER_LEN + 512):
                    logger.debug("Implausible LEN=%d, resyncing", length)
                    del self._buf[:2]
                    self._stats_frames_dropped += 1
                    self._state = _State.SEEK_SOF
                    continue
                self._payload_len = length
                self._state = _State.READ_PAYLOAD
                continue

            if self._state == _State.READ_PAYLOAD:
                needed = 4 + self._payload_len
                if len(self._buf) < needed:
                    return
                self._payload = bytes(self._buf[4:needed])
                self._state = _State.READ_CRC
                continue

            if self._state == _State.READ_CRC:
                crc_start = 4 + self._payload_len
                crc_end = crc_start + 2
                if len(self._buf) < crc_end:
                    return
                received_crc = self._buf[crc_start] | (self._buf[crc_start + 1] << 8)
                expected_crc = crc16_ccitt_false(self._payload)
                if received_crc != expected_crc:
                    logger.warning(
                        "CRC mismatch (got 0x%04x, expected 0x%04x), dropping "
                        "frame and resyncing from next byte",
                        received_crc,
                        expected_crc,
                    )
                    del self._buf[:2]
                    self._stats_frames_dropped += 1
                    self._state = _State.SEEK_SOF
                    continue
                self._state = _State.READ_EOF
                continue

            if self._state == _State.READ_EOF:
                eof_start = 4 + self._payload_len + 2
                eof_end = eof_start + 2
                if len(self._buf) < eof_end:
                    return
                if bytes(self._buf[eof_start:eof_end]) != EOF:
                    logger.warning("EOF mismatch, dropping frame and resyncing")
                    del self._buf[:2]
                    self._stats_frames_dropped += 1
                    self._state = _State.SEEK_SOF
                    continue

                try:
                    frame = parse_payload(self._payload)
                except FrameError as exc:
                    logger.warning("Payload parse error despite valid CRC: %s", exc)
                    self._stats_frames_dropped += 1
                    del self._buf[:eof_end]
                    self._state = _State.SEEK_SOF
                    continue

                del self._buf[:eof_end]
                self._state = _State.SEEK_SOF
                self._stats_frames_ok += 1
                yield frame
                continue

            raise AssertionError(f"unreachable state {self._state}")  # pragma: no cover
