import asyncio
import aiohttp
import socket
import ssl

# 你要使用的 IP 和域名映射
IP_MAP = {
    'www.okx.com': '172.64.144.82',   # 可更换为 104.18.43.174 或其他可用 IP
}

class CustomResolver:
    """让 aiohttp 使用自定义 IP 解析，但保留原始域名"""
    def __init__(self, ip_map):
        self.ip_map = ip_map

    async def resolve(self, host, port=0, family=socket.AF_INET):
        if host in self.ip_map:
            return [{
                'hostname': host,
                'host': self.ip_map[host],
                'port': port,
                'family': socket.AF_INET,
                'proto': socket.IPPROTO_TCP,
                'flags': socket.AI_NUMERICHOST,
            }]
        # 其他域名走系统解析
        return await aiohttp.resolver.DefaultResolver().resolve(host, port, family)

async def main():
    # 创建 SSL 上下文：关闭证书验证（因为你用的是 IP，证书不匹配）
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    # 使用自定义 resolver
    resolver = CustomResolver(IP_MAP)
    connector = aiohttp.TCPConnector(resolver=resolver, ssl=ssl_ctx)

    async with aiohttp.ClientSession(connector=connector) as session:
        # 注意 URL 中使用域名，而不是 IP
        url = "https://www.okx.com/api/v5/public/time"
        async with session.get(url) as resp:
            print(resp.status)
            print(await resp.text())

if __name__ == "__main__":
    asyncio.run(main())