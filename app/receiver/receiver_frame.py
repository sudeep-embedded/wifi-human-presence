"""
Application-level wrapper around a parsed CSIFrame.

This adds metadata that does not belong to the firmware protocol,
such as which receiver captured the frame and when the PC received it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.receiver.protocol import CSIFrame


@dataclass(slots=True)
class ReceiverFrame:
    """
    CSI frame enriched with receiver metadata.

    Attributes
    ----------
    receiver_id:
        Unique logical receiver identifier.
        Example:
            "receiver_01"

    serial_port:
        Physical COM port.
        Example:
            "COM5"

    received_at:
        PC timestamp when the frame arrived.

    frame:
        Parsed CSI frame from the ESP32.
    """

    receiver_id: str
    serial_port: str
    received_at: datetime
    frame: CSIFrame