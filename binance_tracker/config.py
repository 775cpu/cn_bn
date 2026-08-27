"""Binance Tracker 本地配置。此文件是 Python 代码，可直接修改后启动。"""

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "SOLUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "LTCUSDT"]
# SYMBOLS = ["BTCUSDT","BNBUSDT",]

# 网络：默认使用旧版 k.py / ws_agg.py 的 IP 池，启动时自动选择最低延迟地址。
NETWORK_MODE = "direct"  # direct / domain / proxy
REST_URL = "https://api.binance.com"
WS_URL = "wss://stream.binance.com:9443/stream"
REST_IPS = ["13.32.53.197", "18.65.167.85", "13.225.181.100", "99.84.137.219", "18.172.32.150", "13.33.214.96", "143.204.77.51", "13.227.59.18", "13.249.162.25"]
WS_IPS = ["13.192.34.187", "54.95.85.108", "18.178.58.30", "3.112.147.130", "3.113.253.189", "54.92.31.127", "52.198.34.77", "13.193.145.251"]
HTTP_PROXY = None
WS_PROXY = None
# 域名直连必须校验证书；IP 直连由程序自动关闭校验。
VERIFY_SSL = True
IP_SELECT_SECONDS = 300
IP_PING_TIMEOUT = 5.0
IP_SWITCH_MIN_MS = 20.0
IP_SWITCH_MIN_RATIO = 0.20

# 数据与指标。
INTERVALS = ("1s", "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M")
HISTORY_LIMIT = 200
MISMATCH_CHECK_SECONDS = 300
BOLL_PERIOD = 21
BOLL_STDDEV = 3

# 日志滚动。
LOG_DIR = "logs"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5

# 显示：in_place 原地刷新，append 持续追加，off 关闭行情显示。
DISPLAY_MODE = "in_place"
DISPLAY_ONLY_BREAKOUTS = True
DISPLAY_PRICE_DECIMALS = 8
DISPLAY_BOLL_DECIMALS = 8
DISPLAY_REFRESH_SECONDS = 0.0