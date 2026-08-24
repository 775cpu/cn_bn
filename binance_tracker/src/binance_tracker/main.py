import argparse
import asyncio
import logging
from dataclasses import replace
from pathlib import Path
from .config import Settings
from .logging_setup import setup_logging
from .service import BinanceTracker

def resolve_verify_ssl(mode: str, configured: bool, insecure: bool = False) -> bool:
    if insecure:
        return False
    if mode == "direct":
        return False
    return configured

async def run(args: argparse.Namespace) -> None:
    direct_ip = args.ip or args.rest_ip
    direct_ws_ip = args.ws_ip or args.ip
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path(__file__).resolve().parents[2] / config_path
    if config_path.exists():
        print(f"[配置] 读取 {config_path.resolve()}", flush=True)
        settings = Settings.from_python(config_path)
    else:
        print(f"[配置] 未找到 {args.config}，使用默认配置", flush=True)
        settings = Settings()
    mode = args.network_mode or settings.network_mode
    rest_ips = (args.rest_ip or args.ip,) if args.rest_ip or args.ip else settings.rest_ips
    ws_ips = (args.ws_ip or args.ip,) if args.ws_ip or args.ip else settings.ws_ips
    if mode != "direct":
        rest_ips, ws_ips = (), ()
    settings = replace(settings, symbols=tuple(args.symbols or settings.symbols), network_mode=mode, direct_ip=direct_ip, direct_ws_ip=direct_ws_ip, rest_ips=rest_ips, ws_ips=ws_ips, verify_ssl=resolve_verify_ssl(mode, settings.verify_ssl, args.insecure))
    setup_logging(settings.log_dir, settings.log_max_bytes, settings.log_backup_count)
    tracker = BinanceTracker(settings)
    tracker.add_symbols(*settings.symbols)
    logging.getLogger("app").info("starting tracker symbols=%s", sorted(tracker.subscribed_symbols))
    try:
        await tracker.start()
    except Exception as exc:
        print(f"[启动失败] {type(exc).__name__}: {exc}", flush=True)
        raise
    logging.getLogger("app").info("tracking symbols=%s", sorted(tracker.subscribed_symbols))
    try:
        await asyncio.Event().wait()
    finally:
        await tracker.stop()

def main() -> None:
    import rpc
    rpc_server, rpc_thread = rpc.start_rpc_server(port=1188, key='', globals=globals(), locals=locals())

    parser = argparse.ArgumentParser(description="Realtime Binance multi-period kline tracker")
    parser.add_argument("--config", default="config.py", help="Python 配置文件")
    parser.add_argument("--symbols", nargs="+", help="覆盖配置文件中的 symbol 列表")
    parser.add_argument("--ip", help="同时指定 REST 和 WebSocket 的 Binance IP")
    parser.add_argument("--rest-ip", help="仅指定 REST API IP")
    parser.add_argument("--ws-ip", help="仅指定 WebSocket IP")
    parser.add_argument("--insecure", action="store_true", help="指定 IP 直连时关闭 TLS 证书校验")
    parser.add_argument("--network-mode", choices=("direct", "domain", "proxy"), help="网络模式，默认读取配置")
    asyncio.run(run(parser.parse_args()))

if __name__ == "__main__":
    main()
