from app.receiver.receiver_manager import ReceiverManager
from app.pipeline.processing_pipeline import ProcessingPipeline


class DatasetCollector:

    def __init__(self):
        self.receivers = ReceiverManager()

        self.pipeline = ProcessingPipeline(
            dataset_file="dataset/csi_dataset.csv"
        )

        self.current_label = "unknown"

    def add_receiver(self, receiver_id, port):
        self.receivers.add_receiver(
            receiver_id=receiver_id,
            port=port,
        )

    def set_label(self, label):
        self.current_label = label

    def start(self):
        self.receivers.start_all()

    def stop(self):
        self.receivers.stop_all()

    def process_once(self):

        for receiver_name, receiver in self.receivers.receivers.items():

            while not receiver.frame_queue.empty():

                frame = receiver.frame_queue.get()

                features = self.pipeline.process(
                    frame=frame,
                    receiver=receiver_name,
                    label=self.current_label,
                )

                if features is not None:
                    print(
                        f"[{receiver_name}] "
                        f"{self.current_label} "
                        f"Energy={features['energy']:.2f}"
                    )