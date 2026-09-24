<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="source-viewer-overlay" @click.self="close">
        <div class="source-viewer-modal glass-card overflow-hidden flex flex-col">
          <!-- Header：P0-09 要求显示【完整相对路径 + 行号区间】，不再只显示 basename -->
          <div class="flex items-center justify-between px-4 py-2.5 bg-deep-card/95 border-b border-deep-border flex-shrink-0">
            <div class="flex items-center gap-2 min-w-0">
              <div class="flex gap-1.5 flex-shrink-0">
                <div class="w-3 h-3 rounded-full bg-red-500/60"></div>
                <div class="w-3 h-3 rounded-full bg-yellow-500/60"></div>
                <div class="w-3 h-3 rounded-full bg-green-500/60"></div>
              </div>
              <span class="ml-2 text-xs text-gray-300 font-mono truncate" :title="displayPath">{{ displayPath }}</span>
              <span v-if="rangeLabel" class="text-[10px] px-1.5 py-0.5 rounded bg-neon-blue/15 text-neon-blue font-mono flex-shrink-0">
                {{ rangeLabel }}
              </span>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
              <span
                class="text-[10px] px-1.5 py-0.5 rounded font-mono flex-shrink-0"
                :class="sourceKind === 'api' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400'"
                :title="sourceKind === 'api' ? '数据来自后端 API' : '数据来自静态快照（离线演示模式）'"
              >
                {{ sourceKind === 'api' ? 'API' : '离线快照' }}
              </span>
              <span v-if="totalLines" class="text-[10px] text-gray-600 font-mono">{{ totalLines }} lines</span>
              <button @click="close" class="w-6 h-6 flex items-center justify-center rounded hover:bg-deep-surface text-gray-400 hover:text-white transition-colors">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>
          </div>

          <!-- Code -->
          <div class="code-container overflow-auto flex-1" ref="codeContainer">
            <div v-if="loading" class="flex items-center justify-center h-full text-gray-500 text-sm">
              加载中…
            </div>
            <!-- P0-09：失败必须显式报错，绝不静默渲染空白 -->
            <div v-else-if="error" class="flex flex-col items-center justify-center h-full text-center px-6 gap-2">
              <div class="text-red-400 text-sm font-medium">{{ error }}</div>
              <div class="text-[11px] text-gray-500 font-mono break-all">{{ displayPath }}</div>
              <div v-if="errorDetail" class="text-[11px] text-gray-600 font-mono break-all">{{ errorDetail }}</div>
            </div>
            <div v-else-if="!lines.length" class="flex items-center justify-center h-full text-gray-500 text-sm">
              该文件没有可显示的内容
            </div>
            <div v-else class="code-block !rounded-none !border-0 py-3">
              <span
                v-for="line in lines"
                :key="line.number"
                class="code-line"
                :class="{
                  highlighted: line.number === targetStart,
                  'in-range': isInRange(line.number)
                }"
                :data-line="line.number"
                v-html="formatLine(line.text)"
              ></span>
            </div>
          </div>

          <!-- Footer hint -->
          <div v-if="hint" class="px-4 py-2 bg-deep-card/50 border-t border-deep-border text-[11px] text-gray-500 flex-shrink-0">
            {{ hint }}
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
// P0-09：源码读取统一走双通道数据源（API 优先 / 静态快照回落）
// 原来这里自己拼 `${sourceBase}/${basename}`，只对 5 个手工复制的 demo 文件有效，已删除。
import { getSource } from '../api/dataSource'

hljs.registerLanguage('python', python)

const props = defineProps({
  visible: Boolean,
  /** 项目 id：API 模式需要它来定位项目源码 */
  projectId: {
    type: String,
    default: '',
  },
  /**
   * 项目内相对路径（POSIX `/`）。P0-10/P0-09 之后契约保证是相对路径，
   * 因此这里不再做"取 basename"的降级（那个降级正是 P0-09 的根因）。
   */
  path: {
    type: String,
    default: '',
  },
  /** 1-based 起始行（可选） */
  start: {
    type: Number,
    default: null,
  },
  /** 1-based 结束行（可选，用于区间高亮） */
  end: {
    type: Number,
    default: null,
  },
  hint: String,
  /**
   * 可选：自定义源码加载器（默认 null = 走上面的 /api/projects/{id}/source 通道）。
   *
   * 为什么需要它：业务逻辑分析平台（logic-platform）的证据落在**另一条路由**上
   * （`/api/logic-platform/{analysisId}/source?path=&start=&end=`，它刻意不做 basename 兜底）。
   * 与其复制第二个证据查看器（那会让"全应用只有一个证据弹窗"这条纪律失效），
   * 不如让调用方注入自己的取数函数。
   *
   * 签名：`(path, start, end) => Promise<{ok, data?:{lines,total_lines}, source?, error?}>`
   * 返回结构与 `dataSource.getSource()` 完全一致，所以本组件下面的渲染逻辑一个字都不用改。
   */
  sourceLoader: {
    type: Function,
    default: null,
  },
})

const emit = defineEmits(['close', 'loaded'])

const codeContainer = ref(null)
const loading = ref(false)
const error = ref('')
const errorDetail = ref('')
const lines = ref([])          // [{ number, text }] —— 后端已切好窗口，离线模式前端同样切窗口
const totalLines = ref(0)
const sourceKind = ref('offline')
const targetStart = ref(null)
const targetEnd = ref(null)

const displayPath = computed(() => props.path || '')
const rangeLabel = computed(() => {
  if (!props.start) return ''
  if (props.end && props.end > props.start) return `L${props.start}-${props.end}`
  return `L${props.start}`
})

function isInRange(lineNum) {
  if (!targetStart.value || !targetEnd.value) return false
  return lineNum > targetStart.value && lineNum <= targetEnd.value
}

function formatLine(text) {
  if (text === undefined || text === null || text === '') return '&nbsp;'
  const result = hljs.highlight(text, { language: 'python', ignoreIllegals: true })
  return result.value
}

function close() {
  emit('close')
}

async function loadSource() {
  if (!props.visible || !props.path) return

  loading.value = true
  error.value = ''
  errorDetail.value = ''
  lines.value = []
  totalLines.value = 0
  targetStart.value = props.start || null
  targetEnd.value = props.end || null

  // 有注入的加载器就用它（逻辑平台）；否则走双通道数据源的默认通道（训练页）。
  const res = props.sourceLoader
    ? await props.sourceLoader(props.path, props.start, props.end)
    : await getSource(props.projectId, props.path, props.start, props.end)

  if (!res.ok) {
    if (props.sourceLoader) {
      /*
       * 注入通道（逻辑平台）：后端的中文原文直接当标题。
       * 那条通道**没有静态快照回落**，所以不能用"该项目未提供源码，无法跳转"这句
       * 暗示"代码里没这个文件"的话去盖住真正的 404 detail（文件不存在 / 路径越界）。
       */
      error.value = res.error || '源码读取失败'
      errorDetail.value = ''
    } else {
      error.value = '该项目未提供源码，无法跳转'
      errorDetail.value = res.error || ''
    }
    loading.value = false
    return
  }

  sourceKind.value = res.source || 'offline'
  lines.value = Array.isArray(res.data?.lines) ? res.data.lines : []
  totalLines.value = res.data?.total_lines || lines.value.length
  loading.value = false

  emit('loaded', { path: props.path, start: props.start, end: props.end, total: totalLines.value })

  await nextTick()
  scrollToLine()
}

function scrollToLine() {
  if (!codeContainer.value || !targetStart.value) return
  const idx = lines.value.findIndex(l => l.number === targetStart.value)
  if (idx < 0) return
  const lineHeight = 21
  const containerHeight = codeContainer.value.clientHeight
  codeContainer.value.scrollTop = Math.max(0, idx * lineHeight - containerHeight / 3)
}

watch(() => [props.visible, props.path, props.start, props.end], () => {
  if (props.visible) {
    loadSource()
  }
}, { immediate: true })

// ESC key to close
function onKeydown(e) {
  if (e.key === 'Escape' && props.visible) {
    close()
  }
}

if (typeof window !== 'undefined') {
  window.addEventListener('keydown', onKeydown)
}
</script>

<style scoped>
.source-viewer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.source-viewer-modal {
  width: 100%;
  max-width: 900px;
  height: 80vh;
  max-height: 700px;
  display: flex;
  flex-direction: column;
  animation: modalIn 0.2s ease-out;
}

.code-container {
  flex: 1;
  overflow: auto;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

@keyframes modalIn {
  from {
    opacity: 0;
    transform: scale(0.96) translateY(10px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

:deep(.code-line.highlighted) {
  background: rgba(59, 130, 246, 0.25) !important;
  border-left: 3px solid #3b82f6 !important;
  padding-left: 21px !important;
}

:deep(.code-line.in-range) {
  background: rgba(59, 130, 246, 0.08);
}

/* Override code-line default padding for highlighted state */
:deep(.code-line.highlighted::before) {
  left: -3px !important;
}
</style>
