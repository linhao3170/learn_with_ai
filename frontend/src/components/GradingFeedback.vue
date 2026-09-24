<!--
  注意：本组件的 `<template>` 里**不要**再写说明性 HTML 注释。
  Vue 会把模板里的 HTML 注释编译成 comment vnode，**真的渲染进 DOM**；
  而 scripts/browser_clickthrough.mjs 会用 `document.documentElement.outerHTML` 断言
  "页面里不出现正确答案字段名" —— 一段中文注释就会把这条断言弄成假失败。
  设计说明因此放在下面的 <script setup> 头部（脚本注释不会进入 DOM）。
-->
<template>
  <div v-if="offline" data-test="grading-offline" class="mb-6 p-4 rounded-xl bg-amber-500/5 border border-amber-500/30">
    <div class="font-bold mb-2 text-amber-400">⚠️ 离线演示模式：无法判分</div>
    <div class="text-sm text-gray-400 leading-relaxed">
      后端判题接口不可用，本题不会给出对错结论，也不会计入成绩（标记为「未判分」）。
      你的作答已记录：<span class="text-gray-300 font-mono">{{ selected.join('、') || '（未选择）' }}</span>
    </div>
  </div>

  <div v-else-if="grading" data-test="grading-online" class="mb-6 p-4 rounded-xl" :class="panelClass">
    <div class="font-bold mb-2" :class="titleClass">{{ titleText }}</div>

    <!-- 覆盖清单：先给"你提到了什么"，再给"还差什么" -->
    <div v-if="matchedOptions.length" class="mb-3">
      <div class="text-xs text-gray-500 mb-1.5">你选对的项（后端 matched）：</div>
      <div class="flex flex-wrap gap-1.5">
        <span
          v-for="opt in matchedOptions"
          :key="opt.id"
          class="text-[11px] px-2 py-0.5 rounded bg-green-500/10 text-green-400 border border-green-500/20"
        >
          {{ opt.id }} · {{ opt.text }}
        </span>
      </div>
    </div>

    <div v-if="missingSummary" class="mb-3 text-xs text-amber-400/90">
      {{ missingSummary }}
    </div>
    <div v-if="extraSummary" class="mb-3 text-xs text-red-400/90">
      {{ extraSummary }}
    </div>

    <!-- 讲解只在学生提交之后出现 -->
    <div v-if="grading.explanation" class="text-sm text-gray-400 leading-relaxed whitespace-pre-line">{{ grading.explanation }}</div>

    <div v-if="knowledgePoints.length" class="mt-3 flex flex-wrap gap-1.5">
      <span class="text-[10px] text-gray-500">知识点：</span>
      <span
        v-for="kp in knowledgePoints"
        :key="kp"
        class="text-[10px] px-2 py-0.5 rounded-full bg-neon-blue/10 text-neon-blue/80 border border-neon-blue/20"
      >{{ kp }}</span>
    </div>
  </div>
</template>

<script setup>
/**
 * P0-11 · 提交后的反馈面板（"学生先输出，系统后反馈"，README5 §6.6）
 *   - 在线：显示后端判分结果 result(correct/partial/wrong) + 后端返回的 explanation；
 *   - 离线：不判分、不给结论，只说明"离线演示模式：无法判分"，学生可以继续下一关。
 *   - 这里永远不读后端没下发的答案字段（student 契约里也没有这个字段）。
 */
import { computed } from 'vue'

const props = defineProps({
  /** 后端判题响应；离线或未提交时为 null */
  grading: {
    type: Object,
    default: null,
  },
  /** 是否处于离线（无法判分）模式 */
  offline: Boolean,
  /** 学生选中的选项 id 数组 */
  selected: {
    type: Array,
    default: () => [],
  },
  /** 当前题目的选项 [{id, text}]，用于把字母还原成文案 */
  options: {
    type: Array,
    default: () => [],
  },
  /** 是否已用尽提示机会 —— 用尽后才把 missing 的字母亮出来当"讲评"，此前只给数量 */
  revealMissing: Boolean,
})

const result = computed(() => props.grading?.result || '')

const panelClass = computed(() => {
  if (result.value === 'correct') return 'bg-green-500/10 border border-green-500/30'
  if (result.value === 'partial') return 'bg-amber-500/10 border border-amber-500/30'
  return 'bg-red-500/10 border border-red-500/30'
})

const titleClass = computed(() => {
  if (result.value === 'correct') return 'text-green-400'
  if (result.value === 'partial') return 'text-amber-400'
  return 'text-red-400'
})

const titleText = computed(() => {
  if (result.value === 'correct') return '✓ 回答正确！'
  if (result.value === 'partial') return '◐ 部分正确 —— 还有选项没选到'
  return '✗ 这次不对，看看下面的讲评'
})

function textOf(id) {
  return props.options.find(o => o.id === id)?.text || ''
}

const matchedOptions = computed(() =>
  (props.grading?.matched || []).map(id => ({ id, text: textOf(id) })),
)

const missingSummary = computed(() => {
  const missing = props.grading?.missing || []
  if (!missing.length) return ''
  // 默认只报数量，不把 miss 的字母当答案钥匙；用尽提示机会后才亮出来（讲评环节）
  if (!props.revealMissing) return `还有 ${missing.length} 项正确选项没有被选中。`
  const names = missing.map(id => `${id}${textOf(id) ? ' · ' + textOf(id) : ''}`).join('；')
  return `还没选到的 ${missing.length} 项：${names}`
})

const extraSummary = computed(() => {
  const extra = props.grading?.extra || []
  if (!extra.length) return ''
  return `你多选了 ${extra.length} 项（${extra.join('、')}），再想想它们是否真的承担业务职责。`
})

const knowledgePoints = computed(() => props.grading?.knowledge_points || [])
</script>
