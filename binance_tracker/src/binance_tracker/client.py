import asyncio
import logging
from typing import Any
import aiohttp
from .models import Kline

network_log = logging.getLogger("network")

class BinanceClient:
    def __init__(self, rest_url: str, ws_url: str, http_proxy: str | None = None, ws_proxy: str | None = None, direct_ip: str | None = None, direct_ws_ip: str | None = None, verify_ssl: bool = True):
        self.rest_url, self.ws_url = rest_url.rstrip("/"), ws_url
        self.http_proxy, self.ws_proxy = http_proxy, ws_proxy
        self.verify_ssl = verify_ssl
        self.rest_headers: dict[str, str] | None = None
        self.ws_headers: dict[str, str] | None = None
        if direct_ip:
            self.rest_url = f"https://{direct_ip}"
            self.rest_headers = {"Host": "api.binance.com"}
        if direct_ws_ip or direct_ip:
            self.ws_url = f"wss://{direct_ws_ip or direct_ip}:9443/stream"
            self.ws_headers = {"Host": "stream.binance.com"}
        self.session: aiohttp.ClientSession | None = None

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
