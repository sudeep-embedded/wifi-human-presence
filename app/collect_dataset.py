from app.collector.dataset_collector import DatasetCollector
import time


LABELS = {
    "0": "empty",
    "1": "one_person",
    "2": "two_people",
    "3": "walking",
    "4": "sitting",
}


def main():

    collector = DatasetCollector()

    collector.add_receiver(
        receiver_id="left",
        port="COM4",
    )

    # Enable later
    #
    # collector.add_receiver(
    #     receiver_id="right",
    #     port="COM4",
    # )

    collector.start()

    print("\n=== WiFi CSI Dataset Collector ===\n")

    print("0 -> Empty Room")
    print("1 -> One Person")
    print("2 -> Two People")
    print("3 -> Walking")
    print("4 -> Sitting")
    print("q -> Quit\n")

    while True:

        key = input("Select Label: ").strip()

        if key == "q":
            break

        if key not in LABELS:
            print("Invalid selection\n")
            continue

        collector.set_label(LABELS[key])

        print(f"\nRecording: {LABELS[key]}")
        print("Press Ctrl+C to stop recording this label.\n")

        try:

            while True:

                collector.process_once()

                time.sleep(0.02)

        except KeyboardInterrupt:

            print("\nRecording stopped.\n")

    collector.stop()


if __name__ == "__main__":
    main()