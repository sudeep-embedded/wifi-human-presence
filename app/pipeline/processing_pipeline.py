import numpy as np

from app.preprocessing.signal_preprocessor import SignalPreprocessor
from app.features.feature_extractor import FeatureExtractor
from app.dataset.dataset_recorder import DatasetRecorder
from app.source.source_buffer import SourceBuffer
from app.source.window_builder import WindowBuilder


class ProcessingPipeline:

    def __init__(self, dataset_file: str):

        self.preprocessor = SignalPreprocessor()
        self.extractor = FeatureExtractor()
        self.recorder = DatasetRecorder(dataset_file)

        self.buffer = SourceBuffer(max_size=3000)
        self.window_builder = WindowBuilder(
            window_size=100,
            step_size=50,
        )

    def process(
        self,
        frame,
        receiver,
        label,
    ):

        # Convert raw CSI packet into 64 I/Q-derived samples
        processed = self.preprocessor.preprocess(frame)

        # Store sample
        self.buffer.add(processed)

        # Build a 100-sample window
        window = self.window_builder.add(processed)

        # Not enough samples yet
        if window is None:
            return None

        # Rolling variance across the time dimension
        rolling_variance = np.var(window, axis=0)

        features = self.extractor.extract(rolling_variance)

        self.recorder.record(
            timestamp=frame.timestamp_us,
            receiver=receiver,
            label=label,
            features=features,
        )

        return features