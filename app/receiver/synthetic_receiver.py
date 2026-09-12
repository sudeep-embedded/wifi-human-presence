"""
Synthetic receiver for testing the complete CSI pipeline without ESP32
hardware.

This class mirrors the public interface of SerialReader so the rest of
the application can switch between a real ESP32 serial stream and a
synthetic CSI source without changing downstream code.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass

from app.receiver.csi_source import CSISource
from app.receiver.packet_parser import PacketParser
from app.receiver.protocol import CSIFrame
from app.receiver.synthetic_csi_generator import (
    SyntheticCSIGenerator,
    SyntheticConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class SyntheticReaderStats:
    frames_generated: int = 0
    frames_ok: int = 0
    frames_dropped: int = 0
    running: bool = False


class SyntheticReceiver(CSISource):
    """
    Generates synthetic CSI frames in a background thread.

    Public API intentionally matches SerialReader.
    """

    def __init__(
        self,
        frame_rate_hz: float = 20.0,
        config: SyntheticConfig | None = None,
        max_queue_size: int = 10000,
    ) -> None:

        self.frame_queue: queue.Queue[CSIFrame] = queue.Queue(
            maxsize=max_queue_size
        )

        self._generator = SyntheticCSIGenerator(config)
        self._parser = PacketParser()

        self._frame_interval = 1.0 / frame_rate_hz

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._stats_lock = threading.Lock()
        self._stats = SyntheticReaderStats()

    @property
    def stats(self) -> SyntheticReaderStats:
        with self._stats_lock:
            return SyntheticReaderStats(**self._stats.__dict__)

    def start(self) -> None:

        if self._thread and self._thread.is_alive():
            logger.warning("SyntheticReceiver already running.")
            return

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="synthetic-receiver",
        )

        self._thread.start()

    def stop(self) -> None:

        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:

        with self._stats_lock:
            self._stats.running = True

        logger.info("Synthetic receiver started.")

        while not self._stop_event.is_set():

            raw_frame = self._generator.generate_frame_bytes()

            with self._stats_lock:
                self._stats.frames_generated += 1

            for frame in self._parser.feed(raw_frame):

                try:
                    self.frame_queue.put_nowait(frame)

                except queue.Full:

                    try:
                        self.frame_queue.get_nowait()
                    except queue.Empty:
                        pass

                    self.frame_queue.put_nowait(frame)

            parser_stats = self._parser.stats

            with self._stats_lock:
                self._stats.frames_ok = parser_stats["frames_ok"]
                self._stats.frames_dropped = parser_stats[
                    "frames_dropped"
                ]

            time.sleep(self._frame_interval)

        with self._stats_lock:
            self._stats.running = False

        logger.info("Synthetic receiver stopped.")