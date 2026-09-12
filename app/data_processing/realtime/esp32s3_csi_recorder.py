import sys
import time
import json
from pathlib import Path
from datetime import datetime

import numpy as np
import serial


# ============================================================
# CONFIGURATION
# ============================================================

PORT = "COM4"
BAUD = 921600

# One recording session = 2 minutes
RECORD_SECONDS = 120

# CHANGE ONLY THIS:
# "empty"       -> empty-room recording
# "one_person" -> one-person recording
MODE = "one_person"


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(
    r"D:\final_year_projects\wifi-human-presence"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "dataset"
    / "esp32s3_raw"
    / MODE
)


# ============================================================
# IMPORT VERIFIED PACKET PARSER
# ============================================================

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
    ESP32-S3 CSI format used by the verified monitor:

        byte 0 -> imaginary
        byte 1 -> real

        repeated for every subcarrier
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
        + 1j * imag
    )

    return csi


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("ESP32-S3 RAW CSI DATASET RECORDER")
    print("=" * 70)

    print(f"Mode            : {MODE}")
    print(f"Port            : {PORT}")
    print(f"Baud            : {BAUD}")
    print(f"Duration        : {RECORD_SECONDS} seconds")
    print(f"Output directory: {OUTPUT_DIR}")

    print("\nExpected CSI:")
    print("  Bytes/frame   : 128")
    print("  Subcarriers   : 64")
    print("  Data type     : complex64")

    # --------------------------------------------------------
    # Validate mode
    # --------------------------------------------------------

    if MODE not in (
        "empty",
        "one_person"
    ):
        print(
            "\nERROR: MODE must be "
            "'empty' or 'one_person'."
        )
        sys.exit(1)

    # --------------------------------------------------------
    # Create output directory
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Packet parser
    # --------------------------------------------------------

    parser = PacketParser()

    # --------------------------------------------------------
    # Storage
    # --------------------------------------------------------

    timestamps = []
    rssi_values = []
    channels = []
    rates = []

    csi_real = []
    csi_imag = []

    frame_count = 0
    total_serial_bytes = 0

    start_time = time.time()

    # ========================================================
    # SERIAL COLLECTION
    # ========================================================

    try:

        with serial.Serial(
            PORT,
            BAUD,
            timeout=1
        ) as ser:

            print(
                f"\nConnected to {PORT}"
            )

            print(
                "\nRecording started..."
            )

            print(
                "Do NOT move the ESP32, hotspot, "
                "or laptop during the session.\n"
            )

            while True:

                elapsed = (
                    time.time()
                    - start_time
                )

                if elapsed >= RECORD_SECONDS:
                    break

                data = ser.read(4096)

                if not data:
                    continue

                total_serial_bytes += len(data)

                frames = parser.feed(data)

                for frame in frames:

                    # ------------------------------------------------
                    # Decode CSI
                    # ------------------------------------------------

                    csi = decode_csi(frame)

                    # ------------------------------------------------
                    # Verify expected CSI length
                    # ------------------------------------------------

                    if len(csi) != 64:

                        print(
                            f"WARNING: "
                            f"CSI length = {len(csi)}"
                        )

                        continue

                    # ------------------------------------------------
                    # Store frame
                    # ------------------------------------------------

                    frame_count += 1

                    timestamps.append(
                        time.time()
                    )

                    rssi_values.append(
                        frame.rssi
                    )

                    channels.append(
                        frame.channel
                    )

                    rates.append(
                        frame.rate
                    )

                    csi_real.append(
                        csi.real.copy()
                    )

                    csi_imag.append(
                        csi.imag.copy()
                    )

                    # ------------------------------------------------
                    # Progress
                    # ------------------------------------------------

                    if frame_count % 500 == 0:

                        current_elapsed = (
                            time.time()
                            - start_time
                        )

                        fps = (
                            frame_count
                            / current_elapsed
                        )

                        print(
                            f"Frames: {frame_count:6d} | "
                            f"FPS: {fps:6.2f} | "
                            f"RSSI: {frame.rssi:4d} | "
                            f"Channel: {frame.channel:2d} | "
                            f"CSI: {len(csi):2d}"
                        )

    except serial.SerialException as exc:

        print("\nSERIAL ERROR:")
        print(exc)

        sys.exit(1)

    except KeyboardInterrupt:

        print(
            "\nRecording interrupted by user."
        )

    # ========================================================
    # NO DATA CHECK
    # ========================================================

    if frame_count == 0:

        print(
            "\nERROR: No CSI frames recorded."
        )

        sys.exit(1)

    # ========================================================
    # CONVERT TO NUMPY
    # ========================================================

    elapsed = (
        time.time()
        - start_time
    )

    timestamps = np.asarray(
        timestamps,
        dtype=np.float64
    )

    rssi_values = np.asarray(
        rssi_values,
        dtype=np.int16
    )

    channels = np.asarray(
        channels,
        dtype=np.int16
    )

    rates = np.asarray(
        rates,
        dtype=np.int16
    )

    csi_real = np.asarray(
        csi_real,
        dtype=np.float32
    )

    csi_imag = np.asarray(
        csi_imag,
        dtype=np.float32
    )

    csi_complex = (
        csi_real
        + 1j * csi_imag
    ).astype(
        np.complex64
    )

    # ========================================================
    # SESSION NAME
    # ========================================================

    session_id = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    npz_path = (
        OUTPUT_DIR
        / f"{MODE}_{session_id}.npz"
    )

    json_path = (
        OUTPUT_DIR
        / f"{MODE}_{session_id}.json"
    )

    # ========================================================
    # SAVE RAW CSI
    # ========================================================

    np.savez_compressed(

        npz_path,

        timestamp=timestamps,

        rssi=rssi_values,

        channel=channels,

        rate=rates,

        csi_real=csi_real,

        csi_imag=csi_imag,

        csi_complex=csi_complex
    )

    # ========================================================
    # METADATA
    # ========================================================

    metadata = {

        "project":
            "wifi-human-presence",

        "dataset_version":
            "esp32s3_raw_v1",

        "label":
            MODE,

        "device":
            "ESP32-S3",

        "port":
            PORT,

        "baud":
            BAUD,

        "record_duration_seconds":
            float(elapsed),

        "frames":
            int(frame_count),

        "frame_rate":
            float(
                frame_count / elapsed
            ),

        "csi_bytes_per_frame":
            128,

        "subcarriers":
            64,

        "csi_shape":
            [
                int(frame_count),
                64
            ],

        "csi_dtype":
            "complex64",

        "real_dtype":
            "float32",

        "imag_dtype":
            "float32",

        "channels_observed":
            sorted(
                set(
                    int(x)
                    for x in channels
                )
            ),

        "rates_observed":
            sorted(
                set(
                    int(x)
                    for x in rates
                )
            ),

        "rssi_min":
            int(
                rssi_values.min()
            ),

        "rssi_max":
            int(
                rssi_values.max()
            ),

        "serial_bytes_received":
            int(
                total_serial_bytes
            ),

        "timestamp_unit":
            "unix_seconds",

        "raw_format":
            "ESP32-S3 CSI I/Q",

        "classes":
            [
                "empty",
                "one_person"
            ]
    }

    with open(
        json_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            metadata,
            f,
            indent=4
        )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print("\n" + "=" * 70)
    print("CSI RECORDING COMPLETE")
    print("=" * 70)

    print(
        f"Label           : {MODE}"
    )

    print(
        f"Frames recorded : {frame_count}"
    )

    print(
        f"Elapsed time    : {elapsed:.2f} s"
    )

    print(
        f"Frame rate      : "
        f"{frame_count / elapsed:.2f} FPS"
    )

    print(
        f"CSI shape       : "
        f"{csi_complex.shape}"
    )

    print(
        f"CSI dtype       : "
        f"{csi_complex.dtype}"
    )

    print(
        f"Channels        : "
        f"{sorted(set(channels.tolist()))}"
    )

    print(
        f"Rates           : "
        f"{sorted(set(rates.tolist()))}"
    )

    print(
        f"RSSI range      : "
        f"{rssi_values.min()} .. "
        f"{rssi_values.max()}"
    )

    print(
        "\nNPZ saved to:"
    )

    print(npz_path)

    print(
        "\nMetadata saved to:"
    )

    print(json_path)

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()