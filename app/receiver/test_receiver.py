from app.receiver.serial_reader import SerialReader

reader = SerialReader(
    port="COM4",      # Change if your ESP32 is on another COM port
    baud_rate=921600,
)

reader.start()

print("Waiting for CSI frames...\n")

try:
    while True:
        frame = reader.frame_queue.get()

        print(
            f"Time={frame.timestamp_us} "
            f"RSSI={frame.rssi} "
            f"CH={frame.channel} "
            f"CSI={len(frame.csi_data)} bytes"
        )

except KeyboardInterrupt:
    reader.stop()