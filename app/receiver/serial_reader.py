"""
Threaded serial reader.

Runs pyserial reads on a dedicated background thread so the rest of the
application (dashboard, DB writer, inference loop) never blocks on UART
I/O. Automatically reconnects on any serial exception (cable unplugged,
board reset, port busy) instead of dying.

Thread safety: the only shared mutable state exposed to other threads is
the `frame_queue` (a stdlib `queue.Queue`, itself thread-safe) and the
`stats` dict, which is only ever read from other threads and only ever
written from the reader thread -- so no lock is needed for `stats` under
CPython's GIL for simple dict key assignment, but we still guard it with
a lock because multi-step stat updates (increment-then-read elsewhere)
are not atomic and this code should not depend on GIL implementation
details to be correct.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field

import serial
import serial.serialutil

from app.receiver.packet_parser import PacketParser
from app.receiver.protocol import CSIFrame
from app.receiver.csi_source import CSISource

logger = logging.getLogger(__name__)


@dataclass
class ReaderStats:
    connected: bool = False
    bytes_read: int = 0
    frames_ok: int = 0
    frames_dropped: int = 0
    reconnect_count: int = 0
    last_error: str | None = None


class SerialReader(CSISource):
    """Background-threaded serial port reader producing CSIFrame objects.

    Usage:
        reader = SerialReader(port="COM5", baud_rate=921600)
        reader.start()
        while True:
            frame = reader.frame_queue.get()
            ...
        reader.stop()
    """

    def __init__(
        self,
        port: str,
        baud_rate: int,
        reconnect_delay_s: float = 2.0,
        read_timeout_s: float = 1.0,
        max_queue_size: int = 10_000,
    ) -> None:
        self._port = port
        self._baud_rate = baud_rate
        self._reconnect_delay_s = reconnect_delay_s
        self._read_timeout_s = read_timeout_s

        self._frame_queue: "queue.Queue[CSIFrame]" = queue.Queue(maxsize=max_queue_size)

        self._parser = PacketParser()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        self._stats_lock = threading.Lock()
        self._stats = ReaderStats()

    @property
    def frame_queue(self) -> "queue.Queue[CSIFrame]":
        return self._frame_queue

    @property
    def stats(self) -> ReaderStats:
        with self._stats_lock:
            # Return a copy so callers can't mutate our internal state.
            return ReaderStats(**self._stats.__dict__)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            logger.warning("SerialReader already running, ignoring start()")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="serial-reader", daemon=True
        )
        self._thread.start()
        logger.info("SerialReader thread started for port %s", self._port)

    def stop(self, join_timeout_s: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=join_timeout_s)
            if self._thread.is_alive():
                logger.warning(
                    "SerialReader thread did not stop within %.1fs", join_timeout_s
                )
        logger.info("SerialReader stopped")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._read_loop()
            except (serial.serialutil.SerialException, OSError) as exc:
                with self._stats_lock:
                    self._stats.connected = False
                    self._stats.last_error = str(exc)
                    self._stats.reconnect_count += 1
                logger.warning(
                    "Serial error on %s: %s -- reconnecting in %.1fs",
                    self._port,
                    exc,
                    self._reconnect_delay_s,
                )
                self._stop_event.wait(self._reconnect_delay_s)

    def _read_loop(self) -> None:
        with serial.Serial(
            port=self._port,
            baudrate=self._baud_rate,
            timeout=self._read_timeout_s,
        ) as ser:
            with self._stats_lock:
                self._stats.connected = True
                self._stats.last_error = None
            logger.info("Connected to %s @ %d baud", self._port, self._baud_rate)

            while not self._stop_event.is_set():
                chunk = ser.read(4096)  # returns b"" on timeout, not an error
                if not chunk:
                    continue

                with self._stats_lock:
                    self._stats.bytes_read += len(chunk)

                for frame in self._parser.feed(chunk):
                    self._enqueue_frame(frame)

                parser_stats = self._parser.stats
                with self._stats_lock:
                    self._stats.frames_ok = parser_stats["frames_ok"]
                    self._stats.frames_dropped = parser_stats["frames_dropped"]

    def _enqueue_frame(self, frame: CSIFrame) -> None:
        try:
            self._frame_queue.put_nowait(frame)
        except queue.Full:
            # Downstream (DB writer / inference) is falling behind. Drop
            # the oldest queued frame to make room rather than blocking
            # the reader thread, which would risk losing UART bytes.
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._frame_queue.put_nowait(frame)
            except queue.Full:
                pass  # extremely unlikely race; drop this frame silently
            logger.debug("frame_queue full, dropped oldest frame to make room")
