<template>
  <span
    class="inline-flex items-center gap-1 flex-wrap"
    data-test="logic-claim-badge"
    :data-confidence="confidenceKey"
    :data-verified="String(verified)"
  >
    <!-- 置信度：复用置信度词汇表，绝不在这里"提档" -->
    <span
      class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border font-medium whitespace-nowrap leading-none"
      :class="confidence.cls"
      :title="confidence.title"
      data-test="claim-badge"
      :data-claim-confidence="confidenceKey"
      :data-claim-verified="String(verified)"
    >
      <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :class="confidence.dot"></span>
      {{ confidence.label }}
    </span>

    <!-- 生成主体：规则引擎 vs 模型草稿。这条信息决定评审该用多严的眼光看它 -->
    <span
      v-if="generatedBy"
      class="text-[10px] px-1.5 py-0.5 rounded border font-medium whitespace-nowrap leading-none"
      :class="sourceMeta.cls"
      :title="sourceMeta.title"
      data-test="claim-source-badge"
      :data-claim-source="generatedBy"
    >
      {{ sourceMeta.label }}
    </span>

    <!-- 教师已给出的判定（提交后回显） -->
    <span
      v-if="reviewDecision"
      class="text-[10px] px-1.5 py-0.5 rounded border font-medium whitespace-nowrap leading-none"
      :class="reviewDecision === 'reject'
        ? 'bg-red-500/10 text-red-400 border-red-500/30'
        : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'"
      data-test="claim-review-decision"
      :data-review-decision="reviewDecision"
    >
      {{ reviewDecision === 'reject' ? '教师已标问题' : '教师已确认' }}
    </span>

    <!--
      被拦截的断言：标红显示，**绝不出现在页面上被删掉**。
      「机械复核未通过」是硬错误（引用的代码与磁盘源码不符），
      静默删掉就等于把幻觉藏起来 —— 而这个平台的 credibility 全押在"抓得到"上。
      reject_reason 是后端原文，这里不做任何改写。
    -->
    <span
      v-if="verified === false"
      class="text-[10px] px-1.5 py-0.5 rounded border font-medium whitespace-nowrap leading-none
             bg-red-500/10 text-red-400 border-red-500/40"
      :title="rejectReason || '该断言未通过机械复核（引用的代码与磁盘源码不符），已被拦截'"
      data-test="logic-claim-intercepted"
      :data-reject-reason="rejectReason || ''"
    >
      已拦截<span v-if="rejectReason" class="font-normal">：{{ rejectReason }}</span>
    </span>
  </span>
</template>

<script setup>
/**
 * 断言徽章 —— 一条结论的"它有多可信 + 谁写的 + 教师怎么看"三合一
 * =================================================================
 * 为什么值得单独一个组件：本项目的可信度全部押在"每条结论都带诚实标注"上
 * （README §2.1 铁律）。凡是渲染断言的地方（讲稿要点、总结句、板块字段），
 * 都必须同时暴露三件事，缺一件就会让人误判：
 *
 *   1. **置信度**（verified / inferred / needs_review）—— 复用 `utils/businessGraph.js`
 *      的同一份词汇表，不在这里另造一套（README §13.6 第 9 条：同一个不变量只允许一个实现）；
 *   2. **生成主体**（ast_rule_engine / llm_draft）—— 模型写的那部分必须一眼可辨；
 *   3. **教师判定**（已确认 / 已标问题）—— 教师的意见要能挂到具体某一句上。
 *
 * 它刻意不做的事
 * --------------
 * - **不给"综合可信度"打一个总分**：把三个维度压成一个数字，就等于把
 *   "机械可核验"和"语义正确"混为一谈，那正是这个项目明确禁止的表述；
 * - **不因为 `verified === false` 就隐藏这条**：被拦截的断言照原样显示，
 *   本组件直接给出红色「已拦截」与后端给的 `reject_reason`
 *   —— 静默删除等于把幻觉藏起来。
 */
import { computed } from 'vue'
import { confidenceMeta, normalizeConfidence } from '../../utils/businessGraph'

const props = defineProps({
  /** 契约里的 confidence：verified | inferred | inferred-low | unconfirmed | needs_review */
  confidence: { type: String, default: '' },
  /** 生成主体：ast_rule_engine（规则引擎）| llm_draft（模型草稿） */
  generatedBy: { type: String, default: '' },
  /** 是否通过确定性校验（false = 已被拦截） */
  verified: { type: Boolean, default: true },
  /** 被拦截的原因（verified=false 时由父组件显示） */
  rejectReason: { type: String, default: '' },
  /** 教师对这条断言的判定：'' | 'confirm' | 'reject' */
  reviewDecision: { type: String, default: '' },
})

/** `needs_review` 不在置信度四档里，单独映射：它是"校验/审核未过"的意思，不是推断强弱。 */
const confidenceKey = computed(() => {
  const raw = String(props.confidence || '').trim().toLowerCase()
  if (raw === 'needs_review') return 'needs_review'
  return normalizeConfidence(props.confidence)
})

const confidence = computed(() => {
  if (confidenceKey.value === 'needs_review') {
    return {
      label: '待复核',
      cls: 'bg-red-500/10 text-red-400 border-red-500/30',
      dot: 'bg-red-400',
      title: '这条结论未通过确定性校验，或来自模型草稿等待审核 —— 不作为结论呈现',
    }
  }
  return confidenceMeta(props.confidence)
})

const SOURCE_META = {
  ast_rule_engine: {
    label: '规则引擎',
    cls: 'bg-neon-blue/10 text-neon-blue border-neon-blue/30',
    title: '由 AST 规则确定性生成：无 LLM、无联网，同一份源码两次生成结果逐字节一致',
  },
  llm_draft: {
    label: '模型草稿',
    cls: 'bg-neon-purple/10 text-neon-purple border-neon-purple/30',
    title: '讲解措辞由语言模型生成；它引用的代码摘录仍由引擎从磁盘重读并校验，模型返回的代码文本一律丢弃',
  },
}

const sourceMeta = computed(
  () =>
    SOURCE_META[String(props.generatedBy || '')] || {
      label: '来源未标注',
      cls: 'bg-deep-card text-gray-500 border-deep-border',
      title: '契约未标注这条结论的生成主体 —— 如实显示，不代为归类',
    },
)
</script>
