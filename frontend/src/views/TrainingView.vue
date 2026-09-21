<template>
  <div class="min-h-screen bg-grid relative overflow-hidden">
    <!-- 背景装饰 -->
    <div class="glow-orb w-[700px] h-[700px] -top-52 right-[-200px] bg-neon-purple opacity-20"></div>
    <div class="glow-orb w-[500px] h-[500px] bottom-[-150px] left-[-100px] bg-neon-blue opacity-20"></div>

    <div class="relative z-10 max-w-5xl mx-auto px-6 py-8">
      <!-- 顶部：项目信息 + 进度 -->
      <div class="mb-8">
        <div class="flex items-center justify-between mb-4">
          <div>
            <div class="text-xs text-gray-500 font-mono tracking-widest uppercase mb-1">Project Training</div>
            <h1 class="text-2xl font-bold gradient-text">{{ projectName }}</h1>
          </div>
          <div class="text-right">
            <div class="text-xs text-gray-500 mb-1">完成进度</div>
            <div class="text-2xl font-bold text-white font-mono">
              {{ currentLevel }}<span class="text-gray-600">/{{ totalLevels }}</span>
            </div>
          </div>
        </div>

        <!-- 进度条 + 关卡节点 -->
        <div class="relative">
          <div class="h-1 bg-deep-border rounded-full overflow-hidden">
            <div
              class="h-full difficulty-gradient transition-all duration-700 ease-out progress-bar"
              :style="{ width: progressPercent + '%' }"
            ></div>
          </div>
          <div class="flex justify-between mt-2">
            <div
              v-for="(level, i) in levels"
              :key="i"
              class="flex flex-col items-center relative"
              style="width: 25%;"
            >
              <div
                class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 z-10"
                :class="{
                  'bg-neon-blue text-white shadow-lg shadow-neon-blue/30 scale-110': i + 1 === currentLevel,
                  'bg-green-500 text-white': i + 1 < currentLevel,
                  'bg-deep-border text-gray-500': i + 1 > currentLevel,
                }"
                :style="{ marginTop: i + 1 === currentLevel ? '-11px' : '-8px' }"
              >
                <span v-if="i + 1 < currentLevel">✓</span>
                <span v-else>{{ i + 1 }}</span>
              </div>
              <div
                class="text-[11px] mt-2 text-center font-medium transition-colors"
                :class="{
                  'text-neon-blue': i + 1 === currentLevel,
                  'text-green-400': i + 1 < currentLevel,
                  'text-gray-500': i + 1 > currentLevel,
                }"
              >
                {{ level }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 答题区域 -->
      <div class="relative">
        <transition name="slide-fade" mode="out-in">

          <!-- 关卡区域 -->
          <div v-if="currentView === 'level'" :key="'level-' + currentLevel" class="space-y-6">

            <!-- 第 1 关：功能拆分 -->
            <div v-if="currentLevel === 1" class="glass-card p-8 neon-border">
            <div class="flex items-center gap-3 mb-6">
              <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-neon-blue to-cyan-400 flex items-center justify-center text-white font-bold">
                1
              </div>
              <div>
                <h2 class="text-lg font-bold text-white">功能拆分</h2>
                <p class="text-xs text-gray-500">这个系统应该有哪些核心模块？</p>
              </div>
            </div>

            <div class="mb-6 p-4 rounded-xl bg-deep-card/50 border border-deep-border">
              <div class="text-xs text-gray-400 mb-2">📋 项目背景</div>
              <p class="text-sm text-gray-300 leading-relaxed">
                这是一个实验室安全管理系统。高校实验室需要预约使用，设备需要管理，
                安全检查要定期进行，用户有不同的角色权限。
              </p>
            </div>

            <div class="mb-2 text-sm text-gray-400">
              请选出这个系统<strong class="text-neon-blue">应该包含</strong>的核心功能模块（<span class="text-neon-blue">多选</span>）
            </div>
            <div class="mb-4 text-xs text-gray-500">
              已选 {{ selectedCount }} 项
            </div>

            <div class="grid grid-cols-2 gap-3 mb-8">
              <div
                v-for="opt in currentQuestion.options"
                :key="opt.id"
                class="p-4 rounded-xl border cursor-pointer transition-all group"
                :class="getOptionClass(opt)"
                @click="selectOption(opt)"
              >
                <div class="flex items-start gap-3">
                  <div
                    class="w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 transition-all"
                    :class="getCheckboxClass(opt)"
                  >
                    <svg v-if="isSelected(opt.id)" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
                      <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                  </div>
                  <div>
                    <div class="text-sm font-medium text-white mb-1 group-hover:text-neon-blue transition-colors">
                      {{ opt.text }}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 答错引导面板 -->
            <transition name="fade">
              <div v-if="level1Answered && !level1Correct && level1HintsRemaining > 0"
                   class="mb-6 p-5 rounded-xl bg-amber-500/5 border border-amber-500/30 relative overflow-hidden">
                <div class="absolute top-0 right-0 w-32 h-32 bg-amber-500/5 rounded-full -translate-y-1/2 translate-x-1/2"></div>
                <div class="relative">
                  <div class="flex items-center gap-2 mb-3">
                    <div class="w-8 h-8 rounded-lg bg-amber-500/20 flex items-center justify-center text-amber-400 text-lg">💡</div>
                    <div>
                      <div class="font-bold text-amber-400">别急，给你一条线索</div>
                      <div class="text-xs text-amber-400/60">还剩 {{ level1HintsRemaining }} 次尝试机会</div>
                    </div>
                  </div>

                  <div class="text-sm text-gray-300 leading-relaxed mb-4">
                    {{ level1Hint }}
                  </div>

                  <!-- 相关模块线索 -->
                  <div v-if="level1HintModules.length" class="mb-4">
                    <div class="text-xs text-gray-500 mb-2">相关模块提示：</div>
                    <div class="flex flex-wrap gap-2">
                      <div
                        v-for="mod in level1HintModules"
                        :key="mod.name"
                        class="px-3 py-1.5 rounded-lg bg-deep-card/80 border border-deep-border text-xs"
                      >
                        <span class="text-white font-medium">{{ mod.name }}</span>
                        <span class="text-gray-500 ml-2">{{ mod.hint }}</span>
                      </div>
                    </div>
                  </div>

                  <button
                    @click="retryLevel1"
                    class="px-5 py-2 rounded-lg text-sm font-medium text-white
                           bg-gradient-to-r from-amber-500 to-orange-500
                           hover:shadow-lg hover:shadow-amber-500/25 hover:-translate-y-0.5 transition-all"
                  >
                    🔄 再试一次
                  </button>
                </div>
              </div>
            </transition>

            <!-- 答题反馈 -->
            <transition name="fade">
              <div v-if="level1Answered && (level1Correct || level1HintsRemaining === 0)" class="mb-6 p-4 rounded-xl"
                :class="level1Correct ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'"
              >
                <div class="font-bold mb-2" :class="level1Correct ? 'text-green-400' : 'text-red-400'">
                  {{ level1Correct ? '✓ 完全正确！' : '✗ 已经尝试了所有机会' }}
                </div>
                <div class="text-sm text-gray-400 leading-relaxed" v-html="currentQuestion.explanation"></div>
              </div>
            </transition>

            <div class="flex justify-between">
              <div></div>
              <button
                v-if="!level1Answered"
                @click="submitLevel1"
                :disabled="selectedCount === 0"
                class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all
                       bg-gradient-to-r from-neon-blue to-cyan-500
                       hover:shadow-lg hover:shadow-neon-blue/25 hover:-translate-y-0.5
                       disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-y-0"
              >
                提交答案
              </button>
              <button
                v-else-if="level1Correct || level1HintsRemaining === 0"
                @click="nextLevel"
                class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all
                       bg-gradient-to-r from-neon-purple to-neon-pink
                       hover:shadow-lg hover:shadow-neon-purple/25 hover:-translate-y-0.5"
              >
                下一关 →
              </button>
            </div>
          </div>

          <!-- 第 2 关：模块职责 -->
          <div v-else-if="currentLevel === 2" key="level2" class="glass-card p-8 neon-border">
            <div class="flex items-center gap-3 mb-6">
              <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-neon-purple to-pink-400 flex items-center justify-center text-white font-bold">
                2
              </div>
              <div>
                <h2 class="text-lg font-bold text-white">模块职责</h2>
                <p class="text-xs text-gray-500">每个模块具体负责什么？</p>
              </div>
            </div>

            <div class="mb-6 p-4 rounded-xl bg-deep-card/50 border border-deep-border">
              <div class="text-xs text-gray-400 mb-2">🎯 当前模块</div>
              <div class="text-xl font-bold text-neon-purple mb-1">{{ targetModuleName }}</div>
              <p class="text-sm text-gray-400">
                思考一下：这个模块在系统中承担什么角色？它的核心职责是什么？
              </p>
            </div>

            <div class="mb-4 text-sm text-gray-400">请选出最准确的职责描述：</div>

            <div class="space-y-2.5 mb-8">
              <div
                v-for="opt in currentQuestion.options"
                :key="opt.id"
                class="quiz-option"
                :class="{
                  selected: selectedLevel2 === opt.id && !level2Answered,
                  correct: level2Answered && isCorrectOption(opt),
                  wrong: level2Answered && selectedLevel2 === opt.id && !isCorrectOption(opt),
                }"
                @click="selectLevel2(opt.id)"
              >
                <span class="option-letter"
                  :style="{
                    background: level2Answered && isCorrectOption(opt) ? '#4ade80' :
                               level2Answered && selectedLevel2 === opt.id && !isCorrectOption(opt) ? '#f87171' :
                               selectedLevel2 === opt.id ? '#a855f7' : '#1f1f2e',
                    color: (level2Answered && isCorrectOption(opt)) || (selectedLevel2 === opt.id) ? '#fff' : '#94a3b8'
                  }"
                >{{ opt.id }}</span>
                <span class="text-sm text-gray-300 pt-0.5">{{ opt.text }}</span>
              </div>
            </div>

            <!-- 答错引导面板 -->
            <transition name="fade">
              <div v-if="level2Answered && !level2Correct && level2HintsRemaining > 0"
                   class="mb-6 p-5 rounded-xl bg-purple-500/5 border border-purple-500/30 relative overflow-hidden">
                <div class="absolute top-0 right-0 w-32 h-32 bg-purple-500/5 rounded-full -translate-y-1/2 translate-x-1/2"></div>
                <div class="relative">
                  <div class="flex items-center gap-2 mb-3">
                    <div class="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center text-purple-400 text-lg">🔍</div>
                    <div>
                      <div class="font-bold text-purple-400">再深入想想</div>
                      <div class="text-xs text-purple-400/60">还剩 {{ level2HintsRemaining }} 次尝试机会</div>
                    </div>
                  </div>

                  <div class="text-sm text-gray-300 leading-relaxed mb-3">
                    {{ level2Hint }}
                  </div>

                  <!-- 职责关键词线索 -->
                  <div v-if="level2HintKeywords.length" class="mb-4">
                    <div class="text-xs text-gray-500 mb-2">这个模块的核心职责关键词：</div>
                    <div class="flex flex-wrap gap-1.5">
                      <span
                        v-for="kw in level2HintKeywords"
                        :key="kw"
                        class="px-2.5 py-1 text-xs rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20"
                      >
                        {{ kw }}
                      </span>
                    </div>
                  </div>

                  <button
                    @click="retryLevel2"
                    class="px-5 py-2 rounded-lg text-sm font-medium text-white
                           bg-gradient-to-r from-purple-500 to-pink-500
                           hover:shadow-lg hover:shadow-purple-500/25 hover:-translate-y-0.5 transition-all"
                  >
                    🔄 再试一次
                  </button>
                </div>
              </div>
            </transition>

            <!-- 答题反馈 -->
            <transition name="fade">
              <div v-if="level2Answered && (level2Correct || level2HintsRemaining === 0)" class="mb-6 p-4 rounded-xl"
                :class="level2Correct ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'"
              >
                <div class="font-bold mb-2" :class="level2Correct ? 'text-green-400' : 'text-red-400'">
                  {{ level2Correct ? '✓ 回答正确！' : '✗ 已经尝试了所有机会' }}
                </div>
                <div class="text-sm text-gray-400 leading-relaxed" v-html="currentQuestion.explanation"></div>
              </div>
            </transition>

            <div class="flex justify-between">
              <button
                @click="prevLevel"
                class="px-4 py-2.5 rounded-xl text-sm text-gray-400 hover:text-white transition-colors"
              >
                ← 上一关
              </button>
              <button
                v-if="!level2Answered"
                @click="submitLevel2"
                :disabled="!selectedLevel2"
                class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all
                       bg-gradient-to-r from-neon-purple to-pink-500
                       hover:shadow-lg hover:shadow-neon-purple/25 hover:-translate-y-0.5
                       disabled:opacity-40 disabled:cursor-not-allowed"
              >
                提交答案
              </button>
              <button
                v-else-if="level2Correct || level2HintsRemaining === 0"
                @click="nextLevel"
                class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all
                       bg-gradient-to-r from-neon-purple to-neon-pink
                       hover:shadow-lg hover:shadow-neon-purple/25 hover:-translate-y-0.5"
              >
                下一关 →
              </button>
            </div>
          </div>

          <!-- 第 3 关：流程推演 -->
          <div v-else-if="currentLevel === 3" key="level3" class="glass-card p-8 neon-border">
            <div class="flex items-center gap-3 mb-6">
              <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-white font-bold">
                3
              </div>
              <div>
                <h2 class="text-lg font-bold text-white">流程推演</h2>
                <p class="text-xs text-gray-500">核心业务流程的步骤顺序是什么？</p>
              </div>
            </div>

            <div class="mb-6 p-4 rounded-xl bg-deep-card/50 border border-deep-border">
              <div class="text-xs text-gray-400 mb-2">⚡ 核心流程</div>
              <div class="text-xl font-bold text-amber-400 mb-1">{{ flowName }}</div>
              <p class="text-sm text-gray-400">
                一个完整的业务操作，应该按照什么顺序执行？请思考数据和状态的流转逻辑。
              </p>
            </div>

            <div class="mb-4 text-sm text-gray-400">选出步骤顺序正确的选项：</div>

            <div class="space-y-3 mb-8">
              <div
                v-for="opt in currentQuestion.options"
                :key="opt.id"
                class="p-4 rounded-xl border cursor-pointer transition-all font-mono text-sm"
                :class="{
                  'border-neon-amber bg-amber-500/10': selectedLevel3 === opt.id && !level3Answered,
                  'border-green-500 bg-green-500/10': level3Answered && isCorrectOption(opt),
                  'border-red-500 bg-red-500/10': level3Answered && selectedLevel3 === opt.id && !isCorrectOption(opt),
                  'border-deep-border hover:border-amber-500/30': !level3Answered && selectedLevel3 !== opt.id,
                }"
                @click="selectLevel3(opt.id)"
              >
                <div class="flex items-center gap-2">
                  <span
                    class="w-6 h-6 rounded flex items-center justify-center text-xs font-bold flex-shrink-0"
                    :style="{
                      background: level3Answered && isCorrectOption(opt) ? '#4ade80' :
                                 level3Answered && selectedLevel3 === opt.id && !isCorrectOption(opt) ? '#f87171' :
                                 selectedLevel3 === opt.id ? '#f59e0b' : '#1f1f2e',
                      color: (level3Answered && isCorrectOption(opt)) || selectedLevel3 === opt.id ? '#0a0a0f' : '#94a3b8'
                    }"
                  >{{ opt.id }}</span>
                  <span class="text-gray-300">{{ opt.text }}</span>
                </div>
              </div>
            </div>

            <!-- 答错引导面板 -->
            <transition name="fade">
              <div v-if="level3Answered && !level3Correct && level3HintsRemaining > 0"
                   class="mb-6 p-5 rounded-xl bg-amber-500/5 border border-amber-500/30 relative overflow-hidden">
                <div class="absolute top-0 right-0 w-32 h-32 bg-amber-500/5 rounded-full -translate-y-1/2 translate-x-1/2"></div>
                <div class="relative">
                  <div class="flex items-center gap-2 mb-3">
                    <div class="w-8 h-8 rounded-lg bg-amber-500/20 flex items-center justify-center text-amber-400 text-lg">⚡</div>
                    <div>
                      <div class="font-bold text-amber-400">顺着流程再理一遍</div>
                      <div class="text-xs text-amber-400/60">还剩 {{ level3HintsRemaining }} 次尝试机会</div>
                    </div>
                  </div>

                  <div class="text-sm text-gray-300 leading-relaxed mb-3">
                    {{ level3Hint }}
                  </div>

                  <!-- 流程线索：首尾锚点 -->
                  <div v-if="level3FlowAnchor" class="mb-4">
                    <div class="text-xs text-gray-500 mb-2">流程线索：</div>
                    <div class="flex items-center gap-2 text-xs">
                      <span class="px-3 py-1.5 rounded-lg bg-green-500/10 text-green-400 border border-green-500/30 font-mono">
                        ▶ {{ level3FlowAnchor.start }}
                      </span>
                      <span class="text-gray-600">→ ... →</span>
                      <span class="px-3 py-1.5 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/30 font-mono">
                        ◼ {{ level3FlowAnchor.end }}
                      </span>
                    </div>
                    <div class="text-xs text-gray-500 mt-2">
                      流程从 <span class="text-green-400">{{ level3FlowAnchor.start }}</span> 开始，
                      到 <span class="text-purple-400">{{ level3FlowAnchor.end }}</span> 结束。
                      中间步骤应该如何排列？
                    </div>
                  </div>

                  <button
                    @click="retryLevel3"
                    class="px-5 py-2 rounded-lg text-sm font-medium text-white
                           bg-gradient-to-r from-amber-500 to-orange-500
                           hover:shadow-lg hover:shadow-amber-500/25 hover:-translate-y-0.5 transition-all"
                  >
                    🔄 再试一次
                  </button>
                </div>
              </div>
            </transition>

            <!-- 答题反馈 -->
            <transition name="fade">
              <div v-if="level3Answered && (level3Correct || level3HintsRemaining === 0)" class="mb-6 p-4 rounded-xl"
                :class="level3Correct ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'"
              >
                <div class="font-bold mb-2" :class="level3Correct ? 'text-green-400' : 'text-red-400'">
                  {{ level3Correct ? '✓ 流程正确！' : '✗ 已经尝试了所有机会' }}
                </div>
                <div class="text-sm text-gray-400 leading-relaxed" v-html="currentQuestion.explanation"></div>
              </div>
            </transition>

            <div class="flex justify-between">
              <button
                @click="prevLevel"
                class="px-4 py-2.5 rounded-xl text-sm text-gray-400 hover:text-white transition-colors"
              >
                ← 上一关
              </button>
              <button
                v-if="!level3Answered"
                @click="submitLevel3"
                :disabled="!selectedLevel3"
                class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all
                       bg-gradient-to-r from-amber-500 to-orange-500
                       hover:shadow-lg hover:shadow-amber-500/25 hover:-translate-y-0.5
                       disabled:opacity-40 disabled:cursor-not-allowed"
              >
                提交答案
              </button>
              <button
                v-else-if="level3Correct || level3HintsRemaining === 0"
                @click="nextLevel"
                class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all
                       bg-gradient-to-r from-neon-purple to-neon-pink
                       hover:shadow-lg hover:shadow-neon-purple/25 hover:-translate-y-0.5"
              >
                下一关 →
              </button>
            </div>
          </div>

          <!-- 第 4 关：关键实现 -->
          <div v-else-if="currentLevel === 4" key="level4" class="glass-card p-8 neon-border">
            <div class="flex items-center gap-3 mb-6">
              <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-neon-pink to-rose-500 flex items-center justify-center text-white font-bold">
                4
              </div>
              <div>
                <h2 class="text-lg font-bold text-white">关键实现</h2>
                <p class="text-xs text-gray-500">核心功能的实现思路是什么？</p>
              </div>
            </div>

            <!-- 关键实现深度分析 -->
            <div class="mb-6 space-y-4">
              <!-- 代码片段 -->
              <div class="rounded-xl overflow-hidden border border-deep-border">
                <div class="flex items-center justify-between px-4 py-2.5 bg-deep-card/80 border-b border-deep-border">
                  <div class="flex items-center gap-2">
                    <div class="flex gap-1.5">
                      <span class="w-3 h-3 rounded-full bg-red-500/60"></span>
                      <span class="w-3 h-3 rounded-full bg-yellow-500/60"></span>
                      <span class="w-3 h-3 rounded-full bg-green-500/60"></span>
                    </div>
                    <span class="text-xs text-gray-500 font-mono ml-2">{{ keyImpFile }}</span>
                  </div>
                  <span class="text-[10px] text-gray-500">L{{ keyImpLineRange }}</span>
                </div>
                <div class="p-4 bg-deep-card/40 overflow-x-auto">
                  <pre class="text-xs text-gray-300 leading-relaxed font-mono"><code><template v-for="(line, idx) in keyImpCodeLines" :key="idx"><span class="inline-block w-6 text-right mr-3 text-gray-600 select-none">{{ idx + keyImpStartLine }}</span><span v-html="line"></span>
</template></code></pre>
                </div>
              </div>

              <!-- 分析维度 -->
              <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div class="p-3 rounded-lg bg-deep-card/50 border border-deep-border text-center">
                  <div class="text-lg font-bold text-neon-pink font-mono">{{ keyImpData?.complexity || '?' }}</div>
                  <div class="text-[10px] text-gray-500 mt-0.5">圈复杂度</div>
                </div>
                <div class="p-3 rounded-lg bg-deep-card/50 border border-deep-border text-center">
                  <div class="text-lg font-bold text-amber-400 font-mono">{{ keyImpData?.state_writes?.length || 0 }}</div>
                  <div class="text-[10px] text-gray-500 mt-0.5">状态写入</div>
                </div>
                <div class="p-3 rounded-lg bg-deep-card/50 border border-deep-border text-center">
                  <div class="text-lg font-bold text-green-400 font-mono">{{ keyImpData?.validation_checks?.length || 0 }}</div>
                  <div class="text-[10px] text-gray-500 mt-0.5">前置校验</div>
                </div>
                <div class="p-3 rounded-lg bg-deep-card/50 border border-deep-border text-center">
                  <div class="text-lg font-bold text-purple-400 font-mono">{{ keyImpData?.error_handling?.length || 0 }}</div>
                  <div class="text-[10px] text-gray-500 mt-0.5">异常抛出</div>
                </div>
              </div>

              <!-- 设计特征 -->
              <div class="p-3 rounded-lg bg-pink-500/5 border border-pink-500/20">
                <div class="text-xs font-medium text-pink-400 mb-1.5">🧩 设计特征</div>
                <div v-if="keyImpData?.design_characteristics?.length" class="space-y-1.5">
                  <div v-for="char in keyImpData.design_characteristics.slice(0, 3)" :key="char.label"
                       class="text-xs leading-relaxed">
                    <span :class="char.confidence === 'verified' ? 'text-emerald-400' : 'text-amber-400'">
                      {{ char.label }}
                    </span>
                    <span class="text-gray-500 text-[10px] ml-1">({{ char.evidence }})</span>
                  </div>
                </div>
                <div v-else class="text-xs text-gray-300 leading-relaxed">
                  {{ keyImpData?.design_approach || '分析中...' }}
                </div>
              </div>

              <!-- 为什么它是关键实现 -->
              <div v-if="keyImpData?.importance_reasons?.length" class="p-3 rounded-lg bg-deep-card/50 border border-deep-border">
                <div class="text-xs font-medium text-gray-300 mb-2">为什么这是关键实现？</div>
                <div class="flex flex-wrap gap-1.5">
                  <span
                    v-for="reason in keyImpData.importance_reasons"
                    :key="reason"
                    class="text-[10px] px-2 py-0.5 rounded-full bg-pink-500/10 text-pink-300 border border-pink-500/20"
                  >{{ reason }}</span>
                </div>
              </div>
            </div>

            <div class="mb-4 text-sm text-gray-400">选出最合适的实现方案：</div>

            <div class="space-y-2.5 mb-8">
              <div
                v-for="opt in currentQuestion.options"
                :key="opt.id"
                class="quiz-option"
                :class="{
                  selected: selectedLevel4 === opt.id && !level4Answered,
                  correct: level4Answered && isCorrectOption(opt),
                  wrong: level4Answered && selectedLevel4 === opt.id && !isCorrectOption(opt),
                }"
                @click="selectLevel4(opt.id)"
              >
                <span class="option-letter"
                  :style="{
                    background: level4Answered && isCorrectOption(opt) ? '#4ade80' :
                               level4Answered && selectedLevel4 === opt.id && !isCorrectOption(opt) ? '#f87171' :
                               selectedLevel4 === opt.id ? '#ec4899' : '#1f1f2e',
                    color: (level4Answered && isCorrectOption(opt)) || (selectedLevel4 === opt.id) ? '#fff' : '#94a3b8'
                  }"
                >{{ opt.id }}</span>
                <span class="text-sm text-gray-300 pt-0.5">{{ opt.text }}</span>
              </div>
            </div>

            <!-- 答错引导面板 -->
            <transition name="fade">
              <div v-if="level4Answered && !level4Correct && level4HintsRemaining > 0"
                   class="mb-6 p-5 rounded-xl bg-pink-500/5 border border-pink-500/30 relative overflow-hidden">
                <div class="absolute top-0 right-0 w-32 h-32 bg-pink-500/5 rounded-full -translate-y-1/2 translate-x-1/2"></div>
                <div class="relative">
                  <div class="flex items-center gap-2 mb-3">
                    <div class="w-8 h-8 rounded-lg bg-pink-500/20 flex items-center justify-center text-pink-400 text-lg">🧩</div>
                    <div>
                      <div class="font-bold text-pink-400">回到代码本身想一想</div>
                      <div class="text-xs text-pink-400/60">还剩 {{ level4HintsRemaining }} 次尝试机会</div>
                    </div>
                  </div>

                  <div class="text-sm text-gray-300 leading-relaxed mb-3">
                    {{ level4Hint }}
                  </div>

                  <!-- 关键实现线索 -->
                  <div v-if="level4KeyImpHint" class="mb-4 p-3 rounded-lg bg-deep-card/80 border border-deep-border">
                    <div class="text-xs text-gray-500 mb-2">关键方法分析线索：</div>
                    <div class="text-xs text-gray-400 space-y-1">
                      <div v-if="level4KeyImpHint.design_characteristics?.length">
                        · 设计特征：
                        <span v-for="(char, idx) in level4KeyImpHint.design_characteristics.slice(0, 2)" :key="idx"
                              :class="char.confidence === 'verified' ? 'text-emerald-300' : 'text-amber-300'">
                          {{ char.label }}<span v-if="idx < Math.min(1, level4KeyImpHint.design_characteristics.length - 1)">, </span>
                        </span>
                      </div>
                      <div v-else>· 设计思路：<span class="text-pink-300">{{ level4KeyImpHint.design_approach }}</span></div>
                      <div>· 复杂度：<span class="text-white font-mono">{{ level4KeyImpHint.complexity }}</span> · 修改 <span class="text-amber-400 font-mono">{{ level4KeyImpHint.state_write_count }}</span> 个状态字段</div>
                      <div v-if="level4KeyImpHint.validation_count > 0">· 包含 <span class="text-green-400 font-mono">{{ level4KeyImpHint.validation_count }}</span> 处前置校验</div>
                    </div>
                  </div>

                  <button
                    @click="retryLevel4"
                    class="px-5 py-2 rounded-lg text-sm font-medium text-white
                           bg-gradient-to-r from-pink-500 to-rose-500
                           hover:shadow-lg hover:shadow-pink-500/25 hover:-translate-y-0.5 transition-all"
                  >
                    🔄 再试一次
                  </button>
                </div>
              </div>
            </transition>

            <!-- 答题反馈 -->
            <transition name="fade">
              <div v-if="level4Answered && (level4Correct || level4HintsRemaining === 0)" class="mb-6 p-4 rounded-xl"
                :class="level4Correct ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'"
              >
                <div class="font-bold mb-2" :class="level4Correct ? 'text-green-400' : 'text-red-400'">
                  {{ level4Correct ? '✓ 思路正确！' : '✗ 已经尝试了所有机会' }}
                </div>
                <div class="text-sm text-gray-400 leading-relaxed whitespace-pre-line">{{ currentQuestion.explanation }}</div>
              </div>
            </transition>

            <div class="flex justify-between">
              <button
                @click="prevLevel"
                class="px-4 py-2.5 rounded-xl text-sm text-gray-400 hover:text-white transition-colors"
              >
                ← 上一关
              </button>
              <button
                v-if="!level4Answered"
                @click="submitLevel4"
                :disabled="!selectedLevel4"
                class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all
                       bg-gradient-to-r from-neon-pink to-rose-500
                       hover:shadow-lg hover:shadow-neon-pink/25 hover:-translate-y-0.5
                       disabled:opacity-40 disabled:cursor-not-allowed"
              >
                提交答案
              </button>
              <button
                v-else-if="level4Correct || level4HintsRemaining === 0"
                @click="goToResult"
                class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all
                       bg-gradient-to-r from-neon-purple to-neon-pink
                       hover:shadow-lg hover:shadow-neon-purple/25 hover:-translate-y-0.5"
              >
                查看最终结果 →
              </button>
            </div>
          </div>

          </div>

          <!-- 最终结果页 -->
          <div v-else key="result" class="space-y-6">

            <!-- 得分概览卡 -->
            <div class="glass-card p-8 neon-border text-center">
              <div class="mb-6">
                <div class="w-24 h-24 mx-auto mb-4 rounded-full bg-gradient-to-br from-neon-blue via-neon-purple to-neon-pink flex items-center justify-center animate-glow-pulse">
                  <span class="text-4xl font-bold text-white font-mono">{{ finalScore }}</span>
                </div>
                <h2 class="text-2xl font-bold gradient-text mb-2">训练完成！</h2>
                <p class="text-gray-400 text-sm">
                  你答对了 {{ correctCount }} / {{ totalLevels }} 关 ·
                  理解度 <span class="text-neon-blue font-mono font-bold">{{ Math.round(finalScore / totalLevels * 100) }}%</span>
                </p>
              </div>

              <div class="max-w-md mx-auto mb-6">
                <div class="h-2 bg-deep-border rounded-full overflow-hidden progress-bar">
                  <div
                    class="h-full difficulty-gradient rounded-full transition-all duration-1000 ease-out"
                    :style="{ width: (finalScore / totalLevels * 100) + '%' }"
                  ></div>
                </div>
              </div>

              <div class="grid grid-cols-4 gap-3 mb-6 max-w-lg mx-auto">
                <div v-for="(level, i) in levels" :key="i" class="text-center">
                  <div
                    class="w-10 h-10 mx-auto mb-1 rounded-xl flex items-center justify-center text-sm font-bold"
                    :class="results[i] ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'"
                  >
                    {{ results[i] ? '✓' : '✗' }}
                  </div>
                  <div class="text-[10px] text-gray-500">{{ level }}</div>
                </div>
              </div>

              <!-- 理解度雷达图 -->
              <div class="p-5 rounded-xl bg-deep-card/50 border border-deep-border">
                <div class="text-sm font-medium text-white mb-4 text-center">📊 理解度评估</div>
                <div class="flex items-center justify-center gap-8 flex-wrap">
                  <svg :viewBox="radarViewBox" width="200" height="200" class="flex-shrink-0">
                    <defs>
                      <polygon id="radar-grad-shape" :points="radarPolyPoints" fill="none" />
                      <linearGradient id="radar-fill-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#06b6d4;stop-opacity:0.35" />
                        <stop offset="100%" style="stop-color:#a855f7;stop-opacity:0.35" />
                      </linearGradient>
                    </defs>
                    <!-- 背景网格 格层 -->
                    <g v-for="i in 5" :key="'ring-'+i" class="radar-ring">
                      <polygon
                        :points="ringPoints(i)"
                        fill="none"
                        stroke="#1e293b"
                        stroke-width="1"
                      />
                    </g>
                    <!-- 轴线 -->
                    <g v-for="(dim, i) in radarDims" :key="'radar-axis-'+i">
                      <line
                        :x1="radarCX"
                        :y1="radarCY"
                        :x2="radarCX + radarRadius * Math.cos(radarAngle(i))"
                        :y2="radarCY + radarRadius * Math.sin(radarAngle(i))"
                        stroke="#334155"
                        stroke-width="1"
                      />
                    </g>
                    <!-- 数据多边形 -->
                    <polygon
                      :points="radarDataPoints"
                      fill="url(#radar-fill-grad)"
                      stroke="#a855f7"
                      stroke-width="2"
                      class="radar-data"
                    />
                    <!-- 数据点 -->
                    <circle
                      v-for="(dim, i) in radarDims"
                      :key="'radar-dot-'+i"
                      :cx="radarCX + radarRadius * radarScores[i] * Math.cos(radarAngle(i))"
                      :cy="radarCY + radarRadius * radarScores[i] * Math.sin(radarAngle(i))"
                      r="4"
                      fill="#fff"
                      stroke="#a855f7"
                      stroke-width="2"
                    />
                    <!-- 维度标签 -->
                    <g v-for="(dim, i) in radarDims" :key="'radar-label-'+i">
                      <text
                        :x="radarCX + (radarRadius + 22) * Math.cos(radarAngle(i))"
                        :y="radarCY + (radarRadius + 22) * Math.sin(radarAngle(i))"
                        text-anchor="middle"
                        dominant-baseline="middle"
                        fill="#94a3b8"
                        font-size="11"
                        font-weight="500"
                      >{{ dim.label }}</text>
                    </g>
                  </svg>

                  <div class="space-y-2.5 min-w-[160px]">
                    <div v-for="(dim, i) in radarDims" :key="'dim-'+i" class="flex items-center gap-3">
                      <div class="w-2 h-2 rounded-full" :style="{ background: dim.color }"></div>
                      <div class="text-xs text-gray-400 w-20">{{ dim.label }}</div>
                      <div class="flex-1 h-1.5 bg-deep-border rounded-full overflow-hidden">
                        <div
                          class="h-full rounded-full transition-all duration-700 ease-out"
                        :style="{ width: radarScores[i] * 100 + '%', background: dim.color }"
                        ></div>
                      </div>
                      <div class="text-xs font-mono font-bold" :style="{ color: dim.color }">{{ Math.round(radarScores[i] * 100) }}%</div>
                    </div>
                  </div>
                </div>

                <div class="mt-4 pt-4 border-t border-deep-border text-center">
                  <div class="text-sm">
                    综合评级：<strong :class="scoreLevel.color" class="font-bold text-base">{{ scoreLevel.label }}</strong>
                  </div>
                  <p class="text-xs text-gray-500 mt-1 leading-relaxed">{{ scoreLevel.comment }}</p>
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

            <!-- 完整业务逻辑呈现：模块架构图 -->
            <div class="glass-card p-6 neon-border">
              <h3 class="text-base font-bold mb-1 flex items-center gap-2">
                <span class="w-1 h-4 bg-gradient-to-b from-neon-blue to-neon-purple rounded-full"></span>
                模块架构
              </h3>
              <p class="text-xs text-gray-500 mb-4 ml-3">系统由以下核心模块组成，各司其职，相互协作</p>

              <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <div
                  v-for="(mod, i) in projectModules"
                  :key="i"
                  class="p-4 rounded-xl bg-deep-card/50 border border-deep-border text-center
                         hover:border-neon-blue/40 hover:bg-neon-blue/5 transition-all group"
                >
                  <div
                    class="w-10 h-10 mx-auto mb-2 rounded-lg flex items-center justify-center text-lg"
                    :style="{ background: moduleColors[i % moduleColors.length] + '20' }"
                  >
                    {{ moduleIcons[i % moduleIcons.length] }}
                  </div>
                  <div class="text-sm font-medium text-white group-hover:text-neon-blue transition-colors">
                    {{ mod.name }}
                  </div>
                  <div class="text-[10px] text-gray-500 mt-1">{{ mod.class_count }} 个类 · {{ mod.method_count }} 个方法</div>
                  <div class="mt-2 flex justify-center">
                    <span
                      class="text-[10px] px-2 py-0.5 rounded-full"
                      :style="{ background: moduleColors[i % moduleColors.length] + '20', color: moduleColors[i % moduleColors.length] }"
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
            <DeepAnalysisView :deep-analysis="deepAnalysis" />

            <!-- 模块职责清单 -->
            <div class="glass-card p-6 neon-border">
              <h3 class="text-base font-bold mb-4 flex items-center gap-2">
                <span class="w-1 h-4 bg-gradient-to-b from-neon-green to-neon-blue rounded-full"></span>
                模块职责清单
              </h3>

              <div class="space-y-3">
                <div
                  v-for="(mod, i) in projectModules"
                  :key="i"
                  class="p-4 rounded-xl bg-deep-card/50 border border-deep-border"
                >
                  <div class="flex items-center gap-3 mb-2">
                    <div
                      class="w-8 h-8 rounded-lg flex items-center justify-center"
                      :style="{ background: moduleColors[i % moduleColors.length] + '20' }"
                    >
                      <span class="text-base">{{ moduleIcons[i % moduleIcons.length] }}</span>
                    </div>
                    <div>
                      <div class="text-sm font-medium text-white">{{ mod.name }}</div>
                      <div class="text-[11px] text-gray-500">{{ mod.description }}</div>
                    </div>
                    <div class="ml-auto text-[10px] font-mono text-gray-500">
                      核心度 {{ mod.core_score }}
                    </div>
                  </div>
                  <div class="flex flex-wrap gap-1.5 pl-11">
                    <span
                      v-for="(resp, j) in mod.responsibilities.slice(0, 5)"
                      :key="j"
                      class="px-2 py-0.5 text-[11px] rounded bg-deep-hover text-gray-400"
                    >
                      {{ resp }}
                    </span>
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
                @click="goBackToLevel4"
                class="px-6 py-2.5 rounded-xl text-sm font-medium text-gray-300 transition-all
                       border border-deep-border hover:border-neon-blue/30 hover:text-white"
              >
                ← 返回第4关
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import DeepAnalysisView from '../components/DeepAnalysisView.vue'

const emit = defineEmits(['view-analysis'])

// 数据
const projectName = ref('实验室安全助手')
const levels = ['功能拆分', '模块职责', '流程推演', '关键实现']
const totalLevels = 4

// 视图状态
const currentLevel = ref(1)
const currentView = ref('level') // level | result

// 项目数据
const projectModules = ref([])
const coreFlow = ref(null)
const deepAnalysis = ref(null)
const moduleColors = ['#00d4ff', '#a855f7', '#ec4899', '#22d3ee', '#f59e0b']
const moduleIcons = ['📋', '🔐', '🔧', '⚠️', '📊']

// 第1关状态
const selectedLevel1 = ref([])
const level1Answered = ref(false)
const level1Correct = ref(false)
const level1HintsRemaining = ref(2)
const level1HintCount = ref(0)

// 第2关状态
const selectedLevel2 = ref('')
const level2Answered = ref(false)
const level2Correct = ref(false)
const level2HintsRemaining = ref(2)
const level2HintCount = ref(0)

// 第3关状态
const selectedLevel3 = ref('')
const level3Answered = ref(false)
const level3Correct = ref(false)
const level3HintsRemaining = ref(2)
const level3HintCount = ref(0)

// 第4关状态
const selectedLevel4 = ref('')
const level4Answered = ref(false)
const level4Correct = ref(false)
const level4HintsRemaining = ref(2)
const level4HintCount = ref(0)

// 题目数据（实际从后端加载）
const questions = ref([])

const currentQuestion = computed(() => {
  if (!questions.value.length) return { options: [], correct_answers: [], explanation: '' }
  return questions.value[currentLevel.value - 1] || {}
})

const progressPercent = computed(() => {
  if (currentView.value === 'result') return 100
  return ((currentLevel.value - 1) / totalLevels) * 100
})

const selectedCount = computed(() => selectedLevel1.value.length)

const targetModuleName = computed(() => {
  return '预约管理模块'
})

const flowName = computed(() => {
  return '实验室预约流程'
})

const keyFunction = computed(() => {
  return 'create_reservation'
})

// 第4关：关键实现数据
const keyImpData = computed(() => {
  const imps = deepAnalysis.value?.key_implementations?.implementations || []
  return imps.find(imp =>
    imp.method === keyFunction.value ||
    imp.method.toLowerCase().includes(keyFunction.value.replace(/_/g, ''))
  ) || null
})

const keyImpFile = computed(() => {
  if (!keyImpData.value?.filepath) return ''
  const parts = keyImpData.value.filepath.split(/[\\/]/)
  return parts[parts.length - 1]
})

const keyImpStartLine = computed(() => keyImpData.value?.start_line || 1)
const keyImpEndLine = computed(() => keyImpData.value?.end_line || 1)
const keyImpLineRange = computed(() => `${keyImpStartLine.value}-${keyImpEndLine.value}`)

// 代码行：从项目演示文件中读取（用深度分析里已有的代码源，简化处理）
// 实际会从后端拉，这里用 key_implementations 里的数据 + 简单的代码模拟
const keyImpCodeLines = computed(() => {
  const imp = keyImpData.value
  if (!imp) return []

  // 根据分析数据生成代码骨架示意（真实场景会从后端获取完整源码）
  const lines = []
  const method = imp.method
  const cls = imp.class || ''
  const indent = cls ? '    ' : ''

  // 方法签名
  lines.push(`${indent}<span class="text-purple-400">def</span> <span class="text-yellow-300">${method}</span>(<span class="text-orange-300">self</span>, ...):`)

  // docstring
  lines.push(`${indent}    <span class="text-green-600">"""关键业务方法"""</span>`)

  // 校验逻辑
  if (imp.validation_checks && imp.validation_checks.length > 0) {
    lines.push('')
    lines.push(`${indent}    <span class="text-gray-500"># 前置校验</span>`)
    imp.validation_checks.forEach(check => {
      lines.push(`${indent}    <span class="text-purple-400">if</span> <span class="text-cyan-300">${check}</span>:`)
      lines.push(`${indent}        <span class="text-purple-400">raise</span> <span class="text-red-400">ValueError</span>(...)`)
    })
  }

  // 状态写入
  if (imp.state_writes && imp.state_writes.length > 0) {
    lines.push('')
    lines.push(`${indent}    <span class="text-gray-500"># 状态变更</span>`)
    imp.state_writes.slice(0, 3).forEach(field => {
      const cleanField = field.replace('._inferred_', '')
      if (cleanField.includes('[')) {
        lines.push(`${indent}    <span class="text-cyan-300">self.${cleanField}</span> = ...`)
      } else {
        lines.push(`${indent}    <span class="text-cyan-300">self.${cleanField}</span> = ...`)
      }
    })
  }

  // 循环/遍历
  if (imp.loop_count > 0) {
    lines.push('')
    lines.push(`${indent}    <span class="text-gray-500"># 核心逻辑</span>`)
    lines.push(`${indent}    <span class="text-purple-400">for</span> item <span class="text-purple-400">in</span> ...:`)
    lines.push(`${indent}        ...`)
  }

  // 返回值
  lines.push('')
  lines.push(`${indent}    <span class="text-purple-400">return</span> ...`)

  return lines
})

const finalScore = computed(() => {
  let score = 0
  if (level1Correct.value) score++
  if (level2Correct.value) score++
  if (level3Correct.value) score++
  if (level4Correct.value) score++
  return score
})

const correctCount = computed(() => finalScore.value)

const results = computed(() => [
  level1Correct.value,
  level2Correct.value,
  level3Correct.value,
  level4Correct.value,
])

const scoreLevel = computed(() => {
  const pct = finalScore.value / totalLevels
  if (pct === 1) return { label: '非常优秀', color: 'text-green-400', comment: '你对这个项目的业务逻辑理解很透彻，从模块划分到核心实现都掌握得很好。' }
  if (pct >= 0.75) return { label: '良好', color: 'text-neon-blue', comment: '整体理解不错，个别细节还需要加强。建议重点复习答错的部分。' }
  if (pct >= 0.5) return { label: '及格', color: 'text-amber-400', comment: '有一定基础，但对系统的整体把握还不够。建议再走一遍流程，重点理解模块间关系。' }
  return { label: '需要加强', color: 'text-red-400', comment: '对项目的业务逻辑还比较陌生。建议从模块拆分开始重新学习，一步步建立全局认识。' }
})

// ---- 理解度雷达图 ----
const radarDims = [
  { key: 'split', label: '功能拆分', color: '#06b6d4' },
  { key: 'responsibility', label: '模块职责', color: '#a855f7' },
  { key: 'flow', label: '流程推演', color: '#f59e0b' },
  { key: 'implementation', label: '关键实现', color: '#ec4899' },
]

const radarCX = 110
const radarCY = 110
const radarRadius = 70
const radarSize = 220
const radarViewBox = `0 0 ${radarSize} ${radarSize}`

function radarAngle(i) {
  // 从顶部开始，顺时针排列 4 个维度
  return (-Math.PI / 2) + (2 * Math.PI * i / radarDims.length)
}

const radarScores = computed(() => {
  return [
    level1Correct.value ? 1.0 : 0.4,
    level2Correct.value ? 1.0 : 0.4,
    level3Correct.value ? 1.0 : 0.4,
    level4Correct.value ? 1.0 : 0.4,
  ]
})

const radarDataPoints = computed(() => {
  return radarDims.map((_, i) => {
    const r = radarRadius * radarScores.value[i]
    const x = radarCX + r * Math.cos(radarAngle(i))
    const y = radarCY + r * Math.sin(radarAngle(i))
    return `${x},${y}`
  }).join(' ')
})

const radarPolyPoints = computed(() => {
  return radarDims.map((_, i) => {
    const x = radarCX + radarRadius * Math.cos(radarAngle(i))
    const y = radarCY + radarRadius * Math.sin(radarAngle(i))
    return `${x},${y}`
  }).join(' ')
})

function ringPoints(i) {
  const ratio = i / 5
  return radarDims.map((_, idx) => {
    const r = radarRadius * ratio
    const x = radarCX + r * Math.cos(radarAngle(idx))
    const y = radarCY + r * Math.sin(radarAngle(idx))
    return `${x},${y}`
  }).join(' ')
}

const weakPoints = computed(() => {
  const res = []
  const levelCorrect = [level1Correct.value, level2Correct.value, level3Correct.value, level4Correct.value]
  const advice = [
    '功能拆分：建议从"人、事、物"三个角度重新梳理系统模块',
    '模块职责：建议复习每个模块的职责清单，关注"核心职责 vs 附带功能"的区别',
    '流程推演：建议对照业务流程图，梳理"校验→处理→记录"的标准模式',
    '关键实现：建议深入阅读核心方法的代码，理解设计思路和边界条件',
  ]
  radarDims.forEach((dim, i) => {
    if (!levelCorrect[i]) {
      res.push(advice[i])
    }
  })
  return res
})

// 方法
function isSelected(id) {
  return selectedLevel1.value.includes(id)
}

function getOptionClass(opt) {
  if (!level1Answered.value) {
    return isSelected(opt.id)
      ? 'border-neon-blue bg-neon-blue/10'
      : 'border-deep-border hover:border-neon-blue/30'
  }
  const isCorrect = currentQuestion.value.correct_answers.includes(opt.id)
  const wasSelected = isSelected(opt.id)
  if (isCorrect) return 'border-green-500 bg-green-500/10'
  if (wasSelected && !isCorrect) return 'border-red-500 bg-red-500/10'
  return 'border-deep-border opacity-50'
}

function getCheckboxClass(opt) {
  if (!level1Answered.value) {
    return isSelected(opt.id)
      ? 'bg-neon-blue border-neon-blue'
      : 'border-gray-600'
  }
  const isCorrect = currentQuestion.value.correct_answers.includes(opt.id)
  if (isCorrect) return 'bg-green-500 border-green-500'
  return 'border-gray-600'
}

function selectOption(opt) {
  if (level1Answered.value) return
  if (isSelected(opt.id)) {
    selectedLevel1.value = selectedLevel1.value.filter(id => id !== opt.id)
  } else {
    selectedLevel1.value.push(opt.id)
  }
}

function isCorrectOption(opt) {
  return currentQuestion.value.correct_answers.includes(opt.id)
}

function selectLevel2(id) {
  if (level2Answered.value) return
  selectedLevel2.value = id
}

function selectLevel3(id) {
  if (level3Answered.value) return
  selectedLevel3.value = id
}

function selectLevel4(id) {
  if (level4Answered.value) return
  selectedLevel4.value = id
}

function submitLevel1() {
  const correct = currentQuestion.value.correct_answers
  const userSet = new Set(selectedLevel1.value)
  const correctSet = new Set(correct)
  // 完全正确才算对
  const isRight = userSet.size === correctSet.size &&
    [...userSet].every(x => correctSet.has(x))
  level1Correct.value = isRight
  level1Answered.value = true
  if (!isRight && level1HintsRemaining.value > 0) {
    level1HintsRemaining.value--
    level1HintCount.value++
  }
}

function submitLevel2() {
  level2Correct.value = currentQuestion.value.correct_answers.includes(selectedLevel2.value)
  level2Answered.value = true
  if (!level2Correct.value && level2HintsRemaining.value > 0) {
    level2HintsRemaining.value--
    level2HintCount.value++
  }
}

function submitLevel3() {
  level3Correct.value = currentQuestion.value.correct_answers.includes(selectedLevel3.value)
  level3Answered.value = true
  if (!level3Correct.value && level3HintsRemaining.value > 0) {
    level3HintsRemaining.value--
    level3HintCount.value++
  }
}

function submitLevel4() {
  level4Correct.value = currentQuestion.value.correct_answers.includes(selectedLevel4.value)
  level4Answered.value = true
  if (!level4Correct.value && level4HintsRemaining.value > 0) {
    level4HintsRemaining.value--
    level4HintCount.value++
  }
}

// ---- 引导提示内容 ----

// 第1关引导：根据答错的类型给不同线索
const level1Hint = computed(() => {
  const correct = new Set(currentQuestion.value.correct_answers || [])
  const userSet = new Set(selectedLevel1.value)
  const missed = [...correct].filter(x => !userSet.has(x))
  const extra = [...userSet].filter(x => !correct.has(x))

  const hints = [
    '想一想：一个实验室安全系统，最核心的业务是什么？学生进来第一件事做什么？',
    '提示：从"人、事、物"三个角度去拆分——谁来用？做什么事？用什么东西？',
    '再想想：安全检查和设备管理是一回事吗？用户权限需要单独管吗？',
  ]

  let msg = hints[Math.min(level1HintCount.value - 1, hints.length - 1)]
  if (missed.length > 0 && extra.length > 0) {
    msg += `你漏选了 ${missed.length} 个，多选了 ${extra.length} 个。`
  } else if (missed.length > 0) {
    msg += `还有 ${missed.length} 个核心模块没有选到。`
  } else if (extra.length > 0) {
    msg += `你多选了 ${extra.length} 个，这些真的是独立的核心模块吗？`
  }
  return msg
})

const level1HintModules = computed(() => {
  // 从项目模块数据中提取 2 个作为线索，但不直接说对或错
  if (!projectModules.value.length) return []
  const correct = new Set(currentQuestion.value.correct_answers || [])
  // 找两个正确选项对应的模块作为"参考线索"
  const hints = []
  for (const mod of projectModules.value) {
    // 通过模块名匹配选项
    const matchedOpt = currentQuestion.value.options?.find(opt =>
      opt.text.includes(mod.name.replace('模块', '')) ||
      mod.name.includes(opt.text.replace(/模块|管理/g, ''))
    )
    if (matchedOpt && correct.has(matchedOpt.id) && hints.length < 2) {
      hints.push({
        name: mod.name,
        hint: `负责 ${mod.responsibilities?.[0] || '核心业务'}`,
      })
    }
  }
  return hints
})

function retryLevel1() {
  level1Answered.value = false
}

// 第2关引导：给出职责关键词线索
const level2Hint = computed(() => {
  const hints = [
    `再想想"${targetModuleName.value}"这个名字——它的核心职责应该跟什么最相关？`,
    '好的模块职责描述应该回答三个问题：管什么数据？提供什么操作？对外暴露什么接口？',
    '注意区分"核心职责"和"附带功能"——一个模块可以有很多功能，但核心职责只有一个。',
  ]
  return hints[Math.min(level2HintCount.value - 1, hints.length - 1)]
})

const level2HintKeywords = computed(() => {
  // 从目标模块的 responsibilities 中提取关键词
  const targetMod = projectModules.value.find(m => m.name === targetModuleName.value)
  if (!targetMod || !targetMod.responsibilities) return []
  // 提取关键词（去掉常见停用词）
  const words = []
  targetMod.responsibilities.forEach(r => {
    const tokens = r.split(/[、，/（）()]/).filter(t => t.trim().length > 1 && t.length < 6)
    words.push(...tokens)
  })
  // 给 3-4 个关键词作为线索，其中混入一个干扰项
  const unique = [...new Set(words)].slice(0, 4)
  return unique
})

function retryLevel2() {
  level2Answered.value = false
  selectedLevel2.value = ''
}

// 第3关引导：给出流程首尾锚点
const level3Hint = computed(() => {
  const hints = [
    '顺着数据流向去想：用户触发一个操作，第一步做什么？最后一步做什么？',
    '业务流程通常遵循"校验 → 处理 → 记录"的模式，想想每一步属于哪个阶段。',
    '注意：有些步骤是前置条件，有些是核心操作，有些是收尾工作。区分它们的顺序。',
  ]
  return hints[Math.min(level3HintCount.value - 1, hints.length - 1)]
})

const level3FlowAnchor = computed(() => {
  // 从核心流程数据中取第一步和最后一步
  if (!coreFlow.value || !coreFlow.value.steps?.length) return null
  const steps = coreFlow.value.steps
  return {
    start: steps[0].method || steps[0].name,
    end: steps[steps.length - 1].method || steps[steps.length - 1].name,
  }
})

function retryLevel3() {
  level3Answered.value = false
  selectedLevel3.value = ''
}

// 第4关引导：给出关键实现的分析线索
const level4Hint = computed(() => {
  const hints = [
    `关键函数 "${keyFunction.value}" 的核心思路是什么？先想想它要解决什么问题。`,
    '一个好的实现思路，应该先说清楚"输入是什么、输出是什么、核心逻辑分几步"。',
    '注意看函数名里的关键词——"check"、"validate"、"find" 这些词暗示了实现方式。',
  ]
  return hints[Math.min(level4HintCount.value - 1, hints.length - 1)]
})

const level4KeyImpHint = computed(() => {
  // 从深度分析的 key_implementations 中找对应的关键方法
  const imps = deepAnalysis.value?.key_implementations?.implementations || []
  const target = imps.find(imp =>
    imp.method === keyFunction.value ||
    imp.method.toLowerCase().includes(keyFunction.value.replace(/_/g, ''))
  )
  if (!target) {
    // 找不到的话给一个默认的
    return {
      design_approach: '核心业务逻辑',
      complexity: '?',
      state_write_count: '?',
      validation_count: 0,
    }
  }
  return {
    design_approach: target.design_approach,
    complexity: target.complexity,
    state_write_count: (target.state_writes || []).length,
    validation_count: (target.validation_checks || []).length,
  }
})

function retryLevel4() {
  level4Answered.value = false
  selectedLevel4.value = ''
}

function goToResult() {
  currentView.value = 'result'
}

function goBackToLevel4() {
  currentView.value = 'level'
}

function nextLevel() {
  if (currentLevel.value < totalLevels) {
    currentLevel.value++
  }
}

function prevLevel() {
  if (currentLevel.value > 1) {
    currentLevel.value--
  }
}

function restart() {
  currentLevel.value = 1
  currentView.value = 'level'
  selectedLevel1.value = []
  level1Answered.value = false
  level1Correct.value = false
  level1HintsRemaining.value = 2
  level1HintCount.value = 0
  selectedLevel2.value = ''
  level2Answered.value = false
  level2Correct.value = false
  level2HintsRemaining.value = 2
  level2HintCount.value = 0
  selectedLevel3.value = ''
  level3Answered.value = false
  level3Correct.value = false
  level3HintsRemaining.value = 2
  level3HintCount.value = 0
  selectedLevel4.value = ''
  level4Answered.value = false
  level4Correct.value = false
  level4HintsRemaining.value = 2
  level4HintCount.value = 0
}

// 加载数据
onMounted(async () => {
  try {
    const resp = await fetch('/demo/project_analysis.json')
    const data = await resp.json()
    if (data.training && data.training.questions) {
      questions.value = data.training.questions
      projectName.value = data.training.project_name
    }
    // 加载模块和流程数据
    if (data.modules) {
      projectModules.value = data.modules
    }
    if (data.core_flows && data.core_flows.length > 0) {
      coreFlow.value = data.core_flows[0]
    }
    // 加载深度分析数据
    if (data.deep_analysis) {
      deepAnalysis.value = data.deep_analysis
    }
  } catch (e) {
    console.error('加载训练数据失败:', e)
  }
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
