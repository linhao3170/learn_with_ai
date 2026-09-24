/**
 * Sprint 2 · 业务图谱前端的共用小工具
 * ====================================
 * 为什么单独一个模块：置信度徽章、来源徽章、路径归一化、场景文案这四件事要在
 * BusinessGraphView / ModuleCardPanel / FlowScenarioList 三处保持一致，
 * 抄三遍迟早会不一致（而"把推断说成事实"正是 README5 §10.3 红线 #4）。
 *
 * 纪律（对应 README4 §2.1 / §2.2、README5 §10.3）：
 *   1. 置信度**只做标签映射**，不做"提升"——`inferred` 永远是"系统推断"，不许在 UI 里说成已验证；
 *   2. 引擎没给值（字段缺失/空串）时返回"未标注"，**不猜**；
 *   3. `file` 一律按项目内相对路径使用（README4 §2.2：不许用 basename，也不许用开发机绝对路径）。
 */

/** 置信度四档：README4 §2.1 的三档 + README5 §13.5 里真实出现的 `inferred-low`。 */
export const CONFIDENCE_META = {
  verified: {
    label: '已验证',
    cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    dot: 'bg-emerald-400',
    title: '可由 AST / 调用图 / 状态追踪 / 行号直接证实（规则引擎）',
  },
  inferred: {
    label: '系统推断',
    cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    dot: 'bg-amber-400',
    title: '由命名 / 注释 / 结构启发式推断，需教师确认',
  },
  'inferred-low': {
    label: '低置信推断',
    cls: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
    dot: 'bg-orange-400',
    title: '推断信号弱（例如项目没有中文注释，只能退回英文标识符词根），需教师确认',
  },
  unconfirmed: {
    label: '待教师确认',
    cls: 'bg-slate-500/10 text-slate-300 border-slate-500/40 border-dashed',
    dot: 'bg-slate-400',
    title: '需要业务理解，规则引擎给不出——引擎不编，等教师填写',
  },
  unknown: {
    label: '未标注',
    cls: 'bg-deep-card text-gray-500 border-deep-border',
    dot: 'bg-gray-500',
    title: '该条数据没有置信度字段（旧快照）——如实显示"未标注"，不代填',
  },
}

/** 把任意输入归一成上面四个键之一。 */
export function normalizeConfidence(value) {
  const v = String(value ?? '').trim().toLowerCase().replace(/[\s_]+/g, '-')
  if (!v) return 'unknown'
  if (v === 'low' || v === 'inferredlow' || v === 'inferred-low') return 'inferred-low'
  return CONFIDENCE_META[v] ? v : 'unknown'
}

/** 取徽章展示元数据（永不返回 undefined）。 */
export function confidenceMeta(value) {
  return CONFIDENCE_META[normalizeConfidence(value)]
}

/** 来源徽章：教师审核版 vs 系统推断（README5 §10.2"被问业务图谱是不是自动生成的"要能一眼分清）。 */
export const SOURCE_META = {
  teacher: {
    label: '教师审核版',
    cls: 'bg-neon-purple/10 text-neon-purple border-neon-purple/30',
    title: '该条内容来自教师种子图谱（teacher seed），已人工确认',
  },
  auto: {
    label: '系统推断',
    cls: 'bg-neon-blue/10 text-neon-blue border-neon-blue/30',
    title: '该条内容由规则引擎自动生成（source=auto），未经教师审核',
  },
  unknown: {
    label: '来源未标注',
    cls: 'bg-deep-card text-gray-500 border-deep-border',
    title: '快照里没有 source 字段（旧契约）',
  },
}

export function sourceMeta(value) {
  const v = String(value ?? '').trim().toLowerCase()
  if (v === 'teacher' || v === 'auto') return SOURCE_META[v]
  return SOURCE_META.unknown
}

/** 图谱整体状态（business_graph.status）：needs_review | mixed | approved。 */
export const GRAPH_STATUS_META = {
  needs_review: {
    label: '整体待教师审核',
    cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    desc: '域划分、命名与模块边界都还没有教师确认，下面每条结论都带自己的置信度徽章。',
  },
  mixed: {
    label: '部分已审核',
    cls: 'bg-neon-blue/10 text-neon-blue border-neon-blue/30',
    desc: '部分节点来自教师种子图谱，其余仍是系统自动推断——按节点徽章区分。',
  },
  approved: {
    label: '已审核',
    cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    desc: '该图谱已经教师审核。',
  },
  unknown: {
    label: '状态未标注',
    cls: 'bg-deep-card text-gray-400 border-deep-border',
    desc: '快照里没有 status 字段（旧契约）。',
  },
}

export function graphStatusMeta(value) {
  const v = String(value ?? '').trim().toLowerCase()
  return GRAPH_STATUS_META[v] || GRAPH_STATUS_META.unknown
}

/**
 * 把契约里的 `file` 归一成**项目内相对路径**。
 *
 * 实测（本项目两个 demo 的真实数据）：`facts[].file` 是 `"../../../safety_checker.py"`，
 * 模块关系 evidence 是 `"../../app.py"`（引擎按产出目录的相对深度写出来的）。
 * SourceViewerModal 需要的是 `"safety_checker.py"`，所以这里统一剥掉所有前导 `./` / `../`。
 * 注意：这里**不取 basename**（那正是 P0-09 的根因），只剥前缀——`pkg/mod.py` 会保持 `pkg/mod.py`。
 */
export function toProjectRelative(file) {
  const p = String(file ?? '').replace(/\\/g, '/').trim()
  if (!p) return ''
  const stripped = p.replace(/^(?:\.{1,2}\/)+/, '')
  return stripped || p
}

/** 场景三型（README5 §3.4）。 */
export const SCENARIO_META = {
  normal: { label: '正常流程', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30', order: 0 },
  exception: { label: '异常流程', cls: 'bg-red-500/10 text-red-400 border-red-500/30', order: 1 },
  edge_case: { label: '边界情况', cls: 'bg-neon-purple/10 text-neon-purple border-neon-purple/30', order: 2 },
}

export function scenarioMeta(value) {
  const v = String(value ?? '').trim().toLowerCase()
  return SCENARIO_META[v] || { label: v || '类型未标注', cls: 'bg-deep-card text-gray-400 border-deep-border', order: 9 }
}

/** 场景展示顺序：正常 → 异常 → 边界（README4 第三阶段的学习顺序）。 */
export const SCENARIO_ORDER = ['normal', 'exception', 'edge_case']

/** 事实文本状态：引擎拒绝编业务含义时给 `verified_code_only`。 */
export function factTextNote(fact) {
  const status = String(fact?.text_status ?? '').trim()
  if (fact?.text) return ''
  if (status === 'verified_code_only') {
    return '引擎只给出代码表达式，不编业务含义（text_status=verified_code_only）'
  }
  if (status) return `暂无文字说明（text_status=${status}）`
  return '暂无文字说明'
}

/** 模块卡片层级文案。 */
export function levelLabel(level) {
  const n = Number(level)
  if (n === 1) return '一级业务域'
  if (n === 2) return '二级功能点'
  return n ? `第 ${n} 级` : '层级未标注'
}

/** 角色徽章：core（核心业务） / orchestrator（编排）。 */
export const ROLE_META = {
  core: { label: '核心', cls: 'bg-neon-blue/10 text-neon-blue border-neon-blue/30', title: '持有业务状态、对外提供业务操作的域' },
  orchestrator: { label: '编排', cls: 'bg-neon-purple/10 text-neon-purple border-neon-purple/30', title: '只做装配与调用编排，不持有自己的业务状态（README5 §9.2：编排类不进入核心业务模块）' },
}

export function roleMeta(value) {
  const v = String(value ?? '').trim().toLowerCase()
  return ROLE_META[v] || { label: v || '角色未标注', cls: 'bg-deep-card text-gray-400 border-deep-border', title: '' }
}

/** 复杂度七维的中文标签（README4 §五 / README5 §3.3 的公式项）。 */
export const COMPLEXITY_DIMENSIONS = [
  { key: 'domains', label: '一级业务域数' },
  { key: 'capabilities', label: '二级功能点数' },
  { key: 'cross_domain_edges', label: '跨域调用边数' },
  { key: 'written_state_fields', label: '被写入的状态字段数' },
  { key: 'business_branches', label: '业务分支数（if / raise）' },
  { key: 'external_entries', label: '外部入口数' },
  { key: 'role_hits', label: '角色词表命中数' },
]

/** 成员角色：entry（对外入口函数） / rule（规则载体）。 */
export function memberRoleLabel(role) {
  const v = String(role ?? '').trim().toLowerCase()
  if (v === 'entry') return '入口函数'
  if (v === 'rule') return '规则载体'
  if (v === 'capability') return '二级功能点'
  return v || '成员'
}

/**
 * 解析流程步骤对应的项目内相对文件路径。
 *
 * 实测契约缺口：`flows[].steps[].file` 是**空串**（引擎在步骤粒度没写文件，`facts` / `capabilities.members`
 * 里才有）。所以这里按 `capability_id` → `capabilities[].members[*].file` 解析，再退回 `symbol` 索引；
 * 三级都解析不到时返回空串 —— 调用方必须**如实显示"文件未给出"**，绝不猜一个文件名（README4 §2.2）。
 */
export function resolveStepFile(graph, step) {
  if (!step) return ''
  if (step.file) return toProjectRelative(step.file)
  const capabilities = graph?.capabilities || []
  const cap = capabilities.find((c) => c.capability_id === step.capability_id)
  const members = cap?.members || []
  const member = members.find((m) => m.symbol === step.symbol) || members[0]
  if (member?.file) return toProjectRelative(member.file)
  for (const c of capabilities) {
    const hit = (c.members || []).find((m) => m.symbol === step.symbol)
    if (hit?.file) return toProjectRelative(hit.file)
  }
  const fact = (graph?.facts || []).find((f) => f.symbol === step.symbol)
  if (fact?.file) return toProjectRelative(fact.file)
  return ''
}

