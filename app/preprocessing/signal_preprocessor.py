import numpy as np
from app.receiver.receiver_frame import CSIFrame


class SignalPreprocessor:
    """
    Converts raw ESP32 CSI I/Q bytes into CSI amplitude values.
    """

    def remove_dc(self, frame: CSIFrame):
        raw = np.frombuffer(frame.csi_data, dtype=np.int8)

        # ESP32 CSI format: alternating I/Q signed 8-bit values
        i = raw[0::2].astype(np.float32)
        q = raw[1::2].astype(np.float32)

        # Complex CSI -> amplitude
        amplitude = np.sqrt(i * i + q * q)

        # Remove DC component
        amplitude = amplitude - np.mean(amplitude)

        return amplitude

    def normalize(self, csi):
        std = np.std(csi)

        if std == 0:
            return csi

        return (csi - np.mean(csi)) / std

    def preprocess(self, frame: CSIFrame):
        csi = self.remove_dc(frame)
        csi = self.normalize(csi)

        return csi