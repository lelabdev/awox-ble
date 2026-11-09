"""Status must not block on BLE advertising while a session is held."""

import pytest

from awox_ble import cli
from awox_ble.state import LampState, ScanObservation


@pytest.mark.asyncio
async def test_status_returns_last_request_without_scanning(monkeypatch, capsys) -> None:
    async def fake_request(action, value=None):
        assert action == "service-status"
        return {"connected": True, "last_command": {"action": "dim", "value": None}}

    async def forbidden_scan(*args, **kwargs):
        pytest.fail("status must not scan while the mesh session is connected")

    monkeypatch.setattr(cli, "request", fake_request)
    monkeypatch.setattr(cli, "scan_state", forbidden_scan)

    assert await cli.main_async("status", None) == 0
    output = capsys.readouterr().out
    assert "dim" in output
    assert "not independently verified" in output


@pytest.mark.asyncio
async def test_unconnected_short_beacon_returns_fast_partial_state(monkeypatch, capsys) -> None:
    async def fake_request(action, value=None):
        return {"connected": False}

    async def fake_scan(mac, timeout):
        assert timeout == 12
        return ScanObservation(state=None, seen=True)

    monkeypatch.setattr(cli, "request", fake_request)
    monkeypatch.setattr(cli, "scan_state", fake_scan)
    monkeypatch.setattr(cli, "load_mesh_config", lambda: type("Config", (), {"mac": "00"})())

    assert await cli.main_async("status", None) == 3
    output = capsys.readouterr().err
    assert "detected" in output
    assert "light scan" in output


@pytest.mark.asyncio
async def test_explicit_scan_releases_before_waiting(monkeypatch, capsys) -> None:
    called = []

    async def fake_request(action, value=None):
        called.append(action)
        return {"ok": True}

    async def fake_scan(mac, timeout):
        called.append(("scan", timeout))
        return ScanObservation(
            LampState(0x1234, True, 25, 3000), seen=True, confirmed=True, frames=2
        )

    monkeypatch.setattr(cli, "request", fake_request)
    monkeypatch.setattr(cli, "scan_state", fake_scan)
    monkeypatch.setattr(cli, "load_mesh_config", lambda: type("Config", (), {"mac": "00"})())

    assert await cli.main_async("scan", None) == 0
    assert called == ["release", ("scan", 70)]
    assert "Brightness: 25%" in capsys.readouterr().out
