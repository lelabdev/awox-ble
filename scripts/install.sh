#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
for dependency in uv gatttool systemctl; do
  if ! command -v "$dependency" >/dev/null 2>&1; then
    printf 'Missing dependency: %s\n' "$dependency" >&2
    exit 1
  fi
done

uv sync --locked --project "$ROOT"
install -d -m 700 "$HOME/.local/share" "$HOME/.local/bin" "$HOME/.config/systemd/user"
install -d -m 700 "$HOME/.config/awox-mesh"

LINK="$HOME/.local/share/awox-ble"
if [[ -e "$LINK" && ! -L "$LINK" ]]; then
  printf 'Cannot replace an existing directory: %s\n' "$LINK" >&2
  exit 1
fi
ln -sfn "$ROOT" "$LINK"
ln -sfn "$ROOT/.venv/bin/light" "$HOME/.local/bin/light"
ln -sfn "$ROOT/systemd/awox-ble.service" "$HOME/.config/systemd/user/awox-ble.service"

CONF="$HOME/.config/awox-mesh/config.env"
if [[ ! -f "$CONF" ]]; then
  install -m 600 "$ROOT/config.example.env" "$CONF"
  echo "Created $CONF; edit its placeholder values before controlling the light."
else
  chmod 600 "$CONF"
  echo "Preserved the existing $CONF."
fi

systemctl --user daemon-reload
systemctl --user enable --now awox-ble.service
echo "Installed. Try: light service-status"
