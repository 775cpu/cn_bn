# Binance Kline Tracker

pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn python-binance numpy pandas

cd binance_tracker/src/;git clone --depth=1 https://github.com/qgb/qpsu qgb

curl "http://127.0.0.1:1188/r=tracker.display.mode='off'"

import%20binance,B,qgb;r=B
r=B.get_24hr_ticker()
r=B.futures_get_all_price_dict()
r=B.get_24hr_ticker();qgb.N.HTML.list(p,r)


独立的 Binance Spot 实时行情服务：通过 `aggTrade` 接收成交，生成 1m 及更高周期 K 线，实时计算 Bollinger Bands，并用 REST K 线定期校准。

`start.sh` 使用 Binance 域名直连；Windows `start.bat` 使用 [config.py](config.py) 中的 REST/WS 独立 IP 池并自动选择延迟最低的地址。中国网络也可通过代理或 API/WS 地址配置：

```bash
export BINANCE_HTTP_PROXY=http://127.0.0.1:7890
export BINANCE_WS_PROXY=http://127.0.0.1:7890
```

日志位于 `logs/`。每个标的都有独立的 `_<SYMBOL>.log`，记录校准开始、完成、字段级 live/rest 差异和异常；公共日志包括 `app.log`、`network.log`、`error.log`。

Windows 上使用官方 `python-binance` 客户端时，先导入 `B` 即可安装 IP 直连补丁；它会读取 `config.py` 的 `REST_IPS`，选择最低延迟地址，并自动设置 `Host: api.binance.com`：

```python
import binance
import B

r = B.set_client(binance.client.Client(api_key, api_secret))
```


代码接口示例：`tracker.add_symbols("BTCUSDT", "ETHUSDT")`、`tracker.remove_symbols("ETHUSDT")`、`tracker.get_snapshot("BTCUSDT", "1m")`。通过 `tracker.subscribed_symbols` 可查看当前订阅。运行中每笔成交会在控制台输出该标的一行价格和所有周期 Boll 数值。
