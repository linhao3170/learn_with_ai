<template>
  <div>
    <h2 class="text-xl font-bold mb-6 flex items-center gap-2">
      <span class="w-1 h-5 bg-gradient-to-b from-neon-blue to-neon-purple rounded-full"></span>
      代码与结构
    </h2>

    <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
      <!-- 结构树 -->
      <div class="glass-card p-4 overflow-y-auto lg:col-span-1" style="max-height: 600px;">
        <div class="text-[11px] text-gray-500 uppercase tracking-wider mb-3 px-1">项目结构</div>

        <div v-for="cls in classes" :key="cls.name" class="mb-2">
          <div
            class="tree-item font-medium"
            :class="{ 'text-sky-400': true }"
            @click="toggleClass(cls.name)"
          >
            <svg
              width="10" height="10" viewBox="0 0 24 24" fill="none"
              stroke="#64748b" stroke-width="2.5"
              class="transition-transform duration-150 flex-shrink-0"
              :class="{ 'rotate-90': expandedClasses[cls.name] }"
            >
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="1.5">
              <rect x="4" y="3" width="16" height="18" rx="2"></rect>
            </svg>
            <span class="truncate">{{ cls.name }}</span>
          </div>
          <div v-show="expandedClasses[cls.name]" class="ml-5 mt-1 space-y-0.5 border-l border-deep-border pl-2">
            <div
              v-for="m in cls.methods"
              :key="m.name"
              v-show="!m.name.startsWith('__')"
              class="tree-item"
              :class="{ active: activeLine >= m.start_line && activeLine <= m.end_line }"
              @click="jumpToLine(m.start_line)"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="1.5">
                <polyline points="4 17 10 11 4 5"></polyline>
                <line x1="12" y1="19" x2="20" y2="19"></line>
              </svg>
              <span class="truncate font-mono text-[12px]">{{ m.name }}</span>
              <span class="ml-auto text-[10px] text-gray-600 font-mono flex-shrink-0">{{ m.start_line }}</span>
            </div>
          </div>
        </div>

        <div v-if="topFuncs.length > 0" class="mb-2">
          <div class="tree-item font-medium text-purple-400" @click="showTopFuncs = !showTopFuncs">
            <svg
              width="10" height="10" viewBox="0 0 24 24" fill="none"
              stroke="#64748b" stroke-width="2.5"
              class="transition-transform duration-150 flex-shrink-0"
              :class="{ 'rotate-90': showTopFuncs }"
            >
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a855f7" stroke-width="1.5">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
            </svg>
            <span>顶层函数</span>
          </div>
          <div v-show="showTopFuncs" class="ml-5 mt-1 space-y-0.5 border-l border-deep-border pl-2">
            <div
              v-for="f in topFuncs"
              :key="f.name"
              class="tree-item"
              :class="{ active: activeLine >= f.start_line && activeLine <= f.end_line }"
              @click="jumpToLine(f.start_line)"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="1.5">
                <polyline points="4 17 10 11 4 5"></polyline>
                <line x1="12" y1="19" x2="20" y2="19"></line>
              </svg>
              <span class="truncate font-mono text-[12px]">{{ f.name }}</span>
              <span class="ml-auto text-[10px] text-gray-600 font-mono flex-shrink-0">{{ f.start_line }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 代码视图 -->
      <div class="lg:col-span-3">
        <div class="glass-card overflow-hidden relative" style="max-height: 600px; overflow-y: auto;" ref="codeContainer">
          <!-- 顶栏 -->
          <div class="sticky top-0 z-10 px-4 py-2.5 bg-deep-card/95 backdrop-blur border-b border-deep-border flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="w-3 h-3 rounded-full bg-red-500/60"></div>
              <div class="w-3 h-3 rounded-full bg-yellow-500/60"></div>
              <div class="w-3 h-3 rounded-full bg-green-500/60"></div>
              <span class="ml-3 text-xs text-gray-400 font-mono">{{ fileName }}.py</span>
            </div>
            <span class="text-[10px] text-gray-600 font-mono">{{ sourceLines.length }} 行</span>
          </div>
          <!-- 代码 -->
          <div class="code-block !rounded-none !border-0 py-3">
            <span
              v-for="(line, i) in sourceLines"
              :key="i"
              class="code-line"
              :class="{ highlighted: activeLine === i + 1 }"
              :data-line="i + 1"
              v-html="highlightLine(line, i + 1)"
            ></span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, watch, nextTick } from 'vue'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import { useAnalysisStore } from '../stores/analysis'

hljs.registerLanguage('python', python)

const analysis = useAnalysisStore()
const codeContainer = ref(null)
const expandedClasses = reactive({})
const showTopFuncs = ref(true)

const classes = computed(() => analysis.data?.classes || [])
const topFuncs = computed(() => analysis.data?.functions || [])
const sourceLines = computed(() => analysis.sourceLines)
const fileName = computed(() => analysis.data?.overview?.name || 'code')
const activeLine = computed(() => analysis.highlightedLine)

function toggleClass(name) {
  expandedClasses[name] = !expandedClasses[name]
}

function jumpToLine(line) {
  analysis.jumpToLine(line)
  nextTick(() => {
    if (codeContainer.value) {
      const lineHeight = 21
      codeContainer.value.scrollTop = Math.max(0, (line - 5) * lineHeight)
    }
  })
}

function highlightLine(line, lineNum) {
  if (!line) return '&nbsp;'
  const result = hljs.highlight(line || ' ', { language: 'python', ignoreIllegals: true })
  return result.value
}

// 默认展开第一个类
watch(classes, (newClasses) => {
  if (newClasses.length > 0 && Object.keys(expandedClasses).length === 0) {
    expandedClasses[newClasses[0].name] = true
  }
}, { immediate: true })
</script>
