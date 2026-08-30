<template>
  <header class="toolbar">
    <div class="brand"></div>
    <div class="quote">
      <strong>{{ symbol }}</strong>
      <span>{{ lastPrice }}</span>
      <span :class="changeClass">{{ changeText }}</span>
    </div>
    <div class="controls">
      <label class="symbol-add">
        <input
          :value="newSymbol"
          :disabled="addingSymbol"
          placeholder="订阅 SYMBOL"
          spellcheck="false"
          autocomplete="off"
          @input="$emit('update:newSymbol', $event.target.value)"
          @keydown.enter="$emit('add-symbol')"
          @keydown.esc="$emit('close-panels')"
          @focus="$emit('open-ticker-panel')"
        />
        <button class="add-button" type="button" :disabled="addingSymbol || !newSymbol" title="订阅新 symbol：自动订阅 WS 并校准 K 线" @click="$emit('add-symbol')">{{ addingSymbol ? '…' : '＋' }}</button>
      </label>
      <label class="symbol-picker">SYMBOL
        <div class="symbol-menu">
          <button type="button" class="symbol-menu-button" :title="'已订阅 ' + symbols.length + ' 个：点击切换，× 取消订阅'" @click.stop="$emit('toggle-symbol-menu')">
            <span class="symbol-menu-current">{{ symbol || '—' }}</span><span class="caret">▾</span>
          </button>
          <div v-if="showSymbolMenu" class="symbol-menu-panel">
            <div v-for="item in symbols" :key="item" class="symbol-menu-row" :class="{ active: item === symbol }">
              <span class="symbol-menu-name" @click="$emit('switch-symbol', item)">{{ item }}</span>
              <button type="button" class="symbol-remove" :title="'取消订阅 ' + item" @click.stop="$emit('remove-symbol', item)">×</button>
            </div>
            <div v-if="!symbols.length" class="symbol-menu-empty">暂无订阅，在左侧输入框添加</div>
          </div>
        </div>
      </label>
      <label>INTERVAL
        <select :value="interval" @change="$emit('interval-change', $event.target.value)">
          <option v-for="item in intervals" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="icon-button" title="切换全屏" @click="$emit('toggle-fullscreen')">⛶</button>
    </div>
  </header>
</template>

<script>
export default {
  name: 'ChartHeader',
  props: {
    symbol: { type: String, default: '' },
    lastPrice: { type: String, default: '--' },
    changeText: { type: String, default: '--' },
    changeClass: { type: String, default: '' },
    newSymbol: { type: String, default: '' },
    addingSymbol: { type: Boolean, default: false },
    symbols: { type: Array, default: () => [] },
    interval: { type: String, default: '1m' },
    intervals: { type: Array, default: () => ['1m'] },
    showSymbolMenu: { type: Boolean, default: false },
  },
  emits: [
    'update:newSymbol',
    'add-symbol',
    'open-ticker-panel',
    'close-panels',
    'toggle-symbol-menu',
    'switch-symbol',
    'remove-symbol',
    'interval-change',
    'toggle-fullscreen',
  ],
};
</script>
