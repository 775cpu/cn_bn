import argparse
import asyncio
import logging
import json
from dataclasses import replace
from pathlib import Path
from .config import Settings
from .logging_setup import setup_logging
from .service import BinanceTracker

def chart_page(response, symbol=None, interval=None):
    symbol = str(symbol or next(iter(tracker.subscribed_symbols), "BTCUSDT")).upper()
    interval = str(interval or tracker.settings.intervals[0])
    if symbol not in tracker.books:
        symbol = next(iter(tracker.subscribed_symbols), "BTCUSDT")
    if interval not in tracker.settings.intervals:
        interval = tracker.settings.intervals[0]
    page = (Path(__file__).resolve().parents[2] / "realtime_chart" / "dist" / "index.html").read_text(encoding="utf-8")
    page = page.replace("</head>", f"<script>window.__SYMBOLS__={json.dumps(sorted(tracker.subscribed_symbols))};window.__INTERVALS__={json.dumps(list(tracker.settings.intervals))};window.__INITIAL_SYMBOL__={json.dumps(symbol)};window.__INITIAL_INTERVAL__={json.dumps(interval)};</script></head>")
    response.set_header("Content-Type", "text/html; charset=utf-8")
    response.set_data(page)

def chart_history(response, symbol, interval, end_time, limit=100):
    """Return older bars through the existing RPC HTTP endpoint."""
    symbol = str(symbol).upper()
    interval = str(interval)
    try:
        end_time = int(end_time)
        limit = min(max(int(limit), 1), 1000)
    except (TypeError, ValueError, OverflowError):
        logging.getLogger("error").warning(
            "invalid chart history arguments symbol=%r interval=%r end_time=%r limit=%r",
            symbol, interval, end_time, limit,
        )
        response.set_status(400)
        response.set_header("Content-Type", "application/json; charset=utf-8")
        response.set_data(json.dumps({"error": "end_time 和 limit 必须是整数"}, ensure_ascii=False))
        return
    if symbol not in tracker.books or interval not in tracker.settings.intervals:
        response.set_status(400)
        response.set_header("Content-Type", "application/json; charset=utf-8")
        response.set_data(json.dumps({"error": "无效的 symbol 或周期"}, ensure_ascii=False))
        return
    if not tracker._loop or not tracker._client:
        response.set_status(503)
        response.set_header("Content-Type", "application/json; charset=utf-8")
        response.set_data(json.dumps({"error": "行情服务尚未准备完成"}, ensure_ascii=False))
        return
    future = asyncio.run_coroutine_threadsafe(
        tracker._client.klines(symbol, interval, limit, end_time=end_time - 1),
        tracker._loop,
    )
    try:
        bars = [bar.as_dict() for bar in future.result(timeout=20)]
    except Exception:
        logging.getLogger("error").exception(
            "chart history RPC failed symbol=%s interval=%s end_time=%d limit=%d",
            symbol, interval, end_time, limit,
        )
        response.set_status(502)
        bars = []
    response.set_header("Content-Type", "application/json; charset=utf-8")
    response.set_data(json.dumps({"type": "history", "symbol": symbol, "interval": interval, "bars": bars}, ensure_ascii=False))

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
    global tracker
    tracker = BinanceTracker(settings)
    tracker.add_symbols(*settings.symbols)
    logging.getLogger("app").info("starting tracker symbols=%s", sorted(tracker.subscribed_symbols))
    
    rpc_server,rpc_thread=__import__('rpc').start_rpc_server(port=1188, key='', globals=globals(), locals=locals(), redirect_root='/chart_page(p)', websocket_handlers={'/chart-ws': tracker.chart_websocket})
    
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
