import pytest

from awox_ble import service


class FakeMesh:
    def __init__(self) -> None:
        self.is_connected = False
        self.sent = []
        self.stopped = False

    async def send(self, builder) -> None:
        self.is_connected = True
        self.sent.append(builder(b"0" * 16, 0xCA2A))

    async def stop(self) -> None:
        self.stopped = True
        self.is_connected = False


@pytest.mark.asyncio
async def test_same_connection_is_reused(monkeypatch) -> None:
    instance = FakeMesh()
    monkeypatch.setattr(service, "create", lambda cfg: instance)
    monkeypatch.setattr(service, "load_mesh_config", lambda: object())
    controller = service.LampController(idle=120, delay=0)
    first = await controller.execute("brightness", 25)
    second = await controller.execute("brightness", 100)
    assert first["ok"] is True
    assert second["ok"] is True
    assert controller.connected
    assert len(instance.sent) == 2
    await controller.execute("release")
    assert instance.stopped
    assert not controller.connected


@pytest.mark.asyncio
async def test_preset_sends_two_commands_using_same_session(monkeypatch) -> None:
    instance = FakeMesh()
    monkeypatch.setattr(service, "create", lambda cfg: instance)
    monkeypatch.setattr(service, "load_mesh_config", lambda: object())
    controller = service.LampController(delay=0)
    await controller.execute("bright")
    assert len(instance.sent) == 2
    await controller.close()


@pytest.mark.asyncio
async def test_invalid_values_do_not_connect(monkeypatch) -> None:
    monkeypatch.setattr(
        service, "create", lambda cfg: pytest.fail("Should not connect to Bluetooth")
    )
    controller = service.LampController()
    with pytest.raises(ValueError):
        await controller.execute("brightness", -1)
    with pytest.raises(ValueError):
        await controller.execute("temperature", 101)
    with pytest.raises(ValueError):
        await controller.execute("brightness", None)
    with pytest.raises(ValueError):
        await controller.execute("irrelevant")


@pytest.mark.asyncio
async def test_status_is_passive() -> None:
    controller = service.LampController()
    result = await controller.execute("service-status")
    assert result["connected"] is False
    assert result["ok"] is True
