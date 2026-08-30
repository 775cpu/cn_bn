<template>
  <section class="ticker-panel">
    <header class="ticker-panel-head">
      <span class="tsb-label">组内排序</span>
      <button v-for="opt in tickerSortOptions" :key="opt.key" type="button" class="ticker-sort-btn"
              :class="{ active: tickerSortKey === opt.key }" :title="opt.hint" @click="$emit('set-sort', opt.key)">
        {{ opt.label }}<i v-if="tickerSortKey === opt.key">{{ tickerSortDesc ? '▼' : '▲' }}</i>
      </button>
      <span class="ticker-panel-hint">{{ tickers.length }} 个交易对<template v-if="newSymbol"> · 筛选 {{ filteredTickers.length }} 个</template> · 点击行订阅/切换，已订阅为绿色{{ loadingTickers ? ' · 行情加载中…' : tickerAgeText ? ' · ' + tickerAgeText : '' }}</span>
      <button type="button" class="ticker-panel-close" title="关闭" @click="$emit('close-panel')">×</button>
    </header>
    <div class="ticker-grid">
      <template v-for="group in groupedTickers" :key="group.quote">
        <div class="ticker-group-head">{{ group.quote }}<span class="tgh-count">{{ group.items.length }}</span></div>
        <button v-for="item in group.shown" :key="item.symbol" type="button" class="ticker-cell"
                :class="{ subscribed: symbols.includes(item.symbol) }" :title="cellTitle(item)" @click="$emit('pick-ticker', item)">
          <span class="tc-symbol">{{ item.symbol }}</span>
          <span class="tc-price">{{ formatTickerPrice(item.lastPrice) }}</span>
          <span class="tc-pct" :class="item.priceChangePercent >= 0 ? 'up' : 'down'">{{ formatPct(item.priceChangePercent) }}</span>
        </button>
      </template>
      <div v-if="newSymbol.trim() && !groupedTickers.length" class="ticker-empty">
        「{{ newSymbol.trim() }}」无匹配交易对 —— 检查拼写；已下架/未上市/非现货的币不会出现在列表中
      </div>
    </div>
    <footer v-if="tickerHiddenTotal > 0" class="ticker-panel-foot">部分组别仅显示涨跌幅最活跃的前 {{ tickerGroupCap }} 个（{{ tickerHiddenTotal }} 个已折叠），在输入框键入 symbol 可精确筛选</footer>
  </section>
</template>

<script>
export default {
  name: 'TickerPanel',
  props: {
    newSymbol: { type: String, default: '' },
    loadingTickers: { type: Boolean, default: false },
    tickerAgeText: { type: String, default: '' },
    groupedTickers: { type: Array, default: () => [] },
    tickerHiddenTotal: { type: Number, default: 0 },
    tickerGroupCap: { type: Number, default: 240 },
    symbols: { type: Array, default: () => [] },
    tickers: { type: Array, default: () => [] },
    filteredTickers: { type: Array, default: () => [] },
    tickerSortOptions: { type: Array, default: () => [] },
    tickerSortKey: { type: String, default: 'pct' },
    tickerSortDesc: { type: Boolean, default: true },
    cellTitle: { type: Function, default: () => '' },
    formatTickerPrice: { type: Function, default: () => '--' },
    formatPct: { type: Function, default: () => '--' },
  },
  emits: ['close-panel', 'set-sort', 'pick-ticker'],
};
</script>
