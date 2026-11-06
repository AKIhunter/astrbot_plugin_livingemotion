"""Independent offline fixtures; no product functions are replaced."""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from budget_support import Rig
from host_environment import configure_host


def pytest_addoption(parser):
    parser.addoption("--budget-host-source", default=None,
                     help="Explicit AstrBot source root for offline Provider tests")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("offline_verification_network_forbidden")

    for name in ("connect", "connect_ex", "sendto", "bind"):
        monkeypatch.setattr(socket.socket, name, forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


@pytest.fixture
async def rig(tmp_path):
    item = Rig(tmp_path / "synthetic.sqlite3")
    await item.open()
    try:
        yield item
    finally:
        await item.close()


@pytest.fixture
async def wire(tmp_path, monkeypatch, request):
    # AstrBot imports can create its data directory. Confine them to temp storage.
    monkeypatch.chdir(tmp_path)
    configure_host(request.config.getoption("--budget-host-source"))
    from budget_support import Wire

    item = Wire()
    try:
        yield item
    finally:
        await item.provider.client.close()
        await item.unused_client.close()
