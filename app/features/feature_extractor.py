import numpy as np


class FeatureExtractor:
    """
    Extracts numerical features from preprocessed CSI.
    """

    def extract(self, csi: np.ndarray) -> dict:

        return {
            "mean": float(np.mean(csi)),
            "std": float(np.std(csi)),
            "max": float(np.max(csi)),
            "min": float(np.min(csi)),
            "energy": float(np.sum(csi ** 2)),
            "variance": float(np.var(csi)),
        }