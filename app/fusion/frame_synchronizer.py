from collections import deque
from typing import Optional

from app.receiver.receiver_frame import CSIFrame


class FrameSynchronizer:
    """
    Matches CSI frames from two receivers using timestamps.
    """

    def __init__(self, max_time_difference_us: int = 50_000):
        self.receiver_1 = deque()
        self.receiver_2 = deque()
        self.max_time_difference_us = max_time_difference_us

    def add_receiver_1(self, frame: CSIFrame):
        self.receiver_1.append(frame)

    def add_receiver_2(self, frame: CSIFrame):
        self.receiver_2.append(frame)

    def get_synchronized_pair(
        self,
    ) -> Optional[tuple[CSIFrame, CSIFrame]]:

        while self.receiver_1 and self.receiver_2:

            frame1 = self.receiver_1[0]
            frame2 = self.receiver_2[0]

            delta = abs(frame1.timestamp_us - frame2.timestamp_us)

            if delta <= self.max_time_difference_us:
                return (
                    self.receiver_1.popleft(),
                    self.receiver_2.popleft(),
                )

            if frame1.timestamp_us < frame2.timestamp_us:
                self.receiver_1.popleft()
            else:
                self.receiver_2.popleft()

        return None