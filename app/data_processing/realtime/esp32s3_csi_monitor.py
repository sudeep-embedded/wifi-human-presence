import sys
import time
from pathlib import Path

import numpy as np
import serial


# ============================================================
# CONFIG
# ============================================================

PORT = "COM4"
BAUD = 921600

FRAMES_TO_SHOW = 100


# ============================================================
# PROJECT IMPORT
# ============================================================

PROJECT_ROOT = Path(
    r"D:\final_year_projects\wifi-human-presence"
)

sys.path.insert(
    0,
    str(PROJECT_ROOT)
)

from app.receiver.packet_parser import PacketParser


# ============================================================
# CSI DECODER
# ============================================================

def decode_csi(frame):
    """
    Firmware format:
        int8 imaginary, int8 real
        repeated for each subcarrier.
    """

    raw = np.frombuffer(
        frame.csi_data,
        dtype=np.int8
    )

    if raw.size % 2 != 0:
        raise ValueError(
            f"Odd CSI byte count: {raw.size}"
        )

    imag = raw[0::2].astype(
        np.float32
    )

    real = raw[1::2].astype(
        np.float32
    )

    csi = (
        real
        +
        1j * imag
    )

    return csi


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("ESP32-S3 LIVE CSI MONITOR")
    print("=" * 70)

    print(
        f"Port : {PORT}"
    )

    print(
        f"Baud : {BAUD}"
    )

    print(
        "\nWaiting for CSI frames..."
    )

    parser = PacketParser()

    frame_count = 0
    total_bytes = 0

    csi_lengths = []

    amplitudes = []
    phases = []

    start_time = time.time()

    try:

        with serial.Serial(
            PORT,
            BAUD,
            timeout=1
        ) as ser:

            print(
                f"Connected to {PORT}"
            )

            while (
                frame_count
                < FRAMES_TO_SHOW
            ):

                data = ser.read(
                    4096
                )

                if not data:
                    continue

                total_bytes += len(
                    data
                )

                frames = parser.feed(
                    data
                )

                for frame in frames:

                    csi = decode_csi(
                        frame
                    )

                    frame_count += 1

                    csi_lengths.append(
                        len(csi)
                    )

                    amplitude = np.abs(
                        csi
                    )

                    phase = np.angle(
                        csi
                    )

                    amplitudes.append(
                        amplitude
                    )

                    phases.append(
                        phase
                    )

                    print(
                        f"Frame "
                        f"{frame_count:03d} | "
                        f"CSI bytes={frame.csi_len:3d} | "
                        f"subcarriers={len(csi):3d} | "
                        f"RSSI={frame.rssi:4d} | "
                        f"channel={frame.channel:2d}"
                    )

                    if (
                        frame_count
                        == 1
                    ):

                        print(
                            "\nFirst CSI frame:"
                        )

                        print(
                            f"  Real min/max: "
                            f"{csi.real.min():.1f} / "
                            f"{csi.real.max():.1f}"
                        )

                        print(
                            f"  Imag min/max: "
                            f"{csi.imag.min():.1f} / "
                            f"{csi.imag.max():.1f}"
                        )

                        print(
                            f"  Amplitude min/max: "
                            f"{amplitude.min():.2f} / "
                            f"{amplitude.max():.2f}"
                        )

                        print(
                            f"  Phase min/max: "
                            f"{phase.min():.4f} / "
                            f"{phase.max():.4f}"
                        )

            elapsed = (
                time.time()
                - start_time
            )

            print(
                "\n" +
                "=" * 70
            )

            print(
                "CSI MONITOR RESULT"
            )

            print("=" * 70)

            unique_lengths = sorted(
                set(
                    csi_lengths
                )
            )

            print(
                "CSI subcarrier counts:",
                unique_lengths
            )

            print(
                "Frames received:",
                frame_count
            )

            print(
                "Bytes received:",
                total_bytes
            )

            print(
                f"Elapsed time: "
                f"{elapsed:.2f} s"
            )

            if frame_count > 0:

                print(
                    f"Frame rate: "
                    f"{frame_count / elapsed:.2f} frames/s"
                )

            if len(
                unique_lengths
            ) == 1:

                print(
                    "\nStable CSI length: YES"
                )

            else:

                print(
                    "\nWARNING: CSI length changes."
                )

    except serial.SerialException as exc:

        print(
            "\nSERIAL ERROR:"
        )

        print(exc)

        print(
            "\nCheck that COM4 is the correct "
            "ESP32-S3 port and that no other "
            "program is using it."

        )

        sys.exit(1)


if __name__ == "__main__":
    main()