import asyncio
import aiohttp
import json
import time
import ssl
import warnings
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any

warnings.filterwarnings("ignore")

# ================== 配置 ==================
gip_list = [
    '13.192.34.187',
    '54.95.85.108',
    '18.178.58.30',
    '3.112.147.130',
    '3.113.253.189',
    '54.92.31.127',
    '52.198.34.77',
    '13.193.145.251',
]

WS_PORT = 9443
STREAM_PATH = "/ws/btcusdt@aggTrade"
HOST_HEADER = "stream.binance.com"
PING_TIMEOUT = 5
RECONNECT_DELAY = 3
MAX_RETRY_SAME_IP = 2

# ================== K线聚合器 ==================
class KlineAggregator:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.current_minute = None
        self.open = self.high = self.low = self.close = None
        self.volume = 0.0
        self.trades = 0

    def update(self, price: float, quantity: float, timestamp_ms: int):
        ts = datetime.utcfromtimestamp(timestamp_ms / 1000)
        minute = ts.replace(second=0, microsecond=0)

        if self.current_minute != minute:
            self.current_minute = minute
            self.open = self.high = self.low = self.close = price
            self.volume = quantity
            self.trades = 1
        else:
            self.high = max(self.high, price)
            self.low = min(self.low, price)
            self.close = price
            self.volume += quantity
            self.trades += 1

    def get_latest_kline(self):
        if self.current_minute is None:
            return None
        return {
            "time": self.current_minute.strftime('%Y-%m-%d %H:%M:%S'),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "trades": self.trades,
        }

# ================== WebSocket 连通性测试 ==================
async def test_ws_ip(session: aiohttp.ClientSession, ip: str):
    url = f"wss://{ip}:{WS_PORT}{STREAM_PATH}"
    start = time.time()
    try:
        async with session.ws_connect(
            url,
            headers={"Host": HOST_HEADER},
            timeout=aiohttp.ClientTimeout(total=PING_TIMEOUT),
            ssl=False,          # 测试阶段直接禁用 SSL
        ) as ws:
            elapsed = time.time() - start
            return ip, True, elapsed, f"OK {elapsed:.2f}s"
    except Exception as e:
        elapsed = time.time() - start
        return ip, False, elapsed, f"ERR {type(e).__name__}: {e}"

# ================== WebSocket 接收与 K 线处理 ==================
async def ws_receive_loop(ip: str, aggregator: KlineAggregator):
    url = f"wss://{ip}:{WS_PORT}{STREAM_PATH}"
    print(f"[连接] 正在连接 {url} ...")

    # 创建 session 时禁用 SSL 验证（关键修复）
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.ws_connect(
            url,
            headers={"Host": HOST_HEADER},
            heartbeat=30,
            timeout=aiohttp.ClientTimeout(total=0),
            # 也可以直接传 ssl=False，但 connector 已经禁用
        ) as ws:
            print(f"[连接] 已建立 WebSocket 连接：{ip}")
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        if data.get('e') == 'aggTrade':
                            price = float(data['p'])
                            qty = float(data['q'])
                            ts_ms = data['T']
                            symbol = data['s']

                            aggregator.update(price, qty, ts_ms)
                            latest = aggregator.get_latest_kline()
                            if latest:
                                print(
                                    f"[{latest['time']}] {symbol} "
                                    f"O:{latest['open']:.2f} H:{latest['high']:.2f} "
                                    f"L:{latest['low']:.2f} C:{latest['close']:.2f} "
                                    f"Vol:{latest['volume']:.6f} Trades:{latest['trades']}"
                                )
                    except Exception as e:
                        print(f"消息处理异常: {e}")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(f"WebSocket 错误: {ws.exception()}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    print("WebSocket 连接被关闭")
                    break

# ================== 主函数 ==================
async def main():
    # 测试阶段也使用 ssl=False 的 connector（双保险）
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("正在测试各 IP 的 WebSocket 连通性...")
        tasks = [test_ws_ip(session, ip) for ip in gip_list]
        results = await asyncio.gather(*tasks)

        available = []
        print("\n连通性测试结果:")
        for ip, ok, elapsed, msg in results:
            status = "可用" if ok else "不可用"
            print(f"  {ip:20s} {status:4s} {elapsed:.2f}s  {msg}")
            if ok:
                available.append((ip, elapsed))

        if not available:
            print("\n没有可用的 IP，退出。")
            return

        available.sort(key=lambda x: x[1])
        print(f"\n可用 IP（按延迟排序）: {[ip for ip, _ in available]}")
        best_ip, best_delay = available[0]
        print(f"选用延迟最低 IP: {best_ip} ({best_delay:.2f}s)")

    aggregator = KlineAggregator("BTCUSDT")
    ip_pool = [ip for ip, _ in available]
    current_ip = best_ip
    retry_count = 0
    ip_index = 0

    while True:
        try:
            await ws_receive_loop(current_ip, aggregator)
            print(f"连接意外断开，尝试重连（IP: {current_ip}）...")
            retry_count += 1
            if retry_count >= MAX_RETRY_SAME_IP:
                print(f"同一 IP 连续失败 {retry_count} 次，切换到下一个可用 IP...")
                retry_count = 0
                ip_index = (ip_index + 1) % len(ip_pool)
                current_ip = ip_pool[ip_index]
                print(f"新 IP: {current_ip}")
        except KeyboardInterrupt:
            print("\n用户中断，退出。")
            break
        except Exception as e:
            print(f"连接异常: {e}")
            retry_count += 1
            if retry_count >= MAX_RETRY_SAME_IP:
                retry_count = 0
                ip_index = (ip_index + 1) % len(ip_pool)
                current_ip = ip_pool[ip_index]
                print(f"切换到下一个 IP: {current_ip}")

        await asyncio.sleep(RECONNECT_DELAY)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass