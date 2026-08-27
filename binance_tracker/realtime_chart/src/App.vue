<template>
  <main class="terminal">
    <header class="toolbar">
      <div class="brand"><span class="signal"></span><span>BINANCE / LIVE KLINES</span></div>
      <div class="quote"><strong>{{ symbol }}</strong><span>{{ lastPrice }}</span><span :class="changeClass">{{ changeText }}</span></div>
      <div class="controls">
        <label>SYMBOL <select v-model="symbol" @change="subscribe"><option v-for="item in symbols" :key="item" :value="item">{{ item }}</option></select></label>
        <label>INTERVAL <select v-model="interval" @change="subscribe"><option v-for="item in intervals" :key="item" :value="item">{{ item }}</option></select></label>
        <button class="icon-button" title="切换全屏" @click="toggleFullscreen">⛶</button>
      </div>
    </header>
    <div class="status"><i :class="{ online: connected }"></i>{{ connected ? 'LIVE' : 'CONNECTING' }}</div>
    <div class="chart-wrap"><div ref="chart" class="chart"></div><div class="scale-controls"><button title="Auto: 让 K 线和指标尽量铺满屏幕" :class="{ active: autoScale }" @click="toggleAutoScale">A</button><button title="锁定价格尺度" :class="{ active: scaleLocked }" @click="toggleScaleLock">L</button></div></div>
    <footer><span>实时行情</span><span>{{ barCount }} bars</span><span>{{ lastTime }}</span><span class="hint">WebSocket stream</span></footer>
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
      autoScale: true, scaleLocked: false, pricePrecision: 8,
      symbols: window.__SYMBOLS__ || ['BTCUSDT'],
      intervals: window.__INTERVALS__ || ['1m'],
    };
  },
  computed: {
    barCount() { return this.bars.length; },
    lastBar() { return this.bars[this.bars.length - 1] || {}; },
    lastPrice() { return this.lastBar.close == null ? '--' : Number(this.lastBar.close).toLocaleString(undefined, { maximumFractionDigits: 8 }); },
    lastTime() { return this.lastBar.timestamp ? new Date(this.lastBar.timestamp).toLocaleString() : '--'; },
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
    this.chart.setStyles({ grid: { horizontal: { color: '#263238' }, vertical: { color: '#263238' } }, candle: { type: 'candle_solid', bar: { upColor: '#35c99a', downColor: '#ef6b73', noChangeColor: '#9aa6ab' } } });
    this.chart.createIndicator({ name: 'BOLL', calcParams: [21, 3] }, false, { id: 'candle_pane' });
    this.chart.createIndicator('VOL');
    this.updateAxisMode();
    this.connect();
  },
  beforeUnmount() { clearTimeout(this.reconnectTimer); this.socket?.close(); dispose(this.$refs.chart); },
  methods: {
    log(event, details) { console.info(`[realtime-chart] ${event}`, details || ''); },
    toChartBar(bar) { return { timestamp: bar.open_time, open: bar.open, high: bar.high, low: bar.low, close: bar.close, volume: bar.volume }; },
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
      this.socket = new WebSocket(`${scheme}//${location.host}/chart-ws?${query}`);
      this.socket.onopen = () => { this.connected = true; this.log('ws-open'); this.subscribe(); };
      this.socket.onclose = (event) => { this.connected = false; this.log('ws-close', event); this.reconnectTimer = setTimeout(() => this.connect(), 1000); };
      this.socket.onerror = (event) => { this.connected = false; console.error('[realtime-chart] ws-error', event); };
      this.socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        this.log('ws-message', { type: message.type, symbol: message.symbol, interval: message.interval, bars: message.bars?.length });
        if (message.type === 'snapshot') {
          this.symbol = message.symbol; this.interval = message.interval;
          this.pricePrecision = Number.isInteger(message.price_precision) ? message.price_precision : 8;
          this.bars = message.bars.map((bar) => this.toChartBar(bar));
          this.chart.applyNewData(this.bars);
          this.updateAxisMode();
        }
      };
    },
    toggleFullscreen() { document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen(); },
  },
};
</script>
