<template>
  <div>
    <h2 class="text-xl font-bold mb-6 flex items-center gap-2">
      <span class="w-1 h-5 bg-gradient-to-b from-neon-blue to-neon-purple rounded-full"></span>
      可视化流程图
    </h2>

    <div class="flex gap-2 mb-5">
      <button
        v-for="view in views"
        :key="view.id"
        @click="activeView = view.id"
        class="tab-btn"
        :class="{ active: activeView === view.id }"
      >
        {{ view.label }}
      </button>
    </div>

    <!-- 函数选择器 -->
    <div v-if="activeView === 'function'" class="flex flex-wrap gap-2 mb-4 max-h-28 overflow-y-auto p-2 bg-deep-card/50 rounded-lg">
      <button
        v-for="func in allFunctions"
        :key="func.full_name"
        @click="selectFunction(func)"
        class="px-3 py-1.5 text-xs rounded-lg border transition-all font-mono"
        :class="selectedFunc?.full_name === func.full_name
          ? 'border-neon-blue text-neon-blue bg-neon-blue/10'
          : 'border-deep-border text-gray-400 hover:border-neon-blue/30 hover:text-white'"
      >
        {{ func.full_name }}
      </button>
    </div>

    <div class="glass-card p-6 overflow-x-auto relative min-h-[400px] flex items-center justify-center">
      <div class="scan-line"></div>
      <div v-if="loading" class="text-gray-500 text-sm">正在生成流程图...</div>
      <div v-else-if="!mermaidSvg" class="text-gray-500 text-sm">选择函数以查看流程图</div>
      <div v-else class="mermaid-wrapper w-full" v-html="mermaidSvg"></div>
    </div>

    <div class="mt-4 text-xs text-gray-500 text-center">
      基于 Mermaid.js 渲染 · 点击节点可跳转对应代码行
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import mermaid from 'mermaid'
import { useAnalysisStore } from '../stores/analysis'

const analysis = useAnalysisStore()

const views = [
  { id: 'module', label: '模块级流程图' },
  { id: 'function', label: '函数级流程图' },
]

const activeView = ref('module')
const selectedFunc = ref(null)
const mermaidSvg = ref('')
const loading = ref(false)

const allFunctions = computed(() => analysis.allFunctions)

const currentSyntax = computed(() => {
  if (activeView.value === 'module') {
    return analysis.data?.flowcharts?.module?.mermaid_syntax || ''
  }
  if (activeView.value === 'function' && selectedFunc.value) {
    return analysis.data?.flowcharts?.functions?.[selectedFunc.value.full_name]?.mermaid_syntax || ''
  }
  return ''
})

async function renderMermaid() {
  if (!currentSyntax.value) {
    mermaidSvg.value = ''
    return
  }
  loading.value = true
  try {
    const id = 'mermaid-' + Date.now()
    const { svg } = await mermaid.render(id, currentSyntax.value)
    mermaidSvg.value = svg
  } catch (e) {
    console.error('Mermaid render error:', e)
    mermaidSvg.value = '<div class="text-red-400 text-sm">流程图渲染失败</div>'
  }
  loading.value = false
}

function selectFunction(func) {
  selectedFunc.value = func
}

watch([activeView, selectedFunc], () => {
  nextTick(renderMermaid)
})

onMounted(() => {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    securityLevel: 'loose',
    themeVariables: {
      primaryColor: '#16161f',
      primaryTextColor: '#e2e8f0',
      primaryBorderColor: '#00d4ff',
      lineColor: '#a855f7',
      secondaryColor: '#1f1f2e',
      tertiaryColor: '#0a0a0f',
      fontFamily: 'Inter, sans-serif',
      fontSize: '13px',
    },
  })

  // 默认选第一个函数
  if (allFunctions.value.length > 0) {
    selectedFunc.value = allFunctions.value[0]
  }

  nextTick(renderMermaid)
})
</script>
