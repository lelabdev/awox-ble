# awox-ble

Control AwoX / EGLO Bluetooth lights from Linux, without a cloud service or
Zigbee coordinator. Written in Python, based on the
[awox-mesh](https://github.com/paul-schoettl/awox-mesh) BLE implementation.

The `awox-ble` **systemd user service** keeps one authenticated Bluetooth
session open between commands. The lightweight `light` CLI talks to that
service through a private Unix socket, avoiding repeated pairing delays.

## Tested hardware

| Property | Tested device |
| --- | --- |
| Product | **EGLO Filament Zigbee TW** |
| Bluetooth model | `ESMLFzm_w6_TW` |
| Hardware revision | `4.63` |
| Firmware | `3.0.2_1610` |
| Companion app | AwoX HomeControl |
| Transport | Bluetooth Low Energy, AwoX Connect-Z mesh |

Despite the **Zigbee** branding, this project uses the bulb's **Bluetooth**
interface. No Zigbee adapter is required. Other models and firmware versions
may behave differently and have **not** been verified.

## Quick start (Linux)

### 1. Prerequisites

- Python 3.12 or newer (automatically managed by [uv](https://docs.astral.sh/uv/)).
- `git`, `uv`, `systemd --user`, BlueZ, and a functioning BLE adapter.
- **`gatttool`** available on `PATH`: the selected upstream GATT backend
  needs this **legacy BlueZ utility**. It is not bundled with all modern
  distributions. If `command -v gatttool` fails, install a compatible
  legacy BlueZ/GATT tool before proceeding.
- Your own AwoX/EGLO Bluetooth lamp credentials.

This was developed on Arch Linux; other Linux distributions are untested.

### 2. Install the controller

```bash
git clone https://github.com/lelabdev/awox-ble.git
cd awox-ble
bash scripts/install.sh
```

The installer installs locked Python dependencies, creates the `light` command,
and enables `awox-ble.service` for the current user. You do not need root for
the installer. The service can be installed from **any clone directory**.

The installer does not alter your lamp. It does not overwrite an existing
`~/.config/awox-mesh/config.env`, and on first install copies the example
configuration there with permissions `0600`.

### 3. Configure your own bulb

Edit `~/.config/awox-mesh/config.env`. It should contain:

```ini
# EXAMPLE VALUES ONLY — replace all of them with your bulb's values
AWOX_MAC=AA:BB:CC:DD:EE:FF
AWOX_MESH_NAME=your_mesh_name
AWOX_MESH_PASSWORD=your_local_mesh_password
AWOX_MESH_ID=0x1234
AWOX_BACKEND=gatt
```

How to find the values:

- **MAC address**: use `uv run awox-mesh scan` or a BLE scanner.
- **Mesh address**: use `uv run awox-mesh discover` to read the lamp's
  advertised address; `AWOX_MESH_ID` is not the same as its Bluetooth MAC.
- **Mesh name and password**: consult the [AwoX mesh credentials
  tool](https://fsaris.github.io/EspHome-AwoX-BLE-mesh-hub/awoxh-mesh-credentials-tool/).
  **Important:** credentials returned by the cloud may not be the actual
  credentials accepted locally by certain firmware revisions. If login is
  rejected with `0x0e`, verify your bulb's local authentication rather than
  assuming a universal factory password.

Keep your actual password, address, mobile diagnostic logs and captures private.
**Never commit the populated configuration file.**

### 4. Use the light

```bash
light status          # fast status: last request while connected, or short passive scan
light scan            # fresh verified BLE advertisement; may take up to 70 s
light brightness 50   # 50% brightness
light bright          # preset: 100%, neutral white
light dim             # preset: 25%, warm white
light on              # power on
light off             # power off
light temperature 80  # warmer white
```

Other useful commands:

| Command | Description |
| --- | --- |
| `light` | Same as `light status` |
| `light service-status` | Check whether the background session is connected |
| `light release` | Disconnect immediately, allowing the mobile app to connect |
| `systemctl --user status awox-ble.service` | Inspect the daemon |
| `journalctl --user -u awox-ble.service -n 50` | View daemon logs |

The service **does not connect at startup**. It connects when a control
command is issued, keeps the session active for up to **120 seconds after the
last command**, then disconnects so AwoX HomeControl on a phone can reconnect.

**Status vs. fresh scan:** When the BLE session is connected, `light status`
responds immediately with the last *requested* command and explicitly marks
it **unverified**. The light does not normally broadcast its full status
while connected. When the session is disconnected, `light status` listens for
12 seconds; it distinguishes a detected bulb with short-only advertisements
from one that is absent. For an independently observed brightness and colour
temperature, use `light scan`: it **releases the active BLE connection** and
waits up to **70 seconds** for multiple matching, time-separated full status
advertisements. The first full advertisement may contain an older value cached
by BlueZ or not yet updated by the bulb. A state is only marked confirmed after
repeated agreement at least 12 seconds into the scan. If confirmation is not
possible before the timeout, the latest observed brightness is shown as
**unconfirmed**, rather than being represented as a verified current value.
Connect-Z bulbs may send many short beacons but only a few full status beacons
per minute. After `light scan`, the next control command may have
cold-connection latency.

### Performance and limitations

On the tested EGLO bulb, a simple brightness command took **4.17 s cold**
versus **0.20 s with the connection already open**. Actual timings depend on
radio conditions and the hardware.

Presets send brightness first and colour temperature second, with a **2.5 s
delay** because this firmware may silently drop rapid consecutive commands.
These presets have not yet been independently verified on all hardware.
A successful GATT write does **not** guarantee that the light applied the
new setting. Use `light scan` for independent confirmation from a full
Bluetooth advertisement.

The service listens only on the user-accessible Unix socket
`$XDG_RUNTIME_DIR/awox-ble.sock` (mode `0600`), not on a TCP port.
Only one control request runs at a time.

To adjust idle time or preset spacing, edit
`~/.config/systemd/user/awox-ble.service` or add a systemd drop-in with
`systemctl --user edit awox-ble.service`:

- `AWOX_BLE_IDLE_SECONDS`: inactivity timeout (default 120 seconds)
- `AWOX_BLE_PRESET_DELAY`: delay between preset writes (default 2.5 seconds)
- `AWOX_BLE_SOCKET`: optional socket location

Then run `systemctl --user daemon-reload && systemctl --user restart awox-ble.service`.

## Related projects and protocol references

- [paul-schoettl/awox-mesh](https://github.com/paul-schoettl/awox-mesh):
  the pinned Python dependency implementing AwoX BLE authentication,
  session encryption and device control.
- [BastiAKA/awoxble2mqtt-api](https://github.com/BastiAKA/awoxble2mqtt-api):
  another implementation with reverse-engineered Connect-Z packets for
  brightness, colour temperature and power.
- [fsaris/EspHome-AwoX-BLE-mesh-hub](https://github.com/fsaris/EspHome-AwoX-BLE-mesh-hub):
  a related ESPHome mesh project and the credentials tool linked above.

This repository implements a local controller and does not claim ownership of
the upstream BLE protocol implementation.

## Development

```bash
uv sync --locked --group dev
uv run pytest -q
uv run ruff check .
```

Tests use simulated connections; they **do not operate a real bulb**.
The service also sends **no commands automatically** when it starts.

## License

MIT. The upstream `awox-mesh` dependency is separately MIT licensed.
