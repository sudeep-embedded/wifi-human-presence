import numpy as np


class WindowBuilder:
    """
    Builds fixed-length CSI windows from buffered samples.
    """

    def __init__(
        self,
        window_size: int = 100,
        step_size: int = 50,
    ):
        self.window_size = window_size
        self.step_size = step_size

        self._samples = []
        self._since_last_window = 0

    def add(self, sample: np.ndarray):
        sample = np.asarray(sample, dtype=np.float32)

        self._samples.append(sample)
        self._since_last_window += 1

        if len(self._samples) < self.window_size:
            return None

        if self._since_last_window < self.step_size:
            return None

        window = np.asarray(
            self._samples[-self.window_size:],
            dtype=np.float32,
        )

        self._since_last_window = 0

        return window

    def reset(self) -> None:
        self._samples.clear()
        self._since_last_window = 0