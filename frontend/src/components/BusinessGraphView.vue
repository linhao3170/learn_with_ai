<template>
  <div class="business-graph-view" data-test="business-graph-view">
    <!-- 头部：标题 + 复杂度徽章 + 数据来源 -->
    <div class="flex items-start justify-between gap-4 mb-3 flex-wrap">
      <div>
        <h2 class="text-xl font-bold flex items-center gap-2">
          <span class="w-1 h-5 bg-gradient-to-b from-neon-blue to-neon-purple rounded-full"></span>
          业务图谱
        </h2>
        <p class="text-[11px] text-gray-500 mt-1 leading-relaxed">
          一级业务域 → 二级功能点 → 具体动作（真实函数）。每个节点都带
          <span class="text-gray-300">置信度徽章</span>：
          结构事实是<span class="text-emerald-400">已验证</span>，划分与命名是
          <span class="text-amber-400">系统推断</span>，业务含义等教师填写。
        </p>
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <span
          v-if="source"
          class="text-[10px] px-2 py-0.5 rounded-full font-mono border"
          :class="source === 'api'
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
            : 'bg-amber-500/10 text-amber-400 border-amber-500/30'"
          :title="source === 'api' ? '业务图谱来自后端 /api/projects/{id}/business-graph' : '后端不可用：业务图谱来自静态快照 business_graph'"
          data-test="graph-source"
        >{{ source === 'api' ? '图谱来源：在线 API' : '图谱来源：离线快照' }}</span>
        <ComplexityBadge :complexity="graph?.complexity || null" :fallback-level="graph?.level || ''" />
        <button
          type="button"
          data-test="graph-reload"
          class="text-[11px] px-2.5 py-1 rounded-lg border border-deep-border text-gray-400 hover:text-white hover:border-neon-blue/40 transition-colors"
          :disabled="loading"
          @click="load()"
        >{{ loading ? '加载中…' : '重新加载' }}</button>
      </div>
    </div>

    <!-- 加载 / 失败 / 诚实空态 -->
    <div v-if="loading && !graph" class="glass-card p-10 text-center text-sm text-gray-400">
      正在加载业务图谱（{{ projectId }}）…
    </div>
    <div v-else-if="loadError" class="glass-card p-8 text-center">
      <div class="text-red-400 text-sm mb-2">无法加载「{{ projectId }}」的业务图谱</div>
      <div class="text-xs text-gray-500 font-mono break-all">{{ loadError }}</div>
      <div class="text-[11px] text-gray-500 mt-2">
        在线模式请确认后端 /api/projects/{{ projectId }}/business-graph 可用；
        离线模式请确认快照里带有 business_graph 字段。
      </div>
    </div>
    <div v-else-if="!graph" class="glass-card p-8 text-center text-sm text-gray-400">暂无业务图谱数据。</div>

    <template v-else>
      <!-- 概览条：数量 + 图谱状态（needs_review 必须显眼，不能悄悄糊过去） -->
      <div class="glass-card p-3 mb-3 flex flex-wrap items-center gap-x-5 gap-y-2">
        <div class="flex items-center gap-2">
          <span class="text-[10px] px-1.5 py-0.5 rounded border" :class="statusMeta.cls">{{ statusMeta.label }}</span>
          <span class="text-[11px] text-gray-500">{{ statusMeta.desc }}</span>
        </div>
        <div class="flex items-center gap-4 text-[11px] text-gray-400 ml-auto">
          <span>一级业务域 <span class="stat-number text-neon-blue">{{ domains.length }}</span></span>
          <span>二级功能点 <span class="stat-number text-neon-purple">{{ capabilities.length }}</span></span>
          <span>事实 <span class="stat-number text-emerald-400">{{ facts.length }}</span></span>
          <span>模块关系 <span class="stat-number text-amber-400">{{ relations.length }}</span></span>
          <span>流程 <span class="stat-number text-neon-pink">{{ flows.length }}</span></span>
        </div>
      </div>

      <!-- caveats 原样显示（README5 §10.3：不许美化数据）。默认展开，但可折叠 -->
      <details v-if="caveats.length" open class="glass-card p-3 mb-3 text-[11px]" data-test="graph-caveats">
        <summary class="cursor-pointer text-amber-300 font-medium">
          图谱口径与已知边界（引擎原文 caveats，共 {{ caveats.length }} 条）——点开必读
        </summary>
        <ul class="mt-2 space-y-1">
          <li v-for="(c, i) in caveats" :key="i" class="text-amber-200/80 leading-relaxed flex gap-2">
            <span class="text-amber-500 flex-shrink-0">{{ i + 1 }}.</span><span>{{ c }}</span>
          </li>
        </ul>
        <div class="mt-2 text-gray-500 font-mono">
          algorithm_version: {{ graph.algorithm_version || '—' }}
          <span v-if="graph.source_hash"> · source_hash: {{ String(graph.source_hash).slice(0, 24) }}</span>
        </div>
      </details>

      <!-- 标签页 -->
      <div class="flex gap-2 mb-4 flex-wrap">
        <button class="tab-btn" :class="{ active: tab === 'tree' }" data-test="graph-tab-tree" @click="tab = 'tree'">业务模块树</button>
        <button class="tab-btn" :class="{ active: tab === 'flows' }" data-test="graph-tab-flows" @click="tab = 'flows'">
          流程与场景（{{ flows.length }}）
        </button>
      </div>

      <!-- 业务模块树 -->
      <div v-show="tab === 'tree'" class="flex gap-4 items-start flex-col lg:flex-row">
        <div class="flex-1 min-w-0 w-full">
          <div class="flex items-center gap-2 mb-2">
            <button
              type="button"
              data-test="graph-expand-all"
              class="text-[11px] px-2 py-0.5 rounded border border-deep-border text-gray-400 hover:text-white hover:border-neon-blue/40 transition-colors"
              @click="toggleAll"
            >{{ allExpanded ? '全部收起' : '全部展开' }}</button>
            <span class="text-[11px] text-gray-600">点模块名打开右侧卡片；点函数/事实跳源码。</span>
          </div>

          <div v-if="!domains.length" class="glass-card p-8 text-center text-sm text-gray-400">
            该图谱里没有 domains（一级业务域）数据。
          </div>

          <div v-else class="glass-card p-2 space-y-1">
            <div v-for="domain in domains" :key="domain.domain_id">
              <!-- 一级业务域 -->
              <div
                class="tree-item"
                :class="{ active: selectedId === domain.domain_id }"
                data-test="graph-domain"
                :data-domain-id="domain.domain_id"
                :data-role="domain.role || ''"
                @click="selectModule(domain.domain_id)"
              >
                <button
                  type="button"
                  data-test="graph-domain-toggle"
                  class="text-gray-500 hover:text-neon-blue transition-colors flex-shrink-0"
                  :title="isDomainOpen(domain.domain_id) ? '收起功能点' : '展开功能点'"
                  @click.stop="toggleDomain(domain.domain_id)"
                >
                  <svg
                    width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
                    class="transition-transform" :class="{ 'rotate-90': isDomainOpen(domain.domain_id) }"
                  >
                    <polyline points="9 6 15 12 9 18"></polyline>
                  </svg>
                </button>

                <span class="text-sm text-white font-medium truncate">{{ domain.name_cn || '(未命名业务域)' }}</span>

                <span
                  class="text-[10px] px-1.5 py-0.5 rounded border flex-shrink-0"
                  :class="roleMeta(domain.role).cls"
                  :title="roleMeta(domain.role).title"
                >{{ roleMeta(domain.role).label }}</span>

                <span class="text-[10px] text-gray-600 font-mono flex-shrink-0">
                  {{ childCount(domain) }} 个功能点
                </span>

                <!-- 二级拆不出来时必须如实说，不许装成有层级 -->
                <span
                  v-if="isFlat(domain)"
                  class="text-[10px] px-1.5 py-0.5 rounded bg-slate-500/10 text-slate-300 border border-slate-500/40 border-dashed flex-shrink-0"
                  title="README4 §3.1：域内可识别能力数 < 3 时只做一级展示，标记 hierarchy=flat，不允许硬拆"
                >扁平域（未拆到二级）</span>

                <ConfidenceBadge :value="domain.confidence" />
                <span v-if="nameStatusLabel(domain.name_status)" class="text-[10px] text-gray-600">{{ nameStatusLabel(domain.name_status) }}</span>
              </div>

              <!-- 二级功能点 -->
              <div v-show="isDomainOpen(domain.domain_id)" class="pl-6">
                <div v-if="isFlat(domain)" class="text-[10px] text-slate-400 px-2 py-1 leading-relaxed">
                  引擎对该域标记 <span class="font-mono">hierarchy=flat</span>：域内可独立命名的功能点不足 3 个，
                  只做一级展示，不硬拆二级。{{ childrenOf(domain).length ? '下面列出的是系统推断出的候选能力点（仅供教师参考）。' : '' }}
                </div>
                <div v-if="!childrenOf(domain).length" class="text-[11px] text-gray-500 px-2 py-1">
                  该域没有识别出二级功能点。
                </div>

                <div v-for="cap in childrenOf(domain)" :key="cap.capability_id">
                  <div
                    class="tree-item"
                    :class="{ active: selectedId === cap.capability_id }"
                    data-test="graph-capability"
                    :data-capability-id="cap.capability_id"
                    @click="selectModule(cap.capability_id)"
                  >
                    <button
                      type="button"
                      data-test="graph-capability-toggle"
                      class="text-gray-500 hover:text-neon-blue transition-colors flex-shrink-0"
                      :title="isCapOpen(cap.capability_id) ? '收起动作' : '展开动作（真实函数）'"
                      @click.stop="toggleCap(cap.capability_id)"
                    >
                      <svg
                        width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
                        class="transition-transform" :class="{ 'rotate-90': isCapOpen(cap.capability_id) }"
                      >
                        <polyline points="9 6 15 12 9 18"></polyline>
                      </svg>
                    </button>
                    <span class="text-[13px] text-gray-200 truncate">{{ cap.name_cn || '(未命名功能点)' }}</span>
                    <span v-if="cap.entity_cn || cap.verb_cn" class="text-[10px] text-gray-500 flex-shrink-0">
                      {{ [cap.entity_cn, cap.verb_cn].filter(Boolean).join(' · ') }}
                    </span>
                    <span class="text-[10px] text-gray-600 font-mono flex-shrink-0">{{ (cap.members || []).length }} 个动作</span>
                    <ConfidenceBadge :value="cap.confidence" />
                    <span v-if="nameStatusLabel(cap.name_status)" class="text-[10px] text-gray-600">{{ nameStatusLabel(cap.name_status) }}</span>
                  </div>

                  <!-- 动作级（成员函数）：点击直接跳源码 -->
                  <div v-show="isCapOpen(cap.capability_id)" class="pl-6">
                    <div v-if="!(cap.members || []).length" class="text-[11px] text-gray-500 px-2 py-1">该功能点没有绑定成员函数。</div>
                    <div
                      v-for="(m, i) in (cap.members || [])"
                      :key="(m.symbol || '') + i"
                      data-test="graph-member"
                      class="tree-item"
                      :title="memberFile(m) ? '打开源码 ' + memberFile(m) + ':' + m.start_line : '契约没有给出该函数的文件路径'"
                      @click="openMember(m, cap)"
                    >
                      <span class="w-2.5 flex-shrink-0"></span>
                      <code class="text-[11px] text-gray-300 font-mono">{{ m.symbol }}</code>
                      <span class="text-[10px] px-1.5 py-0.5 rounded bg-deep-hover text-gray-500 flex-shrink-0">{{ memberRoleLabel(m.role) }}</span>
                      <span v-if="memberFile(m)" class="text-[10px] text-gray-600 font-mono truncate">
                        {{ memberFile(m) }}:{{ m.start_line }}<template v-if="m.end_line && m.end_line !== m.start_line">-{{ m.end_line }}</template>
                      </span>
                      <span v-else class="text-[10px] text-gray-600 font-mono">文件未给出</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 未归属功能点：不吞数据，也不静默丢掉 -->
            <div v-if="orphanCapabilities.length" class="pt-2 border-t border-deep-border">
              <div class="text-[11px] text-amber-400 px-2 py-1">
                以下 {{ orphanCapabilities.length }} 个功能点的 parent_id 不在 domains 里（契约异常），原样列出而不丢弃：
              </div>
              <div
                v-for="cap in orphanCapabilities"
                :key="cap.capability_id"
                class="tree-item"
                :class="{ active: selectedId === cap.capability_id }"
                data-test="graph-capability"
                :data-capability-id="cap.capability_id"
                @click="selectModule(cap.capability_id)"
              >
                <span class="w-2.5 flex-shrink-0"></span>
                <span class="text-[13px] text-gray-200">{{ cap.name_cn || cap.capability_id }}</span>
                <span class="text-[10px] text-gray-600 font-mono">{{ cap.parent_id }}</span>
                <ConfidenceBadge :value="cap.confidence" />
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧：模块卡片面板 -->
        <div v-if="panelOpen" class="w-full lg:w-[420px] flex-shrink-0 lg:sticky lg:top-4">
          <ModuleCardPanel
            :card="selectedCard"
            :graph="graph"
            :loading="cardLoading"
            :error="cardError"
            @close="closePanel"
            @evidence="onEvidence"
            @select-module="selectModule"
          />
        </div>
      </div>

      <!-- 流程与场景 -->
      <div v-show="tab === 'flows'">
        <FlowScenarioList :flows="flows" :graph="graph" @evidence="onEvidence" />
      </div>
    </template>

    <!-- 证据查看器：与 TrainingView 用的是同一个组件（props: projectId / path / start / end） -->
    <SourceViewerModal
      :visible="viewer.visible"
      :project-id="projectId"
      :path="viewer.path"
      :start="viewer.start"
      :end="viewer.end"
      :hint="viewer.hint"
      @close="viewer.visible = false"
      @loaded="onViewerLoaded"
    />
  </div>
</template>

<script setup>
/**
 * 业务图谱视图（Sprint 2 · P1-06 的业务模块树部分）
 * ================================================
 * 数据通道：`loadBusinessGraph(projectId)` —— API 优先
 * （GET /api/projects/{id}/business-graph），失败回落静态快照里的 `contract.business_graph`。
 *
 * 三条不肯让步的设计：
 *   1. **每个节点都有置信度徽章**（README4 §2.1、README5 §10.3 红线 #4）；
 *      教师种子合并过的节点额外显示"教师审核版"来源徽章（README5 §10.2）。
 *   2. **hierarchy=flat 就如实说"未拆到二级"**，不为了好看硬拆（README4 §3.1）。
 *   3. **证据跳转只复用既有机制**：SourceViewerModal 的 props（projectId/path/start/end），
 *      这里只负责把契约里的相对路径（`../../../safety_checker.py`）归一成项目内相对路径。
 */
import { computed, ref, watch, onMounted } from 'vue'
import ModuleCardPanel from './ModuleCardPanel.vue'
import ComplexityBadge from './ComplexityBadge.vue'
import ConfidenceBadge from './ConfidenceBadge.vue'
import FlowScenarioList from './FlowScenarioList.vue'
import SourceViewerModal from './SourceViewerModal.vue'
import {
  graphStatusMeta,
  memberRoleLabel,
  roleMeta,
  toProjectRelative,
} from '../utils/businessGraph'
import { loadBusinessGraph, loadModuleCard } from '../api/dataSource'

const props = defineProps({
  /** 项目 id：API 模式与离线快照都靠它定位 */
  projectId: {
    type: String,
    default: '',
  },
})

/** 打开一条证据时上报给父级（TrainingView 会写进学习会话的 viewed_evidence） */
const emit = defineEmits(['evidence-viewed'])

const graph = ref(null)
const source = ref('')
const loading = ref(false)
const loadError = ref('')

const tab = ref('tree')

// 展开状态：域和功能点各一套（默认展开第一个域，其余收起，避免一屏几千行）
const openDomains = ref(new Set())
const openCaps = ref(new Set())

// 模块卡片面板
const selectedId = ref('')
const cardOverride = ref(null)   // 本地取不到时从 /business-graph/cards/{id} 取回的那张
const cardLoading = ref(false)
const cardError = ref('')

// 证据弹窗
const viewer = ref({ visible: false, path: '', start: null, end: null, hint: '' })

const domains = computed(() => (Array.isArray(graph.value?.domains) ? graph.value.domains : []))
const capabilities = computed(() => (Array.isArray(graph.value?.capabilities) ? graph.value.capabilities : []))
const facts = computed(() => (Array.isArray(graph.value?.facts) ? graph.value.facts : []))
const relations = computed(() => (Array.isArray(graph.value?.module_relations) ? graph.value.module_relations : []))
const flows = computed(() => (Array.isArray(graph.value?.flows) ? graph.value.flows : []))
const caveats = computed(() => (Array.isArray(graph.value?.caveats) ? graph.value.caveats.filter(Boolean) : []))

const statusMeta = computed(() => graphStatusMeta(graph.value?.status))

const domainIdSet = computed(() => new Set(domains.value.map((d) => d.domain_id)))

/** 域下的二级功能点：优先按 `children` 顺序，缺失时退回按 parent_id 过滤。 */
function childrenOf(domain) {
  const ids = Array.isArray(domain?.children) ? domain.children : []
  const byId = capabilities.value.filter((c) => ids.includes(c.capability_id))
  if (byId.length) return byId
  return capabilities.value.filter((c) => c.parent_id === domain?.domain_id)
}

function childCount(domain) {
  return childrenOf(domain).length
}

/** hierarchy 只有明确等于 'flat' 才标"扁平域"；缺失时不表态。 */
function isFlat(domain) {
  const h = graph.value?.hierarchy?.[domain?.domain_id]
  return String(h || '').toLowerCase() === 'flat'
}

const orphanCapabilities = computed(() => capabilities.value.filter((c) => !domainIdSet.value.has(c.parent_id)))

const allExpanded = computed(() =>
  domains.value.length > 0 && domains.value.every((d) => openDomains.value.has(d.domain_id)))

function isDomainOpen(id) { return openDomains.value.has(id) }
function isCapOpen(id) { return openCaps.value.has(id) }

function toggleDomain(id) {
  const next = new Set(openDomains.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  openDomains.value = next
}

function toggleCap(id) {
  const next = new Set(openCaps.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  openCaps.value = next
}

function toggleAll() {
  if (allExpanded.value) {
    openDomains.value = new Set()
  } else {
    openDomains.value = new Set(domains.value.map((d) => d.domain_id))
  }
}

function nameStatusLabel(status) {
  const map = {
    from_docstring: '名来自中文 docstring',
    from_structural_role: '名来自结构角色',
    from_identifier: '名来自标识符词根',
  }
  return map[String(status || '').trim()] || ''
}

// ---------------------------------------------------------------------------
// 数据加载
// ---------------------------------------------------------------------------
async function load() {
  const id = props.projectId
  loading.value = true
  loadError.value = ''
  const res = await loadBusinessGraph(id)
  loading.value = false

  if (!res.ok) {
    graph.value = null
    source.value = ''
    loadError.value = res.error || '未知错误'
    return
  }
  graph.value = res.data
  source.value = res.source || ''

  // 默认展开第一个域，方便演示时一眼看到层级
  if (!openDomains.value.size && domains.value.length) {
    openDomains.value = new Set([domains.value[0].domain_id])
  }
  // 之前选中的模块如果不在新图谱里，关掉面板（不显示上一个项目的内容）
  if (selectedId.value && !graph.value.module_cards?.[selectedId.value]) {
    selectedId.value = ''
    cardOverride.value = null
  }
}

onMounted(load)
watch(() => props.projectId, () => {
  selectedId.value = ''
  cardOverride.value = null
  openDomains.value = new Set()
  openCaps.value = new Set()
  load()
})

// ---------------------------------------------------------------------------
// 模块卡片
// ---------------------------------------------------------------------------
const panelOpen = computed(() => !!selectedId.value)

/**
 * 卡片优先取图谱里内嵌的 `module_cards[id]`（一份数据、在线离线都一样）；
 * 只有当快照里缺少该卡片时才去问后端 `/business-graph/cards/{id}`（卡片接口存在且离线不可用）。
 */
const selectedCard = computed(() => {
  if (!selectedId.value) return null
  return graph.value?.module_cards?.[selectedId.value] || cardOverride.value
})

async function selectModule(moduleId) {
  if (!moduleId) return
  selectedId.value = moduleId
  cardError.value = ''
  cardOverride.value = null

  if (graph.value?.module_cards?.[moduleId]) return

  cardLoading.value = true
  const res = await loadModuleCard(props.projectId, moduleId)
  cardLoading.value = false
  if (res.ok && res.data) {
    cardOverride.value = res.data
  } else {
    cardError.value = res.error || '该模块卡片不在当前数据里'
  }
}

function closePanel() {
  selectedId.value = ''
  cardOverride.value = null
  cardError.value = ''
}

// ---------------------------------------------------------------------------
// 证据跳转（复用 SourceViewerModal，不重新实现）
// ---------------------------------------------------------------------------
function memberFile(member) {
  return toProjectRelative(member?.file)
}

function openMember(member, cap) {
  const file = memberFile(member)
  if (!file) return
  openEvidence({
    path: file,
    start: Number.isFinite(Number(member.start_line)) ? Number(member.start_line) : null,
    end: Number.isFinite(Number(member.end_line)) ? Number(member.end_line) : null,
    hint: `${cap?.name_cn || ''} · ${member.symbol} · ${file}:${member.start_line}`,
  })
}

function openEvidence(payload) {
  if (!payload?.path) return
  viewer.value = {
    visible: true,
    path: payload.path,
    start: Number.isFinite(Number(payload.start)) ? Number(payload.start) : null,
    end: Number.isFinite(Number(payload.end)) ? Number(payload.end) : null,
    hint: payload.hint || '',
  }
  // 上报一次"看过哪条证据"，供能力报告统计（复用 TrainingView 已有的会话记录）
  emit('evidence-viewed', { path: payload.path, start: viewer.value.start, end: viewer.value.end })
}

function onEvidence(payload) {
  openEvidence(payload)
}

function onViewerLoaded() {
  /* 弹窗内部已按 props 加载完成；这里无需额外动作（保留钩子便于将来统计） */
}
</script>

<style scoped>
/* 树里选中的行用内置的 .tree-item.active 高亮；这里只补一点树内文字的截断规则 */
.business-graph-view :deep(.tree-item) {
  overflow: hidden;
}

.business-graph-view :deep(.tree-item) > span {
  min-width: 0;
}
</style>
