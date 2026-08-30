<template>
  <main class="terminal">
    <ChartHeader
      v-model:newSymbol="newSymbol"
      :symbol="symbol"
      :last-price="lastPrice"
      :change-text="changeText"
      :change-class="changeClass"
      :adding-symbol="addingSymbol"
      :symbols="symbols"
      :interval="interval"
      :intervals="intervals"
      :show-symbol-menu="showSymbolMenu"
      @add-symbol="addSymbol()"
      @open-ticker-panel="openTickerPanel"
      @close-panels="closePanels"
      @toggle-symbol-menu="toggleSymbolMenu"
      @switch-symbol="switchSymbol"
      @remove-symbol="removeSymbol"
      @interval-change="handleIntervalChange"
      @toggle-fullscreen="toggleFullscreen"
    />

    <div v-if="showTickerPanel || showSymbolMenu" class="pop-overlay" @click="closePanels"></div>

    <TickerPanel
      v-if="showTickerPanel"
      :new-symbol="newSymbol"
      :loading-tickers="loadingTickers"
      :ticker-age-text="tickerAgeText"
      :grouped-tickers="groupedTickers"
      :ticker-hidden-total="tickerHiddenTotal"
      :ticker-group-cap="tickerGroupCap"
      :symbols="symbols"
      :tickers="tickers"
      :filtered-tickers="filteredTickers"
      :ticker-sort-options="tickerSortOptions"
      :ticker-sort-key="tickerSortKey"
      :ticker-sort-desc="tickerSortDesc"
      :cell-title="cellTitle"
      :format-ticker-price="formatTickerPrice"
      :format-pct="formatPct"
      @close-panel="closePanels"
      @set-sort="setTickerSort"
      @pick-ticker="pickTicker"
    />

    <div class="status"><i :class="{ online: connected }"></i>{{ connected ? 'LIVE' : 'CONNECTING' }}</div>
    <div class="chart-wrap" @contextmenu.prevent="onChartContextMenu">
      <div ref="chart" class="chart"></div>
      <div class="scale-controls"><button title="Auto: 让 K 线和指标尽量铺满屏幕" :class="{ active: autoScale }" @click="toggleAutoScale">A</button><button title="锁定价格尺度" :class="{ active: scaleLocked }" @click="toggleScaleLock">L</button></div>
      <div v-if="contextMenu" class="ctx-overlay" @click="closeContextMenu" @contextmenu.prevent="closeContextMenu"></div>
      <div v-if="contextMenu" class="ctx-menu" :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }" @click.stop @contextmenu.prevent>
        <div class="ctx-title">{{ symbol }} · {{ interval }} · {{ contextMenu.bar.timestamp }} · {{ formatTime(contextMenu.bar.timestamp) }}</div>
        <button type="button" :disabled="drilling" @click="drillExtreme('high')"><span>跳最高价秒</span><b class="up">{{ formatTickerPrice(contextMenu.bar.high) }}</b></button>
        <button type="button" :disabled="drilling" @click="drillExtreme('low')"><span>跳最低价秒</span><b class="down">{{ formatTickerPrice(contextMenu.bar.low) }}</b></button>
        <button type="button" @click="copyCurrentUrl"><span>复制 URL</span></button>
      </div>
    </div>

    <ChartFooter
      :bar-count="barCount"
      :latency="latency"
      :server-time="serverTime"
      :last-time="lastTime"
      :foot-log="footLog"
      :foot-log-error="footLogError"
    />
  </main>
</template>

<script>
import { ActionType, dispose, init } from 'klinecharts';
import ChartHeader from './components/ChartHeader.vue';
import TickerPanel from './components/TickerPanel.vue';
import ChartFooter from './components/ChartFooter.vue';

export default {
  components: {
    ChartHeader,
    TickerPanel,
    ChartFooter,
  },
  name: 'RealtimeChart',
  data() {
    return {
      chart: null, socket: null, reconnectTimer: null, connected: false,
      symbol: window.__INITIAL_SYMBOL__ || 'BTCUSDT', interval: window.__INITIAL_INTERVAL__ || '1m', bars: [],
      autoScale: true, scaleLocked: false, pricePrecision: 8, latency: '--', serverTime: '--', serverTimeMs: 0,
      pendingHistory: null, historyRetryTimer: null, historyRetryCount: 0, requestedHistory: new Set(), historyExhausted: false, chartGeneration: 0,
      // liveTail=true: the view follows the newest forming bar (WS appends); false: anchored to a history window (REST paging both ways)
      liveTail: true,
      // locating=true between applyNewData and the post-ready scroll: suppresses edge-triggered paging from the transient "end of data" view
      locating: false,
      // appendingNewer=true while a backward page is fed into the chart: the library re-enters the
      // edge callback synchronously inside addData(); use it to stop one user drag from chain-loading pages.
      appendingNewer: false,
      symbols: window.__SYMBOLS__ || ['BTCUSDT'],
      intervals: window.__INTERVALS__ || ['1m'],
      newSymbol: '', addingSymbol: false, footLog: '', footLogError: false, footLogTimer: null,
      tickers: Array.isArray(window.__TICKERS__) ? window.__TICKERS__ : [],
      tickerTime: Number(window.__TICKER_TIME__) || 0,
      loadingTickers: false, showTickerPanel: false, showSymbolMenu: false,
      crosshairBar: null, contextMenu: null, drilling: false, drillTarget: null,
      // URL time anchor (ms): shared deep link to a specific bar; focusTarget is one-shot after each snapshot
      urlTime: Number(window.__INITIAL_TIME__) || 0, focusTarget: Number(window.__INITIAL_TIME__) || 0, urlSyncTimer: null, urlSyncLockUntil: 0,
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
    lastPrice() { return this.lastBar.close == null ? '--' : Number(this.lastBar.close).toLocaleString(undefined, { minimumFractionDigits: this.pricePrecision, maximumFractionDigits: this.pricePrecision }); },
    lastTime() { return this.lastBar.timestamp ? this.formatTime(this.lastBar.timestamp) : '--'; },
    changeText() {
      if (!this.lastBar.open) return '--';
      const value = (this.lastBar.close - this.lastBar.open) / this.lastBar.open * 100;
      return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
    },
    changeClass() { return this.lastBar.close >= this.lastBar.open ? 'up' : 'down'; },
  },
  mounted() {
    this.urlTime = Number(window.__INITIAL_TIME__) || this.urlTime || 0;
    if (this.urlTime) {
      this.updateDocumentTitle();
    }
    this.log('mounted', { symbol: this.symbol, interval: this.interval, url: location.href, initialTime: this.urlTime });
    this.chart = init(this.$refs.chart);
    this.chart.setTimezone('Asia/Shanghai');
    this.chart.setStyles({ grid: { horizontal: { color: '#263238' }, vertical: { color: '#263238' } }, candle: { type: 'candle_solid', bar: { upColor: '#35c99a', downColor: '#ef6b73', noChangeColor: '#9aa6ab' } } });
    // Crosshair candle tooltip: OHLCV plus per-bar 涨跌OC (close vs open) and 振幅HL ((high-low)/open).
    this.chart.setStyles({ candle: { tooltip: { custom: (data, styles) => this.candleTooltipLegends(data, styles) } } });
    this.chart.createIndicator({ name: 'BOLL', calcParams: [21, 3] }, false, { id: 'candle_pane' });
    this.chart.createIndicator('VOL');
    // Track the bar under the crosshair so the right-click menu can drill into it;
    // crosshair moves also refresh the URL time anchor (debounced).
    this.chart.subscribeAction(ActionType.OnCrosshairChange, (data) => {
      this.crosshairBar = data?.kLineData || null;
    });
    this.chart.subscribeAction(ActionType.OnScroll, ({ distance }) => {
      if (!Number.isFinite(distance) || !distance || this.drilling || this.locating) return;
      if (Date.now() < this.urlSyncLockUntil) {
        console.log('[realtime-chart] user-scroll-edge-sync:locked', { distance, urlSyncLockUntil: this.urlSyncLockUntil, now: Date.now() });
        return;
      }
      const range = this.chart?.getVisibleRange?.();
      const list = this.chart?.getDataList?.() || this.bars || [];
      if (!list.length || !range) return;
      const atLeft = Number(range.from) <= 1;
      const atRight = Number(range.to) >= list.length - 2;
      const reason = atLeft ? 'left-edge' : atRight ? 'right-edge' : 'middle';
      if (!atLeft && !atRight) return;
      const idx = atRight ? Math.min(Math.max(Number(range.to), 0), list.length - 1) : Math.min(Math.max(Number(range.from), 0), list.length - 1);
      const timestamp = list[idx]?.timestamp;
      if (Number.isFinite(timestamp)) {
        console.log('[realtime-chart] user-scroll-edge-sync', { distance, range, timestamp, atLeft, atRight, reason, idx, total: list.length });
        this.syncUrlTime(timestamp, true);
      }
    });
    this.chart.setLoadDataCallback(({ type, data, callback }) => {
      const list = this.chart.getDataList();
      if (type === 'forward') {
        // Left edge: page towards older bars.
        const endTime = data?.timestamp ?? list[0]?.timestamp;
        if (!Number.isFinite(endTime) || this.historyExhausted) {
          callback([], false);
          return;
        }
        this.requestHistory(endTime, callback);
      } else if (type === 'backward') {
        // Right edge: page towards newer bars; once caught up with the live bar, WS updates take over.
        const startTime = data?.timestamp ?? list[list.length - 1]?.timestamp;
        if (!Number.isFinite(startTime)) {
          callback([], false);
          return;
        }
        this.requestNewerHistory(startTime, callback);
      } else {
        callback([], false);
      }
    });
    // Keep a visible gap (~15 bars) between the newest bar and the right edge so it reads as "latest".
    this.chart.setOffsetRightDistance(120);
    this.updateAxisMode();
    this.connect();
  },
  beforeUnmount() { clearTimeout(this.reconnectTimer); clearTimeout(this.historyRetryTimer); clearTimeout(this.footLogTimer); clearTimeout(this.urlSyncTimer); clearInterval(this.pingTimer); this.socket?.close(); dispose(this.$refs.chart); },
  methods: {
    log(event, details) {
      // Notable events are mirrored to the footer log label; high-frequency debug
      // events (ws-message/update/pong/history-applied...) stay console-only.
      const footMessages = {
        'history-rpc-error': ['历史行情加载失败', true],
        'newer-rpc-error': ['历史行情加载失败', true],
        'ws-error': ['WebSocket 连接异常，正在重连…', true],
        'server-error': [`服务器错误：${details?.message || ''}`, true],
        'history-rejected-gap': ['历史行情存在缺口，已跳过不连续部分', false],
      };
      const hit = footMessages[event];
      if (hit) {
        console.error(`[realtime-chart] ${event}`, details || '');
        this.setFootLog(hit[0], hit[1]);
      }
    },
    setFootLog(message, isError = false) {
      this.footLog = message || '';
      this.footLogError = !!isError;
      clearTimeout(this.footLogTimer);
      // Temporary log label: revert to the default "WebSocket stream" hint after a few seconds.
      if (message) this.footLogTimer = setTimeout(() => { this.footLog = ''; }, isError ? 60*1000 : 10*1000);
    },
    // klinecharts candle tooltip custom callback: full replacement of the default OHLCV
    
    candleTooltipLegends(data, styles) {
      const d = data?.current || {};
      const price = (v) => Number.isFinite(v)
        ? Number(v).toLocaleString(undefined, { minimumFractionDigits: this.pricePrecision, maximumFractionDigits: this.pricePrecision })
        : '--';
      const prevClose = data?.prev?.close;
      const chg = Number.isFinite(prevClose) && prevClose !== 0 && Number.isFinite(d.close) ? (d.close - prevClose) / prevClose * 100 : null;
      const oc = Number.isFinite(d.open) && d.open !== 0 && Number.isFinite(d.close) ? (d.close - d.open) / d.open * 100 : null;
      const amp = Number.isFinite(d.open) && d.open !== 0 && Number.isFinite(d.high) && Number.isFinite(d.low) ? (d.high - d.low) / d.open * 100 : null;
      const up = styles?.priceMark?.last?.upColor || '#35c99a';
      const down = styles?.priceMark?.last?.downColor || '#ef6b73';
      const flat = styles?.priceMark?.last?.noChangeColor || '#9aa6ab';
      const chgColor = chg == null ? flat : chg > 0 ? up : chg < 0 ? down : flat;
      const ocColor = oc == null ? flat : oc > 0 ? up : oc < 0 ? down : flat;
      const pct = (v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
      return [
        { title: 'Time', value: d.timestamp ? this.formatTime(d.timestamp) : '--' },
        { title: 'Open', value: price(d.open) },
        { title: 'High', value: price(d.high) },
        { title: 'Low', value: price(d.low) },
        { title: 'Close', value: price(d.close) },
        { title: 'Volume', value: Number.isFinite(d.volume) ? this.formatVolume(d.volume) : '--' },
        { title: '涨跌', value: { text: chg == null ? '--' : pct(chg), color: chgColor } },
        { title: 'OC', value: { text: oc == null ? '--' : pct(oc), color: ocColor } },
        { title: '振幅HL', value: { text: amp == null ? '--' : `${amp.toFixed(2)}%`, color: '#e8c15e' } },
      ];
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
      // While a programmatic locate is in flight the transient view may touch an edge; skip it
      // (more=true keeps the paging flag so a real user drag still triggers afterwards).
      if (this.locating) { callback([], true); return; }
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
        this.log('history-rpc-error', { error: error.message || String(error) });
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
    requestNewerHistory(startTime, callback) {
      // Skip edge-triggered paging while a programmatic locate (focus/drill) is still landing.
      if (this.locating || this.appendingNewer) { callback([], true); return; }
      // Live mode: new buckets arrive over WS; never page REST at the live right edge.
      if (this.liveTail) { callback([], false); return; }
      const step = this.intervalStep() || 32 * 86400000;
      const list = this.chart.getDataList();
      const last = list[list.length - 1];
      // Newest loaded bar already is (or past) the current forming bucket: live WS updates take over.
      if (last && this.serverTimeMs && last.timestamp + step > this.serverTimeMs) {
        this.liveTail = true;
        callback([], false);
        return;
      }
      const requestKey = `newer:${this.symbol}:${this.interval}:${startTime}`;
      if (this.pendingHistory || this.requestedHistory.has(requestKey)) {
        this.log('history-skip-duplicate', { requestKey });
        callback([], true); // keep backwardMore=true so the next drag retries
        return;
      }
      this.pendingHistory = { requestKey, callback, generation: this.chartGeneration };
      this.requestedHistory.add(requestKey);
      // First bucket after the newest loaded bar; Binance may return the bucket containing it, filtered client-side.
      const expression = `chart_history(p,symbol='${this.symbol}',interval='${this.interval}',start_time=${startTime + step},limit=500)`;
      const url = `/r=${encodeURIComponent(expression)}`;
      this.log('newer-rpc-request', { url });
      fetch(url).then((response) => response.json().then((data) => ({ response, data }))).then(({ response, data }) => {
        if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
        if (!this.pendingHistory || this.pendingHistory.generation !== this.chartGeneration) return;
        const existing = new Set(this.chart.getDataList().map((bar) => bar.timestamp));
        const newer = (data.bars || [])
          .map((bar) => this.toChartBar(bar))
          .filter((bar) => Number.isFinite(bar.timestamp) && bar.timestamp > startTime && !existing.has(bar.timestamp))
          .sort((a, b) => a.timestamp - b.timestamp);
        const newest = newer[newer.length - 1]?.timestamp ?? startTime;
        // Caught up when the page is short or the newest fetched bucket covers the server clock.
        const caughtUp = newer.length < 500 || (this.serverTimeMs > 0 && newest + step > this.serverTimeMs);
        const pendingCallback = this.pendingHistory.callback;
        this.pendingHistory = null;
        if (newer.length) {
          const merged = new Map(this.bars.concat(newer).map((bar) => [bar.timestamp, bar]));
          this.bars = Array.from(merged.values()).sort((a, b) => a.timestamp - b.timestamp);
        }
        if (caughtUp) this.liveTail = true;
        const appendGen = this.chartGeneration;
        // addData() re-enters this edge callback synchronously while appending; appendingNewer
        // answers the re-entry with an empty page so one user drag cannot chain-load pages.
        this.appendingNewer = true;
        try {
          pendingCallback(newer, !caughtUp);
        } finally {
          this.appendingNewer = false;
        }
        if (caughtUp) {
          // Snap back to the live edge: newest bar with the right-side gap, WS takes over from here.
          this.chart.scrollToRealTime(0);
        } else if (newer.length) {
          // One page per user gesture: once the append settles, leave the last few bars just
          // off-screen right so `to < total`; the library stops loading until the user drags again.
          // A programmatic locate (focus/drill) leaves the viewport mid-list, in which case do nothing.
          const settle = () => {
            this.chart.unsubscribeAction(ActionType.OnDataReady, settle);
            if (this.chartGeneration !== appendGen || this.locating || this.liveTail) return;
            const range = this.chart.getVisibleRange();
            const total = this.chart.getDataList().length;
            if (range.to >= total - 1) this.chart.scrollToDataIndex(total - 1 - 3, 0);
          };
          this.chart.subscribeAction(ActionType.OnDataReady, settle);
        }
        this.log('newer-applied', { bars: newer.length, more: !caughtUp, newest });
      }).catch((error) => {
        this.log('newer-rpc-error', { error: error.message || String(error) });
        if (this.pendingHistory?.generation === this.chartGeneration) {
          const pendingCallback = this.pendingHistory.callback;
          this.pendingHistory = null;
          pendingCallback([], true);
        }
      });
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
        this.setFootLog('交易对行情加载失败', true);
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
      // Row data comes from our own TRADING-filtered 24hr cache: format is guaranteed, skip manual regex.
      this.addSymbol(item.symbol, true);
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
        this.setFootLog(error.message || String(error), true);
      });
    },
    // 与后端 normalize_symbol 同一规则：symbol 是单个 token，允许非 ASCII（如中文 meme 币 币安人生USDT）；
    // 仅拒绝 trim 后为空/过短、含空白、控制字符或引号（引号会破坏 RPC 表达式 chart_add_symbol(symbol='...')）。
    isValidSymbolInput(symbol) {
      const s = String(symbol || '').trim();
      if (s.length < 2) return false;
      return !/[\s'"\x00-\x1f]/.test(s);
    },
    addSymbol(explicitSymbol, trusted = false) {
      const symbol = (explicitSymbol || this.newSymbol || '').toUpperCase().trim();
      if (!symbol || this.addingSymbol) return;
      if (!trusted && !this.isValidSymbolInput(symbol)) {
        this.setFootLog('symbol 格式无效：不能为空且不含空格/引号，如 BTCUSDT', true);
        return;
      }
      const switchTo = () => {
        this.addingSymbol = false;
        this.newSymbol = '';
        this.setFootLog(`已订阅 ${symbol}`, false);
        this.closePanels();
        if (this.symbol !== symbol) {
          this.symbol = symbol;
          this.subscribe();
        }
      };
      if (this.symbols.includes(symbol)) { switchTo(); return; }
      this.addingSymbol = true;
      this.setFootLog('订阅与 K 线校准中…', false);
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
        this.setFootLog(error.message || String(error), true);
      });
    },
    shortSymbol(symbol = this.symbol) {
      const value = String(symbol || '').trim().toUpperCase();
      if (!value) return '—';
      return value.replace(/USDT$|USDC$|BUSD$|BTC$|ETH$|BNB$/i, '').trim() || value;
    },
    updateDocumentTitle() {
      const timestamp = Number.isFinite(this.urlTime) && this.urlTime > 0 ? this.urlTime : Date.now();
      const readableTime = new Date(timestamp).toLocaleString('zh-CN', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false,
      }).replace(/\//g, '-').replace(/\s+/g, ' ');
      document.title = `${this.shortSymbol(this.symbol)} ${this.interval} ${readableTime}`;
    },
    pageUrl() {
      let url = `/chart_page(p,symbol='${encodeURIComponent(this.symbol)}',interval='${encodeURIComponent(this.interval)}'`;
      if (this.urlTime) url += `,time=${this.urlTime}`;
      return `${url})`;
    },
    handleIntervalChange(value) {
      this.interval = value;
      this.subscribe();
    },
    subscribe() {
      history.replaceState({ symbol: this.symbol, interval: this.interval, time: this.urlTime || null }, '', this.pageUrl());
      this.updateDocumentTitle();
      this.log('subscribe', { symbol: this.symbol, interval: this.interval, urlTime: this.urlTime });
      if (this.socket?.readyState === WebSocket.OPEN) {
        // Re-anchor the view to the URL time after interval/symbol switch (drill flow sets drillTarget instead).
        if (!this.drillTarget) this.focusTarget = this.urlTime || 0;
        this.socket.send(JSON.stringify({ type: 'subscribe', symbol: this.symbol, interval: this.interval }));
      }
    },
    syncUrlTime(timestamp, pushHistory = false) {
      if (!Number.isFinite(timestamp)) return;
      const nextUrl = this.pageUrl();
      const currentUrl = `${location.pathname}${location.search}`;
      if (this.urlTime === timestamp && currentUrl === nextUrl) {
        console.log('[realtime-chart] syncUrlTime:skip-equal', { timestamp, currentUrl, nextUrl, pushHistory });
        this.updateDocumentTitle();
        return;
      }
      this.urlTime = timestamp;
      console.log('[realtime-chart] syncUrlTime', { timestamp, pushHistory, currentUrl, nextUrl, symbol: this.symbol, interval: this.interval });
      const state = { symbol: this.symbol, interval: this.interval, time: timestamp };
      this.updateDocumentTitle();
      if (pushHistory) {
        history.pushState(state, document.title, nextUrl);
      } else {
        history.replaceState(state, document.title, nextUrl);
      }
    },
    scheduleUrlTimeSync(force = false) {
      clearTimeout(this.urlSyncTimer);
      this.urlSyncTimer = setTimeout(() => {
        if (this.drilling) return;
        if (!force && Number.isFinite(this.crosshairBar?.timestamp)) return;
        let timestamp = this.crosshairBar?.timestamp;
        if (!Number.isFinite(timestamp)) {
          // No crosshair (dragging history): anchor to the rightmost visible bar so the view restores when reopening.
          const range = this.chart?.getVisibleRange?.();
          const list = this.chart?.getDataList?.() || this.bars;
          const idx = Number.isInteger(range?.to) ? range.to : list.length - 1;
          timestamp = list[Math.min(Math.max(idx, 0), list.length - 1)]?.timestamp;
        }
        if (Number.isFinite(timestamp)) this.syncUrlTime(timestamp);
      }, 400);
    },
    centerOnTimestamp(timestamp) {
      if (!this.chart || !Number.isFinite(timestamp)) return;
      const list = this.chart.getDataList ? this.chart.getDataList() : this.bars || [];
      const index = list.findIndex((item) => item.timestamp === timestamp);
      const targetPixel = this.chart.convertToPixel ? this.chart.convertToPixel({ timestamp }, { paneId: 'candle_pane' }) : null;
      const viewportWidth = this.$refs.chart ? this.$refs.chart.clientWidth : 0;
      const viewportCenter = viewportWidth / 2;
      const targetX = targetPixel && Number.isFinite(targetPixel.x) ? targetPixel.x : null;
      const delta = targetX != null && Number.isFinite(viewportCenter) ? viewportCenter - targetX : 0;
      console.log('[realtime-chart] centerOnTimestamp:calc', {
        timestamp,
        index,
        targetX,
        viewportCenter,
        delta,
        visibleRange: this.chart.getVisibleRange ? this.chart.getVisibleRange() : null,
        total: list.length,
      });
      this.locating = true;
      this.urlSyncLockUntil = Date.now() + 2000;
      if (targetX != null && Math.abs(delta) > 1 && typeof this.chart.scrollByDistance === 'function') {
        this.chart.scrollByDistance(delta, 0);
      } else if (typeof this.chart.scrollToTimestamp === 'function') {
        this.chart.scrollToTimestamp(timestamp, 0);
      }
      setTimeout(() => {
        this.locating = false;
      }, 120);
      const after = this.chart.convertToPixel ? this.chart.convertToPixel({ timestamp }, { paneId: 'candle_pane' }) : null;
      console.log('[realtime-chart] centerOnTimestamp:end', {
        timestamp,
        afterX: after && after.x,
        viewportCenter,
        offset: after && Number.isFinite(after.x) ? after.x - viewportCenter : null,
        visibleRangeAfter: this.chart.getVisibleRange ? this.chart.getVisibleRange() : null,
      });
    },
    locateAfterReady(timestamp) {
      // applyNewData indexes asynchronously: scroll only once the data is ready, otherwise
      // the view stays at the data end, the crosshair misses the anchor, and the transient
      // end-edge view spuriously triggers a newer-bars page.
      const gen = this.chartGeneration;
      this.locating = true;
      let fallback = 0;
      const doLocate = () => {
        if (!this.locating) return;
        this.locating = false;
        clearTimeout(fallback);
        this.chart.unsubscribeAction(ActionType.OnDataReady, doLocate);
        if (this.chartGeneration !== gen) return;
        this.centerOnTimestamp(timestamp);
        const pixel = this.chart.convertToPixel({ timestamp }, { paneId: 'candle_pane' });
        if (pixel && Number.isFinite(pixel.x)) {
          // Draws the crosshair line at the anchor; note: executeAction does NOT re-dispatch
          // OnCrosshairChange, so the Vue-side anchor must be set explicitly below.
          this.chart.executeAction(ActionType.OnCrosshairChange, { x: pixel.x, paneId: 'candle_pane' });
        }
        const anchorBar = this.chart.getDataList().find((item) => item.timestamp === timestamp) || null;
        this.crosshairBar = anchorBar;
      };
      fallback = setTimeout(doLocate, 500);
      this.chart.subscribeAction(ActionType.OnDataReady, doLocate);
    },
    focusOnTime() {
      const timestamp = this.focusTarget;
      if (!timestamp) return;
      // One REST page (up to 1000 bars) ending ~500 bars AFTER the anchor: after scrollToTimestamp
      // the target sits at the right edge with newer bars off-screen, so the chart's right-edge
      // (Backward) paging does NOT auto-chain all the way to live (that storm froze the page on 1s).
      const step = this.intervalStep() || 32 * 86400000;
      const endTime = timestamp + 500 * step;
      const expression = `chart_history(p,symbol='${this.symbol}',interval='${this.interval}',end_time=${endTime},limit=1000)`;
      const url = `/r=${encodeURIComponent(expression)}`;
      this.log('focus-window-request', { url, target: timestamp });
      fetch(url).then((response) => response.json().then((data) => ({ response, data }))).then(({ response, data }) => {
        if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
        if (this.focusTarget !== timestamp) return;
        const history = (data.bars || [])
          .map((bar) => this.toChartBar(bar))
          .filter((bar) => Number.isFinite(bar.timestamp))
          .sort((a, b) => a.timestamp - b.timestamp);
        if (!history.length) throw new Error('该时间附近没有可用 K 线');
        // Replace, do NOT merge the live snapshot tail: otherwise a far-future last bar would
        // break right-edge (backward) paging. Both directions page from this window.
        this.bars = history;
        this.chartGeneration += 1;
        this.pendingHistory = null;
        this.requestedHistory = new Set();
        this.historyExhausted = false;
        this.liveTail = false;
        // Must be set BEFORE applyNewData: its edge paging callbacks fire synchronously inside the call.
        this.locating = true;
        this.chart.applyNewData(this.bars);
        this.updateAxisMode();
        this.locateAfterReady(timestamp);
        this.focusTarget = 0;
        this.setFootLog(`已定位到 ${this.formatTime(timestamp)}（URL time 锚点 · ${this.interval}，左右拖动可连续加载历史）`, false);
      }).catch((error) => {
        console.error('[realtime-chart] focus-window-error', error);
        this.focusTarget = 0;
        this.setFootLog('时间锚点定位失败: ' + (error.message || error), true);
      });
    },

    // 核心修复逻辑：在更新缩放模式时，强制遍历图表重置 y 轴锁定状态，并通知重绘
    updateAxisMode() {
      if (!this.chart) return;
      
      this.chart.setPriceVolumePrecision(this.pricePrecision, 2);
      
      console.log(`[realtime-chart] 📊 updateAxisMode triggered | autoScale: ${this.autoScale} | scaleLocked: ${this.scaleLocked}`);

      try {
        if (this.autoScale && !this.scaleLocked) {
          // 1. 获取所有绘制面板 (DrawPanes)
          const panes = typeof this.chart.getAllDrawPanes === 'function' ? this.chart.getAllDrawPanes() : [];
          console.log(`[realtime-chart] 🔍 遍历 ${panes.length} 个 DrawPanes 寻找 Y 轴以解除锁定...`);

          panes.forEach((pane) => {
            // 2. 尝试获取该面板的 Y 轴组件 (兼容不同底层属性)
            const yAxis = typeof pane.getAxisComponent === 'function' ? pane.getAxisComponent() : pane._axis;
            
            // 3. 强行重置自动计算标志位
            if (yAxis && yAxis._autoCalcTickFlag !== undefined) {
              const oldFlag = yAxis._autoCalcTickFlag;
              const range = typeof yAxis.getRange === 'function' ? yAxis.getRange() : 'unknown';
              
              // 【核心修复】模拟库内双击 Y 轴的内部行为，释放 Y 轴尺度控制权
              yAxis._autoCalcTickFlag = true;
              
              console.log(`[realtime-chart] ✅ 面板 [${pane.getId ? pane.getId() : 'unknown'}] Y轴已释放 | _autoCalcTickFlag: ${oldFlag} -> true | 冻结前的 Range:`, range);
            }
          });
          
          if (typeof this.chart.adjustPaneViewport === 'function') {
            this.chart.adjustPaneViewport(true, true, true, true, true);
          }
        }

        if (typeof this.chart.resize === 'function') {
          this.chart.resize(); 
        }
        
      } catch (err) {
        console.error('[realtime-chart] ❌ updateAxisMode 发生运行时异常:', err);
      }
      
      this.log('axis-updated', { autoScale: this.autoScale, scaleLocked: this.scaleLocked, pricePrecision: this.pricePrecision });
    },

    toggleAutoScale() {
      this.autoScale = !this.autoScale;
      if (this.autoScale) this.scaleLocked = false;
      this.log('auto-scale-click', { autoScale: this.autoScale });
      this.updateAxisMode();
    },

    toggleScaleLock() {
      this.scaleLocked = !this.scaleLocked;
      if (this.scaleLocked) this.autoScale = false;
      this.log('scale-lock-click', { scaleLocked: this.scaleLocked });
      this.updateAxisMode();
    },

    connect() {
      const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const query = new URLSearchParams({ symbol: this.symbol, interval: this.interval });
      this.log('ws-connect', { url: `${scheme}//${location.host}/chart-ws?${query}` });
      const socket = new WebSocket(`${scheme}//${location.host}/chart-ws?${query}`);
      this.socket = socket;
      socket.onopen = () => { if (socket !== this.socket) return; this.connected = true; this.log('ws-open'); };
      socket.onclose = (event) => { if (socket !== this.socket) return; this.connected = false; this.log('ws-close', event); this.reconnectTimer = setTimeout(() => this.connect(), 1000); };
      socket.onerror = (event) => { if (socket !== this.socket) return; this.connected = false; this.log('ws-error', event); };
      socket.onmessage = (event) => {
        if (socket !== this.socket) return;
        const message = JSON.parse(event.data);
        this.log('ws-message', { type: message.type, symbol: message.symbol, interval: message.interval, bars: message.bars?.length });
        if (message.type === 'snapshot') {
          this.symbol = message.symbol; this.interval = message.interval;
          this.pricePrecision = Number.isInteger(message.price_precision) ? message.price_precision : 8;
          this.serverTimeMs = Number(message.server_time) || this.serverTimeMs;
          this.serverTime = this.formatTime(message.server_time);
          this.bars = this.normalizeBars(message.bars.map((bar) => this.toChartBar(bar)));
          this.chartGeneration += 1;
          this.pendingHistory = null;
          this.requestedHistory = new Set();
          this.historyExhausted = false;
          this.liveTail = true;
          this.chart.applyNewData(this.bars);
          this.updateAxisMode();
          if (this.drillTarget) this.openDrillWindow();
          else if (this.focusTarget) this.focusOnTime();
          else {
            // No time anchor: the newest bar sits with a gap to the right edge, and the URL follows it.
            const lastBar = this.bars[this.bars.length - 1];
            if (lastBar) this.syncUrlTime(lastBar.timestamp);
          }
        } else if (message.type === 'update') {
          const bar = this.toChartBar(message.bar);
          this.serverTimeMs = Number(message.server_time) || this.serverTimeMs;
          const last = this.bars[this.bars.length - 1];
          const index = this.bars.findIndex((item) => item.timestamp === bar.timestamp);
          if (index >= 0) {
            this.bars.splice(index, 1, bar);
            this.chart.updateData(bar);
          } else if (this.liveTail && (!this.bars.length || (last && bar.timestamp > last.timestamp))) {
            // Live tail: a new bucket starts forming -> append, and the URL time moves with it.
            this.bars.push(bar);
            this.chart.updateData(bar);
            this.syncUrlTime(bar.timestamp);
          } else if (!this.liveTail && last && bar.timestamp > last.timestamp) {
            // History window: only accept the next contiguous bucket (means paging reached live);
            // far-future live ticks while viewing old history are dropped.
            const step = this.intervalStep() || 32 * 86400000;
            if (bar.timestamp <= last.timestamp + step * 2) {
              this.bars.push(bar);
              this.chart.updateData(bar);
              this.liveTail = true;
              // Paging reached the live bucket: snap to the newest bar with the right-side gap.
              this.chart.scrollToRealTime(0);
              this.syncUrlTime(bar.timestamp);
            }
          } else if (this.liveTail && last && bar.timestamp < last.timestamp) {
            this.bars = this.normalizeBars(this.bars.concat(bar));
            this.chart.applyNewData(this.bars);
          }
          this.serverTime = this.formatTime(message.server_time);
          this.log('realtime-update', { timestamp: bar.timestamp, liveTail: this.liveTail });
        } else if (message.type === 'pong') {
          this.latency = `${Math.max(0, performance.now() - message.sent_at).toFixed(0)} ms`;
          this.serverTimeMs = Number(message.server_time) || this.serverTimeMs;
          this.serverTime = this.formatTime(message.server_time);
          this.log('ws-pong', { latency: this.latency });
        } else if (message.type === 'error') {
          this.log('server-error', { message: message.message });
        }
      };
      clearInterval(this.pingTimer);
      this.pingTimer = setInterval(() => {
        if (this.socket?.readyState === WebSocket.OPEN) {
          this.socket.send(JSON.stringify({ type: 'ping', sent_at: performance.now() }));
        }
      }, 1000);
    },
    onChartContextMenu(event) {
      const bar = this.crosshairBar;
      console.log('[realtime-chart] contextmenu-open', {
        clientX: event?.clientX,
        clientY: event?.clientY,
        timestamp: bar?.timestamp,
        symbol: this.symbol,
        interval: this.interval,
        urlTime: this.urlTime,
        visibleRange: this.chart?.getVisibleRange?.(),
      });
      if (this.drilling || !bar || !Number.isFinite(bar.timestamp)) {
        this.contextMenu = null;
        return;
      }
      this.syncUrlTime(bar.timestamp, true);
      this.contextMenu = {
        x: Math.min(event.clientX, window.innerWidth - 250),
        y: Math.min(event.clientY, window.innerHeight - 130),
        bar,
      };
    },
    closeContextMenu() { this.contextMenu = null; },
    async copyCurrentUrl() {
      const bar = this.contextMenu?.bar || this.crosshairBar;
      const timestamp = Number.isFinite(bar?.timestamp) ? bar.timestamp : this.urlTime;
      console.log('[realtime-chart] copy-url-click', { timestamp, urlTime: this.urlTime, pageUrl: this.pageUrl() });
      if (Number.isFinite(timestamp)) this.syncUrlTime(timestamp, true);
      const shareUrl = new URL(this.pageUrl(), window.location.origin).toString();
      this.contextMenu = null;
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(shareUrl);
        } else {
          const textarea = document.createElement('textarea');
          textarea.value = shareUrl;
          textarea.setAttribute('readonly', '');
          textarea.style.position = 'fixed';
          textarea.style.left = '-9999px';
          document.body.appendChild(textarea);
          textarea.select();
          document.execCommand('copy');
          document.body.removeChild(textarea);
        }
        this.setFootLog(`已复制当前 K 线链接：${shareUrl}`, false);
      } catch (error) {
        console.error('[realtime-chart] copy-url-error', error);
        this.setFootLog('复制 URL 失败', true);
      }
    },
    drillExtreme(side) {
      const bar = this.contextMenu?.bar;
      this.contextMenu = null;
      if (!bar || this.drilling) return;
      this.drilling = true;
      this.setFootLog(`正在服务器端递归钻取${side === 'high' ? '最高' : '最低'}价到 1s…`, false);
      // One RPC: the server recurses coarse -> fine -> 1s internally (each level <= 1000 bars).
      const expression = `r=chart_drill_extreme(symbol='${this.symbol}',start_time=${bar.timestamp},interval='${this.interval}',side='${side}')`;
      const url = `/r=${encodeURIComponent(expression)}`;
      this.log('drill-request', { url });
      fetch(url).then((response) => response.json().then((data) => ({ response, data }))).then(({ response, data }) => {
        if (!response.ok || data.error || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
        this.log('drill-ok', { side, levels: data.path?.length, bar: data.bar, path: data.path });
        const target = {
          timestamp: data.bar.open_time,
          side,
          price: side === 'high' ? data.bar.high : data.bar.low,
          levels: Array.isArray(data.path) ? data.path.length : 0,
        };
        this.drillTarget = target;
        this.focusTarget = 0;
        if (this.interval !== '1s') {
          // Switch the live stream to 1s; openDrillWindow runs once the fresh 1s snapshot arrives.
          this.interval = '1s';
          this.subscribe();
        } else {
          this.openDrillWindow();
        }
      }).catch((error) => {
        console.error('[realtime-chart] drill-error', error);
        this.drillTarget = null;
        this.setFootLog(error.message || String(error), true);
      }).finally(() => {
        this.drilling = false;
      });
    },
    openDrillWindow() {
      const target = this.drillTarget;
      if (!target) return;
      // 1000 1s bars ending 600s after the target second: the target bar is always inside the window.
      const endTime = target.timestamp + 600_000;
      const expression = `chart_history(p,symbol='${this.symbol}',interval='1s',end_time=${endTime},limit=1000)`;
      const url = `/r=${encodeURIComponent(expression)}`;
      this.log('drill-window-request', { url, target: target.timestamp });
      fetch(url).then((response) => response.json().then((data) => ({ response, data }))).then(({ response, data }) => {
        if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
        const history = (data.bars || [])
          .map((bar) => this.toChartBar(bar))
          .filter((bar) => Number.isFinite(bar.timestamp))
          .sort((a, b) => a.timestamp - b.timestamp);
        // Replace (like focusOnTime): no live snapshot tail, so right-edge paging walks newer 1s bars up to live.
        this.bars = history;
        this.chartGeneration += 1;
        this.pendingHistory = null;
        this.requestedHistory = new Set();
        this.historyExhausted = false;
        this.liveTail = false;
        // Must be set BEFORE applyNewData: its edge paging callbacks fire synchronously inside the call.
        this.locating = true;
        this.chart.applyNewData(this.bars);
        this.updateAxisMode();
        this.locateAfterReady(target.timestamp);
        this.drillTarget = null;
        this.focusTarget = 0;
        this.setFootLog(`已定位到 1s ${target.side === 'high' ? '最高' : '最低'}价 ${this.formatTickerPrice(target.price)} · ${this.formatTime(target.timestamp)}（服务端钻取 ${target.levels} 层，可手动右键复制分享链接）`, false);
      }).catch((error) => {
        console.error('[realtime-chart] drill-window-error', error);
        this.drillTarget = null;
        this.setFootLog('1s 定位窗口加载失败: ' + (error.message || error), true);
      });
    },
    toggleFullscreen() { document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen(); },
  },
};
</script>