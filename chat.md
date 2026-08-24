# Binance K 线跟踪项目需求原文

> 来源：Copilot 历史对话
> 项目：`cn_bn`
> 时间：2026-08-24
>
> 以下内容仅整理用户消息，保留原始措辞；代码实现、分析和助手回复未放入本文。

## 1. 初始项目要求

阅读现有代码 ，新建一个py项目文件夹【需要成熟的项目结构】实时接收binance 最新价格数据 ,用最高效的算法和数据结构 并更新所有周期k线，并实时计算boll 指标，比如每60秒过去，就能合成一个1m k线 ，为了防止程序数据错误，在程序开始时，和每隔一段时间 fetch 所有周期k线 原始数据校准。【如果对不上，要能logging记录】

```python
import logging
root_logger = logging.getLogger(None)
filename=f'/home/qgb/.cache/{gport}={U.stime()}.log' 最好不同类型的错误能够写入不同文件
file_handler = logging.FileHandler(filename)
stderr_handler=root_logger.handlers.pop(0)
root_logger.addHandler(file_handler)
print(stderr_handler,U.enable_log(),root_logger.handlers)
```

提供函数接口能够控制  目前订阅更新的 symbol 列表。 我可以随时停止 或者开启新的跟踪

网络方面 参考 现有代码 ，能够在中国内使用，也能直连【现在在GitHub codespaces环境中可以直连】 ，完全解耦

## 2. 项目结构、CI、启动及同步接口

binance_tracker/ 补齐  .gitignore  和git提交自动 CI 测试工作流。 添加 sh 启动脚本。网络 需要参考原本的 k.py 和wsagg py . 提供指定ip 直连模式。并能够命令行启动方便切换   修改订阅接口 不要async  提供能够同步 修改的接口

## 3. 校准冲突现象

以下为用户当时提供的校准日志现象，要求分析冲突原因并改进代码：

```text
2026-08-24 06:13:40,262 ERROR calibration: mismatch symbol=BTCUSDT interval=1m open_time=1787551980000 live={'open_time': 1787551980000, 'open': 77362.0, 'high': 77364.49, 'low': 77319.5, 'close': 77347.99, 'volume': 10.88637, 'quote_volume': 841967.9426891, 'trades': 2879, 'closed': False, 'boll': {'upper': 77320.8928295239, 'middle': 77157.11850000001, 'lower': 76993.34417047612}} rest={'open_time': 1787551980000, 'open': 77362.0, 'high': 77364.49, 'low': 77319.5, 'close': 77347.99, 'volume': 10.88706, 'quote_volume': 842021.3128022, 'trades': 2881, 'closed': False, 'boll': {'upper': None, 'middle': None, 'lower': None}}
2026-08-24 06:13:40,342 ERROR calibration: mismatch symbol=BTCUSDT interval=3m open_time=1787551920000 live={'open_time': 1787551920000, 'open': 77298.84, 'high': 77395.24, 'low': 77298.84, 'close': 77347.99, 'volume': 36.18558, 'quote_volume': 2798471.4857688, 'trades': 10353, 'closed': False, 'boll': {'upper': 77295.14202256575, 'middle': 77096.899, 'lower': 76898.65597743426}} rest={'open_time': 1787551920000, 'open': 77298.84, 'high': 77395.24, 'low': 77298.84, 'close': 77347.99, 'volume': 36.18627, 'quote_volume': 2798524.8558819, 'trades': 10355, 'closed': False, 'boll': {'upper': None, 'middle': None, 'lower': None}}
```

## 4. 原地刷新、配置和显示要求

命令行的 每一行 symbol 不是原地更新，而是持续刷屏。提供配置模式。  默认原地刷新显示 。2026-08-24 06:18:44,437 INFO calibration.BTCUSDT: calibration started intervals=1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,3d,1w,1M
2026-08-24 06:18:44,553 INFO calibration.BTCUSDT: calibration completed interval=1m rows=200
2026-08-24 06:18:44,633 INFO calibration.BTCUSDT: calibration completed interval=3m rows=200
2026-08-24 06:18:44,714 INFO calibration.BTCUSDT: calibration completed interval=5m rows=200
2026-08-24 06:18:44,800 INFO calibration.BTCUSDT: calibration completed interval=15m rows=200
2026-08-24 06:18:44,883 INFO calibration.BTCUSDT: calibration completed interval=30m rows=200
2026-08-24 06:18:44,970 INFO calibration.BTCUSDT: calibration completed interval=1h rows=200
2026-08-24 06:18:45,054 INFO calibration.BTCUSDT: calibration completed interval=2h rows=200
2026-08-24 06:18:45,134 INFO calibration.BTCUSDT: calibration completed interval=4h rows=200
2026-08-24 06:18:45,222 INFO calibration.BTCUSDT: calibration completed interval=6h rows=200
2026-08-24 06:18:45,306 INFO calibration.BTCUSDT: calibration completed interval=8h rows=200
2026-08-24 06:18:45,391 INFO calibration.BTCUSDT: calibration completed interval=12h rows=200
2026-08-24 06:18:45,471 INFO calibration.BTCUSDT: calibration completed interval=1d rows=200
2026-08-24 06:18:45,551 INFO calibration.BTCUSDT: calibration completed interval=3d rows=200
2026-08-24 06:18:45,638 INFO calibration.BTCUSDT: calibration completed interval=1w rows=200
2026-08-24 06:18:45,717 INFO calibration.BTCUSDT: calibration completed interval=1M rows=109
2026-08-24 06:18:45,718 INFO calibration.BTCUSDT: calibration started intervals=1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,3d,1w,1M

提供一个 配置文件  ，能够配置 symbol ，网络 。log 路径，自动滚动大小，等所有可配置项目  。 现在的启动命令行是瀑布显示。 添加配置项目，默认 原地刷新显示。2026-08-24 06:25:47,134 INFO app: symbol=BTCUSDT price=77387.90000000 1m:BOLL=77515.51439635/77308.42200000/77101.32960365 3m:BOLL=77453.47297051/77157.48200000/76861.49102949 5m:BOLL=77440.41677932/77118.05200000/76795.68722068 15m:BOLL=77548.98658683/77181.27550000/76813.56441317 30m:BOLL=78023.19305771/77394.38400000/76765.57494229 1h:BOLL=77844.80579634/77332.84050000/76820.87520366 2h:BOLL=78002.84939703/77089.63400000/76176.41860297 4h:BOLL=78656.37128949/77061.79800000/75467.22471051 6h:BOLL=81471.94659667/75211.49550000/68951.04440333 8h:BOLL=83055.19104572/72365.27650000/61675.36195428 12h:BOLL=82277.91285346/69640.29550000/57002.67814654 1d:BOLL=78614.05570909/67474.94850000/56335.84129091 3d:BOLL=76655.23510734/66614.93600000/56574.63689266 1w:BOLL=84512.94516827/70048.35300000/55583.76083173 1M:BOLL=123194.93301040/88191.78800000/53188.64298960      而且太长了 ,只显示当前价格 超过上下boll边界的  时间周期

## 5. Python 配置和 Bollinger 详细显示

配置文件用 py 代码格式。不要toml 和json  06:35:00 BTCUSDT      price=77280.00000000 breakout=3d=UP 显示boll 详细数值

## 6. 多 IP 延迟切换、启动模式和对话记录

延迟选最优；定时重测后若最优 IP 变化，主动打断当前 【只有延迟 差异足够大 ，才去打断 】 并且把最新历史对话总结追加到chat md 。DIRECT_IP list 可以在py中定义，但是 "%PY_PATH%" -m binance_tracker.main %* 要体现选择ip模式啊。【而且 ws 和 rest ip 不同，配置文件 有吗？】  sh 选择直连模式

### 本轮需求总结

- 多个 IP 并行测速，选择延迟最低的地址。
- 定时重新测速，但只有新地址相对当前地址的延迟改善足够大时，才中断现有连接并切换。
- REST 和 WebSocket 使用独立的 IP 列表，并在 Python 配置文件中配置。
- 启动命令和 `sh` 脚本要明确体现直连 IP 模式。
- Windows 启动命令继续使用 `%PY_PATH% -m binance_tracker.main`，同时传递直连模式参数。

## 7. 启动脚本模式最终确认

这是严格的启动模式要求，后续以最新消息为准：

- `sh` 是 Binance 域名直连。
- `bat` 是使用 Python 配置文件中的 IP。
- `sh` 不应强制传入 `--network-mode direct`，应使用域名直连模式。
- `bat` 不应强制覆盖配置文件中的网络模式，应直接读取 `config.py` 中的 IP 配置。
- 将最新几轮历史对话总结合并后追加到 `chat.md`。

## 8. TLS 默认值和冗余配置清理

域名直连，默认开启 VERIFY_SSL， ip连接，默认关闭。 阅读所有代码，有没有需要清理 的地方  。DIRECT_IP = None
DIRECT_WS_IP = None  这个有什么作用？

### 本轮需求总结

- 域名直连默认 `VERIFY_SSL = True`。
- IP 直连默认关闭 TLS 证书校验。
- 检查全部项目代码并清理不再需要的配置。
- 说明或清理 `DIRECT_IP`、`DIRECT_WS_IP`；当前多 IP 配置应使用 `REST_IPS` 和 `WS_IPS`，单 IP 参数仅作为 CLI 临时覆盖。
