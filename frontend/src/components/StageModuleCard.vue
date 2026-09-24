<template>
  <div class="stage-module-card" data-test="stage-module-card-view">
    <!-- 加载 / 失败：不静默渲染空白（P0-09 的教训） -->
    <div v-if="loading" class="glass-card p-10 text-center text-gray-400 text-sm" data-test="module-card-loading">
      正在加载阶段二任务…
    </div>
    <div v-else-if="loadError" class="glass-card p-10 text-center" data-test="module-card-error">
      <div class="text-red-400 text-sm mb-2">无法加载项目「{{ projectId }}」的阶段二任务</div>
      <div class="text-xs text-gray-500 font-mono break-all">{{ loadError }}</div>
      <div class="text-xs text-gray-500 mt-3 leading-relaxed">
        阶段二的题目与卡片内容都由后端从业务图谱派生（题目配置在
        <span class="font-mono">engine/lexicon/stage_questions.json</span>）。
        离线演示模式下这一阶段不可用——**不在浏览器里另算一份**，否则两边的口径迟早会不一致。
      </div>
    </div>

    <div v-else class="space-y-6">
      <!-- ① 任务说明：只说清"要做什么"，不给任何比对答案 -->
      <section class="glass-card p-6 neon-border">
        <div class="flex items-start justify-between gap-4 mb-3">
          <div>
            <div class="text-xs text-gray-500 font-mono tracking-widest uppercase mb-1">Stage 2 · Module Card</div>
            <h2 class="text-lg font-bold text-white">{{ task?.stage_name_cn || '模块卡片学习' }}</h2>
            <p class="text-xs text-gray-400 mt-1 leading-relaxed">{{ task?.answer_prompt_cn }}</p>
          </div>
          <div class="text-right shrink-0">
            <div class="inline-flex text-[10px] px-1.5 py-0.5 rounded border bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                 data-test="module-card-coverage-only">
              {{ task?.scoring || 'fact_coverage_only' }}
            </div>
            <div class="text-[10px] text-gray-500 mt-2">
              {{ task?.counts?.cards || 0 }} 张卡片 · {{ task?.counts?.questions || 0 }} 个问题
            </div>
          </div>
        </div>

        <!-- 题面（题目文本来自后端配置，前端不认识任何一个业务字段） -->
        <ol class="space-y-1 mb-3">
          <li v-for="(q, i) in questions" :key="q.question_id" class="text-xs text-gray-300 flex gap-2">
            <span class="text-gray-600 font-mono">{{ i + 1 }}</span>
            <span>{{ q.text_cn }}</span>
          </li>
        </ol>

        <p class="text-[11px] text-gray-400 leading-relaxed" data-test="module-card-no-score">
          <span class="text-gray-200 font-semibold">本阶段不打分。</span>
          系统只做「事实覆盖比对」：看你的回答里提到了这张卡片上哪些已核实的事实、哪些还没提到。
          「提到」不等于「讲对了」——理解是否到位由教师看你的原话判断。
        </p>

        <div v-if="task?.caveats?.length" class="mt-3 pt-3 border-t border-deep-border" data-test="module-card-task-caveats">
          <div class="text-[11px] text-gray-500 mb-1">这份任务的边界（后端原文，不是免责声明）</div>
          <ul class="space-y-1">
            <li v-for="(line, i) in task.caveats" :key="i" class="text-[11px] text-gray-500 leading-relaxed flex gap-2">
              <span class="text-gray-600">·</span>
              <span>{{ line }}</span>
            </li>
          </ul>
        </div>
      </section>

      <!-- ② 选卡片：按一级域分组（分组与顺序都来自图谱，页面不写死任何模块名） -->
      <section class="glass-card p-6" data-test="module-card-picker">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-sm font-semibold text-white">先选一张卡片</span>
          <span class="text-[11px] text-gray-500">逐张打开，答完五个问题再换下一张</span>
        </div>

        <div class="space-y-4">
          <div v-for="group in groups" :key="group.domain_id" :data-domain-id="group.domain_id">
            <div class="flex items-center gap-2 mb-2 flex-wrap">
              <span class="text-xs font-semibold text-gray-300">{{ group.domain_name_cn }}</span>
              <span class="text-[10px] px-1.5 py-0.5 rounded border" :class="roleMeta(group.domain_role).cls">
                {{ roleMeta(group.domain_role).label }}
              </span>
              <span class="text-[10px] text-gray-600">{{ group.cards.length }} 张卡片</span>
            </div>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="item in group.cards"
                :key="item.module_id"
                class="text-left rounded-xl border px-3 py-2 transition-all max-w-[260px]"
                :class="item.module_id === selectedId
                  ? 'border-neon-blue/60 bg-neon-blue/10'
                  : 'border-deep-border bg-deep-card/40 hover:border-neon-blue/40'"
                data-test="module-card-option"
                :data-module-id="item.module_id"
                @click="selectCard(item.module_id)"
              >
                <div class="text-xs text-white truncate">{{ item.name_cn || item.module_id }}</div>
                <div class="flex items-center gap-1 mt-1 flex-wrap">
                  <span class="text-[10px] text-gray-500">{{ levelLabel(item.level) }}</span>
                  <ConfidenceBadge :value="item.confidence" />
                  <span v-if="item.card_needs_review"
                        class="text-[10px] px-1.5 py-0.5 rounded border bg-slate-500/10 text-slate-300 border-slate-500/40 border-dashed"
                        data-test="module-card-option-needs-review">
                    待教师确认
                  </span>
                </div>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- ③ 卡片 + 五问作答（学生先输出） -->
      <section v-if="card" class="glass-card p-6" data-test="module-card-panel">
        <div class="flex items-start justify-between gap-4 mb-3">
          <div>
            <div class="text-[11px] text-gray-500 font-mono">{{ card.module_id }}</div>
            <h3 class="text-base font-bold text-white" data-test="module-card-selected"
                :data-module-id="card.module_id">
              {{ card.name_cn || card.module_id }}
            </h3>
            <div class="flex items-center gap-2 mt-1 flex-wrap">
              <span class="text-[10px] text-gray-500">{{ levelLabel(card.level) }}</span>
              <ConfidenceBadge :value="card.confidence" />
              <span class="text-[10px] px-1.5 py-0.5 rounded border" :class="sourceMeta(card.source).cls">
                {{ sourceMeta(card.source).label }}
              </span>
              <span class="text-[10px] text-gray-500">所属：{{ card.domain_name_cn || '未归属到任何域' }}</span>
            </div>
          </div>
          <div class="text-right shrink-0">
            <button
              class="text-[11px] px-3 py-1.5 rounded-lg border border-deep-border text-gray-300 hover:border-neon-blue/40"
              data-test="module-card-reveal"
              @click="revealed = !revealed"
            >
              {{ revealed ? '收起卡片内容' : '展开卡片内容' }}
            </button>
            <div class="text-[10px] text-gray-500 mt-1">建议先自己写，再对照</div>
          </div>
        </div>

        <!-- 卡片待确认提示：说清"哪几项老师还没确认"，而不是藏起来 -->
        <div v-if="card.card_needs_review" class="mb-3 rounded-lg border border-dashed border-slate-500/40 bg-deep-card/40 px-3 py-2"
             data-test="module-card-needs-review">
          <div class="text-xs text-slate-300">该卡片待教师确认</div>
          <div class="text-[11px] text-gray-500 mt-0.5">
            以下内容还没有人确认过，**不参与比对**：{{ card.pending_confirmation_fields.join('、') }}
          </div>
        </div>

        <!-- 卡片内容（学习材料；默认收起，学生可主动展开） -->
        <div v-if="revealed" class="mb-4 rounded-xl border border-deep-border bg-deep-card/40 p-4 space-y-3"
             data-test="module-card-reveal-panel">
          <div class="text-[11px] text-gray-500">
            这些是图谱里已有的内容（每条都带置信度；点出处可跳源码）。它们也是提交后比对的依据。
          </div>

          <div data-test="module-card-field" data-field="objective">
            <div class="text-[11px] text-gray-500 mb-1">模块目标</div>
            <div v-if="card.objective" class="text-xs text-gray-200 leading-relaxed">
              {{ card.objective }}
              <ConfidenceBadge :value="card.objective_confidence" class="ml-1" />
            </div>
            <div v-else class="text-xs text-gray-500">
              还没有教师填写（引擎推不出业务含义就不编）。
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div data-test="module-card-field" data-field="inputs">
              <div class="text-[11px] text-gray-500 mb-1">输入（状态读取 / 前置判断）</div>
              <div v-if="card.inputs.length || card.preconditions.length" class="text-xs text-gray-300 leading-relaxed">
                <span v-if="card.inputs.length" class="font-mono">{{ card.inputs.join(' · ') }}</span>
                <div v-for="fact in card.preconditions" :key="fact.fact_id" class="mt-1 flex items-start gap-2 flex-wrap">
                  <code class="text-[11px] text-amber-300 font-mono">{{ fact.code }}</code>
                  <button class="text-[10px] font-mono text-gray-500 hover:text-neon-blue break-all"
                          data-test="module-card-fact-location" @click="emitFact(fact)">
                    {{ factLocation(fact) }} ↗
                  </button>
                </div>
              </div>
              <div v-else class="text-xs text-gray-500">图谱里没有给出输入信息。</div>
            </div>

            <div data-test="module-card-field" data-field="outputs">
              <div class="text-[11px] text-gray-500 mb-1">输出（状态写入）</div>
              <div v-if="card.outputs.length" class="text-xs text-gray-300 font-mono">
                {{ card.outputs.join(' · ') }}
              </div>
              <div v-else class="text-xs text-gray-500">图谱里没有给出输出信息。</div>
            </div>
          </div>

          <div data-test="module-card-field" data-field="state_changes">
            <div class="text-[11px] text-gray-500 mb-1">状态变化（引擎记到的事实）</div>
            <div v-if="card.state_changes.length" class="space-y-1">
              <div v-for="fact in card.state_changes" :key="fact.fact_id" class="flex items-start gap-2 flex-wrap"
                   data-test="module-card-fact" :data-fact-id="fact.fact_id">
                <code class="text-[11px] text-neon-blue font-mono">{{ fact.code }}</code>
                <ConfidenceBadge :value="fact.confidence" />
                <button class="text-[10px] font-mono text-gray-500 hover:text-neon-blue break-all"
                        data-test="module-card-fact-location" @click="emitFact(fact)">
                  {{ factLocation(fact) }} ↗
                </button>
              </div>
            </div>
            <div v-else class="text-xs text-gray-500">图谱里没有给出状态变化。</div>
          </div>

          <div v-if="card.business_rules.length" data-test="module-card-field" data-field="business_rules">
            <div class="text-[11px] text-gray-500 mb-1">业务规则（引擎只给代码，不编语义）</div>
            <div class="space-y-1">
              <div v-for="fact in card.business_rules" :key="fact.fact_id" class="flex items-start gap-2 flex-wrap"
                   data-test="module-card-fact" :data-fact-id="fact.fact_id">
                <code class="text-[11px] text-amber-300 font-mono">{{ fact.code }}</code>
                <ConfidenceBadge :value="fact.confidence" />
                <button class="text-[10px] font-mono text-gray-500 hover:text-neon-blue break-all"
                        data-test="module-card-fact-location" @click="emitFact(fact)">
                  {{ factLocation(fact) }} ↗
                </button>
              </div>
            </div>
          </div>

          <div v-if="card.exceptions.length" data-test="module-card-field" data-field="exceptions">
            <div class="text-[11px] text-gray-500 mb-1">异常分支</div>
            <div class="space-y-1">
              <div v-for="fact in card.exceptions" :key="fact.fact_id" class="flex items-start gap-2 flex-wrap">
                <code class="text-[11px] text-red-300 font-mono">{{ fact.code }}</code>
                <button class="text-[10px] font-mono text-gray-500 hover:text-neon-blue break-all"
                        data-test="module-card-fact-location" @click="emitFact(fact)">
                  {{ factLocation(fact) }} ↗
                </button>
              </div>
            </div>
          </div>

          <div data-test="module-card-field" data-field="does_not">
            <div class="text-[11px] text-gray-500 mb-1">不负责什么</div>
            <ul v-if="card.does_not.length" class="space-y-1">
              <li v-for="(line, i) in card.does_not" :key="i" class="text-xs text-gray-300 leading-relaxed flex gap-2">
                <span class="text-gray-600">·</span><span>{{ line }}</span>
              </li>
            </ul>
            <div v-else class="text-xs text-gray-500">图谱里没有给出「不负责什么」。</div>
            <div v-if="card.does_not.length" class="mt-1">
              <ConfidenceBadge :value="card.does_not_confidence" />
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div data-test="module-card-field" data-field="upstream_modules">
              <div class="text-[11px] text-gray-500 mb-1">上游模块</div>
              <div v-if="card.upstream_names.length" class="text-xs text-gray-300">
                {{ card.upstream_names.map((m) => m.name_cn || m.module_id).join(' · ') }}
              </div>
              <div v-else class="text-xs text-gray-500">图谱里没有给出上游模块。</div>
            </div>
            <div data-test="module-card-field" data-field="downstream_modules">
              <div class="text-[11px] text-gray-500 mb-1">下游模块</div>
              <div v-if="card.downstream_names.length" class="text-xs text-gray-300">
                {{ card.downstream_names.map((m) => m.name_cn || m.module_id).join(' · ') }}
              </div>
              <div v-else class="text-xs text-gray-500">图谱里没有给出下游模块。</div>
            </div>
          </div>
        </div>

        <!-- 五问作答区 -->
        <div class="space-y-3">
          <div v-for="(q, i) in questions" :key="q.question_id" data-test="module-card-question"
               :data-question-id="q.question_id">
            <div class="flex items-center gap-2 mb-1">
              <span class="text-xs font-semibold text-gray-200">{{ i + 1 }}. {{ q.text_cn }}</span>
              <span class="text-[10px] text-gray-600">{{ (answers[q.question_id] || '').length }} / {{ maxAnswerChars }}</span>
            </div>
            <textarea
              v-model="answers[q.question_id]"
              rows="3"
              :maxlength="maxAnswerChars"
              :placeholder="q.placeholder_cn"
              data-test="module-card-answer"
              :data-question-id="q.question_id"
              class="w-full rounded-xl bg-deep-card border border-deep-border px-4 py-3 text-sm text-gray-200
                     leading-relaxed focus:outline-none focus:border-neon-blue/50 resize-y"
              :disabled="submitting"
            ></textarea>
          </div>
        </div>

        <div class="flex items-center gap-3 mt-4 flex-wrap">
          <button
            class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all bg-gradient-to-r from-neon-blue to-neon-purple
                   disabled:opacity-40 disabled:cursor-not-allowed"
            data-test="module-card-submit"
            :disabled="!canSubmit"
            @click="submit"
          >
            {{ submitting ? '正在比对…' : '提交，看覆盖清单' }}
          </button>
          <span class="text-[11px] text-gray-500">至少回答一个问题</span>
          <span v-if="submitError" class="text-[11px] text-amber-400" data-test="module-card-submit-error">
            {{ submitError }}
          </span>
          <span class="text-[11px] text-gray-600 ml-auto">草稿只存在本机浏览器，不上传学生答案（换卡片 / 刷新后还在）</span>
        </div>
      </section>

      <!-- ④ 提交后才渲染的覆盖清单（提交前这里一个节点都没有） -->
      <section v-if="report" class="glass-card p-6" data-test="module-card-report">
        <div class="flex items-center gap-2 flex-wrap mb-1">
          <h3 class="text-base font-bold text-white">覆盖清单</h3>
          <span class="text-[10px] px-1.5 py-0.5 rounded border bg-emerald-500/10 text-emerald-400 border-emerald-500/30">
            {{ report.scoring }}
          </span>
          <span class="text-[10px] font-mono text-gray-600">{{ report.algorithm_version }}</span>
          <span class="text-[10px] text-gray-500">
            {{ report.module?.name_cn || report.module?.module_id }}
          </span>
        </div>

        <p class="text-xs text-gray-300 mb-4 leading-relaxed" data-test="module-card-report-no-score">
          <span class="text-white font-semibold">本阶段不打分、不给标准答案。</span>
          下面按问题列出：你的回答里提到了哪些事实、哪些还没有提到。
          「提到」不代表「答对」；覆盖不到也不等于答错——你写得对不对，由教师看你的原话判断。
        </p>

        <!-- 待教师确认的字段：说清楚，不许当成"你没提到" -->
        <div v-if="report.card_needs_review" class="mb-4 rounded-lg border border-dashed border-slate-500/40 bg-deep-card/40 px-3 py-2"
             data-test="module-card-report-needs-review">
          <div class="text-xs text-slate-300">该卡片待教师确认</div>
          <ul class="mt-1 space-y-0.5">
            <li v-for="(item, i) in report.unconfirmed_fields" :key="i" class="text-[11px] text-gray-500 leading-relaxed">
              · {{ item.label }}（{{ item.question_id }}）：{{ item.reason }}
            </li>
          </ul>
        </div>

        <div class="space-y-3">
          <div v-for="item in report.questions" :key="item.question_id" class="rounded-xl border border-deep-border bg-deep-card/30 p-4"
               data-test="module-card-question-result" :data-question-id="item.question_id">
            <div class="flex items-center gap-2 flex-wrap mb-2">
              <span class="text-xs font-semibold text-gray-200">{{ item.text_cn }}</span>
              <span class="text-[10px] text-gray-600">{{ item.answer_chars }} 字</span>
              <span v-if="item.empty_answer" class="text-[10px] px-1.5 py-0.5 rounded border bg-deep-card text-gray-400 border-deep-border">
                未作答
              </span>
              <span v-if="item.comparable" class="text-[10px] text-gray-500">
                比中 {{ groupKeys(item.matched_keys).length }} / {{ groupKeys(item.keys_considered).length }}
              </span>
            </div>

            <div v-if="!item.comparable" class="rounded-lg border border-dashed border-slate-500/40 bg-deep-card/40 px-3 py-2"
                 data-test="module-card-not-comparable">
              <div class="text-[11px] text-gray-400">本问题本次不参与比对</div>
              <div class="text-[11px] text-gray-500 mt-0.5">{{ item.not_comparable_reason }}</div>
            </div>

            <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <div class="text-[11px] text-emerald-400 mb-1">你提到了</div>
                <div v-if="!groupKeys(item.matched_keys).length"
                     class="text-[11px] text-gray-500 px-3 py-2 rounded-lg bg-deep-card border border-deep-border">
                  这一问暂时没有命中卡片上的事实。换个说法再说一遍也可以——覆盖清单会重新算。
                </div>
                <div class="space-y-1">
                  <div v-for="key in groupKeys(item.matched_keys)" :key="key.key"
                       class="rounded-lg border border-emerald-500/25 bg-emerald-500/5 px-3 py-1.5"
                       data-test="module-card-matched-key">
                    <div class="text-[11px] text-white break-all">{{ key.key }}</div>
                    <div class="text-[10px] text-gray-400 mt-0.5">
                      {{ key.origins.map(originLabel).join(' / ') }}
                      <span v-if="key.detail" class="font-mono text-gray-500"> · {{ key.detail }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <div class="text-[11px] text-amber-400 mb-1">还没提到</div>
                <div v-if="!groupKeys(item.missed_keys).length"
                     class="text-[11px] text-gray-500 px-3 py-2 rounded-lg bg-deep-card border border-deep-border">
                  这一问的事实都提到了。
                </div>
                <div class="space-y-1">
                  <div v-for="key in groupKeys(item.missed_keys)" :key="key.key"
                       class="rounded-lg border border-deep-border bg-deep-card/40 px-3 py-1.5"
                       data-test="module-card-missed-key">
                    <div class="text-[11px] text-gray-200 break-all">{{ key.key }}</div>
                    <div class="text-[10px] text-gray-500 mt-0.5">
                      {{ key.origins.map(originLabel).join(' / ') }}
                      <span v-if="key.detail" class="font-mono text-gray-600"> · {{ key.detail }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="report.caveats?.length" class="mt-5 pt-4 border-t border-deep-border" data-test="module-card-caveats">
          <div class="text-[11px] text-gray-500 mb-2">这份报告的边界（引擎原文，不是免责声明）</div>
          <ul class="space-y-1">
            <li v-for="(line, i) in report.caveats" :key="i" class="text-[11px] text-gray-400 leading-relaxed flex gap-2">
              <span class="text-gray-600">·</span><span>{{ line }}</span>
            </li>
          </ul>
        </div>

        <div class="text-[11px] text-gray-600 mt-3 font-mono">
          图谱 source_hash {{ (report.source_hash || '').slice(0, 12) || '未给出' }}
          · 卡片 {{ report.module?.module_id }}
          · 命中 {{ report.counts.matched_keys }} 条 / 未提到 {{ report.counts.unmatched_keys }} 条
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
/**
 * 阶段二「模块卡片学习」（培养方案第四章 阶段二）—— 培训六阶段里第二个落地的阶段。
 *
 * 这一阶段做什么
 * ==============
 * 学生逐张打开模块卡片，用**自己的话**回答五个问题（解决什么问题 / 接收什么输入 /
 * 输出什么结果 / 改变了什么状态 / 为什么不应该和其他模块合并）。系统**不打分**，
 * 只做**事实覆盖比对**：你的回答里提到了卡片上哪些已核实的事实、哪些还没提到。
 *
 * 四条纪律（与阶段一完全一致）
 * ============================
 *   1. **不打分**：页面明示 `fact_coverage_only`，且报告里没有任何分数字段；
 *   2. **先输出后反馈**：反馈区用 `v-if="report"`，**提交前一个节点都不渲染**（12.6 硬要求）；
 *   3. **无证据不比对**：置信度 `unconfirmed` 的字段不参与比对，
 *      页面直接提示「该卡片待教师确认」并列出是哪几项（既不藏起来，也不当成"你没提到"）；
 *   4. **判定不在这里**：比对与题目都在后端（`engine/teaching/card_coverage.py` +
 *      `engine/lexicon/stage_questions.json`）。离线时如实说不可用，而不是在浏览器里另算一份。
 *
 * 卡片内容为什么默认收起（一个刻意的取舍）
 * ========================================
 * 业务图谱页面（`BusinessGraphView`）里卡片是全字段可见的；但在阶段二，
 * 把卡片摊开放在问题旁边会让学生直接抄，训练就退化成阅读。
 * 所以这里默认只给卡片名与置信度徽章，**由学生主动点「展开卡片内容」**——
 * 想要对照时随时能看，但默认状态尊重"先自己想"。提交之后卡片内容不再隐藏。
 *
 * 数据来源
 * ========
 * `GET /teaching/module-card/task`（题目 + 卡片）+ `POST /teaching/module-card/coverage`（比对）。
 * 两者都由后端从 `business_graph` 派生：**换一个项目，页面代码一个字都不用改**。
 */
import { computed, onMounted, ref, watch } from 'vue'
import ConfidenceBadge from './ConfidenceBadge.vue'
import { loadModuleCardTask, evaluateModuleCardCoverage } from '../api/dataSource'
import { levelLabel, roleMeta, sourceMeta, toProjectRelative } from '../utils/businessGraph'

const props = defineProps({
  /** 项目 id：任务与比对都靠它定位 */
  projectId: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['open-source', 'evidence-viewed'])

const task = ref(null)
const loading = ref(false)
const loadError = ref('')

const selectedId = ref('')
const revealed = ref(false)
const answers = ref({})
const report = ref(null)
const submitting = ref(false)
const submitError = ref('')

const questions = computed(() => (Array.isArray(task.value?.questions) ? task.value.questions : []))
const cards = computed(() => (Array.isArray(task.value?.cards) ? task.value.cards : []))
const card = computed(() => cards.value.find((item) => item.module_id === selectedId.value) || null)
const maxAnswerChars = computed(() => Number(task.value?.answer_max_chars) || 1000)
const canSubmit = computed(
  () => !!card.value && !submitting.value
    && questions.value.some((q) => String(answers.value[q.question_id] || '').trim().length > 0),
)

/** 按一级域分组（分组与顺序都来自图谱；缺 domain_id 的卡片单独一组，不丢卡片）。 */
const groups = computed(() => {
  const out = []
  const index = new Map()
  for (const item of cards.value) {
    const key = item.domain_id || '__ungrouped__'
    if (!index.has(key)) {
      const group = {
        domain_id: key,
        domain_name_cn: item.domain_name_cn || '（未归属到任何一级域）',
        domain_role: item.domain_role,
        cards: [],
      }
      index.set(key, group)
      out.push(group)
    }
    index.get(key).cards.push(item)
  }
  return out
})

// ---------------------------------------------------------------------------
// 比对键的来源标签：学生要能看懂「系统是拿什么比出来的」
// ---------------------------------------------------------------------------
const ORIGIN_LABELS = {
  card_name: '卡片名称（去掉结构性词）',
  card_name_raw: '卡片名称原文',
  card_objective: '卡片目标文本',
  card_business_rule: '业务规则（代码表达式）',
  card_guard: '前置判断（代码表达式）',
  card_exception: '异常分支',
  card_state_path: '状态字段名',
  card_state_change_code: '状态变化原文',
  card_input: '输入字段名',
  card_output: '输出字段名',
  card_does_not: '「不负责什么」条目',
  card_upstream_name: '上游模块名',
  card_downstream_name: '下游模块名',
}

function originLabel(origin) {
  return ORIGIN_LABELS[String(origin || '')] || '比对键来源未标注'
}

/**
 * 同一个词可能来自多个字段（例如卡片名与目标文本恰好一样）。
 * 展示时按词合并、把来源并排列出——**不丢来源**，也不重复刷屏。
 */
function groupKeys(keys) {
  const out = []
  const index = new Map()
  for (const key of Array.isArray(keys) ? keys : []) {
    const text = String(key?.key ?? '')
    if (!text) continue
    if (!index.has(text)) {
      const item = { key: text, origins: [], detail: '' }
      index.set(text, item)
      out.push(item)
    }
    const item = index.get(text)
    if (key.origin && !item.origins.includes(key.origin)) item.origins.push(key.origin)
    if (!item.detail && key.detail) item.detail = key.detail
  }
  return out
}

// ---------------------------------------------------------------------------
// 草稿持久化（只存草稿，不存报告）
// ---------------------------------------------------------------------------
/**
 * 与阶段一同样的理由：报告是"针对某一份图谱的某一次回答"的结论，
 * 图谱换了（source_hash 变了）之后再把它显示出来就是拿旧结论糊弄学生。
 * 所以只持久化草稿与"上次学到哪张卡片"。
 */
function draftKey(projectId, moduleId) {
  return `lwai.modulecard.draft.${projectId || 'default'}.${moduleId || 'none'}`
}

function cardKey(projectId) {
  return `lwai.modulecard.card.${projectId || 'default'}`
}

function loadJSON(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function saveJSON(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* 隐私模式下 localStorage 不可用：只丢持久化能力，不影响训练 */
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
  revealed.value = false

  const res = await loadModuleCardTask(id)
  loading.value = false

  if (!res.ok) {
    task.value = null
    selectedId.value = ''
    loadError.value = res.error || '未知错误'
    return
  }

  task.value = res.data
  const remembered = String(loadJSON(cardKey(id), '') || '')
  const exists = cards.value.some((item) => item.module_id === remembered)
  selectedId.value = exists ? remembered : (cards.value[0]?.module_id || '')
  loadDraft()
}

function loadDraft() {
  const saved = loadJSON(draftKey(props.projectId, selectedId.value), {})
  const next = {}
  for (const q of questions.value) {
    next[q.question_id] = typeof saved?.[q.question_id] === 'string' ? saved[q.question_id] : ''
  }
  answers.value = next
}

function selectCard(moduleId) {
  if (moduleId === selectedId.value) return
  selectedId.value = moduleId
  // 换卡片 = 换题目：上一张卡片的报告必须清掉（不许拿旧结论冒充新结论）
  report.value = null
  submitError.value = ''
  revealed.value = false
  saveJSON(cardKey(props.projectId), moduleId)
  loadDraft()
}

onMounted(load)
watch(() => props.projectId, () => load())
watch(selectedId, (id) => saveJSON(cardKey(props.projectId), id))
watch(
  answers,
  (value) => {
    if (!selectedId.value) return
    saveJSON(draftKey(props.projectId, selectedId.value), value)
  },
  { deep: true },
)

// ---------------------------------------------------------------------------
// 证据跳转（项目内相对路径 + 行区间，P0-09）
// ---------------------------------------------------------------------------
function emitFact(fact) {
  if (!fact?.file) return
  emit('open-source', fact.file, fact.start_line, fact.end_line, fact.symbol || '')
}

/** 出处标签：**完整项目内相对路径 + 行号区间**（README5 §12.5 第 4 条，不许只显示文件名）。 */
function factLocation(fact) {
  const path = toProjectRelative(fact?.file)
  if (!path) return '出处未给出'
  const start = fact?.start_line
  const end = fact?.end_line
  if (!Number.isFinite(start)) return path
  if (!Number.isFinite(end) || end === start) return `${path}:${start}`
  return `${path}:${start}-${end}`
}

// ---------------------------------------------------------------------------
// 提交：学生先输出 → 系统后反馈
// ---------------------------------------------------------------------------
async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  submitError.value = ''
  // 重新提交时先清空上一份报告：不把旧结论留在屏幕上冒充新结论
  report.value = null

  const payload = {}
  for (const q of questions.value) {
    payload[q.question_id] = String(answers.value[q.question_id] || '')
  }

  const res = await evaluateModuleCardCoverage(props.projectId, selectedId.value, payload)
  submitting.value = false

  if (!res.ok) {
    submitError.value = res.error || '事实覆盖比对失败'
    return
  }
  report.value = res.data
}
</script>

<style scoped>
.stage-module-card textarea::placeholder {
  color: #4b5563;
}
</style>
