import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// 业务模式显示名称映射
export const patternNames = {
  crud: 'CRUD 数据操作',
  data_validation: '数据验证',
  error_handling: '异常处理',
  file_operation: '文件操作',
  data_persistence: '数据持久化',
  statistical_calculation: '统计计算',
  batch_processing: '批量处理',
}

// 模式分类颜色
export const patternColors = {
  data_operation: '#00d4ff',
  validation: '#f59e0b',
  robustness: '#ef4444',
  io: '#22c55e',
  algorithm: '#a855f7',
}

// 知识点分类颜色
export const categoryColors = {
  '基础语法': '#60a5fa',
  '进阶语法': '#a855f7',
  '数据验证': '#f59e0b',
  '设计模式': '#ec4899',
  'IO与持久化': '#22c55e',
  '算法': '#00d4ff',
}

// 关卡颜色
export const levelColors = {
  1: '#4ade80',
  2: '#fbbf24',
  3: '#f87171',
}

export const useAnalysisStore = defineStore('analysis', () => {
  const data = ref(null)
  const sourceCode = ref('')
  const sourceLines = computed(() => sourceCode.value ? sourceCode.value.split('\n') : [])
  const activeTab = ref('overview')
  const highlightedLine = ref(null)

  const allFunctions = computed(() => {
    if (!data.value) return []
    const funcs = []
    for (const cls of data.value.classes || []) {
      for (const m of cls.methods || []) {
        if (!m.name.startsWith('__')) {
          funcs.push({
            name: m.name,
            class_name: cls.name,
            full_name: `${cls.name}.${m.name}`,
            start_line: m.start_line,
            end_line: m.end_line,
          })
        }
      }
    }
    for (const f of data.value.functions || []) {
      funcs.push({
        name: f.name,
        class_name: null,
        full_name: f.name,
        start_line: f.start_line,
        end_line: f.end_line,
      })
    }
    return funcs
  })

  const maxPatternCount = computed(() => {
    if (!data.value?.pattern_summary) return 1
    return Math.max(...Object.values(data.value.pattern_summary), 1)
  })

  const knowledgeByCategory = computed(() => {
    if (!data.value?.knowledge_points) return {}
    const map = {}
    for (const kp of data.value.knowledge_points) {
      if (!map[kp.category]) map[kp.category] = []
      map[kp.category].push(kp)
    }
    return map
  })

  function setAnalysis(result, code) {
    data.value = result
    sourceCode.value = code
  }

  function reset() {
    data.value = null
    sourceCode.value = ''
    activeTab.value = 'overview'
  }

  function jumpToLine(line) {
    highlightedLine.value = line
    setTimeout(() => {
      highlightedLine.value = null
    }, 2000)
  }

  return {
    data,
    sourceCode,
    sourceLines,
    activeTab,
    highlightedLine,
    allFunctions,
    maxPatternCount,
    knowledgeByCategory,
    setAnalysis,
    reset,
    jumpToLine,
  }
})
