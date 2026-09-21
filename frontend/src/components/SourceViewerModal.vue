<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="source-viewer-overlay" @click.self="close">
        <div class="source-viewer-modal glass-card overflow-hidden flex flex-col">
          <!-- Header -->
          <div class="flex items-center justify-between px-4 py-2.5 bg-deep-card/95 border-b border-deep-border flex-shrink-0">
            <div class="flex items-center gap-2 min-w-0">
              <div class="flex gap-1.5">
                <div class="w-3 h-3 rounded-full bg-red-500/60"></div>
                <div class="w-3 h-3 rounded-full bg-yellow-500/60"></div>
                <div class="w-3 h-3 rounded-full bg-green-500/60"></div>
              </div>
              <span class="ml-2 text-xs text-gray-300 font-mono truncate">{{ displayPath }}</span>
              <span v-if="targetLine" class="text-[10px] px-1.5 py-0.5 rounded bg-neon-blue/15 text-neon-blue font-mono flex-shrink-0">
                L{{ targetLine }}
              </span>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
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
              loading...
            </div>
            <div v-else-if="error" class="flex items-center justify-center h-full text-red-400 text-sm">
              {{ error }}
            </div>
            <div v-else class="code-block !rounded-none !border-0 py-3">
              <span
                v-for="(line, i) in lines"
                :key="i"
                class="code-line"
                :class="{ 
                  highlighted: isHighlighted(i + 1),
                  'in-range': isInRange(i + 1)
                }"
                :data-line="i + 1"
                v-html="formatLine(line, i + 1)"
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

hljs.registerLanguage('python', python)

const props = defineProps({
  visible: Boolean,
  filepath: String,
  line: Number,
  endLine: Number,
  sourceBase: {
    type: String,
    default: '/demo/source'
  },
  hint: String,
})

const emit = defineEmits(['close'])

const codeContainer = ref(null)
const sourceCode = ref('')
const loading = ref(false)
const error = ref('')
const targetLine = ref(null)
const targetEndLine = ref(null)

const lines = computed(() => sourceCode.value ? sourceCode.value.split('\n') : [])
const totalLines = computed(() => lines.value.length)

const displayPath = computed(() => {
  if (!props.filepath) return ''
  // Extract just the filename from absolute paths
  const parts = props.filepath.replace(/\\/g, '/').split('/')
  return parts[parts.length - 1]
})

const fileName = computed(() => displayPath.value)

function isHighlighted(lineNum) {
  if (!targetLine.value) return false
  // If there's a range, highlight the start line specially
  if (targetEndLine.value && targetEndLine.value > targetLine.value) {
    return lineNum === targetLine.value
  }
  return lineNum === targetLine.value
}

function isInRange(lineNum) {
  if (!targetLine.value || !targetEndLine.value) return false
  return lineNum > targetLine.value && lineNum <= targetEndLine.value
}

function formatLine(line, lineNum) {
  if (line === undefined || line === null) return '&nbsp;'
  const result = hljs.highlight(line || ' ', { language: 'python', ignoreIllegals: true })
  return result.value
}

function close() {
  emit('close')
}

// Resolve source URL from filepath
function resolveSourceUrl(filepath) {
  if (!filepath) return null
  // Extract filename from absolute path
  const normalized = filepath.replace(/\\/g, '/')
  const parts = normalized.split('/')
  const filename = parts[parts.length - 1]
  if (!filename) return null
  return `${props.sourceBase}/${filename}`
}

async function loadSource() {
  if (!props.visible || !props.filepath) return
  
  const url = resolveSourceUrl(props.filepath)
  if (!url) {
    error.value = 'Invalid file path'
    return
  }

  loading.value = true
  error.value = ''
  sourceCode.value = ''
  targetLine.value = props.line
  targetEndLine.value = props.endLine

  try {
    const resp = await fetch(url)
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`)
    }
    sourceCode.value = await resp.text()
  } catch (e) {
    error.value = `Cannot load source: ${e.message}`
  } finally {
    loading.value = false
  }

  // Scroll to target line after render
  await nextTick()
  scrollToLine()
}

function scrollToLine() {
  if (!codeContainer.value || !targetLine.value) return
  const lineHeight = 21
  const containerHeight = codeContainer.value.clientHeight
  const targetScroll = Math.max(0, (targetLine.value - 1) * lineHeight - containerHeight / 3)
  codeContainer.value.scrollTop = targetScroll
}

watch(() => [props.visible, props.filepath, props.line, props.endLine], () => {
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
