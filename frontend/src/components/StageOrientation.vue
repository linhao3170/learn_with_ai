<template>
  <div class="stage-orientation" data-test="stage-orientation-view">
    <!-- 加载 / 失败：不静默渲染空白（P0-09 的教训） -->
    <div v-if="loading" class="glass-card p-10 text-center text-gray-400 text-sm" data-test="orientation-loading">
      正在加载业务图谱…
    </div>
    <div v-else-if="loadError" class="glass-card p-10 text-center" data-test="orientation-error">
      <div class="text-red-400 text-sm mb-2">无法加载项目「{{ projectId }}」的业务图谱</div>
      <div class="text-xs text-gray-500 font-mono break-all">{{ loadError }}</div>
      <div class="text-xs text-gray-500 mt-3">
        阶段一「项目认知」只读业务图谱，不依赖训练题契约。
      </div>
    </div>

    <div v-else class="space-y-6">
      <!-- ① 项目地图：系统先展示（学生此时还没有输出，所以这里只有事实，没有评价） -->
      <section class="glass-card p-6 neon-border">
        <div class="flex items-start justify-between gap-4 mb-4">
          <div>
            <div class="text-xs text-gray-500 font-mono tracking-widest uppercase mb-1">Stage 1 · Orientation</div>
            <h2 class="text-lg font-bold text-white">项目认知</h2>
            <p class="text-xs text-gray-400 mt-1">
              先读这张地图：这个项目有哪几个一级业务模块、每个模块管什么。然后回答一个问题——
              <span class="text-gray-200">这个项目为什么需要这些模块？</span>
            </p>
          </div>
          <div class="text-right shrink-0">
            <ComplexityBadge :complexity="complexity" :fallback-level="graph?.level || ''" />
            <div v-if="statusMeta" class="mt-2 inline-flex text-[10px] px-1.5 py-0.5 rounded border" :class="statusMeta.cls">
              {{ statusMeta.label }}
            </div>
          </div>
        </div>

        <!-- 核心业务模块（参与覆盖度） -->
        <div class="text-[11px] text-gray-500 mb-2">
          一级业务模块（核心）<span class="text-gray-600">· {{ domains.length }} 个</span>
        </div>
        <div class="space-y-2 mb-5">
          <div
            v-for="domain in domains"
            :key="domain.domain_id"
            class="rounded-xl border border-deep-border bg-deep-card/50 px-4 py-3"
            data-test="orientation-domain"
            :data-domain-id="domain.domain_id"
          >
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-sm font-semibold text-white">{{ domain.name_cn || '（未命名）' }}</span>
              <ConfidenceBadge :value="domain.confidence" />
              <span class="text-[10px] font-mono text-gray-600">{{ domain.domain_id }}</span>
              <span class="text-[10px] text-gray-500">
                {{ childCount(domain) }} 个二级功能模块
              </span>
            </div>

            <!-- 目标文本：没有就让位给"待教师确认"，绝不代填（README4 §2.1 铁律） -->
            <div v-if="objectiveOf(domain)" class="text-xs text-gray-300 mt-1.5 leading-relaxed">
              {{ objectiveOf(domain) }}
              <ConfidenceBadge :value="objectiveConfidenceOf(domain)" class="ml-1" />
            </div>
            <div v-else class="text-xs text-gray-500 mt-1.5" data-test="orientation-objective-unconfirmed">
              该模块「管什么」还没有教师确认——引擎推不出业务含义就不编，等教师填写。
            </div>

            <div v-if="capabilityNames(domain).length" class="text-[11px] text-gray-500 mt-2 leading-relaxed">
              <span class="text-gray-600">包含：</span>
              {{ capabilityNames(domain).join(' · ') }}
            </div>
          </div>
        </div>

        <!-- 编排 / 支撑模块：展示但明确不计入核心覆盖度 -->
        <div v-if="supportingDomains.length" class="mb-5">
          <div class="text-[11px] text-gray-500 mb-2">
            系统装配 / 支撑（不计入核心业务覆盖度）
          </div>
          <div class="space-y-1.5">
            <div
              v-for="domain in supportingDomains"
              :key="domain.domain_id"
              class="rounded-lg border border-deep-border/60 bg-deep-card/30 px-4 py-2 flex items-center gap-2 flex-wrap"
              data-test="orientation-supporting-domain"
            >
              <span class="text-xs text-gray-300">{{ domain.name_cn || '（未命名）' }}</span>
              <span class="text-[10px] px-1.5 py-0.5 rounded border bg-neon-purple/10 text-neon-purple border-neon-purple/30">
                {{ roleLabel(domain.role) }}
              </span>
              <span class="text-[10px] font-mono text-gray-600">{{ domain.domain_id }}</span>
            </div>
          </div>
        </div>

        <!-- 数据来源与诚实边界 -->
        <div class="text-[11px] text-gray-500 leading-relaxed border-t border-deep-border pt-3">
          数据来自 <span class="font-mono">/api/projects/{{ projectId }}/business-graph</span>
          （后端不可用时回落静态快照的 <span class="font-mono">business_graph</span>）；
          来源：{{ sourceLabel }}。图谱供 {{ supportingCount }} 个编排 / 支撑模块，
          共 {{ graph?.capabilities?.length || 0 }} 个二级功能模块。
          <span v-if="graph?.algorithm_version" class="font-mono">
            · {{ graph.algorithm_version }}
          </span>
        </div>
      </section>

      <!-- ② 学生先输出（README5 §12.6：任何"先给答案再问学生"的设计都会把训练退化成阅读） -->
      <section class="glass-card p-6">
        <div class="flex items-center gap-2 mb-2">
          <span class="text-sm font-semibold text-white">轮到你写</span>
          <span class="text-[11px] text-gray-500">阶段一不打分，只回一份"覆盖清单"</span>
        </div>
        <p class="text-xs text-gray-400 mb-3 leading-relaxed">
          用自己的话说说：这个项目为什么需要这些模块？每个模块负责什么、它们之间怎么协作？
          （可以只写你已经有把握的部分——系统不会因为你漏了某个模块而扣分，它只会告诉你漏了哪一块。）
        </p>
        <textarea
          v-model="draft"
          data-test="orientation-input"
          rows="6"
          class="w-full rounded-xl bg-deep-card border border-deep-border px-4 py-3 text-sm text-gray-200
                 leading-relaxed focus:outline-none focus:border-neon-blue/50 resize-y"
          placeholder="例如：这个项目要解决……，所以我看到这几块：……"
          :disabled="submitting"
        ></textarea>
        <div class="flex items-center gap-3 mt-3 flex-wrap">
          <button
            class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all bg-gradient-to-r from-neon-blue to-neon-purple
                   disabled:opacity-40 disabled:cursor-not-allowed"
            data-test="orientation-submit"
            :disabled="!canSubmit"
            @click="submit"
          >
            {{ submitting ? '正在比对…' : '提交，看覆盖清单' }}
          </button>
          <span class="text-[11px] text-gray-500">{{ draft.trim().length }} 字</span>
          <span v-if="submitError" class="text-[11px] text-amber-400" data-test="orientation-submit-error">
            {{ submitError }}
          </span>
          <span class="text-[11px] text-gray-600 ml-auto">
            草稿只存在本机浏览器，不会上传学生答案（页面刷新后保留）
          </span>
        </div>
      </section>

      <!-- ③ 提交后才渲染的覆盖度报告（提交前这里一个节点都没有） -->
      <section v-if="report" class="glass-card p-6" data-test="orientation-report">
        <div class="flex items-center gap-2 flex-wrap mb-1">
          <h3 class="text-base font-bold text-white">覆盖清单</h3>
          <span class="text-[10px] px-1.5 py-0.5 rounded border bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                data-test="orientation-coverage-only">
            coverage_only
          </span>
          <span class="text-[10px] font-mono text-gray-600">{{ report.algorithm_version }}</span>
        </div>

        <!-- 明示"不打分"：这是本阶段的交互契约，不是免责声明 -->
        <p class="text-xs text-gray-300 mb-4 leading-relaxed" data-test="orientation-no-score">
          <span class="text-white font-semibold">本阶段不打分、不给标准答案。</span>
          下面只是一张覆盖清单：你的回答里提到了哪些一级业务模块、哪些还没有提到。
          「提到」不等于「讲对了」——你的理解是否到位，由教师看你的原话判断。
        </p>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- 命中 -->
          <div>
            <div class="text-[11px] text-emerald-400 mb-2">
              你已经提到的模块（{{ report.counts.covered }} / {{ report.counts.comparable_domains }}）
            </div>
            <div v-if="!report.covered.length" class="text-xs text-gray-500 px-3 py-2 rounded-lg bg-deep-card border border-deep-border">
              暂未命中任何模块名。换个说法再试一次也可以——覆盖清单会重新算。
            </div>
            <div class="space-y-1.5">
              <div
                v-for="item in report.covered"
                :key="item.domain_id"
                class="rounded-lg border border-emerald-500/25 bg-emerald-500/5 px-3 py-2"
                data-test="orientation-covered"
                :data-domain-id="item.domain_id"
              >
                <div class="text-xs text-white">{{ item.name_cn || item.domain_id }}</div>
                <div class="text-[10px] text-gray-400 mt-0.5" data-test="orientation-key">
                  比中的词：<span class="font-mono text-emerald-300">{{ item.matched_keys.map((k) => k.key).join(' / ') }}</span>
                  <span class="text-gray-600">（{{ originLabel(item.matched_keys[0]?.origin) }}）</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 漏掉 -->
          <div>
            <div class="text-[11px] text-amber-400 mb-2">
              你还没有提到的模块（{{ report.counts.missed }}）
            </div>
            <div v-if="!report.missed.length" class="text-xs text-gray-500 px-3 py-2 rounded-lg bg-deep-card border border-deep-border">
              这份图谱里的核心模块都提到了。
            </div>
            <div class="space-y-1.5">
              <div
                v-for="item in report.missed"
                :key="item.domain_id"
                class="rounded-lg border border-deep-border bg-deep-card/40 px-3 py-2"
                data-test="orientation-missed"
                :data-domain-id="item.domain_id"
              >
                <div class="text-xs text-gray-200">{{ item.name_cn || item.domain_id }}</div>
                <div class="text-[10px] text-gray-500 mt-0.5">
                  该模块包含：{{ capabilityNamesByIds(item.capability_ids).join(' · ') || '（二级功能模块未命名）' }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 未参与比对的模块：说清"为什么没算"，而不是当成漏掉 -->
        <div v-if="report.not_comparable.length" class="mt-4">
          <div class="text-[11px] text-gray-400 mb-2">
            未参与比对的模块（{{ report.not_comparable.length }}）——不计入上面的分母
          </div>
          <div class="space-y-1.5">
            <div
              v-for="item in report.not_comparable"
              :key="item.domain_id"
              class="rounded-lg border border-dashed border-slate-500/40 bg-deep-card/30 px-3 py-2"
              data-test="orientation-not-comparable"
            >
              <div class="text-xs text-gray-300">{{ item.name_cn || item.domain_id }}</div>
              <div class="text-[10px] text-gray-500 mt-0.5">{{ item.reason }}</div>
            </div>
          </div>
        </div>

        <!-- 报告自己的诚实边界（引擎给的 caveats，原样展示） -->
        <div v-if="report.caveats?.length" class="mt-5 pt-4 border-t border-deep-border" data-test="orientation-caveats">
          <div class="text-[11px] text-gray-500 mb-2">这份报告的边界（引擎原文，不是免责声明）</div>
          <ul class="space-y-1">
            <li v-for="(line, i) in report.caveats" :key="i" class="text-[11px] text-gray-400 leading-relaxed flex gap-2">
              <span class="text-gray-600">·</span><span>{{ line }}</span>
            </li>
          </ul>
        </div>

        <div class="text-[11px] text-gray-600 mt-3 font-mono">
          图谱 source_hash {{ (report.source_hash || '').slice(0, 12) || '未给出' }}
          · 回答 {{ report.input.chars }} 字
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
/**
 * 阶段一「项目认知」（培养方案第四章 阶段一）—— 培训六阶段里第一个真正落地的阶段。
 *
 * 与旧"四关选择题"的区别（这是本组件存在的理由）
 * ================================================
 * 旧四关是"给选项、判对错"；阶段一要求的是**学生先输出、系统后反馈**，且
 * **系统只输出覆盖度报告，不打分、不给标准答案**。所以这里：
 *   1. 展示区只陈述图谱里已有的事实（模块名 / 模块目标 / 复杂度 / 置信度）；
 *      目标文本为空时如实显示"还没有教师确认"，绝不代填；
 *   2. 反馈区用 `v-if="report"` **在提交前一个节点都不渲染**（README5 §12.6 的硬要求）；
 *   3. 判定不在这里做：覆盖度比对只有一份实现 —— 后端的 `engine/teaching/coverage.py`。
 *      离线模式下如实说"不可用"，而不是在浏览器里算一份口径不同的清单出来。
 *
 * 数据来源
 * ========
 * 只读业务图谱（`/business-graph` 或快照里的 `business_graph`），**不依赖训练题契约**，
 * 所以契约加载失败时本阶段依然可用（与业务图谱视图同一取舍）。
 */
import { computed, onMounted, ref, watch } from 'vue'
import ConfidenceBadge from './ConfidenceBadge.vue'
import ComplexityBadge from './ComplexityBadge.vue'
import { loadBusinessGraph, evaluateOrientationCoverage } from '../api/dataSource'
import { graphStatusMeta, roleMeta } from '../utils/businessGraph'

const props = defineProps({
  /** 项目 id：API 与静态快照都靠它定位 */
  projectId: {
    type: String,
    default: '',
  },
})

const graph = ref(null)
const source = ref('')
const loading = ref(false)
const loadError = ref('')

const draft = ref('')
const report = ref(null)
const submitting = ref(false)
const submitError = ref('')

const domains = computed(() =>
  (Array.isArray(graph.value?.domains) ? graph.value.domains : [])
    .filter((d) => !isSupporting(d.role)),
)
const supportingDomains = computed(() =>
  (Array.isArray(graph.value?.domains) ? graph.value.domains : [])
    .filter((d) => isSupporting(d.role)),
)
const supportingCount = computed(() => supportingDomains.value.length)
const complexity = computed(() => graph.value?.complexity || null)
const statusMeta = computed(() => (graph.value?.status ? graphStatusMeta(graph.value.status) : null))
const sourceLabel = computed(() => {
  if (source.value === 'api') return '在线 API'
  if (source.value === 'offline') return '静态快照（离线）'
  return '未知来源'
})

const canSubmit = computed(() => draft.value.trim().length > 0 && !submitting.value)

/** 编排 / 支撑域不参与核心覆盖度（与业务图谱引擎的既有口径一致）。 */
function isSupporting(role) {
  const r = String(role || '').trim().toLowerCase()
  return r === 'orchestrator' || r === 'support'
}

function roleLabel(role) {
  return roleMeta(role).label
}

function cardOf(domain) {
  return graph.value?.module_cards?.[domain?.domain_id] || null
}

/** 模块目标：只在图谱真的给了文本时才显示（空串一律走"待教师确认"分支）。 */
function objectiveOf(domain) {
  const text = cardOf(domain)?.objective
  return text && String(text).trim() ? String(text).trim() : ''
}

function objectiveConfidenceOf(domain) {
  return cardOf(domain)?.objective_confidence || ''
}

/** 域下的二级功能模块名（优先按 children 顺序，缺失时按 parent_id 兜底）。 */
function childCapabilities(domain) {
  const caps = Array.isArray(graph.value?.capabilities) ? graph.value.capabilities : []
  const ids = Array.isArray(domain?.children) ? domain.children : []
  const byId = caps.filter((c) => ids.includes(c.capability_id))
  return byId.length ? byId : caps.filter((c) => c.parent_id === domain?.domain_id)
}

function childCount(domain) {
  return childCapabilities(domain).length
}

function capabilityNames(domain) {
  return childCapabilities(domain).map((c) => c.name_cn).filter(Boolean)
}

function capabilityNamesByIds(ids) {
  const caps = Array.isArray(graph.value?.capabilities) ? graph.value.capabilities : []
  const wanted = Array.isArray(ids) ? ids : []
  return caps.filter((c) => wanted.includes(c.capability_id)).map((c) => c.name_cn).filter(Boolean)
}

/** 比对键来源的中文说明 —— 学生要能看懂"系统是拿什么比出来的"。 */
function originLabel(origin) {
  const map = {
    domain_name: '用域名去掉了结构性词',
    domain_name_raw: '用域名原文',
    domain_objective: '用该模块的目标文本',
  }
  return map[String(origin || '')] || '比对键来源未标注'
}

// ---------------------------------------------------------------------------
// 草稿持久化（只存草稿，不存报告）
// ---------------------------------------------------------------------------
/**
 * 只持久化**草稿文本**，不持久化上一次的覆盖清单：
 * 报告是"针对某一份图谱的某一次回答"的结论，图谱换了（source_hash 变了）之后
 * 再把它显示出来就是拿旧结论糊弄学生。刷新后重算一次成本极低。
 */
function draftKey(projectId) {
  return `lwai.orientation.draft.${projectId || 'default'}`
}

function loadDraft(projectId) {
  try {
    return localStorage.getItem(draftKey(projectId)) || ''
  } catch {
    return ''
  }
}

function saveDraft(projectId, text) {
  try {
    localStorage.setItem(draftKey(projectId), text)
  } catch {
    /* 隐私模式下 localStorage 不可用时只丢持久化能力，不影响训练 */
  }
}

// ---------------------------------------------------------------------------
// 数据加载
// ---------------------------------------------------------------------------
async function load() {
  const id = props.projectId
  loading.value = true
  loadError.value = ''
  report.value = null
  submitError.value = ''

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
  draft.value = loadDraft(id)
}

onMounted(load)
watch(() => props.projectId, (id) => {
  draft.value = loadDraft(id)
  load()
})
watch(draft, (text) => saveDraft(props.projectId, text))

// ---------------------------------------------------------------------------
// 提交：学生先输出 → 系统后反馈
// ---------------------------------------------------------------------------
async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  submitError.value = ''
  // 重新提交时先清空上一份报告：不把旧结论留在屏幕上冒充新结论
  report.value = null

  const res = await evaluateOrientationCoverage(props.projectId, draft.value)
  submitting.value = false

  if (!res.ok) {
    submitError.value = res.error || '覆盖度比对失败'
    return
  }
  report.value = res.data
}
</script>

<style scoped>
.stage-orientation textarea::placeholder {
  color: #4b5563;
}
</style>
