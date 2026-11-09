"""Configuration shared by the local CLI and daemon."""

from __future__ import annotations

import os
from pathlib import Path

from awox_mesh.config import Config, load_default_env_files


def socket_path() -> Path:
    configured = os.environ.get("AWOX_BLE_SOCKET")
    if configured:
        return Path(configured).expanduser()
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    return Path(runtime) / "awox-ble.sock" if runtime else Path.home() / ".cache/awox-ble.sock"


def load_mesh_config() -> Config:
    load_default_env_files()
    return Config.from_env(require_mesh_id=True)


def idle_seconds() -> float:
    return max(5.0, float(os.getenv("AWOX_BLE_IDLE_SECONDS", "120")))


def preset_delay() -> float:
    return max(0.0, float(os.getenv("AWOX_BLE_PRESET_DELAY", "2.5")))
