import sys
import time
from pathlib import Path

import numpy as np
import serial

PROJECT_ROOT = Path(
    r"D:\final_year_projects\wifi-human-presence"
)

sys.path.insert(0, str(PROJECT_ROOT))

from app.receiver.packet_parser import PacketParser


PORT = "COM4"
BAUD = 460800
FRAMES_TO_CAPTURE = 500


def decode_csi(frame):
    raw = np.frombuffer(
        frame.csi_data,
        dtype=np.int8
    )

    if raw.size % 2 != 0:
        raise ValueError(
            f"Odd CSI byte count: {raw.size}"
        )

    imag = raw[0::2].astype(np.float32)
    real = raw[1::2].astype(np.float32)

    return real + 1j * imag


def main():
    print("=" * 70)
    print("ESP32-S3 CSI LAYOUT INSPECTION")
    print("=" * 70)

    parser = PacketParser()

    frames = []
    start = time.time()

    with serial.Serial(
        PORT,
        BAUD,
        timeout=1
    ) as ser:

        print(f"Connected to {PORT}")
        print("Collecting frames...")

        while len(frames) < FRAMES_TO_CAPTURE:

            data = ser.read(4096)

            if not data:
                continue

            for frame in parser.feed(data):

                csi = decode_csi(frame)

                if len(csi) != 64:
                    print(
                        f"WARNING: unexpected CSI length "
                        f"{len(csi)}"
                    )
                    continue

                frames.append({
                    "timestamp_us": frame.timestamp_us,
                    "rssi": frame.rssi,
                    "channel": frame.channel,
                    "rate": frame.rate,
                    "csi": csi,
                })

                if len(frames) == FRAMES_TO_CAPTURE:
                    break

    elapsed = time.time() - start

    matrix = np.stack(
        [item["csi"] for item in frames],
        axis=0
    )

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)

    print(
        f"Frames: {len(frames)}"
    )

    print(
        f"Matrix shape: {matrix.shape}"
    )

    print(
        f"Frame rate: {len(frames) / elapsed:.2f} FPS"
    )

    print(
        f"CSI dtype: {matrix.dtype}"
    )

    print(
        f"Real range: "
        f"{matrix.real.min():.2f} .. "
        f"{matrix.real.max():.2f}"
    )

    print(
        f"Imag range: "
        f"{matrix.imag.min():.2f} .. "
        f"{matrix.imag.max():.2f}"
    )

    amplitude = np.abs(matrix)
    phase = np.angle(matrix)

    print(
        f"Amplitude range: "
        f"{amplitude.min():.4f} .. "
        f"{amplitude.max():.4f}"
    )

    print(
        f"Phase range: "
        f"{phase.min():.4f} .. "
        f"{phase.max():.4f}"
    )

    print(
        f"RSSI range: "
        f"{min(x['rssi'] for x in frames)} .. "
        f"{max(x['rssi'] for x in frames)}"
    )

    print(
        f"Channels observed: "
        f"{sorted(set(x['channel'] for x in frames))}"
    )

    print(
        f"Rates observed: "
        f"{sorted(set(x['rate'] for x in frames))}"
    )

    print("\nFirst-frame complex CSI:")
    print(matrix[0])

    print("\nMean amplitude per CSI index:")
    print(
        np.array2string(
            amplitude.mean(axis=0),
            precision=3,
            suppress_small=True
        )
    )

    print("\nAmplitude std per CSI index:")
    print(
        np.array2string(
            amplitude.std(axis=0),
            precision=3,
            suppress_small=True
        )
    )

    print("\nFirst-frame phase per CSI index:")
    print(
        np.array2string(
            phase[0],
            precision=3,
            suppress_small=True
        )
    )


if __name__ == "__main__":
    main()