<template>
  <div>
    <h2 class="text-xl font-bold mb-6 flex items-center gap-2">
      <span class="w-1 h-5 bg-gradient-to-b from-neon-blue to-neon-purple rounded-full"></span>
      分析概览
    </h2>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      <div
        v-for="(stat, i) in stats"
        :key="i"
        class="glass-card p-5 neon-border"
        :style="{ animationDelay: i * 0.1 + 's' }"
      >
        <div class="flex items-center justify-between mb-3">
          <span class="text-xs text-gray-400">{{ stat.label }}</span>
          <div :style="{ color: stat.color }">
            <span v-html="stat.icon" class="w-4 h-4"></span>
          </div>
        </div>
        <div class="stat-number text-2xl mb-1" :style="{ color: stat.color }">
          {{ stat.value }}
        </div>
        <div class="text-[11px] text-gray-500">{{ stat.sub }}</div>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
      <!-- 业务模式分布 -->
      <div class="glass-card p-5">
        <h3 class="text-sm font-semibold mb-4 flex items-center gap-2">
          <span class="w-1.5 h-1.5 rounded-full bg-neon-blue"></span>
          业务模式分布
        </h3>
        <div class="space-y-3">
          <div
            v-for="(count, name) in patternSummary"
            :key="name"
            class="flex items-center gap-3"
          >
            <div class="w-28 text-[11px] text-gray-400 truncate">
              {{ patternNames[name] || name }}
            </div>
            <div class="flex-1 h-2 bg-deep-card rounded-full overflow-hidden">
              <div
                class="h-full rounded-full bg-gradient-to-r from-neon-blue to-neon-purple transition-all duration-700"
                :style="{ width: (count / maxPatternCount * 100) + '%' }"
              ></div>
            </div>
            <div class="w-6 text-right text-[11px] text-gray-500 font-mono">{{ count }}</div>
          </div>
        </div>
      </div>

      <!-- 知识点分类 -->
      <div class="glass-card p-5">
        <h3 class="text-sm font-semibold mb-4 flex items-center gap-2">
          <span class="w-1.5 h-1.5 rounded-full bg-neon-purple"></span>
          知识点分类
        </h3>
        <div class="grid grid-cols-2 gap-2">
          <div
            v-for="(count, cat) in knowledgeCategories"
            :key="cat"
            class="p-3 rounded-lg bg-deep-card border border-deep-border hover:border-neon-purple/30 transition-all"
          >
            <div class="text-lg font-bold text-white">{{ count }}</div>
            <div class="text-[11px] text-gray-500">{{ cat }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 主流程 -->
    <div class="glass-card p-5 mb-8">
      <h3 class="text-sm font-semibold mb-4 flex items-center gap-2">
        <span class="w-1.5 h-1.5 rounded-full bg-neon-green"></span>
        主业务流程
      </h3>
      <div class="flex flex-wrap items-center gap-2">
        <template v-for="(step, i) in mainFlow" :key="i">
          <div class="px-4 py-2 rounded-lg bg-deep-card border border-deep-border text-sm hover:border-neon-blue/40 transition-all group">
            <span class="text-neon-blue font-mono text-xs mr-2">{{ step.step }}</span>
            {{ step.description.replace('实现 ', '').replace('操作：', ' · ') }}
          </div>
          <svg v-if="i < mainFlow.length - 1" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#374151" stroke-width="2" class="flex-shrink-0">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </template>
      </div>
    </div>

    <!-- 模块描述 -->
    <div v-if="overview?.description" class="glass-card p-5">
      <h3 class="text-sm font-semibold mb-3 flex items-center gap-2">
        <span class="w-1.5 h-1.5 rounded-full bg-neon-pink"></span>
        模块说明
      </h3>
      <p class="text-sm text-gray-400 leading-relaxed">{{ overview.description }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAnalysisStore, patternNames } from '../stores/analysis'

const analysis = useAnalysisStore()

const overview = computed(() => analysis.data?.overview)
const patternSummary = computed(() => analysis.data?.pattern_summary || {})
const knowledgeCategories = computed(() => analysis.data?.knowledge_categories || {})
const maxPatternCount = computed(() => analysis.maxPatternCount)
const mainFlow = computed(() => analysis.data?.main_flow || [])

const stats = computed(() => [
  {
    label: '代码行数',
    value: overview.value?.total_lines || 0,
    sub: 'lines of code',
    color: '#00d4ff',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>',
  },
  {
    label: '业务模式',
    value: analysis.data?.patterns?.length || 0,
    sub: Object.keys(patternSummary.value).length + ' 种类别',
    color: '#a855f7',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><path d="M12 2L2 7l10 5 10-5-10-5z"></path><path d="M2 17l10 5 10-5"></path><path d="M2 12l10 5 10-5"></path></svg>',
  },
  {
    label: '知识点',
    value: analysis.data?.knowledge_points?.length || 0,
    sub: Object.keys(knowledgeCategories.value).length + ' 个分类',
    color: '#ec4899',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>',
  },
  {
    label: '调用节点',
    value: Object.keys(analysis.data?.call_graph?.nodes || {}).length,
    sub: (analysis.data?.call_graph?.entry_points?.length || 0) + ' 个入口',
    color: '#22d3ee',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><circle cx="12" cy="12" r="3"></circle><path d="M12 1v6m0 6v6m4.22-13.22l4.24 4.24M1.54 1.54l4.24 4.24M20.46 20.46l-4.24-4.24M1.54 20.46l4.24-4.24"></path></svg>',
  },
])
</script>
