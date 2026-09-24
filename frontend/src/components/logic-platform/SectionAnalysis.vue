<template>
  <section class="space-y-5" data-test="logic-section">
    <div v-if="loading" class="glass-card p-10 text-center text-sm text-gray-400" data-test="logic-section-loading">
      正在读取板块分析…
    </div>
    <div v-else-if="error" class="glass-card p-10 text-center" data-test="logic-section-error">
      <div class="text-red-400 text-sm mb-2">板块分析不可用</div>
      <div class="text-xs text-gray-500 font-mono break-all">{{ error }}</div>
    </div>

    <template v-else-if="section">
      <!-- 返回 + 板块身份 -->
      <header class="glass-card p-6 neon-border" data-test="logic-section-header">
        <button
          type="button"
          class="text-[11px] text-gray-500 hover:text-white transition-colors mb-3 inline-flex items-center gap-1"
          data-test="logic-back-to-board"
          @click="$emit('back')"
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
               stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
          返回板块看板
        </button>

        <div class="flex items-start justify-between gap-4 flex-wrap">
          <div class="min-w-0">
            <div class="flex items-center gap-1.5 flex-wrap mb-1.5">
              <span class="text-[10px] px-1.5 py-0.5 rounded border" :class="roleMeta(section.role).cls" :title="roleMeta(section.role).title">
                {{ roleMeta(section.role).label }}
              </span>
              <span v-if="section.is_core" class="text-[10px] px-1.5 py-0.5 rounded border bg-neon-blue/10 text-neon-blue border-neon-blue/30">
                核心板块
              </span>
              <ConfidenceBadge :value="section.confidence" />
              <span class="text-[10px] px-1.5 py-0.5 rounded border" :class="sourceMeta(section.source).cls" :title="sourceMeta(section.source).title"
                    data-test="logic-section-source" :data-source="section.source || ''">
                {{ sourceMeta(section.source).label }}
              </span>
              <span class="text-[10px] px-1.5 py-0.5 rounded border" :class="reviewStatusMeta.cls" :title="reviewStatusMeta.title"
                    data-test="logic-section-review-status" :data-review-status="section.review_status || ''">
                {{ reviewStatusMeta.label }}
              </span>
            </div>
            <h2 class="text-lg font-bold text-white" data-test="logic-section-title" :data-section-id="section.section_id">
              {{ section.name_cn || '（未命名板块）' }}
            </h2>
            <div class="text-[10px] text-gray-600 font-mono mt-0.5">
              {{ section.section_id }}
              <span v-if="section.level">· level {{ section.level }}</span>
              <span v-if="section.name_status">· name_status {{ section.name_status }}</span>
            </div>
          </div>

          <!-- 计数取自契约 counts -->
          <div v-if="section.counts" class="text-right shrink-0 space-y-0.5" data-test="logic-section-counts-summary">
            <div v-for="row in countRows" :key="row.key" class="text-[10px] text-gray-500">
              {{ row.label }} <span class="font-mono text-gray-200">{{ row.value }}</span>
            </div>
          </div>
        </div>

        <!-- 板块目标 -->
        <div class="mt-3" data-test="logic-section-objective">
          <div v-if="section.objective" class="text-xs text-gray-200 leading-relaxed">
            {{ section.objective }}
            <span class="ml-1"><ConfidenceBadge :value="section.objective_confidence" /></span>
          </div>
          <div v-else class="text-xs text-gray-500 px-3 py-2 rounded-lg bg-deep-card/60 border border-dashed border-slate-500/40">
            该板块的 objective 为空 —— 规则引擎推不出业务目标时不会编，等教师补充。
          </div>
        </div>

        <!-- 降级说明：板块详情接口没成功时，说清现在看的是哪一份数据 -->
        <div v-if="notice" class="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-[11px] text-amber-200/85 leading-relaxed"
             data-test="logic-section-notice">
          {{ notice }}
        </div>
      </header>

      <!-- ===============================================================
           「不负责什么」：README 说它是全套 UI 里最有记忆点的字段，
           所以这里给它独立区块 + 粉色描边 + 大字号，不塞进正文里。
           =============================================================== -->
      <section class="glass-card p-6 does-not-block" data-test="logic-section-does-not">
        <div class="flex items-center gap-2 mb-2 flex-wrap">
          <span class="text-sm font-bold text-neon-pink">✕ 这个板块不负责什么</span>
          <ConfidenceBadge :value="section.card?.does_not_confidence" />
        </div>
        <ul v-if="doesNot.length" class="space-y-2">
          <li
            v-for="(line, i) in doesNot"
            :key="i"
            class="text-[13px] text-pink-100/90 leading-relaxed flex gap-2 p-2.5 rounded-lg bg-neon-pink/5 border border-neon-pink/20"
            data-test="logic-does-not-item"
          >
            <span class="text-neon-pink flex-shrink-0">—</span><span>{{ line }}</span>
          </li>
        </ul>
        <div v-else class="text-xs text-slate-300 px-3 py-2.5 rounded-lg bg-deep-card/60 border border-dashed border-slate-500/40">
          <span class="font-semibold">引擎未给出这一项。</span>
          <span class="text-gray-500">
            边界需要业务判断，规则引擎不编；请教师补充后再进学生视图。
          </span>
        </div>
        <p class="text-[10px] text-gray-500 mt-2">
          这一项训练的是"模块边界"：说清它不做什么，比堆职责更能暴露设计问题。
        </p>
      </section>

      <!-- ===============================================================
           卡片字段（来自图谱的 raw module card）
           =============================================================== -->
      <section class="glass-card p-6" data-test="logic-section-card-fields">
        <div class="text-sm font-semibold text-white mb-3">板块卡片字段（来自业务图谱，不是这一屏现算的）</div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <div class="text-[11px] text-gray-500 mb-1">业务对象与动作（命名信号，可能是推断）</div>
            <div v-if="entityLine || verbLine" class="flex flex-wrap gap-1.5 text-[11px]">
              <span v-if="entityLine" class="px-2 py-0.5 rounded bg-deep-card border border-deep-border text-gray-300">{{ entityLine }}</span>
              <span v-if="verbLine" class="px-2 py-0.5 rounded bg-deep-card border border-deep-border text-gray-300">{{ verbLine }}</span>
              <span v-if="section.cluster" class="px-2 py-0.5 rounded bg-deep-card border border-deep-border text-gray-500 font-mono">
                cluster {{ section.cluster }}
              </span>
            </div>
            <div v-else class="text-[11px] text-gray-500">
              命名信号未识别（entity / verb 均为空）—— 该项来自函数名词根推断，为空时不代填。
            </div>
          </div>
          <div>
            <div class="text-[11px] text-gray-500 mb-1">板块级证据（点行号跳源码）</div>
            <div v-if="sectionEvidence.length" class="space-y-1">
              <button
                v-for="(ev, i) in sectionEvidence"
                :key="i"
                type="button"
                class="w-full text-left text-[10px] font-mono px-2 py-1 rounded border border-deep-border bg-deep-card
                       text-gray-400 hover:text-neon-blue hover:border-neon-blue/40 transition-colors"
                data-test="logic-section-evidence"
                :data-file="ev.file || ''"
                :disabled="!ev.file"
                @click="openEvidence(ev, '板块证据')"
              >
                {{ location(ev) }}<span v-if="ev.signal" class="text-gray-600 ml-1">[{{ ev.signal }}]</span>
              </button>
            </div>
            <div v-else class="text-[11px] text-gray-500">该板块没有证据条目。</div>
          </div>
        </div>
      </section>

      <!-- ===============================================================
           能力点列表（本页主体）
           =============================================================== -->
      <section class="space-y-4" data-test="logic-capability-list">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-sm font-semibold text-white">
            能力点（{{ capabilities.length }} 个）
          </span>
          <span class="text-[11px] text-gray-500">
            顺序与核心度排序来自引擎；每个能力点下面都能看到<b class="text-gray-300">它凭什么排在这里</b>
          </span>
        </div>

        <div v-if="!capabilities.length" class="glass-card p-8 text-center text-sm text-gray-400">
          这个板块没有可展示的能力点（契约里 capabilities 为空）。这里不替它编几个。
        </div>

        <article
          v-for="(cap, index) in capabilities"
          :key="cap.capability_id"
          class="glass-card p-5 space-y-3"
          data-test="logic-capability"
          :data-capability-id="cap.capability_id"
          :data-walkthrough-state="walkthroughState(cap)"
        >
          <!-- 能力点头部 -->
          <div class="flex items-start justify-between gap-3 flex-wrap">
            <div class="min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span
                  class="text-[10px] font-mono px-1.5 py-0.5 rounded border border-deep-border bg-deep-card text-gray-400"
                  data-test="logic-importance-rank"
                  :data-rank="index + 1"
                  :title="'引擎给出的先后次序（按重要度信号降序 + capability_id 升序）'"
                >讲解顺序 #{{ index + 1 }}</span>
                <span v-if="cap.is_core" class="text-[10px] px-1.5 py-0.5 rounded border bg-neon-blue/10 text-neon-blue border-neon-blue/30">核心能力点</span>
                <ConfidenceBadge :value="cap.confidence" />
              </div>
              <h3 class="text-sm font-bold text-white mt-1.5">{{ cap.name_cn || cap.entity_cn || cap.capability_id }}</h3>
              <div class="text-[10px] text-gray-600 font-mono mt-0.5">
                {{ cap.capability_id }}
                <span v-if="cap.name_status">· name_status {{ cap.name_status }}</span>
                <span v-if="cap.parent_id">· parent {{ cap.parent_id }}</span>
              </div>
            </div>
            <div class="text-right shrink-0">
              <div class="text-[10px] text-gray-500">成员置信度</div>
              <ConfidenceBadge :value="cap.member_confidence" />
            </div>
          </div>

          <!-- 命名信号 -->
          <div class="flex flex-wrap gap-1.5 text-[10px] text-gray-500">
            <span v-if="cap.entity_cn || cap.entity" class="px-1.5 py-0.5 rounded bg-deep-card border border-deep-border">
              对象 {{ cap.entity_cn || cap.entity }}<span v-if="cap.entity && cap.entity !== cap.entity_cn" class="text-gray-600 font-mono"> ({{ cap.entity }})</span>
            </span>
            <span v-if="cap.verb_cn || cap.verb_class" class="px-1.5 py-0.5 rounded bg-deep-card border border-deep-border">
              动作 {{ cap.verb_cn || cap.verb_class }}<span v-if="cap.verb_class && cap.verb_class !== cap.verb_cn" class="text-gray-600 font-mono"> ({{ cap.verb_class }})</span>
            </span>
            <span v-if="cap.cluster" class="px-1.5 py-0.5 rounded bg-deep-card border border-deep-border font-mono">cluster {{ cap.cluster }}</span>
          </div>

          <!--
            核心度排序的**可解释部分**。
            刻意不做成一个"重要度 87 分"的进度条：契约里 importance 是一个 4 元组原始信号，
            压成一个数字就等于造了一个不可追溯的分数（这个项目明令禁止）。
          -->
          <div class="rounded-xl border border-deep-border bg-deep-card/40 p-3" data-test="logic-importance-reasons">
            <div class="text-[10px] text-gray-500 mb-1.5">
              为什么它排在讲解顺序第 {{ index + 1 }} 位（引擎给出的理由，原文）
            </div>
            <ul v-if="reasonsOf(cap).length" class="space-y-1">
              <li v-for="(line, i) in reasonsOf(cap)" :key="i" class="text-[11.5px] text-gray-300 leading-relaxed flex gap-2">
                <span class="text-neon-purple flex-shrink-0">·</span><span>{{ line }}</span>
              </li>
            </ul>
            <div v-else class="text-[11px] text-gray-500">引擎没有给出排序理由（importance_reasons 为空）。</div>

            <div v-if="importanceOf(cap).length" class="mt-2 pt-2 border-t border-deep-border/60 flex flex-wrap gap-x-4 gap-y-1"
                 data-test="logic-importance-raw">
              <div v-for="(dim, i) in importanceOf(cap)" :key="i" class="text-[10px] text-gray-500">
                {{ dim.label }} <span class="font-mono text-gray-300">{{ dim.value }}</span>
              </div>
              <div class="text-[10px] text-gray-600 w-full">
                以上是引擎排序用的 4 维原始信号（<span class="font-mono">importance=[{{ (cap.importance || []).join(', ') }}]</span>）。
                这一屏<b>不把它压成一个分数</b> —— 它只是讲解顺序的参考信号，
                不是对代码质量的评价，也不是任何形式的达标线。
              </div>
            </div>
          </div>

          <!-- 计数 -->
          <div v-if="cap.counts" class="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-gray-500" data-test="logic-capability-counts">
            <span v-for="row in capCountRows(cap)" :key="row.key">
              {{ row.label }} <span class="font-mono text-gray-300">{{ row.value }}</span>
            </span>
          </div>

          <!-- 成员函数：file:start-end 可点，直接跳源码（证据跳转） -->
          <div data-test="logic-members">
            <div class="text-[10px] text-gray-500 mb-1.5">
              成员函数（{{ membersOf(cap).length }} 个，点出处跳源码）
            </div>
            <div v-if="membersOf(cap).length" class="space-y-1">
              <div
                v-for="(m, i) in membersOf(cap)"
                :key="(m.symbol || '') + i"
                class="rounded-lg border border-deep-border bg-deep-card/40 px-2.5 py-1.5"
                data-test="logic-capability-member"
                :data-symbol="m.symbol || ''"
              >
                <div class="flex items-center gap-2 flex-wrap">
                  <code class="text-[11.5px] text-white font-mono">{{ m.symbol }}</code>
                  <span v-if="m.role" class="text-[10px] px-1.5 py-0.5 rounded bg-deep-hover text-gray-400">{{ memberRoleLabel(m.role) }}</span>
                  <span v-if="m.is_public === false" class="text-[10px] text-gray-500" title="非公开成员（下划线前缀）">非公开</span>
                  <button
                    v-if="m.file"
                    type="button"
                    class="text-[10px] font-mono text-gray-500 hover:text-neon-blue transition-colors"
                    data-test="logic-member-evidence"
                    :data-file="m.file"
                    :data-start="m.start_line"
                    @click="openSource(m.file, m.start_line, m.end_line, `成员 ${m.symbol}`)"
                  >{{ location(m) }} ↗</button>
                </div>
                <div v-if="(m.state_writes || []).length || (m.state_reads || []).length" class="mt-1 flex flex-wrap gap-1">
                  <span v-for="w in (m.state_writes || [])" :key="'w' + w"
                        class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-mono">写 {{ w }}</span>
                  <span v-for="r in (m.state_reads || [])" :key="'r' + r"
                        class="text-[10px] px-1.5 py-0.5 rounded bg-deep-hover text-gray-400 border border-deep-border font-mono">读 {{ r }}</span>
                </div>
              </div>
            </div>
            <div v-else class="text-[11px] text-gray-500">该能力点没有绑定成员函数。</div>
          </div>

          <!-- 能力点证据 -->
          <div v-if="evidenceOf(cap).length" class="space-y-1" data-test="logic-capability-evidence">
            <div class="text-[10px] text-gray-500">能力点证据</div>
            <button
              v-for="(ev, i) in evidenceOf(cap)"
              :key="i"
              type="button"
              class="w-full text-left text-[10px] font-mono px-2 py-1 rounded border border-deep-border bg-deep-card
                     text-gray-400 hover:text-neon-blue hover:border-neon-blue/40 transition-colors"
              :disabled="!ev.file"
              @click="openEvidence(ev, `能力点 ${cap.capability_id} 的证据`)"
            >
              {{ location(ev) }}
              <span v-if="ev.symbol" class="text-gray-600 ml-1">{{ ev.symbol }}</span>
              <span v-if="ev.signal" class="text-gray-600 ml-1">[{{ ev.signal }}]</span>
            </button>
          </div>

          <!-- ===========================================================
               沉浸式学习入口 / 超出预算的原文说明
               =========================================================== -->
          <div class="pt-1">
            <template v-if="isAvailable(cap)">
              <button
                type="button"
                class="px-5 py-2 rounded-xl text-xs font-medium text-white transition-all hover:-translate-y-0.5
                       bg-gradient-to-r from-neon-blue via-neon-purple to-neon-pink"
                data-test="logic-walkthrough-start"
                :data-capability-id="cap.capability_id"
                @click="$emit('start-lesson', cap.capability_id)"
              >
                沉浸式学习业务逻辑 →
              </button>
              <span v-if="lessonMeta(cap).generated" class="text-[10px] text-gray-500 ml-2">
                这一课已经生成过（{{ lessonMeta(cap).segments }} 段，
                review_status = {{ lessonMeta(cap).review_status || '未标注' }}）
              </span>
            </template>
            <template v-else>
              <!-- 未展开的原因**原样显示**：截断必须看得见，不许悄悄不显示这个入口 -->
              <div
                class="rounded-xl border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-[11px] text-amber-200/85 leading-relaxed"
                data-test="logic-walkthrough-beyond-budget"
                :data-capability-id="cap.capability_id"
                :data-state="walkthroughState(cap)"
              >
                <span class="font-semibold">本次没有生成这一课的讲稿。</span>
                {{ cap.walkthrough?.reason || '引擎未给出原因（walkthrough.reason 为空）—— 如实说明，不替它编一个。' }}
              </div>
            </template>
          </div>
        </article>
      </section>

      <CaveatsPanel :items="caveats" test-id="logic-section-caveats" desc="板块级 caveat 挂在看板载荷上" />
    </template>
  </section>
</template>

<script setup>
/**
 * 板块分析面板（Step 5）
 * =======================
 * 一个业务板块的完整分析：它负责什么、**不负责什么**、有哪些能力点、
 * 每个能力点凭什么排在前面、它的成员函数在哪几行、能不能进入沉浸式课程。
 *
 * 四条纪律（每一条都对应一类"看起来更专业、实际更不诚实"的做法）
 * ---------------------------------------------------------------
 * 1. **排序可解释，不给分数**。契约里的 `importance` 是一个 4 元组原始信号
 *    （参与流程数 / 业务边界事实数 / 写入状态字段数 / 成员函数数 —— 与引擎
 *    `design/task_builder.py::_importance` 一一对应）。把它压成"重要度 87 分"
 *    就等于造了一个不可追溯的分数，所以这里只列原始 4 维 + `importance_reasons` 原文。
 * 2. **证据是行号，不是文件名**。每个成员/证据都给出 `file:start_line-end_line`，
 *    点一下就跳 `SourceViewerModal`。没有行号的证据不是证据。
 * 3. **「超出预算」不许变成"没有这个能力点"**。`walkthrough.state === 'beyond_budget'` 时
 *    按钮不出，但后端给的 `reason` 整句显示 —— 学生要看到"平台这次没讲它"，
 *    而不是以为"这块没有这个能力点"。
 * 4. **命名与置信度成对出现**。`name_status` / `confidence` / `member_confidence`
 *    都照原样带出来：板块与能力点名字是引擎推断的，不能长得像事实。
 */
import { computed } from 'vue'
import ConfidenceBadge from '../ConfidenceBadge.vue'
import CaveatsPanel from './CaveatsPanel.vue'
import { memberRoleLabel, roleMeta, sourceMeta, toProjectRelative } from '../../utils/businessGraph'

const props = defineProps({
  /** 单个板块对象（GET /{id}/sections/{sid} 的返回，或主载荷里的同一份） */
  section: {
    type: Object,
    default: null,
  },
  /** 看板级 caveats（契约里板块级 caveat 挂在 sections 载荷上，没有按板块各给一份） */
  caveats: {
    type: Array,
    default: () => [],
  },
  /** 课程索引（标注哪些能力点的讲稿已生成） */
  lessonsIndex: {
    type: Object,
    default: null,
  },
  /** 回落说明（板块详情接口没成功时由 store 填） */
  notice: {
    type: String,
    default: '',
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['open-source', 'start-lesson', 'back'])

const REVIEW_STATUS_META = {
  approved: { label: '教师已审核', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30', title: '教师已审核该板块' },
  needs_review: { label: '待教师确认', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30', title: '该板块的划分/命名尚未经教师确认' },
  rejected: { label: '教师已否决', cls: 'bg-red-500/10 text-red-400 border-red-500/30', title: '教师已否决该板块' },
}

const reviewStatusMeta = computed(() => {
  const v = String(props.section?.review_status || '').trim().toLowerCase()
  return REVIEW_STATUS_META[v] || {
    label: v ? `审核状态：${v}` : '审核状态未标注',
    cls: 'bg-deep-card text-gray-500 border-deep-border',
    title: '契约没有给出 review_status —— 如实显示"未标注"，不代为归类',
  }
})

const doesNot = computed(() => {
  const list = props.section?.does_not
  return Array.isArray(list) ? list.filter((x) => String(x || '').trim()) : []
})

const capabilities = computed(() => (Array.isArray(props.section?.capabilities) ? props.section.capabilities : []))
const sectionEvidence = computed(() => (Array.isArray(props.section?.evidence) ? props.section.evidence : []))

const entityLine = computed(() => {
  const s = props.section || {}
  if (!s.entity && !s.entity_cn) return ''
  return `对象 ${s.entity_cn || s.entity}${s.entity && s.entity !== s.entity_cn ? ` (${s.entity})` : ''}`
})

const verbLine = computed(() => {
  const s = props.section || {}
  if (!s.verb_class && !s.verb_cn) return ''
  return `动作 ${s.verb_cn || s.verb_class}${s.verb_class && s.verb_class !== s.verb_cn ? ` (${s.verb_class})` : ''}`
})

/** 板块 counts 的中文标签（键名来自契约，标签只做映射）。 */
const COUNT_LABELS = {
  capabilities: '能力点',
  members: '成员函数',
  walkthrough_available: '可进课程',
  walkthrough_total: '课程候选',
  flows: '业务流程',
  rules: '业务规则',
  guards: '前置判断',
  exceptions: '异常分支',
  state_writes: '状态写入',
}

const countRows = computed(() => {
  const counts = props.section?.counts
  if (!counts) return []
  return Object.keys(counts).map((key) => ({
    key,
    label: COUNT_LABELS[key] || key,
    value: counts[key],
  }))
})

function capCountRows(cap) {
  const counts = cap?.counts
  if (!counts) return []
  return Object.keys(counts).map((key) => ({
    key,
    label: COUNT_LABELS[key] || key,
    value: counts[key],
  }))
}

/**
 * 4 维原始排序信号的中文标签。
 *
 * 依据（引擎源码，不是猜的）：`engine/design/task_builder.py::_importance` 返回
 * `(flow_count, exceptions+guards+rules, state_writes, members)`，
 * `engine/logic_platform/modules.py` 用它降序排序 —— 所以这 4 维的顺序与含义是确定的。
 */
const IMPORTANCE_DIMS = [
  { key: 'flow_count', label: '参与业务流程数' },
  { key: 'boundary', label: '业务边界事实数（异常+前置判断+规则）' },
  { key: 'state_writes', label: '写入状态字段数' },
  { key: 'members', label: '成员函数数' },
]

function importanceOf(cap) {
  const arr = Array.isArray(cap?.importance) ? cap.importance : []
  if (!arr.length) return []
  // 顺序即契约给的顺序；多出来的位（引擎将来加了维度）也照原样列出，不吞掉
  return arr.map((value, index) => ({
    label: IMPORTANCE_DIMS[index]?.label || `第 ${index + 1} 维原始信号`,
    value,
  }))
}

function reasonsOf(cap) {
  const list = cap?.importance_reasons
  return Array.isArray(list) ? list.filter((x) => String(x || '').trim()) : []
}

function membersOf(cap) {
  return Array.isArray(cap?.members) ? cap.members : []
}

function evidenceOf(cap) {
  return Array.isArray(cap?.evidence) ? cap.evidence : []
}

function walkthroughState(cap) {
  const w = cap?.walkthrough
  return String(w?.state || (w?.available ? 'available' : 'unknown'))
}

/** 只有 `available === true` 才给入口；缺字段时按"不可用"处理（保守，且 reason 会显示出来）。 */
function isAvailable(cap) {
  return cap?.walkthrough?.available === true
}

function lessonMeta(cap) {
  return props.lessonsIndex?.lessons?.[cap?.capability_id] || {}
}

/** 出处标签：**完整项目内相对路径 + 行号区间**（不许只显示文件名）。 */
function location(item) {
  const path = toProjectRelative(item?.file)
  if (!path) return '出处未给出'
  const start = item?.start_line
  const end = item?.end_line
  if (!Number.isFinite(Number(start))) return path
  const s = Number(start)
  const e = Number(end)
  if (!Number.isFinite(e) || e === s) return `${path}:${s}`
  return `${path}:${s}-${e}`
}

/** 证据跳转：参数格式与 TrainingView 的 openSource 对齐（4 个位置参数）。 */
function openEvidence(ev, hint) {
  if (!ev?.file) return
  openSource(ev.file, ev.start_line, ev.end_line, `${hint} · ${ev.symbol || ''}`.replace(/\s·\s$/, ''))
}

function openSource(file, start, end, hint) {
  if (!file) return
  emit(
    'open-source',
    String(file).replace(/\\/g, '/'),
    Number.isFinite(Number(start)) ? Number(start) : null,
    Number.isFinite(Number(end)) ? Number(end) : null,
    hint || '',
  )
}
</script>

<style scoped>
/* 「不负责什么」用粉色描边强调（与本项目其它视图的同一处理保持一致） */
.does-not-block {
  border-color: rgba(236, 72, 153, 0.28) !important;
  background: rgba(236, 72, 153, 0.04);
}
</style>
