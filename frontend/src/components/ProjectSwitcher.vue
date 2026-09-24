<template>
  <div class="mb-6">
    <!-- P0-01/P0-03：项目切换器。在线时列表来自 GET /api/projects，离线时是静态 demo 列表。 -->
    <div class="flex flex-wrap items-center gap-3 mb-3">
      <div class="flex items-center gap-2">
        <span class="text-xs text-gray-500">项目</span>
        <div class="relative">
          <select
            :value="modelValue"
            :disabled="loading"
            data-test="project-select"
            @change="$emit('update:modelValue', $event.target.value)"
            class="appearance-none bg-deep-card/80 border border-deep-border rounded-lg pl-3 pr-8 py-1.5 text-sm text-white
                   focus:outline-none focus:border-neon-blue/50 transition-colors cursor-pointer disabled:opacity-50"
          >
            <option v-if="!projects.length" :value="modelValue">{{ modelValue || '加载中…' }}</option>
            <option v-for="p in projects" :key="p.project_id" :value="p.project_id">
              {{ p.project_name || p.project_id }}{{ p.project_name && p.project_name !== p.project_id ? ' (' + p.project_id + ')' : '' }}
            </option>
          </select>
          <svg class="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-gray-500" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>
      </div>

      <span
        class="text-[10px] px-2 py-0.5 rounded-full font-mono border"
        :class="mode === 'api'
          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
          : 'bg-amber-500/10 text-amber-400 border-amber-500/30'"
      >
        {{ mode === 'api' ? '在线 API 模式' : '离线快照模式' }}
      </span>

      <button
        v-if="mode === 'offline'"
        @click="$emit('refresh')"
        class="text-[11px] px-2.5 py-1 rounded-lg border border-deep-border text-gray-400 hover:text-white hover:border-neon-blue/40 transition-colors"
      >
        重试连接后端
      </button>

      <span v-if="projectId" class="text-[10px] text-gray-600 font-mono hidden sm:inline">
        链接：?project={{ projectId }}
      </span>
    </div>

    <!-- P0-13：后端不可用时必须如实告知，不能假装判题可用 -->
    <div
      v-if="mode === 'offline'"
      data-test="offline-banner"
      class="p-3 rounded-xl bg-amber-500/5 border border-amber-500/30 flex items-start gap-3"
    >
      <span class="text-lg leading-none mt-0.5">⚠️</span>
      <div class="text-xs leading-relaxed">
        <div class="font-bold text-amber-400 mb-0.5">离线演示模式：判题与讲解不可用</div>
        <div class="text-amber-400/70">
          未检测到后端 API，当前显示的是静态快照内容。你仍然可以浏览题目与深度分析，
          但提交答案不会被判分，最终成绩页会标记为「未判分」。
          <span v-if="errorDetail" class="text-amber-400/50 font-mono">（{{ errorDetail }}）</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  /** [{ project_id, project_name }] */
  projects: {
    type: Array,
    default: () => [],
  },
  modelValue: {
    type: String,
    default: '',
  },
  mode: {
    type: String,
    default: 'offline',
  },
  loading: Boolean,
  errorDetail: {
    type: String,
    default: '',
  },
  projectId: {
    type: String,
    default: '',
  },
})

defineEmits(['update:modelValue', 'refresh'])
</script>
