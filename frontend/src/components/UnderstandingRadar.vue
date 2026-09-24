<template>
  <!-- 手写 SVG 雷达图（无第三方图表库，沿用仓库既有范式）。维度数量由题目数量决定。 -->
  <div class="flex items-center justify-center gap-8 flex-wrap">
    <svg :viewBox="viewBox" width="200" height="200" class="flex-shrink-0">
      <defs>
        <linearGradient id="radar-fill-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#06b6d4;stop-opacity:0.35" />
          <stop offset="100%" style="stop-color:#a855f7;stop-opacity:0.35" />
        </linearGradient>
      </defs>

      <!-- 背景网格 -->
      <g v-for="i in 5" :key="'ring-' + i">
        <polygon :points="ringPoints(i / 5)" fill="none" stroke="#1e293b" stroke-width="1" />
      </g>

      <!-- 轴线 -->
      <g v-for="(dim, i) in dims" :key="'axis-' + i">
        <line
          :x1="cx" :y1="cy"
          :x2="cx + radius * Math.cos(angle(i))"
          :y2="cy + radius * Math.sin(angle(i))"
          stroke="#334155" stroke-width="1"
        />
      </g>

      <!-- 数据多边形 -->
      <polygon :points="dataPoints" fill="url(#radar-fill-grad)" stroke="#a855f7" stroke-width="2" />

      <!-- 数据点 -->
      <circle
        v-for="(dim, i) in dims"
        :key="'dot-' + i"
        :cx="cx + radius * scoreAt(i) * Math.cos(angle(i))"
        :cy="cy + radius * scoreAt(i) * Math.sin(angle(i))"
        r="4" fill="#fff" stroke="#a855f7" stroke-width="2"
      />

      <!-- 维度标签 -->
      <text
        v-for="(dim, i) in dims"
        :key="'label-' + i"
        :x="cx + (radius + 22) * Math.cos(angle(i))"
        :y="cy + (radius + 22) * Math.sin(angle(i))"
        text-anchor="middle" dominant-baseline="middle" fill="#94a3b8" font-size="11" font-weight="500"
      >{{ dim.label }}</text>
    </svg>

    <div class="space-y-2.5 min-w-[160px]">
      <div v-for="(dim, i) in dims" :key="'dim-' + i" class="flex items-center gap-3">
        <div class="w-2 h-2 rounded-full" :style="{ background: dim.color }"></div>
        <div class="text-xs text-gray-400 w-20 truncate" :title="dim.label">{{ dim.label }}</div>
        <div class="flex-1 h-1.5 bg-deep-border rounded-full overflow-hidden">
          <div class="h-full rounded-full transition-all duration-700 ease-out" :style="{ width: scoreAt(i) * 100 + '%', background: dim.color }"></div>
        </div>
        <div class="text-xs font-mono font-bold" :style="{ color: dim.color }">{{ Math.round(scoreAt(i) * 100) }}%</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  /** [{ label, color }] */
  dims: {
    type: Array,
    default: () => [],
  },
  /** [0..1]，与 dims 一一对应；null 表示未判分 */
  scores: {
    type: Array,
    default: () => [],
  },
})

const cx = 110
const cy = 110
const radius = 70
const size = 220
const viewBox = `0 0 ${size} ${size}`

// 从顶部开始顺时针排列
function angle(i) {
  const n = props.dims.length || 1
  return (-Math.PI / 2) + (2 * Math.PI * i / n)
}

// 未判分的维度画成 0，避免伪造把握度
function scoreAt(i) {
  const s = props.scores[i]
  return Number.isFinite(s) ? Math.max(0, Math.min(1, s)) : 0
}

const dataPoints = computed(() =>
  props.dims.map((_, i) => {
    const r = radius * scoreAt(i)
    return `${cx + r * Math.cos(angle(i))},${cy + r * Math.sin(angle(i))}`
  }).join(' '),
)

function ringPoints(ratio) {
  return props.dims.map((_, i) => {
    const r = radius * ratio
    return `${cx + r * Math.cos(angle(i))},${cy + r * Math.sin(angle(i))}`
  }).join(' ')
}
</script>
