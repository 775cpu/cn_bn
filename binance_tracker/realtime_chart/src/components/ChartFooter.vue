<template>
  <footer>
    <span>{{ barCount }} bars</span>
    <span>延迟 {{ latency }}</span>
    <span>服务器 {{ serverTime }}</span>
    <span>{{ lastTime }}</span>
    <span class="hint foot-log" :class="{ active: footLog, error: footLogError }" :title="footLog">{{ footLog || 'WebSocket stream' }}</span>
  </footer>
</template>

<script>
export default {
  name: 'ChartFooter',
  props: {
    barCount: { type: Number, default: 0 },
    latency: { type: String, default: '--' },
    serverTime: { type: String, default: '--' },
    lastTime: { type: String, default: '--' },
    footLog: { type: String, default: '' },
    footLogError: { type: Boolean, default: false },
  },
};
</script>
