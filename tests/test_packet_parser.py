"""Unit tests for app.receiver.packet_parser and app.receiver.protocol.

Run with: python -m pytest tests/test_packet_parser.py -v
"""

from __future__ import annotations

import struct

import pytest

from app.receiver.packet_parser import PacketParser
from app.receiver.protocol import build_frame_bytes, crc16_ccitt_false
from app.receiver.synthetic_csi_generator import SyntheticCSIGenerator, SyntheticConfig

_HEADER_STRUCT = struct.Struct("<QbB6sBH")


def _make_valid_payload(csi_len: int = 8) -> bytes:
    header = _HEADER_STRUCT.pack(
        123456789,  # timestamp_us
        -55,        # rssi
        6,          # channel
        b"\xaa\xbb\xcc\xdd\xee\xff",
        0,          # rate
        csi_len,
    )
    csi_data = bytes(range(csi_len))
    return header + csi_data


def test_crc16_known_value():
    # CRC-16/CCITT-FALSE of ASCII "123456789" is the standard check value
    # 0x29B1, per the CRC catalogue. Confirms our implementation matches
    # the named algorithm, independent of our own frame format.
    assert crc16_ccitt_false(b"123456789") == 0x29B1


def test_parser_parses_single_valid_frame():
    payload = _make_valid_payload()
    frame_bytes = build_frame_bytes(payload)

    parser = PacketParser()
    frames = list(parser.feed(frame_bytes))

    assert len(frames) == 1
    f = frames[0]
    assert f.timestamp_us == 123456789
    assert f.rssi == -55
    assert f.channel == 6
    assert f.mac == "aa:bb:cc:dd:ee:ff"
    assert f.csi_len == 8
    assert f.csi_data == bytes(range(8))
    assert parser.stats["frames_ok"] == 1
    assert parser.stats["frames_dropped"] == 0


def test_parser_handles_bytes_split_across_multiple_feeds():
    payload = _make_valid_payload()
    frame_bytes = build_frame_bytes(payload)

    parser = PacketParser()
    frames = []
    # Feed one byte at a time -- worst case for a streaming parser.
    for b in frame_bytes:
        frames.extend(parser.feed(bytes([b])))

    assert len(frames) == 1
    assert frames[0].csi_len == 8


def test_parser_resyncs_after_garbage_prefix():
    payload = _make_valid_payload()
    frame_bytes = build_frame_bytes(payload)
    noisy = b"\x00\x11\x22garbage-not-a-frame" + frame_bytes

    parser = PacketParser()
    frames = list(parser.feed(noisy))

    assert len(frames) == 1


def test_parser_drops_corrupted_frame_and_recovers_on_next():
    payload = _make_valid_payload()
    good_frame = build_frame_bytes(payload)

    corrupted = bytearray(good_frame)
    corrupted[10] ^= 0xFF  # flip a bit inside the payload -> CRC mismatch

    stream = bytes(corrupted) + good_frame

    parser = PacketParser()
    frames = list(parser.feed(stream))

    # First (corrupted) frame dropped, second (valid) frame recovered.
    assert len(frames) == 1
    assert parser.stats["frames_dropped"] >= 1
    assert parser.stats["frames_ok"] == 1


def test_parser_rejects_implausible_length_and_resyncs():
    # LEN field claims an absurd payload size; parser must not hang
    # waiting forever for bytes that will never come, and must recover
    # once real data follows.
    bogus = bytes([0xAA, 0x55]) + struct.pack("<H", 0xFFFF) + b"junk"
    payload = _make_valid_payload()
    good_frame = build_frame_bytes(payload)

    parser = PacketParser()
    frames = list(parser.feed(bogus + good_frame))

    assert len(frames) == 1


def test_synthetic_generator_produces_parseable_stream():
    gen = SyntheticCSIGenerator(SyntheticConfig(csi_len=64, seed=42))
    parser = PacketParser()

    frames = []
    for raw in gen.generate_stream(count=20):
        frames.extend(parser.feed(raw))

    assert len(frames) == 20
    assert all(f.csi_len == 64 for f in frames)


def test_synthetic_generator_with_corruption_still_recovers_most_frames():
    gen = SyntheticCSIGenerator(SyntheticConfig(csi_len=32, seed=7))
    parser = PacketParser()

    frames = []
    for raw in gen.generate_stream(count=50, corrupt_every=5):
        frames.extend(parser.feed(raw))

    # 50 frames, every 5th corrupted (10 corrupted) -> expect the 40
    # uncorrupted frames to parse; corrupted ones are dropped, not crashing
    # the parser.
    assert len(frames) == 40
    assert parser.stats["frames_dropped"] == 10


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
