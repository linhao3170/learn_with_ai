<template>
  <div>
    <h2 class="text-xl font-bold mb-6 flex items-center gap-2">
      <span class="w-1 h-5 bg-gradient-to-b from-neon-blue to-neon-purple rounded-full"></span>
      闯关测试
      <span class="text-sm font-normal text-gray-500 ml-2">
        {{ answeredCount }}/{{ questions.length }} 已答
      </span>
    </h2>

    <div class="max-w-3xl space-y-6">
      <div
        v-for="(q, qi) in questions"
        :key="qi"
        class="quiz-card overflow-hidden"
        :style="{
          borderLeft: '3px solid ' + levelColors[q.level],
        }"
      >
        <div class="px-5 py-3 border-b border-deep-border flex items-center justify-between bg-deep-card/50">
          <div class="flex items-center gap-3">
            <span
              class="quiz-level-badge"
              :style="{
                background: levelColors[q.level] + '15',
                color: levelColors[q.level],
                border: '1px solid ' + levelColors[q.level] + '30',
              }"
            >
              关卡 {{ q.level }}
            </span>
            <span class="text-sm font-medium text-white">{{ q.title }}</span>
          </div>
          <div class="flex items-center gap-3">
            <span
              v-if="showResult(qi)"
              class="text-xs font-medium"
              :class="userAnswers[qi] === q.correct_answer ? 'text-green-400' : 'text-red-400'"
            >
              {{ userAnswers[qi] === q.correct_answer ? '正确' : '错误' }}
            </span>
            <div class="flex gap-0.5">
              <span
                v-for="s in 5"
                :key="s"
                class="w-1 h-3 rounded-sm"
                :style="{ background: s <= q.difficulty ? '#f59e0b' : '#1f1f2e' }"
              ></span>
            </div>
          </div>
        </div>

        <div class="p-5">
          <div
            class="text-sm text-gray-300 mb-4 leading-relaxed whitespace-pre-line"
            v-html="formatDescription(q.description)"
          ></div>

          <div class="space-y-2">
            <div
              v-for="opt in q.options"
              :key="opt.id"
              class="quiz-option"
              :class="{
                selected: userAnswers[qi] === opt.id && !showResult(qi),
                correct: showResult(qi) && opt.id === q.correct_answer,
                wrong: showResult(qi) && userAnswers[qi] === opt.id && opt.id !== q.correct_answer,
              }"
              @click="selectAnswer(qi, opt.id)"
            >
              <span
                class="option-letter"
                :style="{
                  background:
                    showResult(qi) && opt.id === q.correct_answer
                      ? '#4ade80'
                      : showResult(qi) && userAnswers[qi] === opt.id && opt.id !== q.correct_answer
                        ? '#f87171'
                        : userAnswers[qi] === opt.id
                          ? '#00d4ff'
                          : '#1f1f2e',
                  color:
                    showResult(qi) && opt.id === q.correct_answer
                      ? '#fff'
                      : showResult(qi) && userAnswers[qi] === opt.id && opt.id !== q.correct_answer
                        ? '#fff'
                        : userAnswers[qi] === opt.id
                          ? '#fff'
                          : '#94a3b8',
                }"
              >{{ opt.id }}</span>
              <span class="text-sm text-gray-300 pt-0.5">{{ opt.text }}</span>
            </div>
          </div>

          <div
            v-if="showResult(qi)"
            class="mt-4 p-3 rounded-lg text-xs"
            :style="{
              background: userAnswers[qi] === q.correct_answer ? 'rgba(74, 222, 128, 0.08)' : 'rgba(248, 113, 113, 0.08)',
              border: '1px solid ' + (userAnswers[qi] === q.correct_answer ? 'rgba(74, 222, 128, 0.3)' : 'rgba(248, 113, 113, 0.3)'),
            }"
          >
            <div
              class="font-medium mb-1"
              :class="userAnswers[qi] === q.correct_answer ? 'text-green-400' : 'text-red-400'"
            >
              {{ userAnswers[qi] === q.correct_answer ? '✓ 回答正确' : '✗ 回答错误' }}
            </div>
            <div class="text-gray-400 leading-relaxed">{{ q.explanation }}</div>
            <div class="text-gray-500 mt-2 text-[11px]">
              证据行：{{ q.evidence_lines?.join(', ') || '-' }}
              <span class="mx-2">·</span>
              知识点：{{ q.knowledge_points?.join(', ') || '-' }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 最终得分 -->
    <div v-if="isFinished" class="mt-8 glass-card p-8 text-center max-w-md mx-auto">
      <div class="text-sm text-gray-400 mb-2">你的最终得分</div>
      <div class="text-6xl font-bold gradient-text mb-3 font-mono">
        {{ score }}<span class="text-2xl text-gray-500">/{{ questions.length }}</span>
      </div>
      <div class="text-sm text-gray-500 mb-6">
        正确率 {{ Math.round(score / questions.length * 100) }}%
      </div>
      <button
        @click="resetQuiz"
        class="px-8 py-2.5 rounded-lg text-sm font-medium text-white
               bg-gradient-to-r from-neon-blue/80 to-neon-purple/80
               hover:opacity-90 transition-opacity"
      >
        重新挑战
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useQuizStore } from '../stores/quiz'
import { levelColors } from '../stores/analysis'

const quiz = useQuizStore()

const questions = computed(() => quiz.questions)
const userAnswers = computed(() => quiz.userAnswers)
const answeredCount = computed(() => quiz.answeredCount)
const score = computed(() => quiz.score)
const isFinished = computed(() => quiz.isFinished)

function selectAnswer(index, optId) {
  quiz.selectAnswer(index, optId)
}

function showResult(index) {
  return quiz.showResult(index)
}

function resetQuiz() {
  quiz.reset()
}

function formatDescription(desc) {
  return desc
    .replace(/```python([\s\S]*?)```/g,
      '<pre class="code-block my-3 text-left !p-3 !text-[11px]"><code>$1</code></pre>')
    .replace(/`([^`]+)`/g,
      '<code class="text-neon-blue font-mono text-xs px-1.5 py-0.5 bg-deep-card rounded border border-deep-border">$1</code>')
}
</script>
