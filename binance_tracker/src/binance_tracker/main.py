import argparse
import asyncio
import logging
from dataclasses import replace
from pathlib import Path
from .config import Settings
from .logging_setup import setup_logging
from .service import BinanceTracker

async def run(args: argparse.Namespace) -> None:
    direct_ip = args.ip or args.rest_ip
    direct_ws_ip = args.ws_ip or args.ip
    settings = Settings.from_python(args.config) if args.config and Path(args.config).exists() else Settings()
    settings = replace(settings, symbols=tuple(args.symbols or settings.symbols), direct_ip=direct_ip or settings.direct_ip, direct_ws_ip=direct_ws_ip or settings.direct_ws_ip, verify_ssl=not (args.insecure or direct_ip or direct_ws_ip) if (args.insecure or direct_ip or direct_ws_ip) else settings.verify_ssl)
    setup_logging(settings.log_dir, settings.log_max_bytes, settings.log_backup_count)
    tracker = BinanceTracker(settings)
    tracker.add_symbols(*settings.symbols)
    logging.getLogger("app").info("starting tracker symbols=%s", sorted(tracker.subscribed_symbols))
    await tracker.start()
    logging.getLogger("app").info("tracking symbols=%s", sorted(tracker.subscribed_symbols))
    try:
        await asyncio.Event().wait()
    finally:
        await tracker.stop()

def main() -> None:
    parser = argparse.ArgumentParser(description="Realtime Binance multi-period kline tracker")
    parser.add_argument("--config", default="config.py", help="Python 配置文件")
    parser.add_argument("--symbols", nargs="+", help="覆盖配置文件中的 symbol 列表")
    parser.add_argument("--ip", help="同时指定 REST 和 WebSocket 的 Binance IP")
    parser.add_argument("--rest-ip", help="仅指定 REST API IP")
    parser.add_argument("--ws-ip", help="仅指定 WebSocket IP")
    parser.add_argument("--insecure", action="store_true", help="指定 IP 直连时关闭 TLS 证书校验")
    asyncio.run(run(parser.parse_args()))

if __name__ == "__main__":
    main()
