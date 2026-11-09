# awox-ble

Fast, local control of AwoX / EGLO Connect-Z Bluetooth lighting from Linux.

Python is used to reuse the [awox-mesh](https://github.com/paul-schoettl/awox-mesh)
protocol implementation. A user-level systemd service holds a **single BLE
session**, and the small `light` CLI communicates with it over a private Unix
socket instead of reconnecting to the lamp on every action.

This is an independent project, not a fork of the upstream BLE protocol library.

## Commands

| Command | Effect |
| --- | --- |
| `light` or `light status` | Read passive BLE advertisements; no connection required |
| `light service-status` | Inspect the daemon's current connection |
| `light bright` | Preset: 100% brightness, neutral white |
| `light dim` | Preset: 25% brightness, warm white |
| `light on`, `light off` | Switch power |
| `light brightness 50` | Set brightness from 0 to 100% |
| `light temperature 80` | Set warm-white percentage |
| `light release` | Disconnect so the phone app can connect |

Commands are sent over a socket at `$XDG_RUNTIME_DIR/awox-ble.sock`,
with mode `0600`. No HTTP endpoint, account, or cloud is needed.

## Install

Requires Arch Linux or a compatible Linux system with BlueZ, `gatttool`,
and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/lelabdev/awox-ble.git
cd awox-ble
uv sync --locked
ln -s "$PWD/.venv/bin/light" ~/.local/bin/light
mkdir -p ~/.config/systemd/user
ln -s "$PWD/systemd/awox-ble.service" ~/.config/systemd/user/awox-ble.service
systemctl --user daemon-reload
systemctl --user enable --now awox-ble.service
```

AwoX BLE credentials belong in `~/.config/awox-mesh/config.env` with
permissions `0600`. They are **not part of this repository**. Configure
`AWOX_MAC`, `AWOX_MESH_NAME`, `AWOX_MESH_PASSWORD`,
`AWOX_MESH_ID`, and `AWOX_BACKEND=gatt`.

## Session and performance

The service does not contact or change the light on startup. It connects on
the first control request and reuses the authenticated connection for
subsequent requests. It releases the connection after **120 seconds** without
commands to let the mobile app access the same bulb. `light release`
disconnects immediately.

On the initial EGLO device, the measured latency for a brightness command
was 4.17 s (cold) versus 0.20 s (warm). Latency varies with the Bluetooth
adapter, firmware, and connection state.

Presets currently send brightness first and color temperature second, with
a configurable 2.5 s gap; the firmware may drop rapid consecutive writes.
Successful GATT writes are *not* equivalent to verified lamp state. Use
`light status` for an independent status advertisement.

Customize these settings through the user service environment:

- `AWOX_BLE_IDLE_SECONDS` — seconds before disconnecting (default 120)
- `AWOX_BLE_PRESET_DELAY` — gap between preset writes (default 2.5)
- `AWOX_BLE_SOCKET` — optional custom Unix socket path

## Development

```bash
uv sync --group dev
uv run pytest -q
uv run ruff check .
```

Tests use a fake mesh; they do not switch any physical lights.

## License

MIT. The pinned upstream `awox-mesh` dependency is also MIT licensed.
