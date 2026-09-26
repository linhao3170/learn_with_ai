<template>
  <div class="glass-card p-5 space-y-5" data-test="immersive-lesson">
    <!-- 顶部：这一课是什么 + 它现在能不能给学生看 -->
    <header class="space-y-3">
      <div class="flex items-start justify-between gap-4 flex-wrap">
        <div class="min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <span class="w-1 h-5 bg-gradient-to-b from-neon-blue to-neon-purple rounded-full"></span>
            <span class="text-[10px] text-gray-500 font-mono tracking-widest uppercase">Immersive Business Logic</span>
          </div>
          <h2 class="text-xl font-bold gradient-text">{{ lesson?.title || '沉浸式学习业务逻辑' }}</h2>
          <div class="text-[11px] text-gray-500 font-mono mt-1 flex items-center gap-2 flex-wrap">
            <span>{{ lesson?.capability_id }}</span>
            <span class="text-gray-600">·</span>
            <span>板块 {{ lesson?.section_name || '—' }}</span>
            <span v-if="lesson?.level" class="text-gray-600">·</span>
            <span v-if="lesson?.level">级别 {{ lesson.level }}</span>
            <span v-if="lesson?.source_hash" class="text-gray-600">·</span>
            <span v-if="lesson?.source_hash" :title="lesson.source_hash">
              源码哈希 {{ lesson.source_hash.slice(0, 22) }}…
            </span>
          </div>
        </div>
        <div class="flex items-center gap-2 flex-wrap">
          <button
            class="px-3 py-1.5 text-xs border border-deep-border rounded-lg text-gray-400 hover:text-white hover:border-neon-blue/40 transition-all"
            data-test="lesson-verify"
            @click="$emit('verify')"
          >
            重新校验证据
          </button>
          <button
            class="px-3 py-1.5 text-xs border border-deep-border rounded-lg text-gray-400 hover:text-white hover:border-neon-blue/40 transition-all"
            data-test="lesson-close"
            @click="$emit('close')"
          >
            返回板块
          </button>
        </div>
      </div>

      <!-- 状态条：发布权在教师，引擎只负责把证据摆齐 -->
      <div class="flex items-center gap-2 flex-wrap text-[11px]" data-test="lesson-status-bar">
        <span
          class="px-2 py-0.5 rounded border font-medium"
          :class="statusMeta.cls"
          data-test="lesson-review-status"
          :data-review-status="review.status"
        >
          {{ statusMeta.label }}
        </span>
        <span
          class="px-2 py-0.5 rounded border font-mono"
          :class="review.verification_passed
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
            : 'bg-red-500/10 text-red-400 border-red-500/30'"
          data-test="lesson-verification-badge"
          :data-verification-passed="String(!!review.verification_passed)"
        >
          机械复核 {{ review.verification_passed ? '通过' : '未通过' }}
          （{{ review.verified_checks ?? 0 }} 通过 / {{ review.failed_checks ?? 0 }} 失败）
        </span>
        <span
          class="px-2 py-0.5 rounded border font-mono"
          :class="isLlmDraft
            ? 'bg-neon-purple/10 text-neon-purple border-neon-purple/30'
            : 'bg-deep-card text-gray-400 border-deep-border'"
          data-test="lesson-generated-by"
          :data-generated-by="review.generated_by"
          :title="isLlmDraft
            ? '讲解措辞由语言模型生成；事实与代码摘录仍全部来自 AST 与磁盘源码'
            : '讲解由 AST 规则确定性生成：无 LLM、无联网，同一份源码两次生成结果逐字节一致'"
        >
          {{ isLlmDraft ? '讲解：模型草稿' : '讲解：规则引擎' }}
        </span>
        <span
          v-if="isLlmDraft"
          class="px-2 py-0.5 rounded border border-deep-border text-gray-400 font-mono"
          data-test="lesson-llm-ratio"
        >
          模型占比 {{ Math.round((review.llm_claim_ratio || 0) * 100) }}%
        </span>
        <span
          v-if="humanReview.status === 'stale'"
          class="px-2 py-0.5 rounded border border-amber-500/40 bg-amber-500/10 text-amber-400 font-medium"
          data-test="lesson-review-stale"
        >
          审核已失效（源码变更后必须重新确认）
        </span>
      </div>

      <!--
        证据口径：摘要常驻（一句话），详述收起（点开才是完整边界）。
        这一屏的"复杂"集中在每条结论下面那串 `文件:行号` 上，所以先把
        「这些行号能证明什么、不能证明什么」讲清楚，再把逐条证据收进折叠区。
      -->
      <EvidenceNote
        test-id="lesson-evidence-note"
        label="证据口径"
        :summary="EVIDENCE_SUMMARY"
        :lines="EVIDENCE_LINES"
      />

      <!-- 拦截项：不许静默删除，必须显示出来 -->
      <ul
        v-if="review.blocking_issues?.length"
        class="text-[11px] text-amber-300/90 bg-amber-500/5 border border-amber-500/20 rounded-lg px-3 py-2 space-y-1"
        data-test="lesson-blocking-issues"
      >
        <li v-for="(item, index) in review.blocking_issues" :key="index" class="flex gap-2">
          <span class="text-amber-500/70 flex-shrink-0">·</span>
          <span>{{ item }}</span>
        </li>
      </ul>

      <p
        v-if="lesson?.truncated"
        class="text-[11px] text-gray-400 bg-deep-card/60 border border-deep-border rounded-lg px-3 py-2"
        data-test="lesson-truncated"
      >
        {{ lesson.truncation_reason }}
      </p>
    </header>

    <p v-if="loading" class="text-sm text-gray-400 py-8 text-center" data-test="lesson-loading">正在生成讲稿与校验…</p>
    <p v-else-if="error" class="text-sm text-red-400 py-4" data-test="lesson-error">{{ error }}</p>

    <template v-else-if="lesson">
      <!-- 课前：负荷免责 + 一句话定调（参考文档固定的开场） -->
      <div class="space-y-3" data-test="lesson-intro">
        <p class="text-sm text-gray-300 leading-relaxed">{{ lesson.intro }}</p>
        <p
          v-if="lesson.one_line_frame"
          class="text-sm text-neon-blue/90 leading-relaxed border-l-2 border-neon-blue/40 pl-3"
          data-test="lesson-frame"
        >
          {{ lesson.one_line_frame }}
        </p>
      </div>

      <!-- 逐段 -->
      <ol class="space-y-4">
        <li
          v-for="segment in lesson.segments || []"
          :key="segment.segment_id"
          class="border border-deep-border rounded-xl overflow-hidden bg-deep-card/40"
          data-test="lesson-segment"
          :data-segment-id="segment.segment_id"
          :data-segment-kind="segment.segment_kind"
        >
          <!-- 段头：严格使用 render.header_format（第 N 段：标题（起-止 行）） -->
          <div class="px-4 py-2.5 border-b border-deep-border bg-deep-surface/50 flex items-center justify-between gap-3 flex-wrap">
            <div class="min-w-0">
              <p
                v-if="segment.lead_in"
                class="text-[11px] text-gray-500 mb-0.5"
                data-test="segment-lead-in"
              >
                {{ segment.lead_in }}
              </p>
              <button
                class="text-left text-sm font-semibold text-white hover:text-neon-blue transition-colors"
                data-test="segment-header"
                :title="`点击跳到 ${segment.source.file}:${segment.source.start_line}`"
                @click="openSource(segment, `本段：${segment.title}`)"
              >
                {{ segment.header_text }}
              </button>
            </div>
            <div class="flex items-center gap-1.5 flex-wrap flex-shrink-0">
              <span class="text-[10px] font-mono px-1.5 py-0.5 rounded border border-deep-border text-gray-400">
                {{ kindMeta(segment.segment_kind).label }}
              </span>
              <span
                class="text-[10px] px-1.5 py-0.5 rounded border font-medium"
                :class="titleStatusMeta(segment.title_status).cls"
                :title="titleStatusMeta(segment.title_status).title"
                data-test="segment-title-status"
                :data-title-status="segment.title_status"
              >
                {{ titleStatusMeta(segment.title_status).label }}
              </span>
            </div>
          </div>

          <!-- 代码摘录：逐字渲染，绝不重排；关键行带教学注释并可点击跳源码 -->
          <div class="code-block rounded-none border-0" data-test="segment-code">
            <div
              v-for="line in linesOf(segment)"
              :key="line.number"
              class="code-line cursor-pointer"
              :class="{ highlighted: annotationAt(segment, line.number) }"
              :data-line="line.number"
              @click="openSource(segment, `第 ${line.number} 行`)"
            >
              <span class="whitespace-pre">{{ line.text === '' ? ' ' : line.text }}</span>
              <span
                v-if="annotationAt(segment, line.number)"
                class="ml-3 text-neon-cyan/80 italic"
                :data-annotation-role="annotationAt(segment, line.number).role"
              >
                {{ annotationAt(segment, line.number).text }}
              </span>
            </div>
          </div>

          <div class="px-4 py-3 space-y-3">
            <!-- 强调句：母本在分支段几乎必写的一句 -->
            <p
              v-if="segment.emphasis_line"
              class="text-xs text-neon-amber bg-neon-amber/5 border border-neon-amber/20 rounded-lg px-3 py-2"
              data-test="segment-emphasis"
            >
              {{ segment.emphasis_line }}
            </p>

            <!-- 分支的结构化事实：真假恒为"取决于输入" -->
            <dl
              v-if="segment.branch_detail"
              class="text-[11px] grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 bg-deep-surface/40 border border-deep-border rounded-lg px-3 py-2"
              data-test="segment-branch-detail"
            >
              <div v-if="segment.branch_detail.condition_code" class="flex gap-2 min-w-0">
                <dt class="text-gray-500 flex-shrink-0">条件</dt>
                <dd class="font-mono text-neon-blue/90 truncate" :title="segment.branch_detail.condition_code">
                  {{ segment.branch_detail.condition_code }}
                </dd>
              </div>
              <div class="flex gap-2">
                <dt class="text-gray-500 flex-shrink-0">真假</dt>
                <dd class="text-amber-300/90">
                  取决于输入（静态分析看不到运行数据，不替你判断）
                </dd>
              </div>
              <div v-if="segment.branch_detail.return_at_line" class="flex gap-2">
                <dt class="text-gray-500 flex-shrink-0">return</dt>
                <dd class="font-mono text-gray-300">
                  第 {{ segment.branch_detail.return_at_line }} 行
                  <span v-if="segment.branch_detail.return_ordinal_in_function" class="text-gray-500">
                    （函数内第 {{ segment.branch_detail.return_ordinal_in_function }} 个）
                  </span>
                </dd>
              </div>
              <div v-if="segment.branch_detail.raises" class="flex gap-2">
                <dt class="text-gray-500 flex-shrink-0">异常</dt>
                <dd class="text-red-300/90">主动抛出，这条业务路径在此中断</dd>
              </div>
              <div v-if="segment.branch_detail.skipped_line_range" class="flex gap-2 sm:col-span-2">
                <dt class="text-gray-500 flex-shrink-0">不会执行</dt>
                <dd class="font-mono text-gray-300">
                  第 {{ segment.branch_detail.skipped_line_range.start_line }}-{{
                    segment.branch_detail.skipped_line_range.end_line
                  }} 行
                </dd>
              </div>
            </dl>

            <!-- 重点记什么 -->
            <div v-if="segment.must_remember?.length" data-test="segment-bullets">
              <p class="text-xs font-semibold text-gray-300 mb-1.5">
                {{ render.bullets_heading }}
              </p>
              <ul class="space-y-1.5">
                <li
                  v-for="claim in segment.must_remember"
                  :key="claim.claim_id"
                  class="text-[12.5px] leading-relaxed flex gap-2"
                  :class="claim.verified === false ? 'text-red-300/90' : 'text-gray-300'"
                  data-test="segment-bullet"
                  :data-claim-id="claim.claim_id"
                  :data-verified="String(claim.verified !== false)"
                >
                  <span class="text-gray-600 flex-shrink-0">-</span>
                  <div class="min-w-0 space-y-1">
                    <p>
                      {{ claim.claim_text }}
                      <span
                        v-if="claim.verified === false"
                        class="ml-1 px-1.5 py-0.5 rounded text-[10px] bg-red-500/10 text-red-400 border border-red-500/30"
                        :title="claim.reject_reason"
                        data-test="bullet-intercepted"
                      >
                        已拦截：{{ claim.reject_reason }}
                      </span>
                    </p>
                    <!--
                      佐证收进折叠区，主张留在外面：
                      - **常驻**：断言原文 + 置信度 / 生成主体 / 已拦截徽章（判断该用多严的眼光看它，
                        靠的就是这三个标记，收起来等于把判断依据藏了）；
                      - **收起**：逐条 `文件:行号` 证据 + 教师标注按钮（数量写在折叠头上，
                        收起不等于删掉，它们仍然在 DOM 里，点一下就能跳源码）。
                    -->
                    <div class="flex items-center gap-1.5 flex-wrap">
                      <ClaimBadge
                        :confidence="claim.confidence"
                        :generated-by="claim.generated_by || review.generated_by"
                        :verified="claim.verified !== false"
                        :reject-reason="claim.reject_reason"
                        :review-decision="decisions[claim.claim_id]?.decision || ''"
                      />
                      <EvidenceFold
                        class="w-full"
                        label="逐条证据与教师标注"
                        :count="(claim.evidence || []).length"
                        :test-id="`claim-fold-${claim.claim_id}`"
                        :default-open="claim.verified === false"
                        hint="点开看这条结论引用的代码位置，并对它做教师标注"
                      >
                        <div class="flex items-center gap-1.5 flex-wrap">
                          <button
                            v-for="(item, index) in claim.evidence || []"
                            :key="`${claim.claim_id}-ev-${index}`"
                            class="text-[10px] font-mono px-1.5 py-0.5 rounded border border-deep-border text-gray-500 hover:text-neon-blue hover:border-neon-blue/40 transition-all"
                            :title="evidenceTitle(item)"
                            data-test="claim-evidence"
                            @click="openEvidence(item, `断言 ${claim.claim_id} 的证据`)"
                          >
                            {{ item.file }}:{{ item.start_line }}-{{ item.end_line }}
                          </button>
                          <span
                            v-if="!(claim.evidence || []).length"
                            class="text-[10px] text-gray-500"
                          >
                            这条断言没有证据条目（无证据的断言不会被当作结论）。
                          </span>
                        </div>
                        <div class="flex items-center gap-2 pt-1" data-test="claim-review-actions">
                          <button
                            class="text-[10px] px-1.5 py-0.5 rounded border transition-all"
                            :class="decisions[claim.claim_id]?.decision === 'confirm'
                              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                              : 'border-deep-border text-gray-500 hover:text-emerald-300 hover:border-emerald-500/40'"
                            @click="setDecision(claim.claim_id, 'confirm')"
                          >
                            确认
                          </button>
                          <button
                            class="text-[10px] px-1.5 py-0.5 rounded border transition-all"
                            :class="decisions[claim.claim_id]?.decision === 'reject'
                              ? 'bg-red-500/20 text-red-300 border-red-500/40'
                              : 'border-deep-border text-gray-500 hover:text-red-300 hover:border-red-500/40'"
                            @click="setDecision(claim.claim_id, 'reject')"
                          >
                            有问题
                          </button>
                        </div>
                      </EvidenceFold>
                    </div>
                  </div>
                </li>
              </ul>
            </div>

            <!-- 知道就行：把不必深入的外部调用分流出去 -->
            <div v-if="segment.know_enough?.length" data-test="segment-know-enough">
              <p class="text-xs font-semibold text-gray-500 mb-1.5">{{ render.know_enough_heading }}</p>
              <ul class="space-y-1">
                <li
                  v-for="claim in segment.know_enough"
                  :key="claim.claim_id"
                  class="text-[12px] leading-relaxed text-gray-500 flex gap-2"
                >
                  <span class="flex-shrink-0">-</span>
                  <span>{{ claim.claim_text }}</span>
                </li>
              </ul>
            </div>

            <!-- 一句话概括（标题字面量含尾随空格，直接用契约里的 render 常量） -->
            <p
              v-if="segment.one_sentence_summary"
              class="text-[12.5px] text-neon-green/90 leading-relaxed bg-neon-green/5 border border-neon-green/20 rounded-lg px-3 py-2"
              data-test="segment-summary"
            >
              <span class="font-semibold">{{ render.summary_heading }}</span
              >{{ segment.one_sentence_summary.claim_text }}
              <button
                v-for="(item, index) in segment.one_sentence_summary.evidence || []"
                :key="`sum-ev-${index}`"
                class="ml-2 text-[10px] font-mono px-1.5 py-0.5 rounded border border-neon-green/25 text-neon-green/70 hover:text-neon-green transition-all"
                :title="evidenceTitle(item)"
                data-test="summary-evidence"
                @click="openEvidence(item, '总结句的证据')"
              >
                {{ item.file }}:{{ item.start_line }}-{{ item.end_line }}
              </button>
            </p>
          </div>
        </li>
      </ol>

      <!-- 课后：路径表 + 记住 N 件事 + 消化 -->
      <section v-if="summaryTable.rows.length" class="space-y-2" data-test="lesson-summary-diagram">
        <p class="text-xs font-semibold text-gray-300">{{ summaryTable.heading }}</p>
        <div class="overflow-x-auto border border-deep-border rounded-lg">
          <table class="w-full text-[11.5px]">
            <thead class="bg-deep-surface/60">
              <tr>
                <th
                  v-for="(head, index) in summaryTable.headers"
                  :key="`h-${index}`"
                  class="text-left px-3 py-2 text-gray-400 font-medium whitespace-nowrap"
                >
                  {{ head }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, index) in summaryTable.rows"
                :key="`r-${index}`"
                class="border-t border-deep-border/60"
              >
                <td
                  v-for="(cell, cellIndex) in row"
                  :key="`c-${index}-${cellIndex}`"
                  class="px-3 py-1.5 text-gray-300 whitespace-nowrap"
                  :class="cellIndex === 0 ? 'font-mono text-gray-500' : ''"
                >
                  {{ cell }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="lesson.lesson_recap?.length" class="space-y-2" data-test="lesson-recap">
        <p class="text-xs font-semibold text-gray-300">
          {{ recapHeading }}
        </p>
        <ol class="space-y-1.5">
          <li
            v-for="(item, index) in lesson.lesson_recap"
            :key="`recap-${index}`"
            class="text-[12.5px] text-gray-300 leading-relaxed flex gap-2"
          >
            <span class="text-neon-purple/70 font-mono flex-shrink-0">{{ index + 1 }}.</span>
            <span>{{ item }}</span>
          </li>
        </ol>
      </section>

      <p class="text-sm text-gray-400 leading-relaxed" data-test="lesson-consolidate">
        {{ lesson.consolidate }}
      </p>

      <!-- 口径与边界：契约里的 caveats 必须能看见，不许丢 -->
      <details class="border border-deep-border rounded-lg" data-test="lesson-caveats">
        <summary class="px-3 py-2 text-xs text-gray-400 cursor-pointer hover:text-gray-200">
          口径与边界（{{
            (lesson.caveats?.length || 0) + (lesson.verification?.caveats?.length || 0)
          }} 条，含已知覆盖缺口）
        </summary>
        <ul class="px-4 pb-3 space-y-1.5 text-[11.5px] text-gray-500 leading-relaxed">
          <li v-for="(item, index) in lesson.caveats || []" :key="`cv-${index}`" class="flex gap-2">
            <span class="flex-shrink-0">·</span><span>{{ item }}</span>
          </li>
          <li
            v-for="(item, index) in lesson.verification?.caveats || []"
            :key="`vcv-${index}`"
            class="flex gap-2"
          >
            <span class="flex-shrink-0">·</span><span>{{ item }}</span>
          </li>
        </ul>
      </details>

      <!-- 教师审核：发布权在这里 -->
      <footer class="flex items-center justify-between gap-3 flex-wrap border-t border-deep-border pt-4">
        <p class="text-[11px] text-gray-500 max-w-xl leading-relaxed">
          发布权在教师：机械复核只能证明「这句话引用的代码确实存在且逐字符一致」，
          不能证明「这句业务解释是对的」。确认后本课才会进入 <span class="font-mono">approved</span>；
          源码一旦变化，本次确认自动失效。
        </p>
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-[11px] text-gray-500" data-test="decision-count">
            已标记 {{ decidedCount }} / {{ totalClaims }} 条
          </span>
          <button
            class="px-3 py-1.5 text-xs rounded-lg border border-red-500/40 text-red-300 hover:bg-red-500/10 transition-all"
            data-test="lesson-reject"
            @click="$emit('review', { status: 'rejected', claims: decisionsPayload(), reviewer: '教师', note: '本课有问题' })"
          >
            标记本课有问题
          </button>
          <button
            class="px-3 py-1.5 text-xs rounded-lg bg-gradient-to-r from-neon-blue to-neon-purple text-white font-medium hover:-translate-y-0.5 transition-all"
            data-test="lesson-confirm"
            @click="$emit('review', { status: 'confirmed', claims: decisionsPayload(), reviewer: '教师' })"
          >
            确认本课（教师）
          </button>
        </div>
      </footer>
    </template>
  </div>
</template>

<script setup>
/**
 * 沉浸式学习业务逻辑 · 讲稿渲染器
 * ==================================
 * 为什么有这个组件：把「逐段精读」这种讲课形态做成可复核的界面。
 * 它复刻的是参考文档（D:\wengdang\shuliyewu.txt）的排版：
 *
 *   第 1 段：准备工作（175-188 行）
 *   <真实源码摘录，关键行带教学注释>
 *   重点记什么：
 *   - ...
 *   一句话概括： ...
 *
 * 三条不可妥协的规矩（README §2.2 / §10.5 / §13.6）
 * ------------------------------------------------
 * 1. **字面模板全部来自契约的 `render` 块**，前端一个字符串都不硬编码 ——
 *    包括「一句话概括：」冒号后面那个半角空格。改了它就不再是那份文档的形态。
 * 2. **代码摘录逐字渲染**。`code_excerpt` 是校验器拿磁盘源码逐字符比对过的，
 *    这里做任何"美化"（换行重排、去缩进、语法高亮重写）都会让界面与校验对象不一致。
 *    所以这里只按 `\n` 切行、按行号对齐，不做别的。
 * 3. **被拦截的断言照原样显示并标红**，不静默删除。评审要能看到"系统抓到了什么"，
 *    而不是只看到一份干净结果 —— 悄悄少显示几条，等于把幻觉藏起来。
 *
 * 它刻意不做什么
 * --------------
 * - 不自己算分数、不判断对错：置信度与审核状态全部读契约字段；
 * - 不把「机械复核通过」翻译成「内容正确」—— 页面上写死这句区分；
 * - 不自动替教师确认：`can_publish` 只有走审核接口才会变 True。
 */
import { computed, reactive } from 'vue'
import ClaimBadge from './ClaimBadge.vue'
// 证据折叠一轮：佐证默认收起、口径摘要常驻（两个组件在反幻觉面板里同样复用）
import EvidenceFold from './EvidenceFold.vue'
import EvidenceNote from './EvidenceNote.vue'

const props = defineProps({
  /** 讲稿契约（GET /api/logic-platform/{id}/lessons/{capability_id}） */
  lesson: { type: Object, required: true },
  /** 可选：最近一次校验报告（POST .../verify 的返回）；不传则用讲稿自带的 verification */
  verification: { type: Object, default: null },
  /** 分析 id（用于证据跳转时回传，组件本身不发请求） */
  analysisId: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['close', 'open-source', 'verify', 'review'])

/**
 * 证据口径（摘要常驻 + 详述收起）
 * ================================
 * 这张讲稿上每一句结论下面都挂着一串 `文件:行号`。**引用成立 ≠ 解释正确**——
 * 这句话必须写在证据旁边，否则读的人会把"机械复核通过"当成"业务解释也是对的"。
 *
 * 下面每一条都对应可执行的事实，不是形容词：
 * - 复核了什么：`engine/logic_platform/verify.py` 的检查项（路径纪律 / 行区间 / 摘录逐字符 /
 *   哈希 / 段落摘录 / 符号存在 / return 行与序号 / 「不会执行」的区间 / 每条断言必须有可核验的证据）；
 * - 模型把关：`engine/logic_platform/narration.py` 的四条规则（只给行号不给代码、行范围必须落在本段内、
 *   落不到证据上的条目直接拒绝并留痕、合并后必须重跑校验器）。
 */
const EVIDENCE_SUMMARY =
  '断言下面的证据只证明一件事：那几行代码确实存在、且与磁盘上的源码逐字符一致。' +
  '它不证明「这句业务解释是对的」—— 那只有教师能判。'

const EVIDENCE_LINES = [
  '证据是一段「文件:行号」，点它就打开源码：看的是磁盘上此刻的内容，而不是讲稿里抄下来的一份副本。',
  '机械复核逐项检查：文件是否为项目内相对路径、行区间是否合法、摘录是否与磁盘源码逐字符一致、摘录哈希是否对得上、' +
    '被引用的函数是否真的存在于语法树里、声称的 return 行与它的序号是否真的对得上、「后面不会执行」的区间是否真实，' +
    '以及每一条断言是否至少带一条可核验的证据（空壳证据按失败处理，不静默跳过）。',
  '机械复核**检查不到**的是：这几行代码是否真的支持这句话的结论。行号是真的、摘录是真的，' +
    '但「由它推出这条业务解释」这一步是语义判断，机器不做这个判断 —— 这就是发布权交给教师的原因。',
  '当徽章写「模型草稿」时（讲解措辞由语言模型渲染）：模型只允许给行号、不允许给代码；' +
    '它给的行范围必须落在本段自己的行范围内；每段摘录都由引擎重新从磁盘读取并再次比对，模型返回的代码文本一律丢弃。' +
    '所以「引用了一段根本不存在的代码」这类幻觉会被机械复核拦下。',
  '仍然可能残留的幻觉风险（据实写出，不粉饰）：行号真实但相关性不成立——这句结论其实不是这几行支持的；' +
    '段标题若标着「标题：引擎推断」，那个名字本身是引擎推断的；分支的真假不断言（静态阅读看不到运行时的输入）。' +
    '遇到这类地方，请点开行号自己核一遍，或用「有问题」把它标出来。',
  '被拦截的断言不会被删掉：它标红显示，并带上后端给出的拦截原因 —— 评审要能看到系统抓到了什么。' +
    '机械复核未通过的内容进不了「已发布」；即使全部通过，也要教师确认过才会变成已确认。',
]

/** 教师对单条断言的标记（提交前只存在本地） */
const decisions = reactive({})

const render = computed(() => props.lesson?.render || {})
const review = computed(() => props.lesson?.review || {})
const humanReview = computed(() => review.value.human_review || {})
const isLlmDraft = computed(() => String(review.value.generated_by || '') === 'llm_draft')

const verification = computed(() => props.verification || props.lesson?.verification || {})

const STATUS_META = {
  needs_review: { label: '待教师确认（未发布）', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30' },
  approved: { label: '教师已确认', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' },
  rejected: { label: '已拦截（未通过校验）', cls: 'bg-red-500/10 text-red-400 border-red-500/30' },
}
const statusMeta = computed(
  () => STATUS_META[String(review.value.status || '')] || STATUS_META.needs_review,
)

/** 段种类 → 中文标签。只做映射，不"提升"含义。 */
const KIND_LABELS = {
  prepare: '准备/取数',
  call: '业务动作',
  branch: '分支',
  state_change: '状态变化',
  exception: '容错（接住异常）',
  raise: '主动抛出',
  loop: '循环',
  return: '返回',
  config_data: '配置/数据',
  wrap_up: '收尾',
}
function kindMeta(kind) {
  return { label: KIND_LABELS[String(kind || '')] || '未标注' }
}

/**
 * 段标题的来源 —— 必须显示。
 * `from_structure` 是代码事实；`from_capability_name` 是引擎推断（那个名字本身可能是 inferred）。
 * 两者混着信是这一层最危险的事，所以给不同的样式与 tooltip。
 */
const TITLE_STATUS_META = {
  from_structure: {
    label: '标题：结构推导',
    cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    title: '标题由代码结构推导（如「提前返回」「容错处理」），是代码事实',
  },
  from_capability_name: {
    label: '标题：引擎推断',
    cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    title: '标题取自图谱里的能力点中文名 —— 该名字本身是引擎推断（inferred），需教师确认',
  },
  from_docstring: {
    label: '标题：源码注释',
    cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    title: '标题取自源码 docstring，作者原文',
  },
}
function titleStatusMeta(status) {
  return (
    TITLE_STATUS_META[String(status || '')] || {
      label: '标题：未标注',
      cls: 'bg-deep-card text-gray-500 border-deep-border',
      title: '契约未标注标题来源 —— 如实显示"未标注"，不代为归类',
    }
  )
}

/** 把 code_excerpt 按真实行号切成行（不做任何重排）。 */
function linesOf(segment) {
  const start = Number(segment?.source?.start_line || 0)
  const text = String(segment?.code_excerpt ?? '')
  return text.split('\n').map((line, index) => ({ number: start + index, text: line }))
}

/** 某一行有没有教学注释。 */
function annotationAt(segment, lineNumber) {
  const found = (segment?.line_annotations || []).find((a) => Number(a.line) === Number(lineNumber))
  return found || null
}

function evidenceTitle(item) {
  const reason = item?.reason ? `\n依据：${item.reason}` : ''
  const excerpt = item?.excerpt ? `\n\n${item.excerpt}` : ''
  return `${item?.file}:${item?.start_line}-${item?.end_line}${reason}${excerpt}`
}

function openSource(segment, hint) {
  const source = segment?.source || {}
  emit(
    'open-source',
    String(source.file || ''),
    Number(source.start_line || 0),
    Number(source.end_line || 0),
    hint || '',
  )
}

function openEvidence(item, hint) {
  emit('open-source', String(item?.file || ''), Number(item?.start_line || 0), Number(item?.end_line || 0), hint || '')
}

/** 课后路径表：把契约里的 markdown 表格渲染成真表格。 */
const summaryTable = computed(() => {
  const raw = String(props.lesson?.summary_diagram || '')
  const rows = []
  let heading = ''
  let headers = []
  for (const line of raw.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed) continue
    if (!trimmed.startsWith('|')) {
      if (!heading) heading = trimmed
      continue
    }
    const cells = trimmed
      .replace(/^\|/, '')
      .replace(/\|$/, '')
      .split('|')
      .map((cell) => cell.trim())
    // 分隔行（|---|---|）跳过
    if (cells.every((cell) => /^-{2,}$/.test(cell) || cell === '')) continue
    if (!headers.length) {
      headers = cells
      continue
    }
    rows.push(cells)
  }
  return { heading, headers, rows }
})

const recapHeading = computed(() => {
  const template = render.value.lesson_recap_heading || '你现在需要记住的 {n} 个核心要点：'
  return template.replace('{n}', String(props.lesson?.lesson_recap?.length || 0))
})

const totalClaims = computed(() => {
  let count = 0
  for (const segment of props.lesson?.segments || []) {
    count += (segment.must_remember || []).length
    count += (segment.know_enough || []).length
    if (segment.one_sentence_summary) count += 1
  }
  return count
})

const decidedCount = computed(() => Object.keys(decisions).length)

function setDecision(claimId, decision) {
  if (!claimId) return
  decisions[claimId] = { decision, note: '' }
}

function decisionsPayload() {
  const payload = {}
  for (const [claimId, value] of Object.entries(decisions)) {
    payload[claimId] = { decision: value.decision, note: value.note || '' }
  }
  return payload
}
</script>
