<template>
  <main class="terminal">
    <header class="toolbar">
      <div class="brand"></div>
      <div class="quote"><strong>{{ symbol }}</strong><span>{{ lastPrice }}</span><span :class="changeClass">{{ changeText }}</span></div>
      <div class="controls">
        <label class="symbol-add">
          <input v-model.trim="newSymbol" placeholder="订阅 SYMBOL" :disabled="addingSymbol" spellcheck="false" autocomplete="off"
                 @keydown.enter="addSymbol()" @keydown.esc="closePanels" @input="symbolStatus = ''" @focus="openTickerPanel">
          <button class="add-button" type="button" :disabled="addingSymbol || !newSymbol" title="订阅新 symbol：自动订阅 WS 并校准 K 线" @click="addSymbol()">{{ addingSymbol ? '…' : '＋' }}</button>
          <span v-if="symbolStatus" class="symbol-status" :class="{ error: symbolStatusError }">{{ symbolStatus }}</span>
        </label>
        <label class="symbol-picker">SYMBOL
          <div class="symbol-menu">
            <button type="button" class="symbol-menu-button" :title="'已订阅 ' + symbols.length + ' 个：点击切换，× 取消订阅'" @click.stop="toggleSymbolMenu">
              <span class="symbol-menu-current">{{ symbol || '—' }}</span><span class="caret">▾</span>
            </button>
            <div v-if="showSymbolMenu" class="symbol-menu-panel">
              <div v-for="item in symbols" :key="item" class="symbol-menu-row" :class="{ active: item === symbol }">
                <span class="symbol-menu-name" @click="switchSymbol(item)">{{ item }}</span>
                <button type="button" class="symbol-remove" :title="'取消订阅 ' + item" @click.stop="removeSymbol(item)">×</button>
              </div>
              <div v-if="!symbols.length" class="symbol-menu-empty">暂无订阅，在左侧输入框添加</div>
            </div>
          </div>
        </label>
        <label>INTERVAL <select v-model="interval" @change="subscribe"><option v-for="item in intervals" :key="item" :value="item">{{ item }}</option></select></label>
        <button class="icon-button" title="切换全屏" @click="toggleFullscreen">⛶</button>
      </div>
    </header>
    <div v-if="showTickerPanel || showSymbolMenu" class="pop-overlay" @click="closePanels"></div>
    <section v-if="showTickerPanel" class="ticker-panel">
      <header class="ticker-panel-head">
        <span class="tsb-label">组内排序</span>
        <button v-for="opt in tickerSortOptions" :key="opt.key" type="button" class="ticker-sort-btn"
                :class="{ active: tickerSortKey === opt.key }" :title="opt.hint" @click="setTickerSort(opt.key)">
          {{ opt.label }}<i v-if="tickerSortKey === opt.key">{{ tickerSortDesc ? '▼' : '▲' }}</i>
        </button>
        <span class="ticker-panel-hint">{{ tickers.length }} 个交易对<template v-if="newSymbol"> · 筛选 {{ filteredTickers.length }} 个</template> · 点击行订阅/切换，已订阅为绿色{{ loadingTickers ? ' · 行情加载中…' : tickerAgeText ? ' · ' + tickerAgeText : '' }}</span>
        <button type="button" class="ticker-panel-close" title="关闭" @click="closePanels">×</button>
      </header>
      <div class="ticker-grid">
        <template v-for="group in groupedTickers" :key="group.quote">
          <div class="ticker-group-head">{{ group.quote }}<span class="tgh-count">{{ group.items.length }}</span></div>
          <button v-for="item in group.shown" :key="item.symbol" type="button" class="ticker-cell"
                  :class="{ subscribed: symbols.includes(item.symbol) }" :title="cellTitle(item)" @click="pickTicker(item)">
            <span class="tc-symbol">{{ item.symbol }}</span>
            <span class="tc-price">{{ formatTickerPrice(item.lastPrice) }}</span>
            <span class="tc-pct" :class="item.priceChangePercent >= 0 ? 'up' : 'down'">{{ formatPct(item.priceChangePercent) }}</span>
          </button>
        </template>
      </div>
      <footer v-if="tickerHiddenTotal > 0" class="ticker-panel-foot">部分组别仅显示涨跌幅最活跃的前 {{ tickerGroupCap }} 个（{{ tickerHiddenTotal }} 个已折叠），在输入框键入 symbol 可精确筛选</footer>
    </section>
    <div class="status"><i :class="{ online: connected }"></i>{{ connected ? 'LIVE' : 'CONNECTING' }}</div>
    <div class="chart-wrap"><div ref="chart" class="chart"></div><div class="scale-controls"><button title="Auto: 让 K 线和指标尽量铺满屏幕" :class="{ active: autoScale }" @click="toggleAutoScale">A</button><button title="锁定价格尺度" :class="{ active: scaleLocked }" @click="toggleScaleLock">L</button></div></div>
    <footer><span>实时行情</span><span>{{ barCount }} bars</span><span>{{ lastTime }}</span><span>服务器 {{ serverTime }}</span><span>延迟 {{ latency }}</span><span class="hint">WebSocket stream</span></footer>
  </main>
</template>

<script>
import { dispose, init } from 'klinecharts';

export default {
  name: 'RealtimeChart',
  data() {
    return {
      chart: null, socket: null, reconnectTimer: null, connected: false,
      symbol: window.__INITIAL_SYMBOL__ || 'BTCUSDT', interval: window.__INITIAL_INTERVAL__ || '1m', bars: [],
      autoScale: true, scaleLocked: false, pricePrecision: 8, latency: '--', serverTime: '--', pendingHistory: null, historyRetryTimer: null, historyRetryCount: 0, requestedHistory: new Set(), historyExhausted: false, chartGeneration: 0,
      symbols: window.__SYMBOLS__ || ['BTCUSDT'],
      intervals: window.__INTERVALS__ || ['1m'],
      newSymbol: '', addingSymbol: false, symbolStatus: '', symbolStatusError: false, symbolStatusTimer: null,
      tickers: Array.isArray(window.__TICKERS__) ? window.__TICKERS__ : [],
      tickerTime: Number(window.__TICKER_TIME__) || 0,
      loadingTickers: false, showTickerPanel: false, showSymbolMenu: false,
      tickerSortKey: 'pct', tickerSortDesc: true,
      tickerSortOptions: [
        { key: 'pct', label: '涨跌幅', hint: '按 24h 涨跌幅绝对值排序（再点切换正/倒序）' },
        { key: 'name', label: '名字', hint: '按 symbol 名字排序（再点切换正/倒序）' },
        { key: 'vol', label: '成交额', hint: '按 24h 成交额（quoteVolume，计价币口径）排序（再点切换正/倒序）' },
        { key: 'price', label: '价格', hint: '按最新价格排序（再点切换正/倒序）' },
      ],
    };
  },
  computed: {
    filteredTickers() {
      const keyword = (this.newSymbol || '').trim().toUpperCase();
      if (!keyword) return this.tickers;
      return this.tickers.filter((item) => item.symbol.includes(keyword));
    },
    tickerGroupCap() {
      return (this.newSymbol || '').trim() ? 1000 : 240;
    },
    groupedTickers() {
      const keyword = (this.newSymbol || '').trim().toUpperCase();
      const source = keyword ? this.tickers.filter((item) => item.symbol.includes(keyword)) : this.tickers;
      const map = new Map();
      for (const item of source) {
        const quote = item.quoteAsset || 'OTHER';
        if (!map.has(quote)) map.set(quote, []);
        map.get(quote).push(item);
      }
      const groups = Array.from(map, ([quote, items]) => ({ quote, items }));
      // USDT first (most active / most pairs), then by pair count desc, then name.
      groups.sort((a, b) => {
        if (a.quote === 'USDT') return -1;
        if (b.quote === 'USDT') return 1;
        if (b.items.length !== a.items.length) return b.items.length - a.items.length;
        return a.quote < b.quote ? -1 : a.quote > b.quote ? 1 : 0;
      });
      const cap = this.tickerGroupCap;
      for (const group of groups) {
        group.items.sort((a, b) => this.tickerCompare(a, b));
        group.shown = group.items.slice(0, cap);
        group.hidden = group.items.length - group.shown.length;
      }
      return groups;
    },
    tickerHiddenTotal() {
      return this.groupedTickers.reduce((sum, group) => sum + group.hidden, 0);
    },
    tickerAgeText() {
      if (!this.tickerTime) return '';
      const seconds = Math.max(0, Math.floor((Date.now() - this.tickerTime) / 1000));
      if (seconds < 60) return `${seconds}s 前更新`;
      const minutes = Math.floor(seconds / 60);
      return `${minutes}m${seconds % 60}s 前更新`;
    },
    barCount() { return this.bars.length; },
    lastBar() { return this.bars[this.bars.length - 1] || {}; },
    lastPrice() { return this.lastBar.close == null ? '--' : Number(this.lastBar.close).toLocaleString(undefined, { maximumFractionDigits: 8 }); },
    lastTime() { return this.lastBar.timestamp ? this.formatTime(this.lastBar.timestamp) : '--'; },
    changeText() {
      if (!this.lastBar.open) return '--';
      const value = (this.lastBar.close - this.lastBar.open) / this.lastBar.open * 100;
      return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
    },
    changeClass() { return this.lastBar.close >= this.lastBar.open ? 'up' : 'down'; },
  },
  mounted() {
    this.log('mounted', { symbol: this.symbol, interval: this.interval, url: location.href });
    this.chart = init(this.$refs.chart);
    this.chart.setTimezone('Asia/Shanghai');
    this.chart.setStyles({ grid: { horizontal: { color: '#263238' }, vertical: { color: '#263238' } }, candle: { type: 'candle_solid', bar: { upColor: '#35c99a', downColor: '#ef6b73', noChangeColor: '#9aa6ab' } } });
    this.chart.createIndicator({ name: 'BOLL', calcParams: [21, 3] }, false, { id: 'candle_pane' });
    this.chart.createIndicator('VOL');
    this.chart.setLoadDataCallback(({ type, data, callback }) => {
      if (type !== 'forward') {
        callback([], false);
        return;
      }
      const endTime = data?.timestamp ?? this.chart.getDataList()[0]?.timestamp;
      if (!Number.isFinite(endTime) || this.historyExhausted) {
        callback([], false);
        return;
      }
      this.requestHistory(endTime, callback);
    });
    this.updateAxisMode();
    this.connect();
  },
  beforeUnmount() { clearTimeout(this.reconnectTimer); clearTimeout(this.historyRetryTimer); clearTimeout(this.symbolStatusTimer); clearInterval(this.pingTimer); this.socket?.close(); dispose(this.$refs.chart); },
  methods: {
    log(event, details) {
      if (event === 'history-rpc-error' || event === 'history-rejected-gap' || event === 'ws-error' || event === 'server-error') {
        console.error(`[realtime-chart] ${event}`, details || '');
      }
    },
    formatTime(timestamp) {
      return new Intl.DateTimeFormat('zh-CN', {
        timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
      }).format(new Date(timestamp));
    },
    normalizeBars(bars) {
      return Array.from(new Map(bars.map((bar) => [bar.timestamp, bar])).values()).sort((a, b) => a.timestamp - b.timestamp);
    },
    intervalStep() {
      return this.interval === '1M' ? 0 : ({ '1s': 1000, '1m': 60000, '3m': 180000, '5m': 300000, '15m': 900000, '30m': 1800000, '1h': 3600000, '2h': 7200000, '4h': 14400000, '6h': 21600000, '8h': 28800000, '12h': 43200000, '1d': 86400000, '3d': 259200000, '1w': 604800000 }[this.interval] || 0);
    },
    toChartBar(bar) { return { timestamp: bar.open_time, open: bar.open, high: bar.high, low: bar.low, close: bar.close, volume: bar.volume }; },
    requestHistory(endTime, callback, auto = false) {
      const requestKey = `${this.symbol}:${this.interval}:${endTime}`;
      if (this.pendingHistory || this.requestedHistory.has(requestKey)) {
        this.log('history-skip-duplicate', { requestKey });
        callback([], false);
        return;
      }
      this.pendingHistory = { requestKey, callback, generation: this.chartGeneration };
      this.requestedHistory.add(requestKey);
      const expression = `chart_history(p,symbol='${this.symbol}',interval='${this.interval}',end_time=${endTime},limit=100)`;
      const url = `/r=${encodeURIComponent(expression)}`;
      this.log('history-rpc-request', { url, auto });
      fetch(url).then((response) => response.json().then((data) => ({ response, data }))).then(({ response, data }) => {
        if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
        if (!this.pendingHistory || this.pendingHistory.generation !== this.chartGeneration) return;
        const step = this.intervalStep();
        const existing = new Set(this.chart.getDataList().map((bar) => bar.timestamp));
        const history = data.bars.map((bar) => this.toChartBar(bar)).filter((bar) => Number.isFinite(bar.timestamp) && bar.timestamp < endTime && !existing.has(bar.timestamp) && (!step || bar.timestamp % step === 0)).sort((a, b) => a.timestamp - b.timestamp);
        const historyEnd = history[history.length - 1]?.timestamp;
        const contiguous = !step || (historyEnd === endTime - step && history.every((bar, index) => index === 0 || bar.timestamp - history[index - 1].timestamp === step));
        if (history.length && !contiguous) {
          this.log('history-rejected-gap', { endTime, historyEnd, step, bars: history.length });
          this.pendingHistory = null;
          callback([], false);
          return;
        }
        const more = history.length === 100 && (!step || history[0].timestamp <= endTime - step);
        const pendingCallback = this.pendingHistory.callback;
        this.pendingHistory = null;
        this.historyRetryCount = 0;
        const merged = new Map(history.concat(this.bars).map((bar) => [bar.timestamp, bar]));
        this.bars = Array.from(merged.values()).sort((a, b) => a.timestamp - b.timestamp);
        pendingCallback(history, more);
        if (!more) this.historyExhausted = true;
        this.log('history-applied', { bars: history.length, more, oldest: history[0]?.timestamp });
      }).catch((error) => {
        console.error('[realtime-chart] history-rpc-error', error);
        if (this.pendingHistory?.generation === this.chartGeneration) {
          const pendingCallback = this.pendingHistory.callback;
          this.pendingHistory = null;
          pendingCallback([], true);
          if (this.historyRetryCount < 3) {
            this.historyRetryCount += 1;
            clearTimeout(this.historyRetryTimer);
            this.historyRetryTimer = setTimeout(() => {
              this.historyRetryTimer = null;
              const firstBar = this.chart.getDataList()[0];
              const visible = this.chart.getVisibleRange();
              if (visible?.from === 0 && firstBar) this.requestHistory(firstBar.timestamp, pendingCallback);
            }, 1500);
          }
        }
      });
    },
    autoLoadHistory() {
      if (this.pendingHistory || this.historyExhausted) return;
      const visible = this.chart.getVisibleRange();
      if (visible && visible.from > 0) {
        this.log('history-auto-stop', { reason: 'viewport-filled', visible });
        return;
      }
      const firstBar = this.chart.getDataList()[0];
      if (firstBar) {
        const endTime = firstBar.timestamp;
        this.requestHistory(endTime, (bars, more) => {
          this.chart.applyMoreData(bars, more, () => {
            if (more) this.autoLoadHistory();
          });
        }, true);
      }
    },
    showSymbolStatus(message, isError) {
      this.symbolStatus = message;
      this.symbolStatusError = !!isError;
      clearTimeout(this.symbolStatusTimer);
      if (isError && message) this.symbolStatusTimer = setTimeout(() => { this.symbolStatus = ''; }, 6000);
    },
    openTickerPanel() {
      this.showSymbolMenu = false;
      this.showTickerPanel = true;
      const ageMs = Date.now() - (this.tickerTime || 0);
      if (!this.tickers.length || ageMs > 60000) this.fetchTickers();
    },
    closePanels() {
      this.showTickerPanel = false;
      this.showSymbolMenu = false;
    },
    toggleSymbolMenu() {
      this.showTickerPanel = false;
      this.showSymbolMenu = !this.showSymbolMenu;
    },
    fetchTickers() {
      if (this.loadingTickers) return;
      this.loadingTickers = true;
      const expression = 'r=chart_ticker24h()';
      const url = `/r=${encodeURIComponent(expression)}`;
      this.log('tickers-rpc-request', { url });
      fetch(url).then((response) => response.json().then((data) => ({ response, data }))).then(({ response, data }) => {
        if (!response.ok || data.error || !data.ok || !Array.isArray(data.tickers)) throw new Error(data.error || `HTTP ${response.status}`);
        this.tickers = data.tickers;
        this.tickerTime = Number(data.time) || Date.now();
        this.log('tickers-loaded', { count: this.tickers.length });
      }).catch((error) => {
        console.error('[realtime-chart] tickers-rpc-error', error);
        this.showSymbolStatus('交易对行情加载失败', true);
      }).finally(() => {
        this.loadingTickers = false;
      });
    },
    formatTickerPrice(value) {
      if (!Number.isFinite(value)) return '--';
      return Number(value).toLocaleString(undefined, { maximumFractionDigits: 8 });
    },
    formatPct(value) {
      if (!Number.isFinite(value)) return '--';
      return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
    },
    formatVolume(value) {
      if (!Number.isFinite(value) || value <= 0) return '--';
      if (value >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
      if (value >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
      if (value >= 1e3) return `${(value / 1e3).toFixed(2)}K`;
      return value.toFixed(2);
    },
    cellTitle(item) {
      return `${item.symbol} · 价 ${this.formatTickerPrice(item.lastPrice)} · 幅 ${this.formatPct(item.priceChangePercent)} · 24h额 ${this.formatVolume(item.quoteVolume)}`;
    },
    setTickerSort(key) {
      // Same key -> toggle direction; new key -> apply its default direction (name A-Z, others big-first).
      if (this.tickerSortKey === key) {
        this.tickerSortDesc = !this.tickerSortDesc;
      } else {
        this.tickerSortKey = key;
        this.tickerSortDesc = key !== 'name';
      }
    },
    tickerCompare(a, b) {
      const dir = this.tickerSortDesc ? -1 : 1;
      if (this.tickerSortKey === 'name') {
        return (a.symbol < b.symbol ? -1 : a.symbol > b.symbol ? 1 : 0) * dir;
      }
      let va = 0;
      let vb = 0;
      if (this.tickerSortKey === 'pct') {
        va = Math.abs(a.priceChangePercent);
        vb = Math.abs(b.priceChangePercent);
      } else if (this.tickerSortKey === 'vol') {
        va = a.quoteVolume || 0;
        vb = b.quoteVolume || 0;
      } else {
        va = a.lastPrice || 0;
        vb = b.lastPrice || 0;
      }
      return (va - vb) * dir;
    },
    pickTicker(item) {
      if (this.symbols.includes(item.symbol)) {
        this.switchSymbol(item.symbol);
        return;
      }
      this.newSymbol = item.symbol;
      this.addSymbol(item.symbol);
    },
    switchSymbol(symbol) {
      this.closePanels();
      if (!symbol || this.symbol === symbol) return;
      this.symbol = symbol;
      this.subscribe();
    },
    removeSymbol(symbol) {
      const expression = `r=chart_remove_symbol(symbol='${symbol}')`;
      const url = `/r=${encodeURIComponent(expression)}`;
      this.log('remove-symbol-request', { url });
      fetch(url).then((response) => response.json().then((data) => ({ response, data }))).then(({ response, data }) => {
        if (!response.ok || data.error || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
        if (Array.isArray(data.symbols)) this.symbols = data.symbols.slice();
        else this.symbols = this.symbols.filter((item) => item !== symbol);
        this.log('remove-symbol-ok', { symbol, symbols: this.symbols });
        if (this.symbol === symbol) {
          const next = this.symbols[0] || '';
          if (next) this.switchSymbol(next);
          else this.closePanels();
        }
      }).catch((error) => {
        console.error('[realtime-chart] remove-symbol-error', error);
        this.showSymbolStatus(error.message || String(error), true);
      });
    },
    addSymbol(explicitSymbol) {
      const symbol = (explicitSymbol || this.newSymbol || '').toUpperCase().trim();
      if (!symbol || this.addingSymbol) return;
      if (!/^[A-Z0-9]{5,20}$/.test(symbol)) {
        this.showSymbolStatus('symbol 格式无效（如 BTCUSDT）', true);
        return;
      }
      const switchTo = () => {
        this.addingSymbol = false;
        this.newSymbol = '';
        this.symbolStatus = '';
        this.closePanels();
        if (this.symbol !== symbol) {
          this.symbol = symbol;
          this.subscribe();
        }
      };
      if (this.symbols.includes(symbol)) { switchTo(); return; }
      this.addingSymbol = true;
      this.showSymbolStatus('订阅与 K 线校准中…', false);
      const expression = `r=chart_add_symbol(symbol='${symbol}')`;
      const url = `/r=${encodeURIComponent(expression)}`;
      this.log('add-symbol-request', { url });
      fetch(url).then((response) => response.json().then((data) => ({ response, data }))).then(({ response, data }) => {
        if (!response.ok || data.error || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
        if (Array.isArray(data.symbols) && data.symbols.length) this.symbols = data.symbols.slice();
        else if (!this.symbols.includes(symbol)) this.symbols = this.symbols.concat(symbol).sort();
        this.log('add-symbol-ok', { symbol, symbols: this.symbols });
        switchTo();
      }).catch((error) => {
        console.error('[realtime-chart] add-symbol-error', error);
        this.addingSymbol = false;
        this.showSymbolStatus(error.message || String(error), true);
      });
    },
    subscribe() {
      const url = `/chart_page(p,symbol='${encodeURIComponent(this.symbol)}',interval='${encodeURIComponent(this.interval)}')`;
      history.replaceState({ symbol: this.symbol, interval: this.interval }, '', url);
      this.log('subscribe', { symbol: this.symbol, interval: this.interval, url });
      if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify({ type: 'subscribe', symbol: this.symbol, interval: this.interval }));
    },
    updateAxisMode() {
      if (!this.chart) return;
      this.chart.setPriceVolumePrecision(this.pricePrecision, 2);
      if (this.autoScale && !this.scaleLocked) this.chart.adjustPaneViewport(true, true, true, true, true);
      this.chart.resize();
      this.log('axis-updated', { autoScale: this.autoScale, scaleLocked: this.scaleLocked, pricePrecision: this.pricePrecision });
    },
    toggleAutoScale() {
      this.autoScale = !this.autoScale;
      if (this.autoScale) this.scaleLocked = false;
      this.log('auto-scale-click', { autoScale: this.autoScale });
      this.updateAxisMode();
    },
    toggleScaleLock() { this.scaleLocked = !this.scaleLocked; if (this.scaleLocked) this.autoScale = false; this.log('scale-lock-click', { scaleLocked: this.scaleLocked }); this.updateAxisMode(); },
    connect() {
      const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const query = new URLSearchParams({ symbol: this.symbol, interval: this.interval });
      this.log('ws-connect', { url: `${scheme}//${location.host}/chart-ws?${query}` });
      const socket = new WebSocket(`${scheme}//${location.host}/chart-ws?${query}`);
      this.socket = socket;
      socket.onopen = () => { if (socket !== this.socket) return; this.connected = true; this.log('ws-open'); };
      socket.onclose = (event) => { if (socket !== this.socket) return; this.connected = false; this.log('ws-close', event); this.reconnectTimer = setTimeout(() => this.connect(), 1000); };
      socket.onerror = (event) => { if (socket !== this.socket) return; this.connected = false; console.error('[realtime-chart] ws-error', event); };
      socket.onmessage = (event) => {
        if (socket !== this.socket) return;
        const message = JSON.parse(event.data);
        this.log('ws-message', { type: message.type, symbol: message.symbol, interval: message.interval, bars: message.bars?.length });
        if (message.type === 'snapshot') {
          this.symbol = message.symbol; this.interval = message.interval;
          this.pricePrecision = Number.isInteger(message.price_precision) ? message.price_precision : 8;
          this.serverTime = this.formatTime(message.server_time);
          this.bars = this.normalizeBars(message.bars.map((bar) => this.toChartBar(bar)));
          this.chartGeneration += 1;
          this.pendingHistory = null;
          this.requestedHistory = new Set();
          this.historyExhausted = false;
          this.chart.applyNewData(this.bars);
          this.updateAxisMode();
        } else if (message.type === 'update') {
          const bar = this.toChartBar(message.bar);
          const index = this.bars.findIndex((item) => item.timestamp === bar.timestamp);
          if (index >= 0) {
            this.bars.splice(index, 1, bar);
            this.chart.updateData(bar);
          } else if (!this.bars.length || bar.timestamp > this.bars[this.bars.length - 1].timestamp) {
            this.bars.push(bar);
            this.chart.updateData(bar);
          } else {
            this.bars = this.normalizeBars(this.bars.concat(bar));
            this.chart.applyNewData(this.bars);
          }
          this.serverTime = this.formatTime(message.server_time);
          this.log('realtime-update', { timestamp: bar.timestamp });
        } else if (message.type === 'pong') {
          this.latency = `${Math.max(0, performance.now() - message.sent_at).toFixed(0)} ms`;
          this.serverTime = this.formatTime(message.server_time);
          this.log('ws-pong', { latency: this.latency });
        } else if (message.type === 'error') {
          console.error('[realtime-chart] server-error', message.message);
        }
      };
      clearInterval(this.pingTimer);
      this.pingTimer = setInterval(() => {
        if (this.socket?.readyState === WebSocket.OPEN) {
          this.socket.send(JSON.stringify({ type: 'ping', sent_at: performance.now() }));
        }
      }, 1000);
    },
    toggleFullscreen() { document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen(); },
  },
};
</script>
