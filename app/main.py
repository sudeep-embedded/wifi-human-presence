from app.receiver.receiver_manager import ReceiverManager
from app.fusion.fusion_manager import FusionManager


def main():

    receivers = ReceiverManager()

    receivers.add_receiver(
        receiver_id="left",
        port="COM3",
    )

    # Uncomment when second ESP32 is ready
    #
    # receivers.add_receiver(
    #     receiver_id="right",
    #     port="COM4",
    # )

    fusion = FusionManager()

    receivers.start_all()

    print("System started.")

    try:

        while True:

            left = receivers.get_receiver("left")

            while not left.frame_queue.empty():
                fusion.synchronizer.add_receiver_1(
                    left.frame_queue.get()
                )

            # Uncomment later
            #
            # right = receivers.get_receiver("right")
            #
            # while not right.frame_queue.empty():
            #     fusion.synchronizer.add_receiver_2(
            #         right.frame_queue.get()
            #     )

            pair = fusion.process()

            if pair is not None:
                print("Synchronized frame pair received.")

    except KeyboardInterrupt:
        pass

    finally:
        receivers.stop_all()


if __name__ == "__main__":
    main()