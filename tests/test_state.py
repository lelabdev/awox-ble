from awox_ble.state import decode_advert


def test_eglo_connect_z_advert() -> None:
    data = bytes.fromhex("a62011223344030002341201fe4d01ffff043f6000000000000000")
    state = decode_advert(0x160, data)
    assert state is not None
    assert state.mesh_id == 0x1234
    assert state.is_on is True
    assert state.brightness == 100
    assert state.temperature_kelvin == 3003


def test_short_advert_is_ignored() -> None:
    assert decode_advert(0x160, bytes.fromhex("a62011223344")) is None
    assert decode_advert(0x159, bytes(27)) is None
