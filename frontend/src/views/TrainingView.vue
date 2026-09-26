<template>
  <div ref="rootRef" class="min-h-screen bg-grid relative overflow-hidden">
    <!-- 背景装饰 -->
    <div class="glow-orb w-[700px] h-[700px] -top-52 right-[-200px] bg-neon-purple opacity-20"></div>
    <div class="glow-orb w-[500px] h-[500px] bottom-[-150px] left-[-100px] bg-neon-blue opacity-20"></div>

    <div class="relative z-10 max-w-5xl mx-auto px-6 py-8">
      <!-- 顶部：项目信息 + 项目切换 + 进度 -->
      <div class="mb-8" data-layer>
        <div class="flex items-center justify-between mb-4">
          <div>
            <div class="text-xs text-gray-500 font-mono tracking-widest uppercase mb-1">Project Training</div>
            <!-- P0-01：项目名来自契约 project_name，不再写死 -->
            <h1 class="text-2xl font-bold gradient-text">{{ projectName }}</h1>
            <div v-if="contract" class="text-[11px] text-gray-500 font-mono mt-1">
              {{ contract.project_id }} · 契约 {{ contract.contract_version }}
              <span v-if="overviewLine" class="text-gray-600">· {{ overviewLine }}</span>
            </div>
          </div>
          <div class="text-right">
            <div class="text-xs text-gray-500 mb-1">完成进度</div>
            <div class="text-2xl font-bold text-white font-mono">
              {{ currentLevel }}<span class="text-gray-600">/{{ totalLevels || '—' }}</span>
            </div>
          </div>
        </div>

        <!-- P0-03：项目切换器 + 双通道模式徽章 + 离线横幅 -->
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

        <!-- 会话提示（P0-03：进度被丢弃时必须说明原因，不静默沿用） -->
        <div v-if="session.notice" class="mb-4 p-3 rounded-xl bg-purple-500/5 border border-purple-500/30 text-xs text-purple-300 leading-relaxed">
          {{ session.notice }}
        </div>
        <div v-else-if="session.restored && currentView === 'level'" class="mb-4 text-[11px] text-gray-500">
          已恢复本项目上次的作答进度（会话 {{ shortSessionId }}）。
        </div>

        <!-- 进度条 + 关卡节点 -->
        <div class="relative" v-if="totalLevels">
          <div class="h-1 bg-deep-border rounded-full overflow-hidden">
            <div
              class="h-full difficulty-gradient transition-all duration-700 ease-out progress-bar"
              :style="{ width: progressPercent + '%' }"
            ></div>
          </div>
          <div class="flex justify-between mt-2">
            <div
              v-for="(level, i) in levels"
              :key="'lv-' + i"
              class="flex flex-col items-center relative"
              :style="{ width: (100 / totalLevels) + '%' }"
            >
              <div
                class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 z-10"
                :class="{
                  'bg-neon-blue text-white shadow-lg shadow-neon-blue/30 scale-110': i + 1 === currentLevel && currentView === 'level',
                  'bg-green-500 text-white': isLevelCorrect(i),
                  'bg-deep-border text-gray-500': !isLevelCorrect(i) && i + 1 !== currentLevel,
                }"
                :style="{ marginTop: i + 1 === currentLevel ? '-11px' : '-8px' }"
              >
                <span v-if="isLevelCorrect(i)">✓</span>
                <span v-else>{{ i + 1 }}</span>
              </div>
              <div
                class="text-[11px] mt-2 text-center font-medium transition-colors truncate max-w-full px-1"
                :class="{
                  'text-neon-blue': i + 1 === currentLevel && currentView === 'level',
                  'text-green-400': isLevelCorrect(i),
                  'text-gray-500': !isLevelCorrect(i) && i + 1 !== currentLevel,
                }"
                :title="level"
              >
                {{ level }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!--
        Sprint 2 · 阶段切换（README5 §6.2 的 A 方案：不动 App.vue 外壳，在 TrainingView 里用 v-show 切子组件）
        - "训练关卡"是本工作区的默认阶段，判分 / 离线横幅的行为一个字都没改；
          （题数**不固定**：第 2 关每个够格的业务模块各一道题，
           所以 4 个业务模块的项目是 7 关，不是 4 关 —— 见训练生成器
           `engine/project_analyzer/training_generator.py` 的 `_generateLevel2`）
        - "业务图谱"是 Sprint 2 新增的学生可见入口（P1-06）。
          这里用 v-if 而不是 v-show：图谱是重面板，且**不该在只做训练时也发请求**，
          也不该把图谱正文混进训练页的可见文本里（走查会用 body 文本做断言）。
        - "项目认知"是 Sprint 3 新增的**阶段一**（培养方案第四章六阶段的第一个）。
        - "模块卡片"是 Sprint 4 新增的**阶段二**（逐张卡片 + 五个问题 → 事实覆盖清单）。
          它紧跟在阶段一后面（学习顺序），题目与判定都在后端，前端不认识任何业务字段。
        - "设计画布"是 Sprint 5 新增的**阶段四 / 五**（自己拆模块 → 六维评审）。

        进哪一个阶段由 `initial-stage` 决定（UI 重设计一轮新增）：
        系统主页面上的六阶段入口把 `mainStage` 直接指到对应阶段；
        省略时仍是 `training`（"训练关卡"），走查与演示动线不变。
      -->
      <!--
        UI 重设计一轮（排版优先级）：
        这五个页签原来是一条平级的按钮排，看不出"哪个是教、哪个是看"。
        现在按**模块层级**分成两组：① 「阶段主线」= 六阶段教学（教）；
        ② 「项目视图」= 训练关卡 + 业务图谱（看）。
        同时把原来直接铺在页签旁边的那几段口径说明**收进可折叠抽屉** ——
        说明一个字没删，只是默认不再占据第一屏（`data-test="stage-scope-toggle"`）。
      -->
      <div class="mb-5 space-y-3" data-test="stage-switcher" data-layer data-layer-delay="80">
        <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
          <!-- 组 1：阶段主线（大模块） -->
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-[10px] font-mono tracking-wider text-neon-blue/70 uppercase">阶段主线</span>
            <button
              class="tab-btn"
              :class="{ active: mainStage === 'orientation' }"
              data-test="stage-orientation"
              @click="mainStage = 'orientation'"
            >① 项目认知</button>
            <button
              class="tab-btn"
              :class="{ active: mainStage === 'module-card' }"
              data-test="stage-module-card"
              @click="mainStage = 'module-card'"
            >② 模块卡片</button>
            <button
              class="tab-btn"
              :class="{ active: mainStage === 'design' }"
              data-test="stage-design"
              @click="mainStage = 'design'"
            >④⑤ 设计画布</button>
          </div>

          <div class="hidden sm:block w-px h-5 bg-deep-border"></div>

          <!-- 组 2：项目视图（辅助） -->
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-[10px] font-mono tracking-wider text-gray-500 uppercase">项目视图</span>
            <button
              class="tab-btn"
              :class="{ active: mainStage === 'training' }"
              data-test="stage-training"
              @click="mainStage = 'training'"
            >训练关卡</button>
            <button
              class="tab-btn"
              :class="{ active: mainStage === 'graph' }"
              data-test="stage-graph"
              @click="mainStage = 'graph'"
            >业务图谱</button>
          </div>
        </div>

        <!-- 当前阶段的一句话定位（长说明在下面的抽屉里，需要时展开） -->
        <p class="text-[11px] text-gray-500" data-test="stage-hint">{{ stageHint }}</p>

        <!-- 口径与来源：可折叠（内容与改动前完全一致，只是默认收起） -->
        <div>
          <button
            class="drawer-head"
            data-test="stage-scope-toggle"
            :aria-expanded="String(scopeOpen)"
            @click="scopeOpen = !scopeOpen"
          >
            <span class="flex items-center gap-2 min-w-0">
              <span class="text-sm leading-none">📎</span>
              <span class="text-xs text-gray-300">这一阶段的判定口径与数据来源</span>
              <span class="text-[10px] text-gray-500 font-mono truncate">{{ STAGE_LABELS[mainStage] }}</span>
            </span>
            <span class="flex items-center gap-2 flex-shrink-0">
              <span class="text-[10px] text-gray-500 font-mono">{{ scopeOpen ? '收起' : '展开' }}</span>
              <svg
                class="drawer-chevron text-gray-500" :class="{ open: scopeOpen }"
                width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"
              >
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </span>
          </button>

          <div class="drawer-body" :class="{ open: scopeOpen }" data-test="stage-scope-body">
            <div class="drawer-inner">
              <div class="pt-2 space-y-2">
                <div
                  v-for="(line, li) in stageScopeLines"
                  :key="li"
                  class="drawer-row glass-card px-3 py-2 text-[11px] text-gray-400 leading-relaxed"
                  :style="{ '--i': li }"
                >
                  <span class="text-gray-600 mr-1.5">{{ li + 1 }}.</span>{{ line }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-show="mainStage === 'training'">
      <!-- 加载 / 错误 -->
      <div v-if="loading" class="glass-card p-10 text-center text-gray-400 text-sm">正在加载项目数据…</div>
      <div v-else-if="loadError" class="glass-card p-10 text-center">
        <div class="text-red-400 text-sm mb-2">无法加载项目「{{ projectId }}」</div>
        <div class="text-xs text-gray-500 font-mono break-all">{{ loadError }}</div>
      </div>

      <!-- 答题区域 -->
      <div v-else class="relative">
        <transition name="slide-fade" mode="out-in">

          <!-- 关卡区域 -->
          <div v-if="currentView === 'level'" :key="'level-' + currentLevel" class="space-y-6">
            <!-- 契约里没有题目时给诚实空状态，不编造题目 -->
            <div v-if="!currentQuestion" class="glass-card p-8 text-center text-sm text-gray-400">
              该项目契约里没有下发训练题（training.questions 为空），无法开始训练。
            </div>

            <div v-else class="glass-card p-8 neon-border" data-layer>
              <div class="flex items-center gap-3 mb-6">
                <div class="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold bg-gradient-to-br" :class="theme.badge">
                  {{ currentLevel }}
                </div>
                <div>
                  <h2 class="text-lg font-bold text-white">{{ currentQuestion.title || ('第 ' + currentLevel + ' 关') }}</h2>
                  <p class="text-xs text-gray-500">
                    {{ questionTypeLabel }}
                    <span v-if="currentQuestion.difficulty" class="ml-2 font-mono">难度 {{ currentQuestion.difficulty }}</span>
                  </p>
                </div>
              </div>

              <!-- 项目背景：来自契约数据（P0-01，不再写死某个项目的业务场景） -->
              <div v-if="projectBackground" class="mb-4 p-4 rounded-xl bg-deep-card/50 border border-deep-border">
                <div class="text-xs text-gray-400 mb-2">📋 项目背景</div>
                <p class="text-sm text-gray-300 leading-relaxed whitespace-pre-line">{{ projectBackground }}</p>
              </div>

              <!-- 题干 -->
              <div v-if="currentQuestion.description" class="mb-6 p-4 rounded-xl bg-deep-card/50 border border-deep-border">
                <div class="text-xs text-gray-400 mb-2">📝 题干</div>
                <p class="text-sm text-gray-300 leading-relaxed whitespace-pre-line">{{ currentQuestion.description }}</p>
              </div>

              <!-- 按题型渲染上下文（模块 / 流程 / 关键实现），数据全部来自契约 -->
              <div v-if="questionType === 'responsibility_match'" class="mb-6 p-4 rounded-xl bg-deep-card/50 border border-deep-border">
                <div class="text-xs text-gray-400 mb-2">🎯 当前模块</div>
                <template v-if="targetModuleName">
                  <div class="text-xl font-bold text-neon-purple mb-1">{{ targetModuleName }}</div>
                  <p class="text-sm text-gray-400">
                    思考一下：这个模块在系统中承担什么角色？它的核心职责是什么？
                  </p>
                </template>
                <div v-else class="text-sm text-amber-400/80">
                  契约未提供可判定的业务模块（modules 里没有 core/business/intermediate 类型的模块），本关缺少模块信息。
                </div>
              </div>

              <div v-else-if="questionType === 'flow_next_step'" class="mb-6 p-4 rounded-xl bg-deep-card/50 border border-deep-border">
                <div class="text-xs text-gray-400 mb-2">⚡ 核心流程</div>
                <template v-if="flowName">
                  <div class="text-xl font-bold text-amber-400 mb-1">{{ flowName }}</div>
                  <p class="text-sm text-gray-400">
                    一个完整的业务操作，应该按照什么顺序执行？请思考数据和状态的流转逻辑。
                  </p>
                </template>
                <div v-else class="text-sm text-amber-400/80">契约未提供 core_flows，本关缺少流程信息。</div>
              </div>

              <KeyImplementationPanel
                v-else-if="questionType === 'key_implementation'"
                :implementation="keyImplementation"
                :project-id="projectId"
                @open-source="openSource"
              />

              <!-- 选项 -->
              <div class="mb-2 text-sm text-gray-400">
                <template v-if="isMultiSelect">
                  请选出<strong :class="theme.accent">应该包含</strong>的选项（<span :class="theme.accent">多选</span>）
                </template>
                <template v-else>请选出最准确的一项：</template>
              </div>
              <div v-if="isMultiSelect" class="mb-4 text-xs text-gray-500">已选 {{ currentState.selected.length }} 项</div>

              <!-- 多选（第 1 关样式）：选项按 --i 依次滑入（层进式） -->
              <div v-if="isMultiSelect" class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-8">
                <div
                  v-for="(opt, oi) in currentQuestion.options"
                  :key="opt.id"
                  data-test="option-multi"
                  :data-option-id="opt.id"
                  data-layer
                  :style="{ '--i': oi }"
                  class="stagger-item p-4 rounded-xl border cursor-pointer transition-all group"
                  :class="multiOptionClass(opt)"
                  @click="toggleOption(opt)"
                >
                  <div class="flex items-start gap-3">
                    <div class="w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 transition-all" :class="multiCheckboxClass(opt)">
                      <svg v-if="currentState.selected.includes(opt.id)" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                    </div>
                    <div class="text-sm font-medium text-white group-hover:text-neon-blue transition-colors">
                      {{ opt.id }} · {{ opt.text }}
                    </div>
                  </div>
                </div>
              </div>

              <!-- 单选（第 2/3/4 关样式）：同样按 --i 依次滑入 -->
              <div v-else class="space-y-2.5 mb-8">
                <div
                  v-for="(opt, oi) in currentQuestion.options"
                  :key="opt.id"
                  data-test="option-single"
                  :data-option-id="opt.id"
                  data-layer
                  :style="{ '--i': oi }"
                  class="stagger-item quiz-option"
                  :class="singleOptionClass(opt)"
                  @click="selectSingle(opt.id)"
                >
                  <span class="option-letter" :style="optionLetterStyle(opt)">{{ opt.id }}</span>
                  <span class="text-sm text-gray-300 pt-0.5">{{ opt.text }}</span>
                </div>
              </div>

              <!-- 答错引导面板（提示分层，README5 §6.6-5） -->
              <transition name="fade">
                <div v-if="showHintPanel" class="mb-6 p-5 rounded-xl bg-amber-500/5 border border-amber-500/30 relative overflow-hidden">
                  <div class="absolute top-0 right-0 w-32 h-32 bg-amber-500/5 rounded-full -translate-y-1/2 translate-x-1/2"></div>
                  <div class="relative">
                    <div class="flex items-center gap-2 mb-3">
                      <div class="w-8 h-8 rounded-lg bg-amber-500/20 flex items-center justify-center text-amber-400 text-lg">💡</div>
                      <div>
                        <div class="font-bold text-amber-400">别急，给你一条线索</div>
                        <div class="text-xs text-amber-400/60">还剩 {{ currentState.hintsRemaining }} 次尝试机会</div>
                      </div>
                    </div>

                    <div class="text-sm text-gray-300 leading-relaxed mb-4">{{ currentHintText }}</div>

                    <!-- 范围线索：只给"有几类、各几个"，不点名答案 -->
                    <div v-if="showModuleTypeChips && moduleTypeSummary.length" class="mb-4">
                      <div class="text-xs text-gray-500 mb-2">模块类型分布（只提示范围）：</div>
                      <div class="flex flex-wrap gap-2">
                        <div
                          v-for="item in moduleTypeSummary"
                          :key="item.type"
                          class="px-3 py-1.5 rounded-lg bg-deep-card/80 border border-deep-border text-xs"
                        >
                          <span class="text-white font-medium">{{ typeLabel(item.type) }}</span>
                          <span class="text-gray-500 ml-2">{{ item.count }} 个</span>
                        </div>
                      </div>
                    </div>

                    <!-- 职责关键词线索 -->
                    <div v-if="hintKeywords.length" class="mb-4">
                      <div class="text-xs text-gray-500 mb-2">这个模块的职责关键词：</div>
                      <div class="flex flex-wrap gap-1.5">
                        <span
                          v-for="kw in hintKeywords"
                          :key="kw"
                          class="px-2.5 py-1 text-xs rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20"
                        >{{ kw }}</span>
                      </div>
                    </div>

                    <!-- 流程首尾锚点 -->
                    <div v-if="flowAnchor" class="mb-4">
                      <div class="text-xs text-gray-500 mb-2">流程线索：</div>
                      <div class="flex items-center gap-2 text-xs">
                        <span class="px-3 py-1.5 rounded-lg bg-green-500/10 text-green-400 border border-green-500/30 font-mono">▶ {{ flowAnchor.start }}</span>
                        <span class="text-gray-600">→ ... →</span>
                        <span class="px-3 py-1.5 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/30 font-mono">◼ {{ flowAnchor.end }}</span>
                      </div>
                    </div>

                    <!-- 关键实现线索 -->
                    <div v-if="keyImplHint" class="mb-4 p-3 rounded-lg bg-deep-card/80 border border-deep-border">
                      <div class="text-xs text-gray-500 mb-2">关键方法分析线索：</div>
                      <div class="text-xs text-gray-400 space-y-1">
                        <div v-if="keyImplHint.design_characteristics?.length">
                          · 设计特征：
                          <span
                            v-for="(char, idx) in keyImplHint.design_characteristics.slice(0, 2)"
                            :key="idx"
                            :class="char.confidence === 'verified' ? 'text-emerald-300' : 'text-amber-300'"
                          >{{ char.label }}<span v-if="idx === 0 && keyImplHint.design_characteristics.length > 1">, </span></span>
                        </div>
                        <div v-else>· 设计思路：<span class="text-pink-300">{{ keyImplHint.design_approach || '—' }}</span></div>
                        <div>· 复杂度：<span class="text-white font-mono">{{ keyImplHint.complexity }}</span> · 修改 <span class="text-amber-400 font-mono">{{ keyImplHint.state_write_count }}</span> 个状态字段</div>
                        <div v-if="keyImplHint.validation_count > 0">· 包含 <span class="text-green-400 font-mono">{{ keyImplHint.validation_count }}</span> 处前置校验</div>
                      </div>
                    </div>

                    <button
                      data-test="retry"
                      @click="retryCurrent"
                      class="px-5 py-2 rounded-lg text-sm font-medium text-white bg-gradient-to-r from-amber-500 to-orange-500
                             hover:shadow-lg hover:shadow-amber-500/25 hover:-translate-y-0.5 transition-all"
                    >
                      🔄 再试一次
                    </button>
                  </div>
                </div>
              </transition>

              <!-- 提交后的反馈（学生先输出，系统后反馈） -->
              <transition name="fade">
                <GradingFeedback
                  v-if="currentState.answered && (currentState.offlineGraded || currentState.grading)"
                  :grading="currentState.grading"
                  :offline="currentState.offlineGraded"
                  :selected="currentState.selected"
                  :options="currentQuestion.options || []"
                  :reveal-missing="currentState.hintsRemaining === 0"
                />
              </transition>

              <div class="flex justify-between items-center">
                <button
                  v-if="currentLevel > 1"
                  @click="prevLevel"
                  class="px-4 py-2.5 rounded-xl text-sm text-gray-400 hover:text-white transition-colors"
                >
                  ← 上一关
                </button>
                <div v-else></div>

                <div class="flex items-center gap-2">
                  <button
                    v-if="!currentState.answered"
                    data-test="submit-answer"
                    @click="submitCurrent"
                    :disabled="!canSubmit || currentState.submitting"
                    class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all bg-gradient-to-r
                           hover:shadow-lg hover:-translate-y-0.5 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-y-0"
                    :class="[theme.button, theme.shadow]"
                  >
                    {{ currentState.submitting ? '提交中…' : '提交答案' }}
                  </button>
                  <button
                    v-else-if="showNextButton"
                    data-test="next-level"
                    @click="nextLevel"
                    class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all
                           bg-gradient-to-r from-neon-purple to-neon-pink
                           hover:shadow-lg hover:shadow-neon-purple/25 hover:-translate-y-0.5"
                  >
                    {{ isLastLevel ? '查看最终结果 →' : '下一关 →' }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- 最终结果页 -->
          <div v-else key="result" class="space-y-6">

            <!-- 得分概览卡 -->
            <div class="glass-card p-8 neon-border text-center">
              <div class="mb-6">
                <div class="w-24 h-24 mx-auto mb-4 rounded-full bg-gradient-to-br from-neon-blue via-neon-purple to-neon-pink flex items-center justify-center animate-glow-pulse">
                  <span class="text-3xl font-bold text-white font-mono">{{ resultSummary.gradedCount ? resultSummary.correct + '/' + resultSummary.gradedCount : '—' }}</span>
                </div>
                <h2 class="text-2xl font-bold gradient-text mb-2">训练完成！</h2>
                <p class="text-gray-400 text-sm">
                  共 {{ resultSummary.total }} 关 ·
                  <span class="text-neon-blue font-mono font-bold">{{ resultSummary.gradedCount }}</span> 关已判分（答对 {{ resultSummary.correct }} 关）
                  <template v-if="resultSummary.ungradedCount || resultSummary.unansweredCount">
                    · <span class="text-amber-400 font-mono font-bold">{{ resultSummary.ungradedCount + resultSummary.unansweredCount }}</span> 关未判分
                  </template>
                </p>
                <p v-if="resultSummary.gradedCount === 0" class="text-xs text-amber-400/80 mt-2">
                  离线演示模式：判题接口不可用，本次没有产生任何成绩，也不会给出掌握度结论。
                </p>
                <p v-else-if="resultSummary.ungradedCount" class="text-xs text-amber-400/60 mt-2">
                  其中 {{ resultSummary.ungradedCount }} 关因为后端不可用而未判分，未计入正确率。
                </p>
              </div>

              <div class="max-w-md mx-auto mb-6">
                <div class="h-2 bg-deep-border rounded-full overflow-hidden progress-bar">
                  <div
                    class="h-full difficulty-gradient rounded-full transition-all duration-1000 ease-out"
                    :style="{ width: gradedPercent + '%' }"
                  ></div>
                </div>
              </div>

              <div class="grid gap-3 mb-6 max-w-lg mx-auto" :style="{ gridTemplateColumns: 'repeat(' + Math.max(resultSummary.total, 1) + ', minmax(0, 1fr))' }">
                <div v-for="(level, i) in levels" :key="'res-' + i" class="text-center">
                  <div
                    class="w-10 h-10 mx-auto mb-1 rounded-xl flex items-center justify-center text-sm font-bold"
                    :class="resultCellClass(i)"
                  >
                    {{ resultCellText(i) }}
                  </div>
                  <div class="text-[10px] text-gray-500 truncate" :title="level">{{ level }}</div>
                </div>
              </div>

              <!-- 理解度雷达图（维度数量 = 题目数量） -->
              <div class="p-5 rounded-xl bg-deep-card/50 border border-deep-border">
                <div class="text-sm font-medium text-white mb-4 text-center">📊 理解度评估</div>
                <UnderstandingRadar :dims="radarDims" :scores="radarScores" />
                <div class="mt-4 pt-4 border-t border-deep-border text-center">
                  <div class="text-sm">
                    综合评级：<strong :class="scoreLevel.color" class="font-bold text-base">{{ scoreLevel.label }}</strong>
                  </div>
                  <p class="text-xs text-gray-500 mt-1 leading-relaxed">{{ scoreLevel.comment }}</p>
                  <p v-if="resultSummary.ungradedCount || resultSummary.unansweredCount" class="text-[11px] text-gray-600 mt-1">
                    灰色维度表示该关未判分，不参与评级。
                  </p>
                </div>

                <div v-if="weakPoints.length" class="mt-4 p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
                  <div class="text-xs font-medium text-amber-400 mb-1.5">💡 薄弱点建议</div>
                  <div class="text-xs text-gray-400 leading-relaxed">
                    <span v-for="(wp, i) in weakPoints" :key="wp">
                      <span v-if="i > 0">，</span>{{ wp }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 完整业务逻辑呈现：模块架构图（全部来自契约 modules） -->
            <div class="glass-card p-6 neon-border">
              <h3 class="text-base font-bold mb-1 flex items-center gap-2">
                <span class="w-1 h-4 bg-gradient-to-b from-neon-blue to-neon-purple rounded-full"></span>
                模块架构
              </h3>
              <p class="text-xs text-gray-500 mb-4 ml-3">
                系统由以下 {{ projectModules.length }} 个模块组成，各司其职，相互协作
              </p>

              <div v-if="!projectModules.length" class="text-sm text-gray-400">契约未提供 modules 数据。</div>
              <div v-else class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <div
                  v-for="(mod, i) in projectModules"
                  :key="mod.module_id || i"
                  class="p-4 rounded-xl bg-deep-card/50 border border-deep-border text-center
                         hover:border-neon-blue/40 hover:bg-neon-blue/5 transition-all group"
                >
                  <div
                    class="w-10 h-10 mx-auto mb-2 rounded-lg flex items-center justify-center text-lg"
                    :style="{ background: paletteColor(i) + '20' }"
                  >
                    {{ paletteIcon(i) }}
                  </div>
                  <div class="text-sm font-medium text-white group-hover:text-neon-blue transition-colors">
                    {{ mod.name }}
                  </div>
                  <div class="text-[10px] text-gray-500 mt-1">
                    {{ mod.type || '未分类' }} · {{ mod.class_count }} 个类 · {{ mod.method_count }} 个方法
                  </div>
                  <div class="mt-2 flex justify-center">
                    <span
                      class="text-[10px] px-2 py-0.5 rounded-full"
                      :style="{ background: paletteColor(i) + '20', color: paletteColor(i) }"
                    >
                      核心度 {{ mod.core_score }}
                    </span>
                  </div>
                </div>
              </div>

              <div class="p-3 rounded-lg bg-deep-card/30 border border-deep-border text-xs text-gray-400">
                <span class="text-neon-blue font-medium">💡 理解要点：</span>
                好的系统设计应该模块职责清晰、边界明确。每个模块专注做一件事，
                模块之间通过接口协作。核心业务模块通常是最复杂、最关键的部分。
              </div>
            </div>

            <!-- 深度业务分析（架构图 + 调用链 + 状态追踪） -->
            <DeepAnalysisView
              :deep-analysis="deepAnalysis"
              :project-id="projectId"
              :modules="projectModules"
              @evidence-viewed="onEvidenceLoaded"
            />

            <!-- 模块职责清单 -->
            <div class="glass-card p-6 neon-border">
              <h3 class="text-base font-bold mb-4 flex items-center gap-2">
                <span class="w-1 h-4 bg-gradient-to-b from-neon-green to-neon-blue rounded-full"></span>
                模块职责清单
              </h3>

              <div v-if="!projectModules.length" class="text-sm text-gray-400">契约未提供 modules 数据。</div>
              <div v-else class="space-y-3">
                <div
                  v-for="(mod, i) in projectModules"
                  :key="'resp-' + (mod.module_id || i)"
                  class="p-4 rounded-xl bg-deep-card/50 border border-deep-border"
                >
                  <div class="flex items-center gap-3 mb-2">
                    <div class="w-8 h-8 rounded-lg flex items-center justify-center" :style="{ background: paletteColor(i) + '20' }">
                      <span class="text-base">{{ paletteIcon(i) }}</span>
                    </div>
                    <div class="min-w-0">
                      <div class="text-sm font-medium text-white truncate">{{ mod.name }}</div>
                      <div class="text-[11px] text-gray-500 truncate">{{ mod.description }}</div>
                    </div>
                    <div class="ml-auto text-[10px] font-mono text-gray-500">核心度 {{ mod.core_score }}</div>
                  </div>
                  <div class="flex flex-wrap gap-1.5 pl-11">
                    <span
                      v-for="(resp, j) in (mod.responsibilities || []).slice(0, 5)"
                      :key="j"
                      class="px-2 py-0.5 text-[11px] rounded bg-deep-hover text-gray-400"
                    >{{ resp }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 底部操作 -->
            <div class="flex gap-3 justify-center pt-2">
              <button
                @click="restart"
                class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all
                       bg-gradient-to-r from-neon-blue to-cyan-500
                       hover:shadow-lg hover:shadow-neon-blue/25 hover:-translate-y-0.5"
              >
                🔄 重新训练
              </button>
              <button
                @click="goBackToLastLevel"
                class="px-6 py-2.5 rounded-xl text-sm font-medium text-gray-300 transition-all
                       border border-deep-border hover:border-neon-blue/30 hover:text-white"
              >
                ← 返回第{{ totalLevels }}关
              </button>
              <button
                @click="$emit('view-analysis')"
                class="px-6 py-2.5 rounded-xl text-sm font-medium text-gray-300 transition-all
                       border border-deep-border hover:border-neon-purple/50 hover:text-white"
              >
                查看完整分析 →
              </button>
            </div>
          </div>
        </transition>
      </div>
      </div>

      <!--
        Sprint 3 · 阶段一「项目认知」：只读业务图谱，不依赖训练题契约
        （所以契约加载失败时它照样可用，理由与业务图谱视图相同）。
      -->
      <StageOrientation
        v-if="mainStage === 'orientation'"
        :project-id="projectId"
      />

      <!--
        Sprint 4 · 阶段二「模块卡片学习」：逐张卡片 + 五个问题 → 事实覆盖清单（不打分）。
        题目与卡片内容都来自后端（`/teaching/module-card/task`，由 business_graph 派生），
        所以它同样不依赖训练题契约；证据跳转复用页面右上角的 SourceViewerModal（P0-09）。
      -->
      <StageModuleCard
        v-if="mainStage === 'module-card'"
        :project-id="projectId"
        @open-source="openSource"
        @evidence-viewed="onEvidenceLoaded"
      />

      <!--
        Sprint 5 · 阶段四「设计画布」+ 阶段五「六维评审」（README §18 优先级 3）。
        题干、需求简报、必备能力数量与六维评审**全部来自后端**（`/teaching/design/*`，
        由 business_graph 与 engine/lexicon/design_*.json 派生），所以它同样不依赖训练题契约。
        画布本身（原生 drag + 手写 SVG）是学生的输入；判定只在后端 ——
        离线时页面会明确显示「设计任务不可用」，而不是在浏览器里算一份分数出来。
      -->
      <StageDesign
        v-if="mainStage === 'design'"
        :project-id="projectId"
      />

      <!--
        Sprint 2 · 业务图谱（P1-06）：一级域 → 二级功能点 → 动作，点击进卡片 / 跳源码。
        它在"训练关卡"之外，所以在契约加载失败（loadError）时也应当可达 —— 图谱有自己的数据通道
        （/business-graph 或快照里的 business_graph），不依赖 training 契约是否加载成功。
      -->
      <BusinessGraphView
        v-if="mainStage === 'graph'"
        :project-id="projectId"
        :initial-module-id="initialModuleId"
        @evidence-viewed="onEvidenceLoaded"
      />
    </div>

    <!-- 证据查看器（按项目内相对路径 + 行区间打开，P0-09） -->
    <SourceViewerModal
      :visible="sourceViewer.visible"
      :project-id="projectId"
      :path="sourceViewer.path"
      :start="sourceViewer.start"
      :end="sourceViewer.end"
      :hint="sourceViewer.hint"
      @close="sourceViewer.visible = false"
      @loaded="onEvidenceLoaded"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import DeepAnalysisView from '../components/DeepAnalysisView.vue'
import ProjectSwitcher from '../components/ProjectSwitcher.vue'
import GradingFeedback from '../components/GradingFeedback.vue'
import KeyImplementationPanel from '../components/KeyImplementationPanel.vue'
import UnderstandingRadar from '../components/UnderstandingRadar.vue'
import SourceViewerModal from '../components/SourceViewerModal.vue'
// Sprint 2：业务图谱视图（P1-06）——一级域 / 二级功能点 / 模块卡片 / 复杂度徽章 / 流程场景
import BusinessGraphView from '../components/BusinessGraphView.vue'
// Sprint 3：阶段一「项目认知」——项目地图 + 学生自由文本 → 覆盖清单（不打分）
import StageOrientation from '../components/StageOrientation.vue'
// Sprint 4：阶段二「模块卡片学习」——逐张卡片 + 五个问题 → 事实覆盖清单（不打分）
import StageModuleCard from '../components/StageModuleCard.vue'
import StageDesign from '../components/StageDesign.vue'
// P0-13：数据统一走双通道数据源（API 优先 / 静态快照回落）
import { useDataSource, DEFAULT_PROJECT_ID } from '../api/dataSource'
// P0-03：会话与进度持久化
import { useLearningSession } from '../stores/learningSession'
// UI 重设计一轮：层进式展现（进入视口逐层点亮；不支持 IntersectionObserver 时保持默认可见）
import { useLayeredReveal } from '../composables/useReveal'

const props = defineProps({
  /**
   * 进入本工作区时落在哪个阶段（系统主页面上的六阶段入口用它直接指路）。
   * 取值：'orientation' | 'module-card' | 'design' | 'training' | 'graph'；
   * 非法值 / 省略 → 'training'（保持改动前的默认落地行为）。
   */
  initialStage: {
    type: String,
    default: 'training',
  },
  initialModuleId: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['view-analysis'])

const ds = useDataSource()
const session = useLearningSession()

const mode = ds.mode
const HINTS_PER_LEVEL = 2

// ---------------------------------------------------------------------------
// 项目加载（P0-03：project_id 来自 ?project=<id>，可切换）
// ---------------------------------------------------------------------------
const projectId = ref(ds.readProjectFromUrl() || DEFAULT_PROJECT_ID)
const projects = ref([...ds.demos])
const contract = ref(null)
const loading = ref(true)
const loadError = ref('')

/** 本工作区的五个阶段（顺序 => 页签分组的顺序）。 */
const STAGE_KEYS = ['orientation', 'module-card', 'design', 'training', 'graph']

/** 页签文案（抽屉标题里也会用到，所以提到这里只留一份）。 */
const STAGE_LABELS = {
  orientation: '① 项目认知',
  'module-card': '② 模块卡片',
  design: '④⑤ 设计画布',
  training: '训练关卡',
  graph: '业务图谱',
}

/**
 * 主阶段：'orientation'（Sprint 3 · 阶段一 项目认知） | 'module-card'（Sprint 4 · 阶段二 模块卡片）
 * | 'design'（Sprint 5 · 阶段四 / 五 设计画布 + 六维评审）
 * | 'training'（旧四关题型，**默认**；题数随项目而定） | 'graph'（Sprint 2 业务图谱）。
 * 用 v-show/v-if 切换而**不引 vue-router**，与 App.vue 的 currentView 机制一致（README5 §6.2 方案 A）。
 */
const mainStage = ref(STAGE_KEYS.includes(props.initialStage) ? props.initialStage : 'training')

/** 口径抽屉：默认收起（说明一条没删，只是不再占第一屏）。 */
const scopeOpen = ref(false)

/** 当前阶段的一句话定位（长口径在 `stageScopeLines` 里）。 */
const STAGE_HINTS = {
  orientation: '阶段一 · 写出你认识的项目地图，系统只回覆盖清单，不打分。',
  'module-card': '阶段二 · 逐张卡片回答五个问题，系统只做事实覆盖比对，不打分。',
  design: '阶段四 / 五 · 自己拆模块、画依赖，提交后得到六维结构信号（有分数，算不出来的维度不填 0）。',
  training: '训练关卡 · 旧四关题型（当前学生主流程）：功能拆分 / 模块职责 / 流程推演 / 关键实现。',
  graph: '业务图谱 · 一级域 → 二级功能点 → 卡片与证据，用来回看"这个结论凭什么这么说"。',
}
const stageHint = computed(() => STAGE_HINTS[mainStage.value] || '')

/**
 * 每个阶段的判定口径与数据来源（可折叠抽屉的内容）。
 *
 * ⚠️ 这些句子里**不许出现效果数字**：数字的唯一来源是 `validation/acceptance_latest.md`，
 * 手抄进前端第二天就会过期（docs/08 §19.2 ㉑）。这里只写"谁在算、算不出来会怎样"。
 */
const STAGE_SCOPE_LINES = {
  orientation: [
    '覆盖度比对在后端执行：engine/teaching/coverage.py；前端不算第二份。',
    '系统只回「你已经提到的」与「你还没提到的」两份清单，没有分数、没有标准答案。',
    '域目标是否可比，取决于该项目有没有教师确认的种子图谱；没有就只用域名比对，并在页面上说明。',
    '后端不可用（离线演示模式）时如实报「覆盖度报告不可用」，不在浏览器里补算。',
  ],
  'module-card': [
    '题目与「问题 → 字段」映射都从后端下发：engine/teaching/card_coverage.py + stage_questions 词典。',
    '只做事实覆盖比对，不打分；反馈先给命中的事实，再给还没提到的事实。',
    '卡片上 unconfirmed 的字段不参与比对，页面显示「该卡片待教师确认」。',
    '离线时整页如实报「模块卡片任务不可用」——把题目烤进静态快照会造出第二份题目定义。',
  ],
  design: [
    '题干 / 需求简报 / 必备能力清单 / 六维评审全部来自后端：engine/design/ 与 engine/lexicon/design_*.json。',
    '算不出来的维度返回 not_evaluated（score = null + reason），页面显示「本轮未评估」，绝不填 0。',
    '画布（原生 drag + 手写 SVG）只是学生的输入；判定只在后端，前端不自己算分。',
    '第 2 次提交会 iteration + 1 并显示与上一轮的对比；离线时如实报「设计任务不可用」。',
  ],
  training: [
    '判题只在后端：正确答案不下发到学生视图，前端既不持有、也无法推断对错（走查会检查页面里不出现答案字段名）。',
    '离线演示模式下如实报「无法判分」，最终结果页标记未判分，不给掌握度结论。',
    '题目来自契约 training.questions，题数随项目而定（第 2 关按够格的业务模块逐模块出题）。',
    '提示分层：每答错一次消耗一次机会，用尽后才允许继续。',
  ],
  graph: [
    '在线走 GET /api/projects/{id}/business-graph；后端不可用时回落到静态快照的 business_graph 字段。',
    '事实层（调用图 / 状态写入 / 流程 / 依赖）来自 AST，可复现；业务划分是规则引擎的推断结果。',
    '节点带置信度徽章（verified / inferred / inferred-low / unconfirmed），推断级结论注明待教师确认。',
    '复杂度是七维公式的分级信号，不是"好 / 坏"的判定；每个徽章都能展开看公式与阈值。',
  ],
}
const stageScopeLines = computed(() => STAGE_SCOPE_LINES[mainStage.value] || [])

// 切换阶段时把抽屉收起：它的内容是"当前阶段"的口径，留着展开会误导
watch(mainStage, () => { scopeOpen.value = false })

// 外部（系统主页面）改了 initial-stage 时跟随（组件复用的情况下也正确）
watch(() => props.initialStage, (v) => {
  if (v && STAGE_KEYS.includes(v)) mainStage.value = v
})


// P0-01：项目名来自契约 project_name，不再写死项目名字符串
const projectName = computed(() => contract.value?.project_name || contract.value?.project_id || '（未命名项目）')

// 所有业务内容都从契约派生
const questions = computed(() => contract.value?.training?.questions || [])
const projectModules = computed(() => contract.value?.modules || [])
const deepAnalysis = computed(() => contract.value?.deep_analysis || null)

const overviewLine = computed(() => {
  const o = contract.value?.overview
  if (!o) return ''
  return `${o.total_files ?? '?'} 文件 · ${o.module_count ?? projectModules.value.length} 模块 · ${o.total_lines ?? '?'} 行`
})

// 项目背景：优先用契约自带的 project_description；为空时用 overview 的真实统计拼一句，不编造业务场景
const projectBackground = computed(() => {
  const desc = contract.value?.training?.project_description
  if (desc && String(desc).trim()) return String(desc).trim()
  const o = contract.value?.overview
  if (!o) return ''
  return `本项目包含 ${o.total_files ?? '?'} 个源码文件、${o.total_classes ?? '?'} 个类、${o.module_count ?? projectModules.value.length} 个模块，共 ${o.total_lines ?? '?'} 行代码。`
})

// P0-01：目标模块 = 业务类模块（core/business/intermediate）中 core_score 最高的一个
const BUSINESS_MODULE_TYPES = ['core', 'business', 'intermediate']
const businessModules = computed(() => {
  const list = projectModules.value.filter(m => BUSINESS_MODULE_TYPES.includes(String(m.type || '').toLowerCase()))
  return list.length ? list : projectModules.value
})
const targetModule = computed(() => {
  const list = businessModules.value
  if (!list.length) return null
  return list.reduce((best, m) => (Number(m.core_score) || 0) > (Number(best.core_score) || 0) ? m : best, list[0])
})
const targetModuleName = computed(() => targetModule.value?.name || '')

// P0-01：流程名来自 core_flows[0].name
const coreFlow = computed(() => contract.value?.core_flows?.[0] || null)
const flowName = computed(() => coreFlow.value?.name || '')

// P0-01：关键函数来自 deep_analysis.key_implementations.implementations[0]
const keyImplementation = computed(() => deepAnalysis.value?.key_implementations?.implementations?.[0] || null)
const keyFunction = computed(() => keyImplementation.value?.method || '')

// ---------------------------------------------------------------------------
// 关卡状态
// ---------------------------------------------------------------------------
const currentLevel = ref(1)
const currentView = ref('level') // level | result

/** 每关一份独立状态，便于切换项目/关卡时保留 */
const levelStates = ref({})

function defaultLevelState() {
  return {
    selected: [],        // 多选：数组；单选：长度为 0/1 的数组（统一数据结构）
    answered: false,
    grading: null,       // 后端判题响应；离线时为 null
    offlineGraded: false,// true = 本题未判分（离线演示模式）
    hintsRemaining: HINTS_PER_LEVEL,
    hintsUsed: 0,
    submitting: false,
  }
}

function initLevelStates() {
  const next = {}
  questions.value.forEach((_, i) => {
    const restored = session.state.answers?.[i]
    const st = defaultLevelState()
    if (restored) {
      // P0-03：恢复"选了什么 + 上次的判分结论"，但不恢复讲解文本（讲解只在本次提交后展示）
      st.selected = Array.isArray(restored.selected) ? restored.selected : [restored.selected].filter(Boolean)
      st.hintsUsed = Number(session.state.hints_used?.[i + 1]) || 0
      st.hintsRemaining = Math.max(0, HINTS_PER_LEVEL - st.hintsUsed)
      if (restored.graded) {
        st.answered = true
        st.grading = { result: restored.result, matched: [], missing: [], extra: [], explanation: '' }
      } else if (restored.result === 'ungraded') {
        st.answered = true
        st.offlineGraded = true
      }
    }
    next[i] = st
  })
  levelStates.value = next
}

const totalLevels = computed(() => questions.value.length)
const levels = computed(() => questions.value.map((q, i) => q.title || `第 ${i + 1} 关`))
const currentQuestion = computed(() => questions.value[currentLevel.value - 1] || null)
const currentState = computed(() => levelStates.value[currentLevel.value - 1] || defaultLevelState())
const questionType = computed(() => currentQuestion.value?.question_type || '')
const isMultiSelect = computed(() => questionType.value === 'module_selection')
const isLastLevel = computed(() => currentLevel.value >= totalLevels.value)

const progressPercent = computed(() => {
  if (currentView.value === 'result') return 100
  if (!totalLevels.value) return 0
  return ((currentLevel.value - 1) / totalLevels.value) * 100
})

// 题型文案（展示用；题型本身来自契约）
const QUESTION_TYPE_LABELS = {
  module_selection: '功能拆分',
  responsibility_match: '模块职责',
  flow_next_step: '流程推演',
  key_implementation: '关键实现',
}
const questionTypeLabel = computed(() => QUESTION_TYPE_LABELS[questionType.value] || (currentQuestion.value?.question_type || '训练题'))

// 每关的配色主题（纯样式，与业务内容无关）
const LEVEL_THEMES = [
  { badge: 'from-neon-blue to-cyan-400', accent: 'text-neon-blue', button: 'from-neon-blue to-cyan-500', shadow: 'shadow-neon-blue/25' },
  { badge: 'from-neon-purple to-pink-400', accent: 'text-neon-purple', button: 'from-neon-purple to-pink-500', shadow: 'shadow-neon-purple/25' },
  { badge: 'from-amber-400 to-orange-500', accent: 'text-amber-400', button: 'from-amber-500 to-orange-500', shadow: 'shadow-amber-500/25' },
  { badge: 'from-neon-pink to-rose-500', accent: 'text-neon-pink', button: 'from-neon-pink to-rose-500', shadow: 'shadow-neon-pink/25' },
]
const theme = computed(() => LEVEL_THEMES[(currentLevel.value - 1) % LEVEL_THEMES.length])

// 模块卡片的调色板 / 图标（按下标取，不再按写死的模块名取）
const MODULE_PALETTE = ['#00d4ff', '#a855f7', '#ec4899', '#22d3ee', '#f59e0b', '#4ade80']
const MODULE_ICONS = ['📦', '🔐', '🔧', '⚠️', '📊', '🧩']
function paletteColor(i) { return MODULE_PALETTE[i % MODULE_PALETTE.length] }
function paletteIcon(i) { return MODULE_ICONS[i % MODULE_ICONS.length] }

// ---------------------------------------------------------------------------
// 选择 / 提交 / 判分（P0-11：判分只在后端，前端永不读 correct_answers）
// ---------------------------------------------------------------------------
const canSubmit = computed(() => currentState.value.selected.length > 0)

function isAnswered(id) {
  return currentState.value.selected.includes(id)
}

function toggleOption(opt) {
  const st = currentState.value
  if (st.answered) return
  const idx = st.selected.indexOf(opt.id)
  if (idx >= 0) st.selected.splice(idx, 1)
  else st.selected.push(opt.id)
}

function selectSingle(id) {
  const st = currentState.value
  if (st.answered) return
  st.selected = [id]
}

/** 判分后：matched 高亮绿色，选错的标红；没有 correct_answers 可用，也不需要 */
function gradingMatched(id) {
  return (currentState.value.grading?.matched || []).includes(id)
}

function multiOptionClass(opt) {
  const st = currentState.value
  if (!st.answered) {
    return isAnswered(opt.id) ? 'border-neon-blue bg-neon-blue/10' : 'border-deep-border hover:border-neon-blue/30'
  }
  if (gradingMatched(opt.id)) return 'border-green-500 bg-green-500/10'
  if (isAnswered(opt.id)) return 'border-red-500 bg-red-500/10'
  return 'border-deep-border opacity-50'
}

function multiCheckboxClass(opt) {
  const st = currentState.value
  if (!st.answered) return isAnswered(opt.id) ? 'bg-neon-blue border-neon-blue' : 'border-gray-600'
  if (gradingMatched(opt.id)) return 'bg-green-500 border-green-500'
  return 'border-gray-600'
}

function singleOptionClass(opt) {
  const st = currentState.value
  if (!st.answered) return isAnswered(opt.id) ? 'selected' : ''
  if (gradingMatched(opt.id)) return 'correct'
  if (isAnswered(opt.id)) return 'wrong'
  return ''
}

function optionLetterStyle(opt) {
  const st = currentState.value
  const selected = isAnswered(opt.id)
  if (st.answered) {
    if (gradingMatched(opt.id)) return { background: '#4ade80', color: '#fff' }
    if (selected) return { background: '#f87171', color: '#fff' }
  }
  return selected
    ? { background: '#a855f7', color: '#fff' }
    : { background: '#1f1f2e', color: '#94a3b8' }
}

const showNextButton = computed(() => {
  const st = currentState.value
  if (!st.answered) return false
  if (st.offlineGraded) return true                                  // 离线：不判分，允许继续
  if (st.grading?.result === 'correct') return true
  return st.hintsRemaining === 0                                     // 用尽机会后也允许继续
})

const showHintPanel = computed(() => {
  const st = currentState.value
  if (!st.answered || st.offlineGraded) return false
  if (st.grading?.result === 'correct') return false
  return st.hintsRemaining > 0
})

async function submitCurrent() {
  const st = currentState.value
  const q = currentQuestion.value
  if (!q || st.answered || st.submitting || !st.selected.length) return

  const index = currentLevel.value - 1
  st.submitting = true
  // P0-11：判题走后端；离线时 submitAnswer 返回 offline=true，不伪造分数
  const res = await ds.submitAnswer(projectId.value, index, st.selected)
  st.submitting = false
  st.answered = true

  if (res.ok) {
    st.grading = res.data
    st.offlineGraded = false
    if (res.data.result !== 'correct' && st.hintsRemaining > 0) {
      st.hintsRemaining--
      st.hintsUsed++
      session.recordHint(currentLevel.value)
    }
    session.recordAnswer(index, { selected: st.selected, result: res.data.result, graded: true })
  } else {
    // 离线演示模式：明确"未判分"，学生可以直接进入下一关
    st.grading = null
    st.offlineGraded = true
    session.recordAnswer(index, { selected: st.selected, result: 'ungraded', graded: false })
  }
}

function retryCurrent() {
  const st = currentState.value
  st.answered = false
  st.grading = null
  st.offlineGraded = false
}

// ---------------------------------------------------------------------------
// 提示内容（全部由契约数据驱动，P0-01：不再出现某个具体项目的样例文案）
// ---------------------------------------------------------------------------
const moduleTypeSummary = computed(() => {
  const counts = {}
  projectModules.value.forEach(m => {
    const t = String(m.type || 'unknown')
    counts[t] = (counts[t] || 0) + 1
  })
  return Object.entries(counts).map(([type, count]) => ({ type, count }))
})

// 只有"功能拆分"这一关才用模块类型分布做提示（它才是关于模块职责边界的题）
const showModuleTypeChips = computed(() => questionType.value === 'module_selection')

function typeLabel(type) {
  const map = { core: '核心业务', business: '业务', intermediate: '中间层', orchestrator: '编排', peripheral: '外围支撑', unknown: '未标注类型' }
  return map[type] || type
}

const currentHintText = computed(() => {
  const used = currentState.value.hintsUsed
  const pick = (hints) => hints[Math.min(Math.max(used - 1, 0), hints.length - 1)]

  if (questionType.value === 'module_selection') {
    return pick([
      `这个项目一共有 ${projectModules.value.length} 个代码模块，其中真正承担业务职责的只是其中一部分——先判断"谁持有业务状态并对外提供操作"。`,
      '从"人、事、物"三个角度拆：谁来用？做什么事？对什么资源做？只负责装配/编排的模块不算业务模块。',
      '再看一眼模块的类型：编排（orchestrator）与外围支撑（peripheral）都不该算核心业务模块。',
    ])
  }
  if (questionType.value === 'responsibility_match') {
    return pick([
      targetModuleName.value
        ? `再想想「${targetModuleName.value}」这个名字——它的核心职责应该跟什么最相关？`
        : '契约里没有可判定的业务模块，先看模块清单，找出承担业务职责的那几个。',
      '好的模块职责描述应该回答三个问题：管什么数据？提供什么操作？对外暴露什么接口？',
      '注意区分"核心职责"和"附带功能"——一个模块可以有很多功能，但核心职责只有一个。',
    ])
  }
  if (questionType.value === 'flow_next_step') {
    return pick([
      '顺着数据流向去想：用户触发一个操作，第一步做什么？最后一步做什么？',
      '业务流程通常遵循"校验 → 处理 → 记录"的模式，想想每一步属于哪个阶段。',
      '注意：有些步骤是前置条件，有些是核心操作，有些是收尾工作。区分它们的顺序。',
    ])
  }
  return pick([
    keyFunction.value
      ? `关键函数「${keyFunction.value}」的核心思路是什么？先想想它要解决什么问题。`
      : '先看代码证据：这个方法要做几件事？边界条件在哪？',
    '一个好的实现思路，应该先说清楚"输入是什么、输出是什么、核心逻辑分几步"。',
    '注意看函数名里的关键词——"check"、"validate"、"find" 这些词暗示了实现方式。',
  ])
})

const hintKeywords = computed(() => {
  if (questionType.value !== 'responsibility_match') return []
  const resps = targetModule.value?.responsibilities || []
  const words = []
  resps.forEach(r => {
    const tokens = String(r).split(/[、，/（）()]/).filter(t => t.trim().length > 1 && t.length < 6)
    words.push(...tokens)
  })
  return [...new Set(words)].slice(0, 4)
})

const flowAnchor = computed(() => {
  if (questionType.value !== 'flow_next_step') return null
  const steps = coreFlow.value?.steps
  if (!steps?.length) return null
  return {
    start: steps[0].method || steps[0].name,
    end: steps[steps.length - 1].method || steps[steps.length - 1].name,
  }
})

const keyImplHint = computed(() => {
  if (questionType.value !== 'key_implementation') return null
  const imp = keyImplementation.value
  if (!imp) return null
  return {
    design_approach: imp.design_approach,
    design_characteristics: imp.design_characteristics,
    complexity: imp.complexity ?? '?',
    state_write_count: (imp.state_writes || []).length,
    validation_count: (imp.validation_checks || []).length,
  }
})

// ---------------------------------------------------------------------------
// 结果统计（P0-11：区分"已判分"与"未判分"，不谎报分数）
// ---------------------------------------------------------------------------
const perLevel = computed(() => questions.value.map((_, i) => {
  const st = levelStates.value[i] || defaultLevelState()
  const graded = !!st.grading
  return {
    index: i,
    graded,
    answered: st.answered,
    correct: graded && st.grading.result === 'correct',
  }
}))

const resultSummary = computed(() => {
  const graded = perLevel.value.filter(p => p.graded)
  const ungraded = perLevel.value.filter(p => !p.graded && p.answered)
  const unanswered = perLevel.value.filter(p => !p.answered)
  return {
    total: totalLevels.value,
    gradedCount: graded.length,
    correct: graded.filter(p => p.correct).length,
    ungradedCount: ungraded.length,
    unansweredCount: unanswered.length,
  }
})

const gradedPercent = computed(() => {
  const { gradedCount, total } = resultSummary.value
  if (!total || !gradedCount) return 0
  return (resultSummary.value.correct / gradedCount) * 100
})

function isLevelCorrect(i) {
  return !!perLevel.value[i]?.correct
}

function resultCellText(i) {
  const p = perLevel.value[i]
  if (!p?.graded) return '—'
  return p.correct ? '✓' : '✗'
}

function resultCellClass(i) {
  const p = perLevel.value[i]
  if (!p?.graded) return 'bg-deep-border/40 text-gray-500 border border-deep-border'
  return p.correct
    ? 'bg-green-500/20 text-green-400 border border-green-500/30'
    : 'bg-red-500/20 text-red-400 border border-red-500/30'
}

// 雷达图维度 = 各关（标签去掉"第N关："前缀），未判分的维度用灰色
const radarDims = computed(() => questions.value.map((q, i) => ({
  label: String(q.title || `第 ${i + 1} 关`).replace(/^第\s*\d+\s*关\s*[：:]\s*/, ''),
  color: perLevel.value[i]?.graded ? MODULE_PALETTE[i % MODULE_PALETTE.length] : '#4b5563',
})))

const radarScores = computed(() => perLevel.value.map(p => (p.graded ? (p.correct ? 1 : 0) : 0)))

const scoreLevel = computed(() => {
  const { gradedCount, correct } = resultSummary.value
  if (!gradedCount) {
    return {
      label: '未判分',
      color: 'text-amber-400',
      comment: '后端判题不可用（离线演示模式），本次没有产生成绩。接入后端后重新提交即可获得真实评级。',
    }
  }
  const pct = correct / gradedCount
  if (pct === 1) return { label: '非常优秀', color: 'text-green-400', comment: '你对这个项目的业务逻辑理解很透彻，从模块划分到核心实现都掌握得很好。' }
  if (pct >= 0.75) return { label: '良好', color: 'text-neon-blue', comment: '整体理解不错，个别细节还需要加强。建议重点复习答错的部分。' }
  if (pct >= 0.5) return { label: '及格', color: 'text-amber-400', comment: '有一定基础，但对系统的整体把握还不够。建议再走一遍流程，重点理解模块间关系。' }
  return { label: '需要加强', color: 'text-red-400', comment: '对项目的业务逻辑还比较陌生。建议从模块拆分开始重新学习，一步步建立全局认识。' }
})

// 薄弱点建议按题型给（与具体项目无关，不写死业务样例）
const ADVICE_BY_TYPE = {
  module_selection: '功能拆分：先判断哪些模块持有业务状态并对外提供操作，只做装配编排的模块不算核心业务模块',
  responsibility_match: '模块职责：对照模块卡片里的职责清单，区分"核心职责"与"附带功能"',
  flow_next_step: '流程推演：按"校验 → 处理 → 记录/状态变更"梳理顺序，注意前置条件的先后',
  key_implementation: '关键实现：对照真实源码，看边界校验、状态写入与异常处理是否齐全',
}
const weakPoints = computed(() => {
  const res = []
  perLevel.value.forEach((p, i) => {
    if (p.graded && !p.correct) {
      const t = questions.value[i]?.question_type
      // 同一题型可能有多道题（第 2 关每个业务模块一道），建议去重后只出现一次
      const advice = ADVICE_BY_TYPE[t] || `第 ${i + 1} 关建议重新作答并阅读讲评`
      if (!res.includes(advice)) res.push(advice)
    }
  })
  return res
})

// ---------------------------------------------------------------------------
// 证据跳转（P0-09：项目内相对路径 + 行区间）
// ---------------------------------------------------------------------------
const sourceViewer = ref({ visible: false, path: '', start: null, end: null, hint: '' })

function openSource(path, start, end, hint = '') {
  if (!path) return
  sourceViewer.value = {
    visible: true,
    path: String(path).replace(/\\/g, '/'),
    start: Number.isFinite(start) ? start : null,
    end: Number.isFinite(end) ? end : null,
    hint: hint || `${path}${start ? ' · L' + start : ''}`,
  }
}

// 打开证据就记一次事件（供能力报告统计）
function onEvidenceLoaded({ path, start, end }) {
  session.recordEvidence(path, start, end)
}

// ---------------------------------------------------------------------------
// 导航 / 会话
// ---------------------------------------------------------------------------
const shortSessionId = computed(() => String(session.state.session_id || '').slice(-6))

function nextLevel() {
  if (currentLevel.value < totalLevels.value) currentLevel.value++
  else currentView.value = 'result'
}

function prevLevel() {
  if (currentLevel.value > 1) currentLevel.value--
}

function goBackToLastLevel() {
  currentView.value = 'level'
  currentLevel.value = totalLevels.value || 1
}

function restart() {
  currentView.value = 'level'
  currentLevel.value = 1
  levelStates.value = {}
  questions.value.forEach((_, i) => { levelStates.value[i] = defaultLevelState() })
  // P0-03：清空会话里本项目的作答记录，并写回 localStorage
  session.resetProgress()
}

function onProjectChange(id) {
  if (!id || id === projectId.value) return
  projectId.value = id
}

async function reload() {
  const listRes = await ds.listProjects()
  projects.value = listRes.data.projects
  await loadProject(projectId.value)
}

async function loadProject(id) {
  loading.value = true
  loadError.value = ''
  const res = await ds.loadContract(id)
  if (!res.ok) {
    contract.value = null
    loadError.value = res.error || '未知错误'
    loading.value = false
    return
  }
  contract.value = res.data

  // P0-03：恢复会话；契约版本/项目不一致时 store 会丢弃并说明原因
  session.restoreFor(res.data.project_id || id, String(res.data.contract_version || ''))
  initLevelStates()

  // 恢复阶段（stage 形如 'level:2' / 'result'）
  const stage = String(session.state.stage || '')
  if (stage === 'result') {
    currentView.value = 'result'
  } else {
    currentView.value = 'level'
    const m = stage.match(/^level:(\d+)$/)
    const restoredLevel = m ? Number(m[1]) : 1
    currentLevel.value = Math.min(Math.max(restoredLevel, 1), Math.max(totalLevels.value, 1))
  }

  loading.value = false
}

onMounted(async () => {
  // 项目列表：在线取 API，离线用静态 demo 列表
  const listRes = await ds.listProjects()
  projects.value = listRes.data.projects
  // URL 深链：把当前项目写回 ?project=，方便复制链接直达
  ds.writeProjectToUrl(projectId.value)
  await loadProject(projectId.value)
})

// 切换项目：写回 ?project= 深链 + 重新加载
watch(projectId, async (id) => {
  ds.writeProjectToUrl(id)
  await loadProject(id)
})

// 记录阶段，供下次恢复
watch([currentLevel, currentView], () => {
  if (!contract.value) return
  session.setStage(currentView.value === 'result' ? 'result' : `level:${currentLevel.value}`)
})

// ---------------------------------------------------------------------------
// 层进式展现（UI 重设计一轮）
// ---------------------------------------------------------------------------
// 舞台/关卡/视图一变就重新武装一次：切页签会换掉一批 DOM（v-if 懒挂载），
// 换关卡会重建答题卡（`:key="'level-' + currentLevel"`）—— 新节点要重新进入
// "先武装、再点亮"的流程，否则它们只会直接出现（不难看，但没有层次感）。
// 注意：`useLayeredReveal` 的重新扫描放在下一帧（rAF），所以扫到的一定是新 DOM。
const rootRef = ref(null)
useLayeredReveal(rootRef, {
  watchSource: () => [mainStage.value, currentLevel.value, currentView.value],
})
</script>

<style scoped>
.slide-fade-enter-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-fade-enter-from {
  opacity: 0;
  transform: translateX(30px);
}
.slide-fade-leave-to {
  opacity: 0;
  transform: translateX(-30px);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
