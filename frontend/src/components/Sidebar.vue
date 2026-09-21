<template>
  <aside class="w-64 fixed left-0 top-14 bottom-0 border-r border-deep-border/50 bg-deep-surface/30 backdrop-blur-sm overflow-y-auto p-4 z-40">
    <!-- 模块概览卡片 -->
    <div class="mb-6">
      <div class="text-[10px] text-gray-500 font-mono uppercase tracking-widest mb-3 px-2">模块概览</div>
      <div class="glass-card p-4">
        <div class="text-sm font-semibold text-white mb-1 truncate" :title="overview?.name">
          {{ overview?.name || '未命名' }}
        </div>
        <div class="text-[11px] text-gray-500 mb-3 line-clamp-2">
          {{ overview?.primary_purpose || '-' }}
        </div>
        <div class="grid grid-cols-2 gap-2 text-center">
          <div class="bg-deep-card rounded p-2">
            <div class="stat-number text-sm text-neon-blue">{{ overview?.total_functions || 0 }}</div>
            <div class="text-[10px] text-gray-500">函数</div>
          </div>
          <div class="bg-deep-card rounded p-2">
            <div class="stat-number text-sm text-neon-purple">{{ overview?.total_classes || 0 }}</div>
            <div class="text-[10px] text-gray-500">类</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 导航 -->
    <div class="mb-6">
      <div class="text-[10px] text-gray-500 font-mono uppercase tracking-widest mb-3 px-2">导航</div>
      <div class="space-y-1">
        <div
          v-for="item in navItems"
          :key="item.id"
          class="sidebar-item"
          :class="{ active: activeTab === item.id }"
          @click="$emit('navigate', item.id)"
        >
          <span v-html="item.icon" class="w-4 h-4 flex-shrink-0"></span>
          <span class="flex-1">{{ item.label }}</span>
          <span v-if="item.count" class="text-[10px] text-gray-500 font-mono">{{ item.count }}</span>
        </div>
      </div>
    </div>

    <!-- 难度评估 -->
    <div>
      <div class="text-[10px] text-gray-500 font-mono uppercase tracking-widest mb-3 px-2">难度评估</div>
      <div class="glass-card p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-gray-400">综合难度</span>
          <span class="text-sm font-bold text-white font-mono">{{ difficultyScore }}/5</span>
        </div>
        <div class="h-1.5 rounded-full bg-deep-card overflow-hidden progress-bar">
          <div
            class="h-full rounded-full difficulty-gradient transition-all duration-1000 ease-out"
            :style="{ width: (difficultyScore / 5 * 100) + '%' }"
          ></div>
        </div>
        <div class="text-[11px] text-gray-500 mt-2 capitalize">{{ complexityLevel }}</div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useAnalysisStore } from '../stores/analysis'

const props = defineProps({
  activeTab: String,
})

defineEmits(['navigate'])

const analysis = useAnalysisStore()

const overview = computed(() => analysis.data?.overview)
const difficultyScore = computed(() => analysis.data?.difficulty_score || 0)
const complexityLevel = computed(() => {
  const map = { beginner: '入门', intermediate: '中级', advanced: '高级' }
  return map[analysis.data?.overview?.complexity_level] || analysis.data?.overview?.complexity_level || '-'
})

const navItems = computed(() => [
  {
    id: 'overview',
    label: '分析概览',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14"><rect x="3" y="3" width="7" height="7" rx="1"></rect><rect x="14" y="3" width="7" height="7" rx="1"></rect><rect x="14" y="14" width="7" height="7" rx="1"></rect><rect x="3" y="14" width="7" height="7" rx="1"></rect></svg>',
  },
  {
    id: 'patterns',
    label: '业务模式',
    count: analysis.data?.patterns?.length || 0,
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14"><path d="M12 2L2 7l10 5 10-5-10-5z"></path><path d="M2 17l10 5 10-5"></path><path d="M2 12l10 5 10-5"></path></svg>',
  },
  {
    id: 'flowchart',
    label: '流程图',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14"><rect x="8" y="3" width="8" height="5" rx="1"></rect><rect x="8" y="16" width="8" height="5" rx="1"></rect><path d="M12 8v4M12 12v4"></path><circle cx="5" cy="12" r="2"></circle><circle cx="19" cy="12" r="2"></circle></svg>',
  },
  {
    id: 'code',
    label: '代码结构',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>',
  },
  {
    id: 'knowledge',
    label: '知识点',
    count: analysis.data?.knowledge_points?.length || 0,
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>',
  },
  {
    id: 'quiz',
    label: '闯关测试',
    count: analysis.data?.quiz?.length || 0,
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14"><path d="M12 2L15 8l7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1 3-6z"></path></svg>',
  },
])
</script>
