<template>
  <!--
    系统主页面（UI 重设计一轮）
    ============================================================================
    它回答的问题只有一个：**这个系统能为我做哪两件事，我该从哪儿进去。**

    排版优先级（这次改动的核心）：
      ① 两大核心功能 —— 培训系统 / 业务逻辑分析平台 —— 各占半屏，是页面上最大的两块；
      ② 六阶段与六步流程作为"大模块内部的细目"，点得动就直接进对应阶段；
      ③ 次级入口（业务图谱 / 函数级分析详情 / 来源依据）收成小模块；
      ④ **来源依据与口径默认收起**：证据一条都没删，只是不再和主功能抢第一屏。

    这个页面自己只做一件事：取项目列表与契约（用来显示项目名、题数、模块数），
    以及把选中的项目写回 ?project= 深链。它**不算任何业务结论** ——
    页面上出现的每个数字都来自契约字段或 dataSource 的模式判定。
  -->
  <div ref="rootRef" class="min-h-screen bg-grid relative overflow-hidden" data-test="home">
    <!-- 背景装饰：与训练页 / 平台页同一套 glow-orb 语言 -->
    <div class="glow-orb w-[720px] h-[720px] -top-56 right-[-220px] bg-neon-purple opacity-20"></div>
    <div class="glow-orb w-[540px] h-[540px] bottom-[-180px] left-[-140px] bg-neon-blue opacity-20"></div>

    <!-- 顶部条 -->
    <div class="fixed top-0 left-0 right-0 z-50 border-b border-deep-border/50 bg-deep-surface/70 backdrop-blur-xl">
      <div class="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between gap-4">
        <div class="flex items-center gap-3 min-w-0">
          <div class="relative flex-shrink-0">
            <span class="absolute inset-0 rounded-lg bg-neon-blue/40 animate-ring-pulse"></span>
            <div class="relative w-8 h-8 rounded-lg bg-gradient-to-br from-neon-blue via-neon-purple to-neon-pink flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="16 18 22 12 16 6"></polyline>
                <polyline points="8 6 2 12 8 18"></polyline>
              </svg>
            </div>
          </div>
          <div class="min-w-0">
            <div class="text-sm font-bold tracking-wide gradient-text">LearnWithAI</div>
            <div class="text-[10px] text-gray-500 font-mono tracking-wider">SYSTEM HOME · 业务逻辑思维培养平台</div>
          </div>
        </div>
        <div class="flex items-center gap-2 flex-shrink-0">
          <button class="home-user-chip" data-test="home-login" @click="loginOpen = true">
            <span class="w-5 h-5 rounded-full bg-neon-purple/30 text-neon-purple flex items-center justify-center text-[10px]">{{ currentUser ? currentUser.slice(0, 1).toUpperCase() : '?' }}</span>
            <span class="hidden sm:inline">{{ currentUser || '登录' }}</span>
          </button>
          <span
            class="text-[10px] px-1.5 py-0.5 rounded border font-mono"
            :class="online
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
              : 'bg-amber-500/10 text-amber-400 border-amber-500/30'"
            data-test="home-mode"
            :data-mode="online ? 'api' : 'offline'"
          >{{ online ? 'API' : '离线演示模式' }}</span>
          <button
            class="px-3 py-1.5 text-xs font-medium text-gray-400 hover:text-white border border-deep-border rounded-lg transition-all hover:border-neon-blue/30 hover:bg-neon-blue/5"
            data-test="home-refresh"
            :disabled="loading"
            @click="reload"
          >{{ loading ? '加载中…' : '刷新' }}</button>
        </div>
      </div>
    </div>

    <div class="relative z-10 max-w-6xl mx-auto px-6 pt-20 pb-20 space-y-10">
      <!-- ==================================================================
           一、身份区：这是什么、现在看的是哪个项目
           —— 刻意做得**紧凑**：标题与契约事实条并排，项目切换器只占一行，
              让下面那两块核心模块尽量落在第一屏里（它们是这个页面的主角）。
           ================================================================== -->
      <section class="space-y-4" data-layer data-test="home-hero">
        <div class="flex flex-wrap items-end justify-between gap-5">
          <div class="max-w-2xl">
            <div class="text-[11px] text-gray-500 font-mono tracking-[0.32em] uppercase mb-2">
              Business Logic Thinking · Training Platform
            </div>
            <h1 class="text-2xl md:text-[34px] font-bold leading-tight mb-3">
              把一份真实代码库，变成<span class="gradient-text">可教、可查、可复现</span>的业务逻辑
            </h1>
            <p class="text-sm text-gray-400 leading-relaxed">
              我们不只是代码分析工具。先用<span class="text-neon-blue">规则引擎</span>把代码解析成「业务图谱 + 代码证据」，
              再用<span class="text-neon-purple">六阶段训练</span>带学生从「看懂这个项目」走到「自己会设计」。
              页面上每一个结论都能回指到某个契约字段或某一行源码。
            </p>
          </div>

          <!-- 契约事实条：全部来自 loadContract 的返回，没有数字是页面自己算的 -->
          <div class="grid grid-cols-2 gap-2 w-full md:w-auto md:min-w-[280px]" data-layer data-test="home-stats">
            <div class="stat-tile">
              <div class="text-[10px] text-gray-500 mb-0.5">当前项目</div>
              <div class="text-[13px] font-mono text-white truncate" :title="projectId">{{ projectId }}</div>
            </div>
            <div class="stat-tile">
              <div class="text-[10px] text-gray-500 mb-0.5">契约版本</div>
              <div class="text-[13px] font-mono text-white">{{ contract?.contract_version || '—' }}</div>
            </div>
            <div class="stat-tile">
              <div class="text-[10px] text-gray-500 mb-0.5">训练题</div>
              <div class="text-[13px] font-mono text-white">
                {{ questionCount === null ? '—' : questionCount + ' 关' }}
              </div>
            </div>
            <div class="stat-tile">
              <div class="text-[10px] text-gray-500 mb-0.5">业务模块</div>
              <div class="text-[13px] font-mono text-white">
                {{ moduleCount === null ? '—' : moduleCount + ' 个' }}
              </div>
            </div>
          </div>
        </div>

        <!-- 项目切换器（在线/离线模式徽章与离线横幅都由它给出；P0-03 的深链也在这里写回） -->
        <ProjectSwitcher
          :projects="projects"
          :model-value="projectId"
          :mode="mode"
          :loading="loading"
          :error-detail="ds.lastError.value"
          :project-id="projectId"
          @update:model-value="onProjectChange"
          @refresh="reload"
        />

        <QuickSearch :items="searchItems" @select="onSearchSelect" />

        <p v-if="loadError" class="text-[11px] text-red-400/80 font-mono break-all" data-test="home-load-error">
          契约读取失败：{{ loadError }}（下面的两张卡片仍可进入，但页面上的统计会是「—」）
        </p>
      </section>

      <!-- ==================================================================
           二、两大核心功能（大模块化：各占一半，最大的两块）
           ================================================================== -->
      <section class="space-y-4" data-layer data-test="home-core-section">
        <div class="flex items-baseline justify-between gap-x-4 gap-y-1 flex-wrap">
          <div class="flex items-baseline gap-x-3 gap-y-1 flex-wrap">
            <span class="text-[11px] text-neon-blue/80 font-mono tracking-[0.3em] uppercase">01 / Core Modules</span>
            <h2 class="text-xl md:text-2xl font-bold text-white">两大核心功能</h2>
            <span class="text-xs text-gray-500">
              左边是「怎么教」，右边是「凭什么这么说」——它们共用同一份图谱与同一份源码副本
            </span>
          </div>
          <div class="text-[11px] text-gray-500 font-mono">点击任一模块进入 →</div>
        </div>

        <!-- lg 起：左卡 | 链 | 右卡；窄屏：竖排，链改成一段竖线 -->
        <div class="grid grid-cols-1 lg:grid-cols-[1fr_76px_1fr] gap-6 items-stretch">
          <!-- ---------------- 核心 1：培训系统 ---------------- -->
          <article
            class="module-block p-6 md:p-7 flex flex-col chain-pull-left"
            data-test="home-core-training"
          >
            <div class="sheen-layer"></div>

            <header class="flex items-start gap-4 mb-5">
              <div class="relative flex-shrink-0">
                <span class="absolute inset-0 rounded-2xl bg-neon-blue/30 animate-ring-pulse"></span>
                <div class="relative w-12 h-12 rounded-2xl bg-gradient-to-br from-neon-blue to-cyan-500 flex items-center justify-center text-2xl">
                  🎓
                </div>
              </div>
              <div class="min-w-0">
                <div class="text-[10px] font-mono tracking-wider text-neon-blue mb-1">核心功能 1 · 怎么教</div>
                <h3 class="text-lg md:text-xl font-bold text-white">培训系统 · 六阶段</h3>
                <p class="text-xs text-gray-400 mt-1 leading-relaxed">
                  学生先输出、系统后反馈。阶段一 / 二<span class="text-gray-300">不打分</span>，
                  设计画布<span class="text-gray-300">有分数，但算不出来的维度如实显示「本轮未评估」</span>。
                </p>
              </div>
            </header>

            <!-- 六阶段：点得动的才是"已落地"的阶段；没做的不给按钮（不把没做的说成做了） -->
            <div class="stage-list flex-1" data-test="home-stage-list">
              <button
                v-for="(stage, i) in TEACHING_STAGES"
                :key="stage.key"
                class="stage-row w-full text-left"
                :class="{
                  'is-clickable': stage.status === 'done',
                  'is-done': stage.status === 'done',
                  'opacity-60 cursor-not-allowed': stage.status !== 'done',
                }"
                :data-test="stage.status === 'done' ? 'home-stage-entry' : 'home-stage-todo'"
                :data-stage="stage.key"
                :disabled="stage.status !== 'done'"
                @click="enterTraining(stage.key)"
              >
                <span class="stage-dot">{{ i + 1 }}</span>
                <span class="min-w-0 flex-1">
                  <span class="stage-name flex items-center gap-2 flex-wrap">
                    <span class="text-sm font-medium text-gray-200">{{ stage.name }}</span>
                    <span
                      class="text-[10px] px-1.5 py-0.5 rounded border font-mono"
                      :class="stage.status === 'done'
                        ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                        : 'border-deep-border bg-deep-card/60 text-gray-500'"
                    >{{ stage.status === 'done' ? '已落地' : '未开始' }}</span>
                  </span>
                  <span class="block text-[11px] text-gray-500 mt-0.5 leading-relaxed">{{ stage.desc }}</span>
                </span>
                <svg
                  v-if="stage.status === 'done'"
                  class="flex-shrink-0 mt-1 text-gray-600" width="14" height="14" viewBox="0 0 24 24"
                  fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"
                >
                  <polyline points="9 18 15 12 9 6"></polyline>
                </svg>
              </button>
            </div>

            <!-- 既有主线：学生现在的主流程（旧四关题型）与业务图谱 -->
            <div class="mt-4 pt-4 border-t border-deep-border/70 space-y-2">
              <div class="text-[10px] text-gray-500 font-mono tracking-wider mb-1">既有主线</div>
              <button
                v-for="entry in TRAINING_ENTRIES"
                :key="entry.key"
                class="mini-module"
                data-test="home-training-entry"
                :data-stage="entry.key"
                @click="enterTraining(entry.key)"
              >
                <span class="text-lg leading-none">{{ entry.icon }}</span>
                <span class="min-w-0">
                  <span class="block text-sm text-gray-200">{{ entry.name }}</span>
                  <span class="block text-[11px] text-gray-500 mt-0.5">{{ entry.desc }}</span>
                </span>
                <span class="ml-auto text-[11px] font-mono text-gray-500 flex-shrink-0">
                  {{ entry.key === 'training' && questionCount !== null ? questionCount + ' 关' : '→' }}
                </span>
              </button>
            </div>

            <button
              class="mt-5 w-full px-5 py-3 rounded-xl text-sm font-medium text-white transition-all
                     bg-gradient-to-r from-neon-blue to-cyan-500 hover:shadow-lg hover:shadow-neon-blue/25 hover:-translate-y-0.5"
              data-test="home-enter-training"
              @click="enterTraining('training')"
            >
              进入培训系统 →
            </button>
          </article>

          <!-- ---------------- 链：把两个核心模块串起来 ---------------- -->
          <div class="hidden lg:flex flex-col items-center justify-center" data-test="home-chain">
            <div class="text-[10px] text-gray-600 font-mono mb-3 [writing-mode:vertical-rl]">SAME GRAPH</div>
            <div class="chain-rail w-full" :class="{ 'is-live': chainLive }">
              <span
                v-for="k in 5"
                :key="'knot-' + k"
                class="chain-knot"
                :style="{ left: (8 + (k - 1) * 21) + '%', '--i': k }"
              ></span>
              <span class="chain-car"></span>
            </div>
            <div class="text-[10px] text-gray-600 font-mono mt-3 [writing-mode:vertical-rl]">SAME SOURCE</div>
          </div>
          <div class="lg:hidden chain-rail-v" aria-hidden="true"></div>

          <!-- ---------------- 核心 2：业务逻辑分析平台 ---------------- -->
          <article
            class="module-block module-block--purple p-6 md:p-7 flex flex-col chain-pull-right"
            data-test="home-core-logic"
          >
            <div class="sheen-layer"></div>

            <header class="flex items-start gap-4 mb-5">
              <div class="relative flex-shrink-0">
                <span class="absolute inset-0 rounded-2xl bg-neon-purple/30 animate-ring-pulse"></span>
                <div class="relative w-12 h-12 rounded-2xl bg-gradient-to-br from-neon-purple to-neon-pink flex items-center justify-center text-2xl">
                  🔬
                </div>
              </div>
              <div class="min-w-0">
                <div class="text-[10px] font-mono tracking-wider text-neon-purple mb-1">核心功能 2 · 凭什么这么说</div>
                <h3 class="text-lg md:text-xl font-bold text-white">业务逻辑分析平台</h3>
                <p class="text-xs text-gray-400 mt-1 leading-relaxed">
                  投入项目 → 分析大小 → 按大小分流 → 板块看板 → 板块分析 → 沉浸式讲稿。
                  事实来自 AST，可复现；结论带置信度与出处。
                </p>
              </div>
            </header>

            <!-- 六步流程（与平台页的 STEPS 同一套文案，这里只做"预告"） -->
            <ol class="space-y-2 flex-1" data-test="home-logic-steps">
              <li
                v-for="(step, i) in LOGIC_STEPS"
                :key="step"
                class="flex items-center gap-3 text-[12px]"
              >
                <span class="w-5 h-5 flex-shrink-0 rounded-md border border-deep-border bg-deep-card/60
                             text-[10px] font-mono text-gray-400 flex items-center justify-center">{{ i + 1 }}</span>
                <span class="text-gray-300">{{ step }}</span>
                <span class="flex-1 h-px bg-gradient-to-r from-deep-border to-transparent"></span>
              </li>
            </ol>

            <!-- 三句立场：这个平台的可信度全押在这三句上，所以放在卡片里（细节收进抽屉） -->
            <div class="mt-4 space-y-1.5" data-test="home-logic-claims">
              <div class="text-[11px] text-gray-400"><span class="text-emerald-400">事实来自 AST，可复现</span></div>
              <div class="text-[11px] text-gray-400"><span class="text-amber-400">板块划分为引擎推断，待教师确认</span></div>
              <div class="text-[11px] text-gray-400"><span class="text-neon-blue">核心度排序是讲解顺序的参考信号</span></div>
            </div>

            <p
              v-if="!online"
              class="mt-4 text-[11px] text-amber-300/90 leading-relaxed"
              data-test="home-logic-offline-hint"
            >
              离线演示模式下这个平台不可用：大小定级 / 板块划分 / 讲稿与校验全部在后端执行，
              前端不会自己编一份看板出来。启动后端后即可进入。
            </p>

            <button
              class="mt-5 w-full px-5 py-3 rounded-xl text-sm font-medium text-white transition-all
                     bg-gradient-to-r from-neon-purple to-neon-pink hover:shadow-lg hover:shadow-neon-purple/25 hover:-translate-y-0.5"
              data-test="go-logic-platform"
              @click="$emit('enter-logic')"
            >
              进入业务逻辑分析平台 →
            </button>
          </article>
        </div>
      </section>

      <!-- ==================================================================
           三、次级入口（小型模块化）
           ================================================================== -->
      <section class="space-y-4" data-layer data-test="home-mini-section">
        <div class="flex items-baseline gap-x-3 flex-wrap">
          <span class="text-[11px] text-neon-purple/80 font-mono tracking-[0.3em] uppercase">02 / More</span>
          <h2 class="text-lg font-bold text-white">其他入口</h2>
          <span class="text-xs text-gray-500">次级视图与证据，收成小模块</span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            class="mini-module"
            data-test="home-mini-module"
            data-target="graph"
            @click="enterTraining('graph')"
          >
            <span class="text-xl leading-none">🕸️</span>
            <span class="min-w-0">
              <span class="block text-sm text-gray-200">业务图谱</span>
              <span class="block text-[11px] text-gray-500 mt-0.5 leading-relaxed">
                一级域 → 二级功能点 → 卡片 → 复杂度徽章 → 证据跳转
              </span>
            </span>
          </button>

          <button
            class="mini-module"
            data-test="home-mini-module"
            data-target="analysis"
            @click="$emit('view-analysis')"
          >
            <span class="text-xl leading-none">🧩</span>
            <span class="min-w-0">
              <span class="block text-sm text-gray-200">函数级分析详情</span>
              <span class="block text-[11px] text-gray-500 mt-0.5 leading-relaxed">
                旧版函数级 demo（概览 / 流程 / 调用链 / 代码证据）
              </span>
            </span>
          </button>

          <button
            class="mini-module"
            data-test="home-mini-module"
            data-target="evidence"
            @click="evidenceOpen = !evidenceOpen"
          >
            <span class="text-xl leading-none">📎</span>
            <span class="min-w-0">
              <span class="block text-sm text-gray-200">来源依据与口径</span>
              <span class="block text-[11px] text-gray-500 mt-0.5 leading-relaxed">
                数据从哪来、结论怎么算、哪些还没做（默认收起）
              </span>
            </span>
            <span class="ml-auto text-[11px] text-gray-500 flex-shrink-0">{{ evidenceOpen ? '收起' : '展开' }}</span>
          </button>
        </div>
      </section>

      <!-- ==================================================================
           四、来源依据与口径（可折叠 —— 证据一条不删，只是不抢第一屏）
           ================================================================== -->
      <section class="space-y-3" data-layer data-test="home-evidence-section">
        <button
          class="drawer-head"
          data-test="home-evidence-toggle"
          :aria-expanded="String(evidenceOpen)"
          @click="evidenceOpen = !evidenceOpen"
        >
          <span class="flex items-center gap-2 min-w-0">
            <span class="text-base leading-none">📎</span>
            <span class="text-sm text-gray-200">来源依据与口径</span>
            <span class="text-[11px] text-gray-500">
              数据来源 / 结论口径 / 判分边界 / 验收与门禁 / 还没做的
            </span>
          </span>
          <span class="flex items-center gap-2 flex-shrink-0">
            <span class="text-[11px] text-gray-500 font-mono">{{ evidenceOpen ? '收起' : '展开' }}</span>
            <svg
              class="drawer-chevron text-gray-500" :class="{ open: evidenceOpen }"
              width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"
            >
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </span>
        </button>

        <div class="drawer-body" :class="{ open: evidenceOpen }" data-test="home-evidence-body">
          <div class="drawer-inner">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              <div
                v-for="(group, gi) in EVIDENCE_GROUPS"
                :key="group.title"
                class="drawer-row glass-card p-4"
                :style="{ '--i': gi }"
                data-test="home-evidence-row"
              >
                <div class="text-xs font-semibold text-white mb-2 flex items-center gap-2">
                  <span class="w-1 h-3.5 rounded-full bg-gradient-to-b from-neon-blue to-neon-purple"></span>
                  {{ group.title }}
                </div>
                <ul class="space-y-1.5">
                  <li
                    v-for="line in group.lines"
                    :key="line"
                    class="text-[11px] text-gray-400 leading-relaxed flex gap-1.5"
                  >
                    <span class="text-gray-600 flex-shrink-0">·</span>
                    <span class="min-w-0 break-words">{{ line }}</span>
                  </li>
                </ul>
              </div>
            </div>

            <!-- 运行时的真实状态（不是写死在文案里的） -->
            <div class="drawer-row mt-3 glass-card p-4" :style="{ '--i': EVIDENCE_GROUPS.length }">
              <div class="text-xs font-semibold text-white mb-2 flex items-center gap-2">
                <span class="w-1 h-3.5 rounded-full bg-gradient-to-b from-emerald-400 to-neon-blue"></span>
                本次运行的实际来源
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1 text-[11px] font-mono text-gray-400">
                <div>模式：{{ online ? '在线 API（/api 经 vite 代理到后端）' : '离线快照（后端不可达）' }}</div>
                <div>项目：{{ projectId }}</div>
                <div>契约版本：{{ contract?.contract_version || '—' }}</div>
                <div>契约来源：{{ contractSource || '—' }}</div>
                <div class="md:col-span-2 break-all">
                  离线快照候选路径：{{ snapshotPaths.join(' ｜ ') }}
                </div>
                <div v-if="ds.lastError.value" class="md:col-span-2 text-amber-400/80 break-all">
                  最近一次错误：{{ ds.lastError.value }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
    <LoginDialog :open="loginOpen" @close="loginOpen = false" @guest="loginOpen = false" @submit="onLogin" />
  </div>
</template>

<script setup>
/**
 * 系统主页面
 * ==========
 * 结构：身份区（这是什么 / 现在看哪个项目）→ 两大核心功能（大模块）→ 其他入口（小模块）
 *      → 来源依据与口径（可折叠）。
 *
 * 三条刻意的取舍：
 *   1. **不做"全面板仪表盘"**：主页面不放图谱、不放题、不放分数 ——
 *      那些是点进去以后的事。主页面只负责"让你想点进去"。
 *   2. **状态与事实只用契约与 dataSource 给的**：题数 / 模块数 / 契约版本来自
 *      `loadContract`，模式来自 `dataSource.mode`，快照路径来自 `snapshotCandidates`。
 *      页面自己不推断任何业务结论（这是全仓的纪律，P0-13）。
 *   3. **六阶段的"已落地 / 未开始"是项目事实，不是页面判断的**：
 *      取值依据是 `README.md` §0.2 与 `docs/07-status-and-acceptance.md` §16.1；
 *      **未开始的阶段不给按钮**（`disabled`），落地的阶段才点得动。
 *      改了实现就要改这张表 —— 它与文档里的那张完成度表是一件事。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ProjectSwitcher from '../components/ProjectSwitcher.vue'
import QuickSearch from '../components/QuickSearch.vue'
import LoginDialog from '../components/LoginDialog.vue'
import { useDataSource, snapshotCandidates, DEFAULT_PROJECT_ID } from '../api/dataSource'
import { useLayeredReveal } from '../composables/useReveal'

const emit = defineEmits(['enter-training', 'view-analysis', 'enter-logic'])

const ds = useDataSource()
const mode = ds.mode
const online = computed(() => mode.value === 'api')

const rootRef = ref(null)

// ---------------------------------------------------------------------------
// 六阶段 / 既有主线 / 平台六步：文案与状态表
// ---------------------------------------------------------------------------

/** 六阶段教学主线。`status` 取自 README §0.2 与 docs/07 §16.1 的完成度表。 */
const TEACHING_STAGES = [
  {
    key: 'orientation',
    name: '阶段一 · 项目认知',
    desc: '写下你知道的项目地图 → 只回覆盖清单，不打分',
    status: 'done',
  },
  {
    key: 'module-card',
    name: '阶段二 · 模块卡片学习',
    desc: '逐张卡片回答五个问题 → 事实覆盖清单，不打分',
    status: 'done',
  },
  {
    key: 'flow-sim',
    name: '阶段三 · 流程推演',
    desc: '选定场景 → 拖拽排序业务流程 → 第一分歧点（这一阶段还没有实现）',
    status: 'todo',
  },
  {
    key: 'design',
    name: '阶段四 / 五 · 设计画布 + 六维评审',
    desc: '自己拆模块 → 六维结构信号；算不出来的维度显示「本轮未评估」，不填 0',
    status: 'done',
  },
  {
    key: 'reconstruct',
    name: '阶段六 · 重构挑战',
    desc: '追加需求 → 改设计 → 影响范围命中（这一阶段还没有实现）',
    status: 'todo',
  },
]

/** 既有主线：学生当前的主流程（旧四关题型）与图谱视图。 */
const TRAINING_ENTRIES = [
  { key: 'training', name: '训练关卡', desc: '旧四关题型，学生当前的主流程', icon: '🎯' },
  { key: 'graph', name: '业务图谱', desc: '域树 / 卡片 / 复杂度 / 流程场景', icon: '🕸️' },
]

/** 平台六步（与 LogicPlatformView 的 STEPS 是同一套说法，这里只做预告）。 */
const LOGIC_STEPS = [
  '投入项目',
  '分析项目大小',
  '按大小分流',
  '业务板块看板',
  '板块分析',
  '沉浸式讲稿',
]

/**
 * 来源依据抽屉的静态部分。
 * 这里**只写路径与口径，不写数字** —— 数字的唯一来源是 `validation/acceptance_latest.md`
 * （脚本生成），手抄到前端里第二天就会过期（docs/08 §19.2 ㉑ 就是这一类教训）。
 */
const EVIDENCE_GROUPS = [
  {
    title: '数据从哪来',
    lines: [
      '在线：GET /api/projects/{id}/analysis?mode=student（走 vite 代理到 127.0.0.1:8000）',
      '离线：frontend/public/demo 下的静态快照（同一个契约形状，只是少了判题与讲解）',
      '业务图谱另有一条通道：/api/projects/{id}/business-graph，离线时回落到快照里的 business_graph',
      '源码证据：/api/projects/{id}/source?path=&start=&end=，离线走 /demo 下的源码副本',
    ],
  },
  {
    title: '结论怎么算',
    lines: [
      '事实层（调用图 / 状态写入 / 流程 / 依赖 / 关键实现）全部来自 Python AST 解析，同一输入字节级相同',
      '业务图谱（一级域 / 二级功能点 / 卡片）是规则引擎的划分结果，带置信度徽章，待教师确认',
      '复杂度是七维公式算出来的分级信号，不是"好/坏"的判定',
      '核心度排序只是讲解顺序的参考信号，不等于重要性结论',
    ],
  },
  {
    title: '判分边界（不许越线的地方）',
    lines: [
      '训练答案只在后端，学生契约里不含答案字段：前端既不持有、也无法推断对错',
      '离线时如实报「无法判分」，最终结果页标记未判分，不给出掌握度结论',
      '设计层六维评审里算不出来的维度返回 not_evaluated（页面显示「本轮未评估」），不填 0',
      '判定不交给 LLM；LLM 只能做讲解与润色，且默认关闭',
    ],
  },
  {
    title: '验收与门禁',
    lines: [
      'validation/acceptance_latest.md —— 最近一次验收的机器生成记录（数字的唯一来源）',
      'python scripts/build_acceptance_report.py —— 一进程内跑完只读验收脚本',
      'python scripts/verify_docs.py —— 文档门禁：路径 / 章节引用 / 版本号 / 数字 / 行号锚点',
      'node scripts/browser_clickthrough.mjs —— 真实 DOM + 真实 HTTP 的端到端点击走查',
    ],
  },
  {
    title: '还没做的（如实列出）',
    lines: [
      '阶段三（流程推演）与阶段六（重构挑战）：未实现，主页面不给入口',
      'engine/design/reconstruct.py：尚未建立',
      '人工核对业务图谱的判定列仍未填 —— 所以「准确率」目前没有可报告的来源',
      '教师 Gold Graph 编辑器 / 图谱审核：未做（只有关键实现的确认与拒绝）',
    ],
  },
]

// ---------------------------------------------------------------------------
// 项目与契约（与 TrainingView 同一条数据通道，避免第二套读取逻辑）
// ---------------------------------------------------------------------------
const projectId = ref(ds.readProjectFromUrl() || DEFAULT_PROJECT_ID)
const projects = ref([...ds.demos])
const contract = ref(null)
const contractSource = ref('')
const loading = ref(true)
const loadError = ref('')
const loginOpen = ref(false)
const currentUser = ref('')

const questionCount = computed(() => {
  const qs = contract.value?.training?.questions
  return Array.isArray(qs) ? qs.length : null
})
const moduleCount = computed(() => {
  const ms = contract.value?.modules
  return Array.isArray(ms) ? ms.length : null
})

const searchItems = computed(() => {
  const pages = [
    { key: 'page-training', kind: 'page', label: '培训系统', description: '进入六阶段训练工作区', group: '核心功能', icon: '🎓', stage: 'training' },
    { key: 'page-logic', kind: 'page', label: '业务逻辑分析平台', description: '项目规模、业务板块与沉浸式讲稿', group: '核心功能', icon: '🔬', action: 'logic' },
    { key: 'page-analysis', kind: 'page', label: '函数级分析详情', description: '概览、业务模式、流程图、代码证据', group: '项目视图', icon: '🧩', action: 'analysis' },
    { key: 'stage-orientation', kind: 'stage', label: '阶段一 · 项目认知', description: '项目地图与覆盖清单', group: '阶段主线', icon: '①', stage: 'orientation' },
    { key: 'stage-cards', kind: 'stage', label: '阶段二 · 模块卡片学习', description: '五问卡片与事实覆盖', group: '阶段主线', icon: '②', stage: 'module-card' },
    { key: 'stage-design', kind: 'stage', label: '阶段四 / 五 · 设计画布', description: '模块拆分与六维评审', group: '阶段主线', icon: '④', stage: 'design' },
    { key: 'stage-graph', kind: 'stage', label: '业务图谱', description: '域、功能点、卡片与源码证据', group: '项目视图', icon: '🕸️', stage: 'graph' },
  ]
  const modules = Array.isArray(contract.value?.modules) ? contract.value.modules : []
  const moduleItems = modules.map((mod, index) => ({
    key: `module-${mod.module_id || index}`,
    kind: 'module',
    label: mod.name_cn || mod.name || mod.module_id || `业务模块 ${index + 1}`,
    description: mod.description || mod.primary_purpose || '打开业务图谱中的模块卡片',
    group: '业务模块', icon: '◈', stage: 'graph', moduleId: mod.module_id,
  }))
  return [...pages, ...moduleItems]
})

/** 离线快照候选路径：直接问数据源，别在页面里再抄一份路径表（P0-13）。 */
const snapshotPaths = computed(() => snapshotCandidates(projectId.value))

async function loadProject(id) {
  loading.value = true
  loadError.value = ''
  const res = await ds.loadContract(id)
  if (!res.ok) {
    contract.value = null
    contractSource.value = ''
    loadError.value = res.error || '未知错误'
  } else {
    contract.value = res.data
    contractSource.value = res.source === 'api' ? '在线 API' : '静态快照'
  }
  loading.value = false
}

async function reload() {
  const listRes = await ds.listProjects()
  projects.value = listRes.data.projects
  await loadProject(projectId.value)
}

function onProjectChange(id) {
  if (!id || id === projectId.value) return
  projectId.value = id
}

function enterTraining(stage) {
  emit('enter-training', stage)
}

function onSearchSelect(item) {
  if (item.action === 'logic') return emit('enter-logic')
  if (item.action === 'analysis') return emit('view-analysis')
  emit('enter-training', item.moduleId ? { stage: item.stage, moduleId: item.moduleId } : item.stage)
}

function onLogin({ username }) {
  currentUser.value = username
  try { localStorage.setItem('lwai.demo.user', username) } catch { /* storage may be disabled */ }
  loginOpen.value = false
}

// ---------------------------------------------------------------------------
// 入场：链式拉动（两个核心卡由 CSS 动画拉入）+ 链节点亮 + 层进式展现
// ---------------------------------------------------------------------------
const evidenceOpen = ref(false)
const chainLive = ref(false)

/** 链节点亮的定时器：卸载时要清掉，避免在已卸载的组件上改状态。 */
let chainTimer = null

onMounted(async () => {
  try { currentUser.value = localStorage.getItem('lwai.demo.user') || '' } catch { currentUser.value = '' }
  const listRes = await ds.listProjects()
  projects.value = listRes.data.projects
  ds.writeProjectToUrl(projectId.value)
  await loadProject(projectId.value)

  // 两张卡落地之后（0.75s 动画）再点亮链节，形成"先拉过来、再串起来"的次序
  if (typeof window !== 'undefined') {
    chainTimer = window.setTimeout(() => { chainLive.value = true }, 620)
  }
})

onBeforeUnmount(() => {
  if (chainTimer !== null && typeof window !== 'undefined') window.clearTimeout(chainTimer)
  chainTimer = null
})

watch(projectId, async (id) => {
  ds.writeProjectToUrl(id)
  await loadProject(id)
})

// 层进式：`[data-layer]` 进入视口时逐层点亮（不支持 IO 的浏览器保持默认可见）
useLayeredReveal(rootRef, { watchSource: () => projectId.value })
</script>
