from dataclasses import dataclass, field
import os
from pathlib import Path
import runpy

DEFAULT_INTERVALS = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M")
INTERVAL_MS = {"1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000, "12h": 43_200_000, "1d": 86_400_000, "3d": 259_200_000, "1w": 604_800_000}

@dataclass(frozen=True)
class Settings:
    symbols: tuple[str, ...] = ("BTCUSDT",)
    rest_url: str = field(default_factory=lambda: os.getenv("BINANCE_REST_URL", "https://api.binance.com"))
    ws_url: str = field(default_factory=lambda: os.getenv("BINANCE_WS_URL", "wss://stream.binance.com:9443/stream"))
    http_proxy: str | None = field(default_factory=lambda: os.getenv("BINANCE_HTTP_PROXY"))
    ws_proxy: str | None = field(default_factory=lambda: os.getenv("BINANCE_WS_PROXY"))
    direct_ip: str | None = field(default_factory=lambda: os.getenv("BINANCE_DIRECT_IP"))
    direct_ws_ip: str | None = field(default_factory=lambda: os.getenv("BINANCE_DIRECT_WS_IP"))
    direct_ips: tuple[str, ...] = ()
    rest_ips: tuple[str, ...] = ()
    ws_ips: tuple[str, ...] = ()
    ip_select_seconds: int = 300
    ip_ping_timeout: float = 5.0
    ip_switch_min_ms: float = 20.0
    ip_switch_min_ratio: float = 0.20
    network_mode: str = "domain"
    verify_ssl: bool = field(default_factory=lambda: os.getenv("BINANCE_VERIFY_SSL", "1") != "0")
    calibration_seconds: int = 300
    history_limit: int = 200
    boll_period: int = 20
    boll_stddev: float = 2.0
    intervals: tuple[str, ...] = DEFAULT_INTERVALS
    log_dir: str = "logs"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5
    display_mode: str = "in_place"
    display_only_breakouts: bool = True
    display_price_decimals: int = 8
    display_boll_decimals: int = 8
    display_refresh_seconds: float = 0.0

    @classmethod
    def from_python(cls, filename: str | Path) -> "Settings":
        data = runpy.run_path(str(filename))
        base = cls()
        return cls(
            symbols=tuple(str(symbol).upper() for symbol in data.get("SYMBOLS", base.symbols)),
            rest_url=data.get("REST_URL", base.rest_url), ws_url=data.get("WS_URL", base.ws_url),
            http_proxy=data.get("HTTP_PROXY") or None, ws_proxy=data.get("WS_PROXY") or None,
            direct_ip=data.get("DIRECT_IP") or None, direct_ws_ip=data.get("DIRECT_WS_IP") or None,
            direct_ips=tuple(data.get("DIRECT_IPS", base.direct_ips)), ip_select_seconds=int(data.get("IP_SELECT_SECONDS", base.ip_select_seconds)), ip_ping_timeout=float(data.get("IP_PING_TIMEOUT", base.ip_ping_timeout)),
            rest_ips=tuple(data.get("REST_IPS", base.rest_ips)), ws_ips=tuple(data.get("WS_IPS", base.ws_ips)), ip_switch_min_ms=float(data.get("IP_SWITCH_MIN_MS", base.ip_switch_min_ms)), ip_switch_min_ratio=float(data.get("IP_SWITCH_MIN_RATIO", base.ip_switch_min_ratio)), network_mode=str(data.get("NETWORK_MODE", base.network_mode)),
            verify_ssl=bool(data.get("VERIFY_SSL", base.verify_ssl)), calibration_seconds=int(data.get("CALIBRATION_SECONDS", base.calibration_seconds)),
            history_limit=int(data.get("HISTORY_LIMIT", base.history_limit)), boll_period=int(data.get("BOLL_PERIOD", base.boll_period)),
            boll_stddev=float(data.get("BOLL_STDDEV", base.boll_stddev)), intervals=tuple(data.get("INTERVALS", base.intervals)),
            log_dir=data.get("LOG_DIR", base.log_dir), log_max_bytes=int(data.get("LOG_MAX_BYTES", base.log_max_bytes)),
            log_backup_count=int(data.get("LOG_BACKUP_COUNT", base.log_backup_count)), display_mode=data.get("DISPLAY_MODE", base.display_mode),
            display_only_breakouts=bool(data.get("DISPLAY_ONLY_BREAKOUTS", base.display_only_breakouts)),
            display_price_decimals=int(data.get("DISPLAY_PRICE_DECIMALS", base.display_price_decimals)), display_boll_decimals=int(data.get("DISPLAY_BOLL_DECIMALS", base.display_boll_decimals)),
            display_refresh_seconds=float(data.get("DISPLAY_REFRESH_SECONDS", base.display_refresh_seconds)),
        )
