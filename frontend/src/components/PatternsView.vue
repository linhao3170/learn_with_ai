<template>
  <div>
    <h2 class="text-xl font-bold mb-6 flex items-center gap-2">
      <span class="w-1 h-5 bg-gradient-to-b from-neon-blue to-neon-purple rounded-full"></span>
      业务模式识别
      <span class="text-sm font-normal text-gray-500 ml-2">
        共 {{ patterns.length }} 个匹配
      </span>
    </h2>

    <div class="space-y-3">
      <div
        v-for="(pattern, i) in patterns"
        :key="i"
        class="glass-card p-4 cursor-pointer"
        @click="togglePattern(i)"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3 flex-wrap">
            <span
              class="pattern-tag"
              :style="{
                background: getColor(pattern.category) + '15',
                color: getColor(pattern.category),
                border: '1px solid ' + getColor(pattern.category) + '30',
              }"
            >
              <span
                class="w-1.5 h-1.5 rounded-full"
                :style="{ background: getColor(pattern.category) }"
              ></span>
              {{ pattern.pattern_name }}
              <span v-if="pattern.sub_type" class="opacity-70 ml-1">{{ pattern.sub_type }}</span>
            </span>
            <span class="text-xs text-gray-400">
              {{ pattern.target_type === 'class' ? '类' : '函数' }}
              <code class="text-neon-blue mx-1 font-mono">{{ pattern.target_name }}</code>
              行 {{ pattern.target_line }}
            </span>
          </div>
          <div class="flex items-center gap-3">
            <div class="flex items-center gap-1">
              <span
                v-for="s in 5"
                :key="s"
                class="w-1.5 h-4 rounded-sm transition-all"
                :style="{ background: s <= Math.round(pattern.score * 5) ? getColor(pattern.category) : '#1f1f2e' }"
              ></span>
            </div>
            <span class="text-xs font-mono text-gray-500 w-12 text-right">
              {{ (pattern.score * 100).toFixed(0) }}%
            </span>
            <svg
              width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="#6b7280" stroke-width="2"
              class="transition-transform duration-200 flex-shrink-0"
              :class="{ 'rotate-180': expanded === i }"
            >
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </div>
        </div>

        <div
          v-show="expanded === i"
          class="mt-4 pt-4 border-t border-deep-border"
        >
          <p class="text-sm text-gray-300 mb-3">{{ pattern.description }}</p>
          <div class="text-[11px] text-gray-500 uppercase tracking-wider mb-2">证据</div>
          <div class="space-y-1.5">
            <div
              v-for="(ev, ei) in pattern.evidence"
              :key="ei"
              class="flex items-center gap-2 text-xs"
            >
              <span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-deep-card text-gray-400 border border-deep-border">
                L{{ ev.line_start }}
              </span>
              <span class="text-gray-400">{{ ev.description }}</span>
              <span class="text-[10px] text-gray-600">({{ ev.evidence_type }})</span>
            </div>
          </div>
          <div class="mt-3 flex items-center gap-2">
            <span class="text-[11px] text-gray-500">置信度：</span>
            <span
              class="text-[11px] font-medium px-2 py-0.5 rounded"
              :style="{
                background: pattern.confidence === 'high' ? 'rgba(34, 197, 94, 0.15)' :
                           pattern.confidence === 'medium' ? 'rgba(251, 191, 36, 0.15)' :
                           'rgba(107, 114, 128, 0.15)',
                color: pattern.confidence === 'high' ? '#4ade80' :
                       pattern.confidence === 'medium' ? '#fbbf24' : '#9ca3af',
              }"
            >
              {{ confidenceLabel(pattern.confidence) }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAnalysisStore, patternColors } from '../stores/analysis'

const analysis = useAnalysisStore()
const expanded = ref(null)

const patterns = computed(() => analysis.data?.patterns || [])

function togglePattern(i) {
  expanded.value = expanded.value === i ? null : i
}

function getColor(category) {
  return patternColors[category] || '#00d4ff'
}

function confidenceLabel(c) {
  return { high: '高置信度', medium: '中置信度', low: '低置信度' }[c] || c
}
</script>
