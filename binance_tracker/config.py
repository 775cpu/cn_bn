"""Binance Tracker 本地配置。此文件是 Python 代码，可直接修改后启动。"""

SYMBOLS = ["BTCUSDT"]

# 网络：域名直连、代理、或指定 IP 直连三选一组合。
REST_URL = "https://api.binance.com"
WS_URL = "wss://stream.binance.com:9443/stream"
DIRECT_IP = None
DIRECT_WS_IP = None
HTTP_PROXY = None
WS_PROXY = None
VERIFY_SSL = True

# 数据与指标。
INTERVALS = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M")
HISTORY_LIMIT = 200
CALIBRATION_SECONDS = 300
BOLL_PERIOD = 20
BOLL_STDDEV = 2.0

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