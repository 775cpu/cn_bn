# Binance Kline Tracker

独立的 Binance Spot 实时行情服务：通过 `aggTrade` 接收成交，生成 1m 及更高周期 K 线，实时计算 Bollinger Bands，并用 REST K 线定期校准。

## 使用

```bash
cd binance_tracker
python -m venv .venv && . .venv/bin/activate
pip install -e '.[test]'
python -m binance_tracker.main
# 或
./start.sh --symbols BTCUSDT ETHUSDT
```

默认读取 [config.py](config.py)。配置文件就是 Python 代码，可配置 symbol、REST/WebSocket 地址、代理或直连 IP、TLS、周期、校准频率、Bollinger 参数、日志目录及滚动大小、显示模式等。命令行 `--symbols` 会覆盖配置文件中的列表，`--config path.py` 可切换配置。

`start.sh` 使用 Binance 域名直连；Windows `start.bat` 使用 [config.py](config.py) 中的 REST/WS 独立 IP 池并自动选择延迟最低的地址。中国网络也可通过代理或 API/WS 地址配置：

```bash
export BINANCE_HTTP_PROXY=http://127.0.0.1:7890
export BINANCE_WS_PROXY=http://127.0.0.1:7890
```

指定 IP 直连（兼容旧代码的 `Host` 头和关闭证书校验方式，指定 IP 后自动关闭证书校验）：

```bash
./start.sh --ip 13.32.53.197 --symbols BTCUSDT ETHUSDT
# 也可以分别指定
./start.sh --rest-ip 13.32.53.197 --ws-ip 13.32.53.197
```

Windows 可直接运行 `start.bat`，默认使用 `C:\QGB\miniforge3\python.exe`，不存在时回退到 PATH 中的 `python`：

```bat
start.bat --symbols BTCUSDT ETHUSDT
```

域名模式默认开启 `VERIFY_SSL`；IP 模式默认关闭证书校验。`REST_IPS`、`WS_IPS` 配置多个 IP，`IP_SELECT_SECONDS` 配置重新测速间隔。每次测速会并行请求 `/api/v3/time`，记录所有可用地址和延迟；如果最快地址变化且达到切换阈值，当前 WebSocket 会自动重连。

REST 和 WebSocket 分别配置 `REST_IPS`、`WS_IPS`。只有新地址比当前地址至少快 `IP_SWITCH_MIN_MS` 毫秒，或至少快 `IP_SWITCH_MIN_RATIO` 比例时，才会打断当前连接并切换。

配置文件不再使用 `DIRECT_IP`、`DIRECT_WS_IP`；这两个旧字段原本只表示单个 REST/WS IP，现在请使用 IP 列表。命令行 `--ip`、`--rest-ip`、`--ws-ip` 仍可作为临时单 IP 覆盖。

程序接口中的 `add_symbols()` 和 `remove_symbols()` 是同步方法，可以从控制线程直接调用；网络任务仍由 `start()` 管理。

日志位于 `logs/`。每个标的都有独立的 `calibration_<SYMBOL>.log`，记录校准开始、完成、字段级 live/rest 差异和异常；公共日志包括 `app.log`、`network.log`、`calibration.log`、`error.log`。

突破显示示例：`06:35:00 BTCUSDT price=77280.00000000 breakout=3d=UP(U=...,M=...,L=...)`。

代码接口示例：`tracker.add_symbols("BTCUSDT", "ETHUSDT")`、`tracker.remove_symbols("ETHUSDT")`、`tracker.get_snapshot("BTCUSDT", "1m")`。通过 `tracker.subscribed_symbols` 可查看当前订阅。运行中每笔成交会在控制台输出该标的一行价格和所有周期 Boll 数值。
