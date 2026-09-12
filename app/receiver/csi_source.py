"""
Abstract interface for all CSI data sources.

Every CSI source in the project must implement this interface.

Examples:
    - SerialSource (ESP32-S3)
    - SyntheticSource (Testing)
    - ReplaySource (Recorded CSI)
    - PCAPSource (Future)

The rest of the application must never know where the CSI came from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from queue import Queue

from app.receiver.protocol import CSIFrame


class CSISource(ABC):
    """Common interface implemented by every CSI source."""

    @property
    @abstractmethod
    def frame_queue(self) -> Queue[CSIFrame]:
        """Queue containing parsed CSIFrame objects."""
        raise NotImplementedError

    @property
    @abstractmethod
    def stats(self):
        """Return source statistics."""
        raise NotImplementedError

    @abstractmethod
    def start(self) -> None:
        """Start producing CSI frames."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """Stop producing CSI frames."""
        raise NotImplementedError