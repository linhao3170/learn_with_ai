import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAnalysisStore } from './analysis'

export const useQuizStore = defineStore('quiz', () => {
  const userAnswers = ref({})

  const questions = computed(() => {
    const analysis = useAnalysisStore()
    return analysis.data?.quiz || []
  })

  const answeredCount = computed(() => Object.keys(userAnswers.value).length)

  const score = computed(() => {
    let s = 0
    for (let i = 0; i < questions.value.length; i++) {
      if (userAnswers.value[i] === questions.value[i].correct_answer) s++
    }
    return s
  })

  const isFinished = computed(() => answeredCount.value === questions.value.length && questions.value.length > 0)

  function selectAnswer(index, optionId) {
    if (userAnswers.value[index] !== undefined) return
    userAnswers.value[index] = optionId
  }

  function showResult(index) {
    return userAnswers.value[index] !== undefined
  }

  function reset() {
    userAnswers.value = {}
  }

  return {
    userAnswers,
    questions,
    answeredCount,
    score,
    isFinished,
    selectAnswer,
    showResult,
    reset,
  }
})
