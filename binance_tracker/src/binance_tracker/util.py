"""Compatibility helpers for python-binance on networks requiring direct IPs."""

from __future__ import annotations

import logging
import runpy
import threading
import time
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests

from .client import DEFAULT_DIRECT_IPS

log = logging.getLogger("network")
_PATCH_LOCK = threading.Lock()
_PATCHED = False


def _select_ip(ips: tuple[str, ...], timeout: float) -> str:
    results: list[tuple[float, str]] = []
    for ip in ips:
        started = time.perf_counter()
        try:
            response = requests.get(
                f"https://{ip}/api/v3/time",
                headers={"Host": "api.binance.com"},
                verify=False,
                timeout=timeout,
            )
            response.raise_for_status()
            results.append((time.perf_counter() - started, ip))
        except requests.RequestException as exc:
            log.warning("official client IP probe failed ip=%s error=%s", ip, exc)
    if not results:
        raise ConnectionError(f"no Binance REST IP available: {ips}")
    results.sort()
    selected = results[0][1]
    log.info("official client selected REST IP=%s candidates=%s", selected, [(ip, round(latency * 1000, 1)) for latency, ip in results])
    return selected


def _configured_rest_ips() -> tuple[str, ...]:
    config_file = Path(__file__).resolve().parents[2] / "config.py"
    if config_file.exists():
        values = runpy.run_path(str(config_file)).get("REST_IPS", ())
        if values:
            return tuple(str(ip) for ip in values)
    return DEFAULT_DIRECT_IPS


def _install_session_router(client, ip: str) -> None:
    session = client.session
    original_request = session.request

    @wraps(original_request)
    def request(method, url, **kwargs):
        parsed = urlsplit(url)
        if parsed.hostname and parsed.hostname.endswith(".binance.com"):
            url = urlunsplit((parsed.scheme, ip, parsed.path, parsed.query, parsed.fragment))
            headers = dict(kwargs.get("headers") or {})
            headers["Host"] = parsed.hostname
            kwargs["headers"] = headers
            kwargs["verify"] = False
        return original_request(method, url, **kwargs)

    session.request = request
    client._direct_ip = ip


def patch_binance_client(
    ips: list[str] | tuple[str, ...] | None = None,
    timeout: float = 10.0,
    skip_constructor_ping: bool = True,
) -> None:
    """Monkey-patch python-binance.Client to use Binance REST IPs.

    Call once before ``binance.client.Client(...)``. The selected IP is tested
    using the Binance REST endpoint and all later official-library requests are
    routed through it with the required virtual-host header.
    """
    global _PATCHED
    with _PATCH_LOCK:
        if _PATCHED:
            return
        try:
            from binance.client import Client
        except ImportError as exc:
            raise RuntimeError("python-binance is required for patch_binance_client()") from exc

        original_init = Client.__init__

        @wraps(original_init)
        def init(client, *args, **kwargs):
            selected_ip = _select_ip(tuple(ips or _configured_rest_ips()), timeout)
            original_ping = Client.ping
            if skip_constructor_ping:
                Client.ping = lambda self, *ping_args, **ping_kwargs: {}
            try:
                original_init(client, *args, **kwargs)
            finally:
                Client.ping = original_ping
            _install_session_router(client, selected_ip)

        Client.__init__ = init
        _PATCHED = True
        log.info("python-binance Client IP monkey patch installed")


def create_binance_client(*args, ips=None, timeout=10.0, **kwargs):
    """Create a patched official Binance client."""
    patch_binance_client(ips=ips, timeout=timeout)
    from binance.client import Client
    return Client(*args, **kwargs)
