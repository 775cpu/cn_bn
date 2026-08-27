import asyncio
import logging
import time
from typing import Any
import aiohttp
from .models import Kline

network_log = logging.getLogger("network")

DEFAULT_DIRECT_IPS = ("13.32.53.197", "18.65.167.85", "13.225.181.100", "99.84.137.219", "18.172.32.150", "13.33.214.96", "143.204.77.51", "13.227.59.18", "13.249.162.25")

class BinanceClient:
    def __init__(self, rest_url: str, ws_url: str, http_proxy: str | None = None, ws_proxy: str | None = None, direct_ip: str | None = None, direct_ws_ip: str | None = None, verify_ssl: bool = True, direct_ips: tuple[str, ...] = (), ip_ping_timeout: float = 5.0, rest_ips: tuple[str, ...] = (), ws_ips: tuple[str, ...] = (), switch_min_ms: float = 20.0, switch_min_ratio: float = 0.20):
        self.rest_url, self.ws_url = rest_url.rstrip("/"), ws_url
        self.http_proxy, self.ws_proxy = http_proxy, ws_proxy
        self.verify_ssl = verify_ssl
        self.ip_ping_timeout = ip_ping_timeout
        fallback_ips = direct_ips or ((direct_ip,) if direct_ip else ())
        self.rest_ips = tuple(dict.fromkeys(rest_ips or fallback_ips))
        self.ws_ips = tuple(dict.fromkeys(ws_ips or ((direct_ws_ip,) if direct_ws_ip else fallback_ips)))
        self.ip_ping_timeout = ip_ping_timeout
        self.switch_min_ms = switch_min_ms
        self.switch_min_ratio = switch_min_ratio
        self.current_rest_ip: str | None = None
        self.current_ws_ip: str | None = None
        self.rest_headers: dict[str, str] | None = None
        self.ws_headers: dict[str, str] | None = None
        if direct_ip:
            self.rest_url = f"https://{direct_ip}"
            self.rest_headers = {"Host": "api.binance.com"}
        if direct_ws_ip or direct_ip:
            self.ws_url = f"wss://{direct_ws_ip or direct_ip}:9443/stream"
            self.ws_headers = {"Host": "stream.binance.com"}
        self.session: aiohttp.ClientSession | None = None

    async def select_best_ip(self) -> bool:
        if not self.rest_ips and not self.ws_ips:
            return False
        assert self.session is not None
        network_log.info("IP latency probe started rest=%d ws=%d timeout=%.1fs", len(self.rest_ips), len(self.ws_ips), self.ip_ping_timeout)

        async def probe_rest(ip: str):
            started = time.perf_counter()
            try:
                async with self.session.get(f"https://{ip}/api/v3/time", headers={"Host": "api.binance.com"}, ssl=False, timeout=aiohttp.ClientTimeout(total=self.ip_ping_timeout)) as response:
                    response.raise_for_status()
                    await response.read()
                return ip, time.perf_counter() - started
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                network_log.warning("REST IP probe failed ip=%s error=%s", ip, exc)
                return ip, None

        async def probe_ws(ip: str):
            started = time.perf_counter()
            websocket = None
            try:
                websocket = await self.session.ws_connect(
                    f"wss://{ip}:9443/ws/btcusdt@aggTrade",
                    headers={"Host": "stream.binance.com"},
                    ssl=False,
                    timeout=self.ip_ping_timeout,
                    heartbeat=None,
                )
                return ip, time.perf_counter() - started
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                network_log.warning("WS IP probe failed ip=%s error=%s", ip, exc)
                return ip, None
            finally:
                if websocket is not None:
                    await websocket.close()

        async def select(pool: tuple[str, ...], host: str, current: str | None):
            if not pool:
                return current, None, False, []
            probe_function = probe_rest if host == "api.binance.com" else probe_ws
            results = await asyncio.gather(*(probe_function(ip) for ip in pool))
            available = sorted((result for result in results if result[1] is not None), key=lambda item: item[1])
            if not available:
                network_log.error("no usable Binance IP host=%s pool=%s", host, pool)
                return current, None, False, []
            candidate, latency = available[0]
            old_latency = next((value for ip, value in results if ip == current), None)
            improvement = old_latency is None or (old_latency - latency) * 1000 >= self.switch_min_ms or latency <= old_latency * (1 - self.switch_min_ratio)
            selected = candidate if current is None or improvement else current
            return selected, latency, selected != current, available

        rest_ip, rest_latency, rest_changed, rest_available = await select(self.rest_ips, "api.binance.com", self.current_rest_ip)
        ws_ip, ws_latency, ws_changed, ws_available = await select(self.ws_ips, "stream.binance.com", self.current_ws_ip)
        self.current_rest_ip, self.current_ws_ip = rest_ip, ws_ip
        if rest_ip:
            self.rest_url, self.rest_headers = f"https://{rest_ip}", {"Host": "api.binance.com"}
        if ws_ip:
            self.ws_url, self.ws_headers = f"wss://{ws_ip}:9443/stream", {"Host": "stream.binance.com"}
        network_log.info("selected REST IP=%s latency=%s candidates=%s; WS IP=%s latency=%s candidates=%s", rest_ip, round(rest_latency * 1000, 1) if rest_latency else None, [(ip, round(latency * 1000, 1)) for ip, latency in rest_available], ws_ip, round(ws_latency * 1000, 1) if ws_latency else None, [(ip, round(latency * 1000, 1)) for ip, latency in ws_available])
        network_log.info("IP latency probe completed REST=%s WS=%s", rest_ip or "domain", ws_ip or "domain")
        return rest_changed or ws_changed

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        return self

    async def __aexit__(self, *_):
        if self.session:
            await self.session.close()

    async def klines(self, symbol: str, interval: str, limit: int) -> list[Kline]:
        assert self.session is not None
        url = f"{self.rest_url}/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        for attempt in range(3):
            try:
                async with self.session.get(url, params=params, proxy=self.http_proxy, headers=self.rest_headers if self.rest_url.startswith("https://") else None, ssl=self.verify_ssl) as response:
                    response.raise_for_status()
                    payload: Any = await response.json()
                    return [Kline(int(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]), float(row[7]), int(row[8]), index < len(payload) - 1) for index, row in enumerate(payload)]
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                network_log.warning("REST %s %s attempt=%d: %s", symbol, interval, attempt + 1, exc)
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
        return []

    async def stream(self, symbols: set[str]):
        assert self.session is not None
        streams = "/".join(f"{symbol.lower()}@aggTrade" for symbol in sorted(symbols))
        url = f"{self.ws_url}?streams={streams}"
        return await self.session.ws_connect(url, proxy=self.ws_proxy, headers=self.ws_headers if self.ws_url.startswith("wss://") else None, ssl=self.verify_ssl, heartbeat=20, autoping=True, timeout=30)
