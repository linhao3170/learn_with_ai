<template>
  <!--
    P0-09/P0-11：第 4 关的"关键实现"证据面板。
    以前这里用分析结果**拼**过一段示意代码（假的 raise ValueError(...)），现在直接按契约给出的
    相对路径 + start_line/end_line 去取**真实源码**；取不到就如实说明，不再编造代码。
  -->
  <div class="mb-6 space-y-4">
    <div v-if="!implementation" class="p-4 rounded-xl bg-deep-card/50 border border-deep-border text-sm text-gray-400">
      本项目未提供关键实现数据，本关不展示代码证据。
    </div>

    <template v-else>
      <!-- 代码片段 -->
      <div class="rounded-xl overflow-hidden border border-deep-border">
        <div class="flex items-center justify-between px-4 py-2.5 bg-deep-card/80 border-b border-deep-border">
          <div class="flex items-center gap-2 min-w-0">
            <div class="flex gap-1.5 flex-shrink-0">
              <span class="w-3 h-3 rounded-full bg-red-500/60"></span>
              <span class="w-3 h-3 rounded-full bg-yellow-500/60"></span>
              <span class="w-3 h-3 rounded-full bg-green-500/60"></span>
            </div>
            <span class="text-xs text-gray-400 font-mono ml-2 truncate" :title="implementation.filepath">
              {{ implementation.filepath }}
            </span>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <span class="text-[10px] text-gray-500 font-mono">L{{ implementation.start_line }}-{{ implementation.end_line }}</span>
            <button
              @click="$emit('open-source', implementation.filepath, implementation.start_line, implementation.end_line)"
              class="text-[10px] px-2 py-0.5 rounded border border-deep-border text-gray-400 hover:text-neon-blue hover:border-neon-blue/40 transition-colors"
            >
              在证据查看器中打开
            </button>
          </div>
        </div>
        <div class="p-4 bg-deep-card/40 overflow-x-auto max-h-72 overflow-y-auto">
          <pre v-if="codeLoading" class="text-xs text-gray-500 font-mono">加载源码中…</pre>
          <pre v-else-if="codeError" class="text-xs text-amber-400/80 font-mono whitespace-pre-wrap">{{ codeError }}</pre>
          <pre v-else class="text-xs text-gray-300 leading-relaxed font-mono"><code><template v-for="line in codeLines" :key="line.number"><span class="inline-block w-10 text-right mr-3 text-gray-600 select-none">{{ line.number }}</span><span v-html="formatLine(line.text)"></span>
</template></code></pre>
        </div>
      </div>

      <!-- 分析维度 -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div class="p-3 rounded-lg bg-deep-card/50 border border-deep-border text-center">
          <div class="text-lg font-bold text-neon-pink font-mono">{{ implementation.complexity ?? '?' }}</div>
          <div class="text-[10px] text-gray-500 mt-0.5">圈复杂度</div>
        </div>
        <div class="p-3 rounded-lg bg-deep-card/50 border border-deep-border text-center">
          <div class="text-lg font-bold text-amber-400 font-mono">{{ (implementation.state_writes || []).length }}</div>
          <div class="text-[10px] text-gray-500 mt-0.5">状态写入</div>
        </div>
        <div class="p-3 rounded-lg bg-deep-card/50 border border-deep-border text-center">
          <div class="text-lg font-bold text-green-400 font-mono">{{ (implementation.validation_checks || []).length }}</div>
          <div class="text-[10px] text-gray-500 mt-0.5">前置校验</div>
        </div>
        <div class="p-3 rounded-lg bg-deep-card/50 border border-deep-border text-center">
          <div class="text-lg font-bold text-purple-400 font-mono">{{ (implementation.error_handling || []).length }}</div>
          <div class="text-[10px] text-gray-500 mt-0.5">异常抛出</div>
        </div>
      </div>

      <!-- 设计特征 -->
      <div class="p-3 rounded-lg bg-pink-500/5 border border-pink-500/20">
        <div class="text-xs font-medium text-pink-400 mb-1.5">🧩 设计特征</div>
        <div v-if="implementation.design_characteristics?.length" class="space-y-1.5">
          <div v-for="char in implementation.design_characteristics.slice(0, 3)" :key="char.label" class="text-xs leading-relaxed">
            <span :class="char.confidence === 'verified' ? 'text-emerald-400' : 'text-amber-400'">{{ char.label }}</span>
            <span class="text-gray-500 text-[10px] ml-1">({{ char.evidence }})</span>
          </div>
        </div>
        <div v-else class="text-xs text-gray-300 leading-relaxed">{{ implementation.design_approach || '暂无设计特征数据' }}</div>
      </div>

      <!-- 为什么它是关键实现 -->
      <div v-if="implementation.importance_reasons?.length" class="p-3 rounded-lg bg-deep-card/50 border border-deep-border">
        <div class="text-xs font-medium text-gray-300 mb-2">为什么这是关键实现？</div>
        <div class="flex flex-wrap gap-1.5">
          <span
            v-for="reason in implementation.importance_reasons"
            :key="reason"
            class="text-[10px] px-2 py-0.5 rounded-full bg-pink-500/10 text-pink-300 border border-pink-500/20"
          >{{ reason }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import { getSource } from '../api/dataSource'

hljs.registerLanguage('python', python)

const props = defineProps({
  /** deep_analysis.key_implementations.implementations[i] */
  implementation: {
    type: Object,
    default: null,
  },
  projectId: {
    type: String,
    default: '',
  },
})

defineEmits(['open-source'])

const codeLines = ref([])
const codeLoading = ref(false)
const codeError = ref('')

function formatLine(text) {
  if (text === undefined || text === null || text === '') return '&nbsp;'
  return hljs.highlight(text, { language: 'python', ignoreIllegals: true }).value
}

async function loadCode() {
  const imp = props.implementation
  if (!imp?.filepath) {
    codeLines.value = []
    return
  }
  codeLoading.value = true
  codeError.value = ''
  codeLines.value = []
  const res = await getSource(props.projectId, imp.filepath, imp.start_line, imp.end_line)
  if (res.ok) {
    // 只显示该实现自身的行区间（窗口里的上下文只用于弹窗浏览）
    codeLines.value = (res.data?.lines || []).filter(
      l => l.number >= (imp.start_line || 1) && l.number <= (imp.end_line || l.number),
    )
  } else {
    codeError.value = `无法加载源码：${res.error || '未知原因'}`
  }
  codeLoading.value = false
}

watch(() => [props.implementation?.filepath, props.implementation?.start_line, props.projectId], loadCode, { immediate: true })
</script>
