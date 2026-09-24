<template>
  <div
    class="glass-card p-3"
    data-test="flow-card"
    :data-flow-id="flow.flow_id"
    :data-scenario="flow.scenario_type || ''"
    :data-lifecycle="flow.is_lifecycle ? 'true' : 'false'"
  >
    <div class="flex items-start justify-between gap-2 flex-wrap">
      <div class="flex items-center gap-2 flex-wrap min-w-0">
        <button
          type="button"
          data-test="flow-toggle"
          class="text-gray-500 hover:text-neon-blue transition-colors flex-shrink-0"
          :title="open ? '收起步骤' : '展开步骤'"
          @click="$emit('toggle', flow.flow_id)"
        >
          <svg
            width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            class="transition-transform" :class="{ 'rotate-90': open }"
          >
            <polyline points="9 6 15 12 9 18"></polyline>
          </svg>
        </button>
        <button
          type="button"
          class="text-sm font-semibold text-white text-left hover:text-neon-blue transition-colors"
          @click="$emit('toggle', flow.flow_id)"
        >
          {{ flow.name_cn || '(未命名流程)' }}
        </button>
        <ConfidenceBadge v-if="flow.confidence" :value="flow.confidence" />
        <span v-if="flow.name_status" class="text-[10px] text-gray-600 font-mono">{{ flow.name_status }}</span>
        <span v-if="showScenarioBadge" class="text-[10px] px-1.5 py-0.5 rounded border" :class="scenarioMeta(flow.scenario_type).cls">
          {{ scenarioMeta(flow.scenario_type).label }}
        </span>
        <span
          v-if="flow.is_lifecycle"
          data-test="lifecycle-badge"
          class="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 border border-orange-500/30"
          title="初始化 / 装配类流程：不是用户业务，讲课时不要当主流程讲（README5 §3.4）"
        >数据准备流程，非用户业务</span>
      </div>
      <div class="flex items-center gap-2 text-[10px] text-gray-500 font-mono flex-shrink-0">
        <span>{{ steps.length }} 步</span>
        <span
          v-if="flow.weight_factor !== undefined && flow.weight_factor !== 1"
          :title="'引擎给的降权系数 weight_factor=' + flow.weight_factor"
        >×{{ flow.weight_factor }}</span>
      </div>
    </div>

    <p v-if="flow.description" class="text-[11px] text-gray-500 mt-1 leading-relaxed">{{ flow.description }}</p>

    <div class="flex flex-wrap gap-3 mt-1 text-[10px] text-gray-500">
      <span v-if="domainNames.length">涉及域：{{ domainNames.join('、') }}</span>
      <span v-if="flow.failure_point" class="text-red-400/80">失败点：{{ flow.failure_point }}</span>
    </div>

    <div v-show="open" class="mt-2 pl-4 relative">
      <div class="absolute left-1.5 top-1 bottom-1 w-px bg-deep-border"></div>
      <div
        v-for="step in steps"
        :key="step.order"
        data-test="flow-step"
        :data-step-order="step.order"
        class="relative pb-2 last:pb-0"
      >
        <div class="absolute -left-4 top-1 w-2.5 h-2.5 rounded-full border-2 border-deep-border bg-deep-surface"></div>
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-[10px] text-gray-600 font-mono w-5">{{ step.order }}.</span>
          <span class="text-[12px] text-white">{{ step.name_cn || '（未命名功能点）' }}</span>
          <code class="text-[11px] text-gray-400 font-mono">{{ step.symbol }}</code>
          <span v-if="step.module" class="text-[10px] px-1.5 py-0.5 rounded bg-deep-card text-gray-500">{{ step.module }}</span>
          <span v-if="step.is_module_boundary" class="text-[10px] px-1 py-0.5 rounded bg-neon-purple/20 text-neon-purple">跨模块</span>
          <span v-if="step.is_state_change" class="text-[10px] px-1 py-0.5 rounded bg-amber-500/20 text-amber-400">状态变更</span>
          <span v-if="step.is_validation" class="text-[10px] px-1 py-0.5 rounded bg-green-500/20 text-green-400">校验</span>
          <button
            v-if="fileOf(step)"
            type="button"
            data-test="flow-step-evidence"
            class="text-[10px] text-gray-500 font-mono hover:text-neon-blue transition-colors inline-flex items-center gap-1"
            :title="'打开源码：' + fileOf(step) + ' L' + step.line"
            @click="openStep(step)"
          >
            <FileIcon />
            {{ fileOf(step) }}:{{ step.line }}
          </button>
          <!-- 行号在、文件解析不到时要如实说明，不许悄悄少显示一个可点项 -->
          <span
            v-else-if="step.line"
            class="text-[10px] text-gray-600 font-mono cursor-default"
            title="步骤给了行号，但契约没给文件路径，且按 capability_id / symbol 都解析不到 —— 不猜文件"
          >L{{ step.line }}（文件未给出）</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 单条流程卡片（流程名 + 场景徽章 + 生命周期标注 + 步骤列表）。
 * 抽出来是因为它在页面上要出现在两处：三型场景分组里、以及页面最后的"数据准备流程"区块里。
 */
import { computed } from 'vue'
import ConfidenceBadge from '../ConfidenceBadge.vue'
import FileIcon from './FileIcon.vue'
import { resolveStepFile, scenarioMeta, toProjectRelative } from '../../utils/businessGraph'

const props = defineProps({
  flow: { type: Object, required: true },
  /** 整个 business_graph：用于把步骤解析到文件 */
  graph: { type: Object, default: null },
  open: { type: Boolean, default: false },
  /** 是否显示场景徽章（生命周期区块里需要，因为它不在场景分组内了） */
  showScenarioBadge: { type: Boolean, default: false },
})

const emit = defineEmits(['toggle', 'evidence'])

const steps = computed(() => (Array.isArray(props.flow?.steps) ? props.flow.steps : []))

const domainNames = computed(() => {
  const ids = Array.isArray(props.flow?.involved_domains) ? props.flow.involved_domains : []
  const map = new Map()
  ;(props.graph?.domains || []).forEach((d) => map.set(d.domain_id, d.name_cn || d.domain_id))
  return [...new Set(ids)].map((id) => map.get(id) || id)
})

function fileOf(step) {
  return resolveStepFile(props.graph, step)
}

function openStep(step) {
  const file = fileOf(step)
  if (!file) return
  emit('evidence', {
    path: toProjectRelative(file),
    start: Number.isFinite(Number(step.line)) ? Number(step.line) : null,
    end: null,
    hint: `${props.flow?.name_cn || '流程'} · 第 ${step.order} 步 ${step.symbol || ''}`,
  })
}
</script>
