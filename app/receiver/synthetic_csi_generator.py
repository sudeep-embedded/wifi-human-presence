"""
Synthetic CSI frame generator for testing the receiver/parser without
attached ESP32-S3 hardware.

IMPORTANT LIMITATION: this generates protocol-valid frames with
statistically plausible CSI byte values (random int8 pairs, optionally
with a slow sinusoidal drift to emulate "something moving"). It does NOT
generate real multipath physics -- it is a pipe-testing tool only, never
a substitute for real labeled data when training the presence/counting
model. See the AI-model-phase discussion: a model trained on this
generator's output would learn nothing transferable to real CSI.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

import struct

from app.receiver.protocol import build_frame_bytes

_HEADER_STRUCT = struct.Struct("<QbB6sBH")


@dataclass
class SyntheticConfig:
    csi_len: int = 128  # e.g. 64 subcarriers * 2 (imag, real)
    channel: int = 6
    mac: bytes = b"\xaa\xbb\xcc\xdd\xee\xff"
    rssi_base: int = -55
    rssi_jitter: int = 3
    seed: int | None = None


class SyntheticCSIGenerator:
    """Yields raw wire-format frame bytes, byte-for-byte compatible with
    what PacketParser expects from the real serial stream."""

    def __init__(self, config: SyntheticConfig | None = None) -> None:
        self._cfg = config or SyntheticConfig()
        self._rng = random.Random(self._cfg.seed)
        self._t0 = time.time()

    def generate_frame_bytes(self) -> bytes:
        timestamp_us = int((time.time() - self._t0) * 1_000_000)
        rssi = self._cfg.rssi_base + self._rng.randint(
            -self._cfg.rssi_jitter, self._cfg.rssi_jitter
        )
        rate = 0

        # CSI values are conceptually signed int8 (-128..127) but Python's
        # bytes() constructor requires 0..255; mask to the two's-complement
        # unsigned representation, which is what actually goes on the wire
        # (the firmware side does the same -- int8_t reinterpreted as raw
        # bytes -- so this must match, not just "be a valid byte").
        csi_data = bytes(
            self._rng.randint(-128, 127) & 0xFF for _ in range(self._cfg.csi_len)
        )

        header = _HEADER_STRUCT.pack(
            timestamp_us,
            max(-128, min(127, rssi)),
            self._cfg.channel,
            self._cfg.mac,
            rate,
            self._cfg.csi_len,
        )
        payload = header + csi_data
        return build_frame_bytes(payload)

    def generate_stream(self, count: int, corrupt_every: int | None = None):
        """Yield `count` frames as raw bytes. If corrupt_every is set,
        flips one bit in every Nth frame (to exercise parser resync in
        tests) -- returned frames are NOT guaranteed valid in that case.
        """
        for i in range(count):
            frame = bytearray(self.generate_frame_bytes())
            if corrupt_every and (i + 1) % corrupt_every == 0:
                idx = self._rng.randrange(len(frame))
                frame[idx] ^= 0xFF
            yield bytes(frame)
