<template>
  <div class="flow-scenario-list">
    <div v-if="!flows.length" class="glass-card p-8 text-center text-sm text-gray-400">
      该项目的业务图谱里没有 flows 数据（引擎没有抽出可展示的流程链）。
    </div>

    <template v-else>
      <!-- 口径说明：三型场景 + 生命周期流程处理（README5 §3.4） -->
      <div class="glass-card p-3 mb-4 text-[11px] text-gray-400 leading-relaxed" data-test="flow-caveat">
        <span class="text-gray-300 font-medium">场景口径：</span>
        正常 / 异常 / 边界三型来自结构信号（主路径 / <span class="font-mono">raise</span> 失败点 / 边界条件），
        描述由模板 + 代码事实拼装，<span class="text-amber-400">不是 LLM 编的业务故事</span>。
        <span class="block mt-1">
          标注
          <span class="text-orange-400 font-medium">数据准备流程，非用户业务</span>
          的流程（初始化 / 装配类，is_lifecycle=true）不参与场景分组，统一放在页面最后，
          并保留引擎给的降权系数 —— 这是 README5 §3.4 记录的那个真实教学错误的修复
          （曾经把"系统初始化"当成用户主流程讲）。
        </span>
      </div>

      <!-- 三组：正常 → 异常 → 边界。缺失的组如实说明，不留空壳 -->
      <section v-for="group in groups" :key="group.type" class="mb-6" :data-scenario="group.type">
        <div class="flex items-center gap-2 mb-2 flex-wrap">
          <span class="text-[11px] px-2 py-0.5 rounded border font-medium" :class="group.meta.cls">
            {{ group.meta.label }}
          </span>
          <span class="text-[11px] text-gray-500">{{ group.list.length }} 条</span>
          <span v-if="group.movedLifecycle" class="text-[11px] text-orange-400/70">
            （另有 {{ group.movedLifecycle }} 条数据准备流程，见页面最后的独立区块）
          </span>
        </div>

        <div v-if="!group.list.length" class="text-xs text-gray-500 pl-1" data-test="scenario-empty">
          该项目没有生成「{{ group.meta.label }}」——引擎只在能落到真实调用链（≥2 步）时才出流程，不出空壳。
        </div>

        <div v-else class="space-y-2">
          <FlowCard
            v-for="flow in group.list"
            :key="flow.flow_id"
            :flow="flow"
            :graph="graph"
            :open="isOpen(flow.flow_id)"
            @toggle="toggle"
            @evidence="$emit('evidence', $event)"
          />
        </div>
      </section>

      <!-- 其他场景类型：契约里出现未定义类型时不吞数据 -->
      <section v-if="otherFlows.length" class="mb-6" data-scenario="other">
        <div class="text-[11px] text-gray-500 mb-2">
          其他场景类型（契约里出现了未在 README5 §3.4 定义的类型，原样展示）
        </div>
        <div class="space-y-2">
          <FlowCard
            v-for="flow in otherFlows"
            :key="flow.flow_id"
            :flow="flow"
            :graph="graph"
            :open="isOpen(flow.flow_id)"
            show-scenario-badge
            @toggle="toggle"
            @evidence="$emit('evidence', $event)"
          />
        </div>
      </section>

      <!-- 数据准备流程：必须排在最后（README5 §3.4） -->
      <section v-if="lifecycleFlows.length" class="mb-4" data-scenario="lifecycle" data-test="lifecycle-section">
        <div class="flex items-center gap-2 mb-2 flex-wrap">
          <span class="text-[11px] px-2 py-0.5 rounded border bg-orange-500/10 text-orange-400 border-orange-500/30 font-medium">
            数据准备流程（非用户业务）
          </span>
          <span class="text-[11px] text-gray-500">{{ lifecycleFlows.length }} 条 · 排在页面最后</span>
        </div>
        <p class="text-[11px] text-gray-500 mb-2 leading-relaxed">
          这些流程是初始化 / 装配 / 造数据，讲课时不要当用户主流程讲；它们仍然保留，因为"系统怎么被装配起来"
          本身是设计问题。
        </p>
        <div class="space-y-2">
          <FlowCard
            v-for="flow in lifecycleFlows"
            :key="flow.flow_id"
            :flow="flow"
            :graph="graph"
            :open="isOpen(flow.flow_id)"
            show-scenario-badge
            @toggle="toggle"
            @evidence="$emit('evidence', $event)"
          />
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
/**
 * 流程与三型场景（README5 §3.4 / README4 第三阶段）
 * =================================================
 * 两件必须做对的事：
 *   1. 按 `scenario_type` 分组：正常 / 异常 / 边界；
 *   2. **生命周期流程显眼标注、并且排在页面最后** —— README5 §3.4 记录过这个真实教学错误：
 *      初始化 / 装配流程被当成用户主流程讲，学生学到的是错的东西。
 *
 * 为什么生命周期流程**不留在三型分组里**：留在分组里，它就会出现"边界情况"分组之前，
 * 等于在页面上又排到了业务流前面。所以它们统一进最后的独立区块，并在区块里保留场景徽章，
 * 信息不丢、顺序一定对。
 *
 * 关于行号：契约里 `flows[].steps[].file` 实测是空串（引擎在步骤粒度没写文件），
 * 解析规则见 `utils/businessGraph.resolveStepFile`：capability_id → symbol，解析不到就只显示行号。
 */
import { computed, ref, watch } from 'vue'
import FlowCard from './business-graph/FlowCard.vue'
import { SCENARIO_ORDER, scenarioMeta } from '../utils/businessGraph'

const props = defineProps({
  /** business_graph.flows */
  flows: {
    type: Array,
    default: () => [],
  },
  /** 整个 business_graph：用来做 capability_id / symbol → file 的解析 */
  graph: {
    type: Object,
    default: null,
  },
})

defineEmits(['evidence'])

const openIds = ref(new Set())

function toggle(id) {
  const next = new Set(openIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  openIds.value = next
}

function isOpen(id) {
  return openIds.value.has(id)
}

const graphFlows = computed(() => (Array.isArray(props.flows) ? props.flows : []))

const businessFlows = computed(() => graphFlows.value.filter((f) => !f.is_lifecycle))
const lifecycleFlows = computed(() => graphFlows.value.filter((f) => f.is_lifecycle))

/**
 * 默认展开第一条正常的业务流：演示时一进来就能看到步骤，
 * 而且默认展开的绝不是"数据准备流程"（否则又把 README5 §3.4 的错误演示了一遍）。
 */
watch(
  () => graphFlows.value.length,
  () => {
    if (openIds.value.size || !graphFlows.value.length) return
    const first = businessFlows.value.find((f) => String(f.scenario_type) === 'normal') || businessFlows.value[0]
    if (first) openIds.value = new Set([first.flow_id])
  },
  { immediate: true },
)

/** 三组场景（只含业务流） */
const groups = computed(() => SCENARIO_ORDER.map((type) => {
  const list = businessFlows.value.filter((f) => String(f.scenario_type || '').toLowerCase() === type)
  const movedLifecycle = lifecycleFlows.value
    .filter((f) => String(f.scenario_type || '').toLowerCase() === type).length
  return { type, meta: scenarioMeta(type), list, movedLifecycle }
}))

const otherFlows = computed(() =>
  businessFlows.value.filter((f) => !SCENARIO_ORDER.includes(String(f.scenario_type || '').toLowerCase())))
</script>
