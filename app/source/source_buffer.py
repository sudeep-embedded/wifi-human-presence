from collections import deque
from typing import Optional

import numpy as np


class SourceBuffer:
    """
    Stores recent CSI samples for window-based processing.
    """

    def __init__(self, max_size: int = 3000):
        self.max_size = max_size
        self._buffer = deque(maxlen=max_size)

    def add(self, sample: np.ndarray) -> None:
        self._buffer.append(np.asarray(sample, dtype=np.float32))

    def size(self) -> int:
        return len(self._buffer)

    def is_ready(self, window_size: int) -> bool:
        return len(self._buffer) >= window_size

    def get_latest(self, window_size: int) -> Optional[np.ndarray]:
        if not self.is_ready(window_size):
            return None

        samples = list(self._buffer)[-window_size:]
        return np.asarray(samples, dtype=np.float32)

    def clear(self) -> None:
        self._buffer.clear()