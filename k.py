import asyncio
import aiohttp
import json
import time
import warnings
from typing import List, Tuple, Optional

warnings.filterwarnings("ignore")

gip_list = ['13.32.53.197', '18.65.167.85', '13.225.181.100', '99.84.137.219', '18.172.32.150', '13.33.214.96', '143.204.77.51', '13.227.59.18', '13.249.162.25']

HEADERS = {"Host": "api.binance.com"}
SYMBOL = "BTCUSDT"
INTERVAL = "1m"          # 1 分钟 K 线
LIMIT = 10               # 最近 10 根 1 分钟 K 线 = 最近 10 分钟
PING_TIMEOUT = 5         # 连通性测试超时（秒）
KLINE_TIMEOUT = 10       # 获取 K 线超时（秒）


async def test_ip(session: aiohttp.ClientSession, ip: str) -> Tuple[str, bool, float, str]:
    """测试单个 IP 是否可访问 Binance API，返回 (ip, 是否可用, 耗时, 详细信息)"""
    url = f"https://{ip}/api/v3/time"
    start = time.time()
    try:
        async with session.get(
            url,
            headers=HEADERS,
            ssl=False,
            timeout=aiohttp.ClientTimeout(total=PING_TIMEOUT)
        ) as resp:
            text = await resp.text()
            elapsed = time.time() - start
            if resp.status == 200:
                return ip, True, elapsed, f"OK {resp.status} {elapsed:.2f}s"
            else:
                return ip, False, elapsed, f"HTTP {resp.status} {elapsed:.2f}s {text[:80]}"
    except Exception as e:
        elapsed = time.time() - start
        return ip, False, elapsed, f"ERR {type(e).__name__}: {e}"


async def fetch_klines(
    session: aiohttp.ClientSession,
    ip: str,
    symbol: str = SYMBOL,
    interval: str = INTERVAL,
    limit: int = LIMIT
) -> Optional[List]:
    """通过指定 IP 获取 K 线数据（1 分钟级别，最近 limit 根）"""
    url = f"https://{ip}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        async with session.get(
            url,
            headers=HEADERS,
            ssl=False,
            timeout=aiohttp.ClientTimeout(total=KLINE_TIMEOUT)
        ) as resp:
            text = await resp.text()
            if resp.status == 200:
                data = json.loads(text)
                if isinstance(data, list) and len(data) > 0:
                    return data
                else:
                    print(f"返回数据异常，IP: {ip}, 内容: {text[:200]}")
                    return None
            else:
                print(f"获取K线失败，IP: {ip}, HTTP {resp.status}: {text[:200]}")
                return None
    except Exception as e:
        print(f"获取K线异常，IP: {ip}: {type(e).__name__}: {e}")
        return None


def print_klines(klines: List[List], ip: str):
    """打印 1 分钟 K 线数据，格式化显示"""
    print(f"\n===== {SYMBOL} 最近 {len(klines)} 根 1 分钟 K 线（使用 IP: {ip}）=====")
    print(f"{'开盘时间(UTC)':<20} {'收盘时间(UTC)':<20} {'开盘':<12} {'最高':<12} {'最低':<12} {'收盘':<12} {'成交量':<15} {'成交额':<15} {'笔数':<8}")
    print("-" * 120)
    for k in klines:
        open_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(k[0] / 1000))
        close_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(k[6] / 1000))
        open_price = k[1]
        high = k[2]
        low = k[3]
        close_price = k[4]
        volume = k[5]
        quote_volume = k[7]
        trades = k[8]
        print(f"{open_time:<20} {close_time:<20} {open_price:<12} {high:<12} {low:<12} {close_price:<12} {volume:<15} {quote_volume:<15} {trades:<8}")
    print("=" * 120)


async def main():
    async with aiohttp.ClientSession() as session:
        # 1. 并发测试所有 IP 连通性
        print("正在测试 IP 连通性...")
        tasks = [test_ip(session, ip) for ip in gip_list]
        results = await asyncio.gather(*tasks)

        available = []
        print("\n连通性测试结果:")
        for ip, ok, elapsed, msg in results:
            status = "可用" if ok else "不可用"
            print(f"  {ip:20s} {status:4s} {elapsed:.2f}s  {msg}")
            if ok:
                available.append((ip, elapsed))

        if not available:
            print("\n没有可用 IP，退出。")
            return

        # 2. 选择延迟最低的可用 IP
        available.sort(key=lambda x: x[1])
        selected_ip = available[0][0]
        print(f"\n可用 IP（按延迟排序）: {[ip for ip, _ in available]}")
        print(f"选用延迟最低 IP: {selected_ip} ({available[0][1]:.2f}s)")

        # 3. 获取最近 10 根 1 分钟 K 线
        print(f"\n获取 {SYMBOL} 最新 {LIMIT} 根 1 分钟 K 线...")
        klines = await fetch_klines(session, selected_ip)

        # 如果首选 IP 失败，尝试其他可用 IP
        if not klines:
            print("首选 IP 获取失败，尝试其他可用 IP...")
            for ip, _ in available[1:]:
                print(f"尝试 IP: {ip}")
                klines = await fetch_klines(session, ip)
                if klines:
                    selected_ip = ip
                    break

        if not klines:
            print("所有可用 IP 均无法获取 K 线。")
            return

        # 4. 打印结果
        print_klines(klines, selected_ip)


if __name__ == "__main__":
    asyncio.run(main())