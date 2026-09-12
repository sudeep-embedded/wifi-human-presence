from app.receiver.serial_reader import SerialReader


class ReceiverManager:
    """
    Manages multiple CSI receivers.
    """

    def __init__(self):
        self.receivers = {}

    def add_receiver(
        self,
        receiver_id: str,
        port: str,
        baud_rate: int = 921600,
    ):

        if receiver_id in self.receivers:
            raise ValueError(f"Receiver '{receiver_id}' already exists.")

        self.receivers[receiver_id] = SerialReader(
            port=port,
            baud_rate=baud_rate,
        )

    def start_all(self):

        for receiver in self.receivers.values():
            receiver.start()

    def stop_all(self):

        for receiver in self.receivers.values():
            receiver.stop()

    def get_receiver(self, receiver_id: str):

        return self.receivers.get(receiver_id)