from binance_tracker.util import _install_session_router


class FakeSession:
    def __init__(self):
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.calls[-1]


class FakeClient:
    def __init__(self):
        self.session = FakeSession()


def test_official_session_routes_binance_domain_to_ip():
    client = FakeClient()
    _install_session_router(client, "192.0.2.10")
    client.session.request("GET", "https://api.binance.com/api/v3/ping", headers={})
    _, url, kwargs = client.session.calls[0]
    assert url == "https://192.0.2.10/api/v3/ping"
    assert kwargs["headers"]["Host"] == "api.binance.com"
    assert kwargs["verify"] is False


def test_official_session_keeps_non_binance_urls():
    client = FakeClient()
    _install_session_router(client, "192.0.2.10")
    client.session.request("GET", "https://example.com/test")
    assert client.session.calls[0][1] == "https://example.com/test"


def test_official_session_routes_futures_binance_domain():
    client = FakeClient()
    _install_session_router(client, "192.0.2.10")
    client.session.request("GET", "https://fapi.binance.com/fapi/v1/ping")
    _, url, kwargs = client.session.calls[0]
    assert url == "https://192.0.2.10/fapi/v1/ping"
    assert kwargs["headers"]["Host"] == "fapi.binance.com"