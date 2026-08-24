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

默认直连 Binance；中国网络可通过环境变量配置代理或 API/WS 地址：

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

程序接口中的 `add_symbols()` 和 `remove_symbols()` 是同步方法，可以从控制线程直接调用；网络任务仍由 `start()` 管理。

日志位于 `logs/`。每个标的都有独立的 `calibration_<SYMBOL>.log`，记录校准开始、完成、字段级 live/rest 差异和异常；公共日志包括 `app.log`、`network.log`、`calibration.log`、`error.log`。

突破显示示例：`06:35:00 BTCUSDT price=77280.00000000 breakout=3d=UP(U=...,M=...,L=...)`。

代码接口示例：`tracker.add_symbols("BTCUSDT", "ETHUSDT")`、`tracker.remove_symbols("ETHUSDT")`、`tracker.get_snapshot("BTCUSDT", "1m")`。通过 `tracker.subscribed_symbols` 可查看当前订阅。运行中每笔成交会在控制台输出该标的一行价格和所有周期 Boll 数值。
