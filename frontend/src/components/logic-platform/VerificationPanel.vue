<template>
  <section class="glass-card p-6 space-y-5" data-test="logic-verification-panel">
    <!-- =================================================================
         头部：把"这个面板能证明什么、不能证明什么"写在最上面。
         这一句话比下面所有数字都重要 —— 它防止读者把"引用对得上"
         读成"业务解释是对的"。
         ================================================================= -->
    <header>
      <div class="flex items-start justify-between gap-4 flex-wrap">
        <div class="min-w-0">
          <div class="text-xs text-gray-500 font-mono tracking-widest uppercase mb-1">Verification · 反幻觉面板</div>
          <h3 class="text-base font-bold text-white">确定性校验与人工审核</h3>
        </div>
        <div class="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            class="px-4 py-2 rounded-xl text-xs border border-deep-border text-gray-300 hover:text-white hover:border-neon-blue/40 transition-all disabled:opacity-40"
            data-test="logic-reverify"
            :disabled="verifying || !lesson"
            @click="$emit('verify')"
          >
            {{ verifying ? '正在重跑校验…' : '重新校验' }}
          </button>
        </div>
      </div>

      <!--
        证据折叠一轮：原来铺在标题下面的一整段口径，变成
        **一行常驻摘要 + 可展开的完整说明** —— 口径一条没删，只是不再占满首屏。
      -->
      <div class="mt-2">
        <EvidenceNote
          test-id="logic-verification-note"
          label="完整口径"
          :summary="VERIFICATION_SUMMARY"
          :lines="VERIFICATION_LINES"
        />
      </div>

      <div v-if="verifyError" class="mt-2 text-[11px] text-red-400 break-all font-mono" data-test="logic-verify-error">
        {{ verifyError }}
      </div>
    </header>

    <!-- 没有讲稿时的诚实空态 -->
    <div v-if="!lesson" class="text-xs text-gray-500 py-6 text-center" data-test="logic-verification-empty">
      还没有打开任何一课讲稿 —— 校验是针对"某一课的某一次生成结果"的，没有讲稿就没有可校验的对象。
    </div>

    <template v-else>
      <!-- ===============================================================
           ① 结论（后端原文）+ 发布闸门
           =============================================================== -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="rounded-xl border border-deep-border bg-deep-card/40 p-4" data-test="logic-verification-conclusion">
          <div class="flex items-center gap-2 flex-wrap mb-2">
            <span
              class="text-[10px] px-1.5 py-0.5 rounded border font-medium"
              :class="summaryMeta.cls"
              data-test="logic-verify-summary-can-publish"
              :data-can-publish="String(!!summaryCanPublish)"
            >{{ summaryMeta.label }}</span>
            <span v-if="report.verify_version" class="text-[10px] text-gray-600 font-mono">{{ report.verify_version }}</span>
          </div>
          <p v-if="summaryConclusion" class="text-[11.5px] text-gray-300 leading-relaxed" data-test="logic-verify-conclusion">
            {{ summaryConclusion }}
          </p>
          <p v-else class="text-[11.5px] text-gray-500 leading-relaxed">
            后端没有给出结论文本（summary.conclusion 为空）—— 如实说明，不在这里编一句。
          </p>
        </div>

        <!-- 发布闸门：can_publish 与 needs_review 必须一直可见 -->
        <div
          class="rounded-xl border p-4"
          :class="canPublish
            ? 'border-emerald-500/40 bg-emerald-500/5'
            : 'border-amber-500/40 bg-amber-500/5'"
          data-test="logic-publish-gate"
          :data-can-publish="String(canPublish)"
          :data-review-status="review.status || ''"
        >
          <div class="flex items-center gap-2 flex-wrap mb-2">
            <span class="text-[11px] font-semibold" :class="canPublish ? 'text-emerald-300' : 'text-amber-300'">
              {{ canPublish ? '这一课已通过人工确认（可发布）' : '这一课尚未发布' }}
            </span>
            <span class="text-[10px] px-1.5 py-0.5 rounded border font-mono"
                  :class="reviewStatusMeta.cls" data-test="logic-review-status" :data-review-status="review.status || ''">
              review.status = {{ review.status || '未标注' }}
            </span>
          </div>
          <p class="text-[11px] leading-relaxed" :class="canPublish ? 'text-emerald-200/80' : 'text-amber-200/85'">
            <template v-if="!canPublish">
              引擎不会把 <span class="font-mono">can_publish</span> 置为 true：
              只有教师走审核接口确认过、且机械复核通过，这一课才会变成
              <span class="font-mono">approved</span>。
            </template>
            <template v-else>
              当前状态由教师确认得出；这份确认绑定源码哈希，源码一变它会立刻失效。
            </template>
          </p>
          <div class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-gray-500">
            <span>机械复核 {{ review.verification_passed ? '通过' : '未通过' }}</span>
            <span>通过 <span class="font-mono text-gray-300">{{ review.verified_checks ?? '—' }}</span></span>
            <span>失败 <span class="font-mono text-gray-300">{{ review.failed_checks ?? '—' }}</span></span>
          </div>
        </div>
      </div>

      <!-- 拦截项：blocking_issues 一直显示，不折叠 -->
      <ul
        v-if="blockingIssues.length"
        class="space-y-1.5"
        data-test="logic-verification-blocking"
      >
        <li
          v-for="(line, i) in blockingIssues"
          :key="i"
          class="text-[11px] text-amber-300/90 bg-amber-500/5 border border-amber-500/20 rounded-lg px-3 py-1.5 leading-relaxed flex gap-2"
          data-test="logic-blocking-issue"
        >
          <span class="text-amber-500/70 flex-shrink-0">·</span><span>{{ line }}</span>
        </li>
      </ul>

      <!-- ===============================================================
           ② 校验计数 + 逐项检查（失败在前）
           =============================================================== -->
      <div>
        <div class="flex items-center gap-2 flex-wrap mb-2">
          <span class="text-sm font-semibold text-white">确定性校验</span>
          <span v-if="report.algorithm_version" class="text-[10px] text-gray-600 font-mono">{{ report.algorithm_version }}</span>
          <span class="text-[10px] text-gray-500">按状态分组，失败与跳过在前</span>
        </div>

        <div v-if="countEntries.length" class="flex flex-wrap gap-2 mb-2" data-test="logic-verification-counts">
          <span
            v-for="item in countEntries"
            :key="item.key"
            class="text-[10px] px-2 py-0.5 rounded border font-mono"
            :class="item.cls"
            :data-count-key="item.key"
            :data-count-value="item.value"
          >{{ item.label }} {{ item.value }}</span>
        </div>

        <div v-if="!checks.length" class="text-[11px] text-gray-500 py-3" data-test="logic-checks-empty">
          这份载荷没有校验明细（checks 为空）—— 如实说明，不在这里补一行"全部通过"。
        </div>

        <!--
          逐项明细默认收起（它是最长的一块），但**失败项例外**：
          `default-open` 在有失败时为真 —— 失败不许藏在一次点击之后。
          收起只是把高度归零，检查项一条都没少，仍然在 DOM 里。
        -->
        <EvidenceFold
          v-else
          label="逐项检查明细（失败与跳过在前）"
          :count="checks.length"
          test-id="logic-checks-fold"
          :default-open="failedCount > 0"
          hint="有失败项时默认展开：失败不藏在一次点击之后"
        >
          <div class="space-y-1.5">
            <div
              v-for="check in sortedChecks"
              :key="check.check_id + '|' + (check.target_id || '')"
              class="rounded-lg border px-3 py-2"
              :class="checkRowCls(check)"
              data-test="logic-check"
              :data-status="check.status || ''"
              :data-check-id="check.check_id || ''"
            >
              <div class="flex items-start justify-between gap-3 flex-wrap">
                <div class="min-w-0">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span
                      class="text-[10px] px-1.5 py-0.5 rounded border font-medium"
                      :class="statusMeta(check.status).cls"
                      data-test="logic-check-status"
                    >{{ statusMeta(check.status).label }}</span>
                    <span class="text-[11.5px] text-gray-200">{{ check.check_name || check.check_id }}</span>
                    <span v-if="check.scope" class="text-[10px] text-gray-600 font-mono">{{ check.scope }}</span>
                  </div>
                  <div v-if="check.target_id" class="text-[10px] text-gray-600 font-mono mt-0.5 truncate">
                    target: {{ check.target_id }}
                  </div>
                </div>
                <!-- 失败/跳过的检查必须能直接跳到它校验的那几行 -->
                <button
                  v-if="check.file"
                  type="button"
                  class="text-[10px] font-mono text-gray-500 hover:text-neon-blue transition-colors flex-shrink-0"
                  data-test="logic-check-location"
                  :data-file="check.file"
                  :data-line="check.line ?? ''"
                  @click="$emit('open-source', check.file, check.line, check.line, `校验项 ${check.check_id}`)"
                >{{ checkLocation(check) }} ↗</button>
              </div>
              <p
                v-if="check.detail"
                class="text-[11px] mt-1 leading-relaxed"
                :class="check.status === 'fail' ? 'text-red-200/85' : 'text-gray-500'"
                data-test="logic-check-detail"
              >{{ check.detail }}</p>
            </div>
          </div>
        </EvidenceFold>
      </div>

      <!-- ===============================================================
           ③ 被拦截的断言 / 段落：只列 id，不隐藏
           =============================================================== -->
      <div
        v-if="rejectedClaimIds.length || rejectedSegmentIds.length"
        class="rounded-xl border border-red-500/30 bg-red-500/5 px-4 py-3 space-y-1.5"
        data-test="logic-verification-rejected"
      >
        <div class="text-[11px] font-semibold text-red-300">
          本次被拦截的内容（照原样列出，不删除）
        </div>
        <!-- 事实（有几条被拦）常驻；具体是哪几条收进折叠区 -->
        <p class="text-[10px] text-gray-500 leading-relaxed">
          被拦截不等于"已删除"：讲稿里它们仍然显示（标红），因为评审要能看到系统抓到了什么。
        </p>
        <EvidenceFold
          label="被拦截的 id 清单"
          :count="rejectedClaimIds.length + rejectedSegmentIds.length"
          test-id="logic-rejected-ids-fold"
          hint="点开看具体是哪几条断言 / 哪几段被拦下"
        >
          <div class="space-y-1">
            <div v-if="rejectedClaimIds.length" class="text-[11px] text-red-200/80 leading-relaxed">
              被拦截的断言 {{ rejectedClaimIds.length }} 条：
              <span class="font-mono break-all">{{ rejectedClaimIds.join('、') }}</span>
            </div>
            <div v-if="rejectedSegmentIds.length" class="text-[11px] text-red-200/80 leading-relaxed">
              被拦截的段落 {{ rejectedSegmentIds.length }} 段：
              <span class="font-mono break-all">{{ rejectedSegmentIds.join('、') }}</span>
            </div>
          </div>
        </EvidenceFold>
      </div>

      <!-- ===============================================================
           ④ 生成主体与人工审核
           =============================================================== -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="rounded-xl border border-deep-border bg-deep-card/40 p-4" data-test="logic-generated-by-block">
          <div class="text-[11px] text-gray-500 mb-2">这一课是谁写的</div>
          <div class="flex items-center gap-2 flex-wrap">
            <span
              class="text-[10px] px-1.5 py-0.5 rounded border font-medium"
              :class="generatedByMeta.cls"
              :title="generatedByMeta.title"
              data-test="logic-generated-by"
              :data-generated-by="review.generated_by || ''"
            >{{ generatedByMeta.label }}</span>
            <span class="text-[10px] text-gray-500 font-mono">generated_by = {{ review.generated_by || '未标注' }}</span>
          </div>
          <div class="mt-2 text-[10px] text-gray-500 leading-relaxed">
            <template v-if="isLlmDraft">
              模型起草的断言占比
              <span class="font-mono text-gray-300">{{ ratioText }}</span>
              （llm_claim_ratio）。
              模型写的只是措辞：它引用的代码摘录仍由引擎从磁盘重读并校验，模型返回的代码文本一律丢弃。
            </template>
            <template v-else>
              规则引擎确定性生成：无 LLM、无联网，同一份源码两次生成结果逐字节一致。
              <span v-if="ratioText" class="font-mono text-gray-400">llm_claim_ratio = {{ ratioText }}</span>
            </template>
          </div>
        </div>

        <div
          class="rounded-xl border p-4"
          :class="humanReview.stale
            ? 'border-amber-500/50 bg-amber-500/10'
            : 'border-deep-border bg-deep-card/40'"
          data-test="logic-human-review"
          :data-status="humanReview.status || ''"
          :data-stale="String(!!humanReview.stale)"
        >
          <div class="text-[11px] text-gray-500 mb-2">人工审核记录</div>

          <!-- stale 必须显眼：这是"审核失效了，请重新确认" -->
          <div
            v-if="humanReview.stale"
            class="mb-2 rounded-lg border border-amber-500/50 bg-amber-500/10 px-3 py-2"
            data-test="logic-review-stale"
          >
            <div class="text-[11px] font-semibold text-amber-300">审核已失效（stale）</div>
            <p class="text-[10px] text-amber-200/85 mt-0.5 leading-relaxed">
              源码在上次审核之后发生了变化（source_hash 不一致）。
              系统<b>不沿用</b>失效的审核结论，本课已退回
              <span class="font-mono">needs_review</span>，必须重新确认。
            </p>
          </div>

          <div class="space-y-1 text-[11px] text-gray-300">
            <div>状态：<span class="font-mono text-gray-200">{{ humanReview.status || 'none' }}</span></div>
            <div v-if="humanReview.reviewer">审核人：{{ humanReview.reviewer }}</div>
            <div v-if="humanReview.updated_at" class="text-gray-500 font-mono">{{ humanReview.updated_at }}</div>
            <div v-if="humanReview.note" class="text-gray-400 leading-relaxed">备注：{{ humanReview.note }}</div>
          </div>

          <div v-if="claimDecisions.length" class="mt-2 pt-2 border-t border-deep-border" data-test="logic-human-review-claims">
            <div class="text-[10px] text-gray-500 mb-1">逐条断言的审核</div>
            <ul class="space-y-0.5">
              <li v-for="item in claimDecisions" :key="item.claim_id" class="text-[10px] leading-relaxed">
                <span class="font-mono text-gray-400">{{ item.claim_id }}</span>
                <span :class="item.decision === 'reject' ? 'text-red-300' : 'text-emerald-300'">
                  · {{ item.decision === 'reject' ? '有问题' : '已确认' }}
                </span>
                <span v-if="item.note" class="text-gray-500">（{{ item.note }}）</span>
              </li>
            </ul>
          </div>

          <div v-else-if="!humanReview.status || humanReview.status === 'none'" class="mt-2 text-[10px] text-gray-500">
            还没有任何人工审核记录。这一课目前是"机器可核验、人未确认"的状态。
          </div>
        </div>
      </div>

      <!-- ===============================================================
           ⑤ 讲解层（LLM）状态：如实报告"这个平台有没有用 AI"
           =============================================================== -->
      <div class="rounded-xl border border-deep-border bg-deep-card/40 p-4" data-test="logic-narration-status"
           :data-enabled="String(!!narrationStatus?.enabled)">
        <div class="flex items-start justify-between gap-3 flex-wrap">
          <div class="min-w-0">
            <div class="flex items-center gap-2 flex-wrap mb-1">
              <span class="text-[11px] text-gray-500">AI 讲解层（LLM）</span>
              <span
                class="text-[10px] px-1.5 py-0.5 rounded border font-medium"
                :class="narrationStatus?.enabled
                  ? 'bg-neon-purple/10 text-neon-purple border-neon-purple/30'
                  : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'"
                data-test="logic-narration-enabled"
              >{{ narrationStatus ? (narrationStatus.enabled ? '已启用' : '已关闭（默认）') : '状态未知' }}</span>
            </div>
            <p class="text-[11px] text-gray-400 leading-relaxed max-w-2xl">
              {{ narrationStatus?.reason || '后端没有上报讲解层状态（本面板不会替它说"没启用"或"已启用"）。' }}
            </p>
            <ul v-if="narrationFacts.length" class="mt-1.5 space-y-0.5">
              <li v-for="(line, i) in narrationFacts" :key="i" class="text-[10px] text-gray-500 leading-relaxed flex gap-1.5">
                <span class="text-gray-600 flex-shrink-0">·</span><span>{{ line }}</span>
              </li>
            </ul>
          </div>
          <button
            type="button"
            class="px-4 py-2 rounded-xl text-xs border border-deep-border text-gray-300 hover:text-white hover:border-neon-purple/40 transition-all disabled:opacity-40 flex-shrink-0"
            data-test="logic-narration-attempt"
            :disabled="narrating || !lesson"
            @click="$emit('narrate')"
          >
            {{ narrating ? '正在请求…' : '请求 AI 讲解' }}
          </button>
        </div>

        <!-- 讲解请求的结果（503 的中文原文原样显示，绝不藏起来） -->
        <div
          v-if="narrationNotice"
          class="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-[11px] text-amber-200/85 leading-relaxed break-words"
          data-test="logic-narration-notice"
        >{{ narrationNotice }}</div>

        <div v-if="narrationCaveats.length" class="mt-2 pt-2 border-t border-deep-border" data-test="logic-narration-caveats">
          <div class="text-[10px] text-gray-500 mb-1">讲解层自带的边界（后端原文）</div>
          <ul class="space-y-0.5">
            <li v-for="(line, i) in narrationCaveats" :key="i" class="text-[10px] text-gray-500 leading-relaxed flex gap-1.5">
              <span class="text-gray-600 flex-shrink-0">·</span><span>{{ line }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- 校验报告自己的 caveats -->
      <CaveatsPanel :items="report.caveats || []" test-id="logic-verification-caveats" desc="来自校验报告" />
    </template>
  </section>
</template>

<script setup>
/**
 * 反幻觉面板 VerificationPanel
 * =============================
 * 这个面板存在的唯一理由：**让"这份讲稿能不能信"变成可被审阅的事实，而不是一句保证**。
 *
 * 它显示四类东西，缺一不可：
 *   1. **机械校验的结论与计数**（checks / passed / failed / skipped），
 *      并且引用失败项时给出 `file:line`，可以点开跳到源码 —— 校验结论本身也要有证据；
 *   2. **发布闸门**：`review.can_publish` 与 `review.status`。
 *      引擎永远不会把 `can_publish` 置 true；只有教师审核才会。所以
 *      "还没发布"这件事必须**一直可见**，不能只在鼠标悬停时出现；
 *   3. **生成主体**（`generated_by` / `llm_claim_ratio`）：
 *      评审有资格知道这一课是规则引擎写的还是模型起草的；
 *   4. **人工审核记录，含 stale**：源码一变，旧审核自动失效 ——
 *      这条如果看不到，评审会拿着一份已经作废的确认当真。
 *
 * 它刻意不做的事
 * --------------
 * - **不把 `passed/checks` 做成一个百分比**：分母是"这台机器检查了什么"，
 *   不是"业务上对不对"；做成进度条就是在骗人；
 * - **不把 `can_publish === false` 说成"已发布"**，也不隐藏 `blocking_issues`；
 * - **不替后端编讲解层状态**：拿不到就写"状态未知"。
 */
import { computed } from 'vue'
import CaveatsPanel from './CaveatsPanel.vue'
// 证据折叠一轮：口径收成「常驻摘要 + 可展开说明」，逐项明细与被拦截清单默认收起
import EvidenceFold from './EvidenceFold.vue'
import EvidenceNote from './EvidenceNote.vue'
import { toProjectRelative } from '../../utils/businessGraph'

/**
 * 完整口径（摘要常驻在面板顶部，这六条收在抽屉里）
 * ==================================================
 * 原来它们是铺在标题下面的一整段。收敛成抽屉**不是为了少说**，
 * 而是为了"第一眼看到的是结论，边界在点开之后一条不少"。
 * 每一条都对应可执行的事实，没有一句是形容词：
 * - `can_publish` 恒为 false：`engine/logic_platform/verify.py` 的 `apply_verification`；
 * - 重新校验重读磁盘：`verify.py` 刻意绕开解析缓存（`_read_lines` 直接开文件）；
 * - `stale`：`backend/app/services/logic_platform_service.py` 的 `_apply_reviews` 按 `source_hash` 判定；
 * - 模型把关四条规则：`engine/logic_platform/narration.py` 模块 docstring。
 *
 * 「机械复核逐项检查了什么」这一句**不再是手抄的**：它由下面那组常量拼出来，
 * 而那组常量必须与 `engine/logic_platform/verification_manifest.json` 逐项相同
 * （门禁 `scripts/verify_docs.py` 的 D9 会核对清单 ↔ 组件 ↔ `verify.py` 的 `CHECKS`）。
 */
const VERIFICATION_SUMMARY =
  '机械复核只证明一件事：讲稿里引用的代码确实存在，且与磁盘上的源码逐字符一致。' +
  '它不能证明「这句业务解释是对的」—— 那只有教师能判；' +
  '下面的通过数只说明「这台机器检查了什么」，不构成对内容的评价。'

// ---------------------------------------------------------------------------
// 口径文案 ↔ 引擎机制：机器可核对的唯一来源
// ---------------------------------------------------------------------------
/**
 * 与 `ImmersiveLesson.vue` 里那组同名常量**必须逐字相同**（两个组件讲的是同一台机器），
 * 且两者都要与 `engine/logic_platform/verification_manifest.json` 逐项相同。
 *
 * ⚠️ 这些 id 只给门禁读，**不许**渲染进 DOM；改引擎检查项时先改清单，再改这里，
 * 最后才改说明文案 —— 顺序反了就会出现"页面在说一台不存在的机器"。
 */
const VERIFICATION_MANIFEST_VERSION = '1.0'
const VERIFIED_CHECK_IDS = [
  'V01_path_relative',
  'V02_span_valid',
  'V03_excerpt_fidelity',
  'V04_hash_matches',
  'V05_segment_excerpt',
  'V06_symbol_exists',
  'V07_return_claim',
  'V08_return_ordinal',
  'V09_skipped_range',
  'V10_claim_has_evidence',
  'V11_evidence_checkable',
]
const VERIFIED_CHECK_SUMMARIES = [
  '文件是否为项目内相对路径',
  '行区间是否合法（起止行有序、且不超出文件总行数）',
  '摘录是否与磁盘源码逐字符一致',
  '摘录哈希是否对得上',
  '整段代码摘录是否也与磁盘源码逐字符一致',
  '被引用的函数是否真的存在于语法树里、且这一段落在它的行范围内',
  '声称的 return 行上是否真有 return',
  '「这是第几个 return」是否与重新数出来的序号对得上',
  '「后面几行不会执行」的区间是否真实存在于该函数内',
  '每条断言是否至少带一条可核验的证据',
  '每条证据是否都带非空摘录与哈希（否则它根本核不了）',
]
const VERIFIED_CHECKS_SUFFIX = '空壳证据按失败处理，不静默跳过'
const NARRATION_GATE_RULE_IDS = [
  'N1_model_gives_lines_not_code',
  'N2_span_inside_segment',
  'N3_reject_without_evidence',
  'N4_reverify_after_merge',
]
const CAN_PUBLISH_ALWAYS_FALSE = true

const VERIFICATION_LINES = [
  '引擎永远不会把「可发布」置为真：只有教师走审核接口确认过、且机械复核通过，这一课才会变成已确认；' +
    '发布权属于人，引擎只负责把证据摆齐。',
  '「重新校验」会调用后端把源码重新从磁盘读一遍再逐字符比对，' +
    '因此它给出的是"现在这一刻引用是否仍然成立"，而不是复用讲稿里上一次的结论。',
  '源码一旦变化，此前的人工审核会自动失效（stale）：界面会明写「审核已失效」并退回待确认，' +
    '绝不沿用一份已经作废的确认。',
  '机械复核逐项检查：' +
    VERIFIED_CHECK_SUMMARIES.join('、') +
    '（' + VERIFIED_CHECKS_SUFFIX + '）。',
  '它仍然检查不到"这几行代码是否真的支持这句话的结论"：行号与摘录是真的，' +
    '但语义上的推导只有人能判。所以任何一项失败只说明"引用层面不成立"，全部通过也只说明"引用层面成立"。',
  '当这一课是模型草稿（generated_by = llm_draft）时：模型只允许给行号、不允许给代码，' +
    '行范围必须落在本段内，摘录由引擎从磁盘重读并复核，模型返回的代码文本一律丢弃；' +
    '落不到段内证据上的条目会被拦下，并留在拦截清单里供评审查看。',
  '被拦截不等于"已删除"：被拦下的断言在讲稿里仍然显示（标红），因为评审要能看到系统抓到了什么。',
]

const props = defineProps({
  /** 当前讲稿（review / verification 都在它里面） */
  lesson: {
    type: Object,
    default: null,
  },
  /** 最近一次「重新校验」的返回：{lesson_id, capability_id, report, summary} */
  verification: {
    type: Object,
    default: null,
  },
  /** 讲解层状态：{enabled, reason, config, llm_in_critical_path, detached_from_engine, caveats} */
  narrationStatus: {
    type: Object,
    default: null,
  },
  /** 正在重跑校验 */
  verifying: {
    type: Boolean,
    default: false,
  },
  /** 正在请求讲解 */
  narrating: {
    type: Boolean,
    default: false,
  },
  /** 讲解请求的结果提示（503 原文等） */
  narrationNotice: {
    type: String,
    default: '',
  },
  /** 校验请求本身的失败原因 */
  error: {
    type: String,
    default: '',
  },
})

defineEmits(['verify', 'narrate', 'open-source'])

const review = computed(() => props.lesson?.review || {})
const humanReview = computed(() => review.value.human_review || {})

/**
 * 校验报告的来源优先级：**刚跑完的那一次**优先。
 * 讲稿里的 verification 是"生成这一课时"的结果；重新校验的结果是"现在这一刻"的结果。
 * 两者可能不同（源码被改过），所以必须标清楚看的是哪一份。
 */
const report = computed(() => props.verification?.report || props.lesson?.verification || {})
const summary = computed(() => props.verification?.summary || null)

const verifyError = computed(() => props.error || '')

const isLlmDraft = computed(() => String(review.value.generated_by || '') === 'llm_draft')

/** 发布闸门：只读契约，不做任何"推算"。 */
const canPublish = computed(() => review.value.can_publish === true)
const summaryCanPublish = computed(() => summary.value?.can_publish === true)
const summaryConclusion = computed(() => String(summary.value?.conclusion || '').trim())

const summaryMeta = computed(() =>
  summaryCanPublish.value
    ? { label: '本次校验：可发布', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' }
    : { label: '本次校验：不可发布', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30' })

const blockingIssues = computed(() => {
  const list = review.value.blocking_issues
  return Array.isArray(list) ? list.filter((x) => String(x || '').trim()) : []
})

const REVIEW_STATUS_META = {
  needs_review: { label: '待教师确认', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30' },
  approved: { label: '教师已确认', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' },
  rejected: { label: '已否决', cls: 'bg-red-500/10 text-red-400 border-red-500/30' },
}
const reviewStatusMeta = computed(
  () => REVIEW_STATUS_META[String(review.value.status || '')] || {
    label: '状态未标注',
    cls: 'bg-deep-card text-gray-500 border-deep-border',
  },
)

const GENERATED_META = {
  ast_rule_engine: {
    label: '规则引擎',
    cls: 'bg-neon-blue/10 text-neon-blue border-neon-blue/30',
    title: 'AST 规则确定性生成：无 LLM、无联网，同一份源码两次结果逐字节一致',
  },
  llm_draft: {
    label: '模型草稿',
    cls: 'bg-neon-purple/10 text-neon-purple border-neon-purple/30',
    title: '措辞由语言模型生成，因此强制 needs_review；模型给出的代码文本一律丢弃，代码只从磁盘重读',
  },
}
const generatedByMeta = computed(
  () => GENERATED_META[String(review.value.generated_by || '')] || {
    label: '生成主体未标注',
    cls: 'bg-deep-card text-gray-500 border-deep-border',
    title: '契约没有标注这一课是谁生成的 —— 如实显示，不代为归类',
  },
)

const ratioText = computed(() => {
  const v = review.value.llm_claim_ratio
  if (v === null || v === undefined || v === '') return ''
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  return `${Math.round(n * 100)}%`
})

/** 计数：用契约里的键，不重排、不合并。 */
const COUNT_LABELS = {
  checks: '检查项',
  passed: '通过',
  failed: '失败',
  skipped: '跳过',
  rejected_claims: '拦截断言',
  rejected_segments: '拦截段落',
}
const countEntries = computed(() => {
  const counts = report.value?.counts
  if (!counts || typeof counts !== 'object') return []
  return Object.keys(counts).map((key) => ({
    key,
    label: COUNT_LABELS[key] || key,
    value: counts[key],
    cls: key === 'failed' && Number(counts[key]) > 0
      ? 'bg-red-500/10 text-red-400 border-red-500/30'
      : key === 'passed'
        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
        : 'bg-deep-card text-gray-400 border-deep-border',
  }))
})

const checks = computed(() => (Array.isArray(report.value?.checks) ? report.value.checks : []))

/** 失败项数：用来决定「逐项明细」要不要默认展开（失败不许藏在一次点击之后）。 */
const failedCount = computed(() => checks.value.filter((c) => String(c?.status || '') === 'fail').length)

/**
 * 失败最前，然后 skipped，最后 pass。
 * **只排序、不丢弃**：任何一条检查都不许因为"看起来不重要"被吞掉。
 */
const STATUS_ORDER = { fail: 0, skipped: 1, pass: 2 }
const sortedChecks = computed(() =>
  [...checks.value].sort((a, b) => {
    const oa = STATUS_ORDER[String(a?.status || '')] ?? 3
    const ob = STATUS_ORDER[String(b?.status || '')] ?? 3
    if (oa !== ob) return oa - ob
    return String(a?.check_id || '').localeCompare(String(b?.check_id || ''))
  }),
)

const STATUS_META = {
  pass: { label: '通过', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' },
  fail: { label: '失败', cls: 'bg-red-500/10 text-red-400 border-red-500/40' },
  skipped: { label: '跳过', cls: 'bg-slate-500/10 text-slate-300 border-slate-500/40' },
}
function statusMeta(status) {
  return STATUS_META[String(status || '')] || {
    label: String(status || '未标注'),
    cls: 'bg-deep-card text-gray-500 border-deep-border',
  }
}

function checkRowCls(check) {
  if (check.status === 'fail') return 'border-red-500/40 bg-red-500/5'
  if (check.status === 'skipped') return 'border-slate-500/30 bg-deep-card/40'
  return 'border-deep-border bg-deep-card/40'
}

function checkLocation(check) {
  const path = toProjectRelative(check?.file)
  if (!path) return '位置未给出'
  const line = check?.line
  return Number.isFinite(Number(line)) ? `${path}:${Number(line)}` : path
}

const rejectedClaimIds = computed(() => (Array.isArray(report.value?.rejected_claim_ids) ? report.value.rejected_claim_ids : []))
const rejectedSegmentIds = computed(() => (Array.isArray(report.value?.rejected_segment_ids) ? report.value.rejected_segment_ids : []))

const claimDecisions = computed(() => {
  const claims = humanReview.value?.claims
  if (!claims || typeof claims !== 'object') return []
  return Object.keys(claims).map((claimId) => ({
    claim_id: claimId,
    decision: String(claims[claimId]?.decision || ''),
    note: String(claims[claimId]?.note || ''),
  }))
})

/** 讲解层的两个硬事实：它跟引擎解耦，且不在关键路径上。 */
const narrationFacts = computed(() => {
  const s = props.narrationStatus
  if (!s) return []
  const out = []
  if (s.llm_in_critical_path === false) out.push('讲解层不在关键路径上（llm_in_critical_path = false）：关掉它，事实层与证据校验一切照旧。')
  if (s.detached_from_engine === true) out.push('讲解层与引擎解耦（detached_from_engine = true）：它只改写措辞，不产生任何事实。')
  if (s.config && typeof s.config === 'object') {
    const keys = Object.keys(s.config)
    if (keys.length) out.push(`讲解层配置项：${keys.map((k) => `${k}=${s.config[k]}`).join('，')}`)
  }
  return out
})

const narrationCaveats = computed(() => (Array.isArray(props.narrationStatus?.caveats) ? props.narrationStatus.caveats : []))
</script>
