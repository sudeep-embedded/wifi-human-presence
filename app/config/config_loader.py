"""
YAML configuration loading and validation.

Only the sections needed by the receiver/parser layer are validated here
(serial, logging). Sections for preprocessing/features/model/dashboard will
be added to this schema in later phases -- unvalidated extra keys in the
YAML are currently ignored, not rejected, so the file can be extended
ahead of the code that consumes it without breaking this loader.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ConfigError(ValueError):
    """Raised when the YAML config is missing required keys or has
    values outside their valid range."""

@dataclass(frozen=True)
class ReceiverConfig:
    mode: str

@dataclass(frozen=True)
class SerialConfig:
    port: str
    baud_rate: int
    reconnect_delay_s: float
    read_timeout_s: float


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    log_dir: str
    log_filename: str
    max_bytes: int
    backup_count: int


@dataclass(frozen=True)
class AppConfig:
    receiver: ReceiverConfig
    serial: SerialConfig
    logging: LoggingConfig
    raw: dict = field(repr=False)

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _require(d: dict, key: str, path: str) -> object:
    if key not in d:
        raise ConfigError(f"Missing required config key: {path}.{key}")
    return d[key]


def load_config(path: str | Path) -> AppConfig:
    """Load and validate config/config.yaml (or an override path).

    Raises ConfigError on any missing key or invalid value -- fails loudly
    at startup rather than letting a bad config surface as a confusing
    runtime error three layers deep (e.g. a garbage baud rate producing
    nothing but CRC failures with no obvious cause).
    """
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ConfigError("Top-level YAML must be a mapping")
    receiver_raw = raw.get("receiver", {})
    receiver = ReceiverConfig(
    mode=str(receiver_raw.get("mode", "serial")).lower()
)

    if receiver.mode not in {"serial", "synthetic"}:
        raise ConfigError(
        "receiver.mode must be either 'serial' or 'synthetic'"
    )

    serial_raw = _require(raw, "serial", "")
    serial = SerialConfig(
        port=str(_require(serial_raw, "port", "serial")),
        baud_rate=int(_require(serial_raw, "baud_rate", "serial")),
        reconnect_delay_s=float(serial_raw.get("reconnect_delay_s", 2.0)),
        read_timeout_s=float(serial_raw.get("read_timeout_s", 1.0)),
    )
    if serial.baud_rate <= 0:
        raise ConfigError("serial.baud_rate must be positive")
    if serial.reconnect_delay_s < 0:
        raise ConfigError("serial.reconnect_delay_s must be >= 0")

    logging_raw = raw.get("logging", {})
    level = str(logging_raw.get("level", "INFO")).upper()
    if level not in _VALID_LOG_LEVELS:
        raise ConfigError(
            f"logging.level must be one of {sorted(_VALID_LOG_LEVELS)}, got {level!r}"
        )
    logging_cfg = LoggingConfig(
        level=level,
        log_dir=str(logging_raw.get("log_dir", "logs")),
        log_filename=str(logging_raw.get("log_filename", "app.log")),
        max_bytes=int(logging_raw.get("max_bytes", 5 * 1024 * 1024)),
        backup_count=int(logging_raw.get("backup_count", 5)),
    )

    return AppConfig(
    receiver=receiver,
    serial=serial,
    logging=logging_cfg,
    raw=raw,
)
